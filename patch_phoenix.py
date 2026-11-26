#!/usr/bin/env python3
"""Neutralize the telemetry endpoints compiled into a Discord Phoenix binary.

Strings are located by content and overwritten with same-length values, so the
ELF layout does not change. The input file is never modified.

    patch_phoenix.py patch discord-phoenix -o discord-phoenix.patched
    patch_phoenix.py check discord-phoenix.patched
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
from collections.abc import Callable
from typing import NamedTuple


class Rule(NamedTuple):
    name: str
    pattern: re.Pattern[bytes]
    replace: Callable[[re.Match[bytes]], bytes]
    expected: int


def unreachable_host(host: bytes) -> bytes:
    """Same-length name under .invalid, which never resolves."""
    return b"x" * (len(host) - 8) + b".invalid"


def unreachable_dsn(m: re.Match[bytes]) -> bytes:
    scheme, key, at, host, slash, project = m.groups()
    return (
        scheme
        + b"0" * len(key)
        + at
        + unreachable_host(host)
        + slash
        + b"0" * len(project)
    )


def blank_credential(m: re.Match[bytes]) -> bytes:
    head, secret, tail = m.groups()
    return head + b"x" * len(secret) + tail


def rule(
    name: str,
    pattern: bytes,
    replace: Callable[[re.Match[bytes]], bytes],
    expected: int = 1,
) -> Rule:
    return Rule(name, re.compile(pattern), replace, expected)


RULES = [
    rule(
        "sentry dsn",
        rb"(https://)([0-9a-f]{32})(@)(o\d+\.ingest\.[a-z.]*sentry\.io)(/)(\d+)",
        unreachable_dsn,
    ),
    rule(
        "errmon credential",
        rb'("credential":")(k\d+[a-z]:[0-9a-f]{40}:[A-Za-z0-9_-]+)(")',
        blank_credential,
    ),
    rule(
        "phoenix hosts",
        rb"(?:phoenix-errmon|phoenix-external-reports|project-phoenix)\.vibeyard\.tools",
        lambda m: unreachable_host(m.group()),
        expected=4,
    ),
    rule("/science route", rb"(?<!routes)/science", lambda m: b"/xxxxxxx"),
    rule("mux beacon", rb"img\.litix\.io", lambda m: unreachable_host(m.group())),
    rule(
        "amplitude", rb"api\.lab\.amplitude\.com", lambda m: unreachable_host(m.group())
    ),
]


def patch(data: bytearray) -> list[tuple[Rule, int]]:
    """Apply every rule in place and return the match count per rule."""
    counts = []
    for r in RULES:
        hits = [(m.start(), m.end(), r.replace(m)) for m in r.pattern.finditer(data)]
        for start, end, new in hits:
            assert len(new) == end - start, f"{r.name}: replacement changes length"
            data[start:end] = new
        counts.append((r, len(hits)))
    return counts


def count_leftovers(data: bytes | bytearray) -> list[tuple[Rule, int]]:
    return [(r, len(r.pattern.findall(data))) for r in RULES]


def read(path: str) -> bytearray:
    with open(path, "rb") as f:
        return bytearray(f.read())


def cmd_patch(args: argparse.Namespace) -> int:
    if os.path.abspath(args.binary) == os.path.abspath(args.output):
        print("error: output must differ from the input", file=sys.stderr)
        return 2
    data = read(args.binary)
    print(f"input   {hashlib.sha256(data).hexdigest()}")
    counts = patch(data)
    mismatched = [(r, n) for r, n in counts if n != r.expected]
    for r, n in counts:
        print(
            f"{'ok ' if n == r.expected else 'MISMATCH'} {r.name}: {n} (expected {r.expected})"
        )
    if mismatched:
        print(
            "error: this build does not match the known layout; nothing written",
            file=sys.stderr,
        )
        return 1
    tmp = args.output + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    shutil.copymode(args.binary, tmp)
    os.replace(tmp, args.output)
    print(f"output  {hashlib.sha256(data).hexdigest()}  {args.output}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    found = count_leftovers(read(args.binary))
    for r, n in found:
        print(f"{'FOUND' if n else 'clean'} {r.name}: {n}")
    return 1 if any(n for _, n in found) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("patch", help="write a patched copy of BINARY")
    p.add_argument("binary")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(run=cmd_patch)
    c = sub.add_parser("check", help="list telemetry still present in BINARY")
    c.add_argument("binary")
    c.set_defaults(run=cmd_check)
    args = ap.parse_args(argv)
    return int(args.run(args))


if __name__ == "__main__":
    sys.exit(main())
