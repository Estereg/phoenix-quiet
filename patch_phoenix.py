#!/usr/bin/env python3
"""Neutralize the telemetry endpoints compiled into a Discord Phoenix binary.

Endpoints are found by the shape of the string, not by its position, and are
overwritten with same-length values, so the binary layout does not change. The
input file is never modified.

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
    required: bool


def unreachable(name: bytes) -> bytes:
    """Same-length name under .invalid, which never resolves."""
    return b"x" * (len(name) - 8) + b".invalid"


def dsn(m: re.Match[bytes]) -> bytes:
    scheme, key, at, host, slash, project = m.groups()
    return (
        scheme + b"0" * len(key) + at + unreachable(host) + slash + b"0" * len(project)
    )


def credential(m: re.Match[bytes]) -> bytes:
    head, secret, tail = m.groups()
    return head + b"x" * len(secret) + tail


def domain(name: str, pattern: bytes) -> Rule:
    return Rule(name, re.compile(pattern), lambda m: unreachable(m.group()), False)


# Patched values must not match their own rule, so check and a second patch
# can tell a patched binary from an untouched one.
# Sentry and /science are on every build that reports at all, so a build
# without them is not one this tool understands. The rest vary between builds.
RULES = [
    Rule(
        "sentry dsn",
        re.compile(rb"(https://)(?!0{32}@)([0-9a-f]{32})(@)([a-z0-9.-]+)(/)(\d+)"),
        dsn,
        True,
    ),
    Rule(
        "/science route",
        re.compile(rb"(?<!routes)/science"),
        lambda m: b"/xxxxxxx",
        True,
    ),
    Rule(
        "errmon credential",
        re.compile(rb'("credential":")(?!x+")([^"]+)(",\s*"endpoint":")'),
        credential,
        False,
    ),
    domain("vibeyard.tools", rb"vibeyard\.tools"),
    domain("litix.io", rb"litix\.io"),
    domain("amplitude.com", rb"amplitude\.com"),
    domain("datadog.discord.tools", rb"datadog\.discord\.tools"),
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
    missing = [r.name for r, n in counts if r.required and n == 0]
    for r, n in counts:
        status = "MISSING" if r.required and n == 0 else "ok" if n else "none"
        print(f"{status:8} {r.name}: {n}")
    if missing:
        print(
            f"error: not found: {', '.join(missing)}. This does not look like a "
            "Phoenix build; nothing written",
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
        print(f"{'FOUND' if n else 'clean':8} {r.name}: {n}")
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
