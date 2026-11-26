# phoenix-quiet

Removes the telemetry endpoints from Discord Phoenix, the native desktop client
Discord is building. It overwrites a handful of strings in the binary, so the
client has nowhere to send them.

Not affiliated with Discord. Modifying the client may go against Discord's
terms; use it at your own risk. The repo contains no Discord code and no
credentials, you patch your own copy.

## Usage

Python 3, standard library only.

```sh
./Discord-Phoenix.AppImage --appimage-extract
python3 patch_phoenix.py patch squashfs-root/usr/bin/discord-phoenix -o patched
mv patched squashfs-root/usr/bin/discord-phoenix
squashfs-root/AppRun
```

`patch` never overwrites its input and keeps every replacement the same length
as the original. It looks for the shape of each endpoint (a Sentry DSN, the
`vibeyard.tools`, `litix.io` and `amplitude.com` domains, the `/science` route),
not for fixed positions or counts, so it is not tied to one build. It refuses to
write anything if it finds no Sentry DSN or no `/science` route, since then it is
not looking at a Phoenix binary. `check` lists whatever is still present:

```sh
python3 patch_phoenix.py check squashfs-root/usr/bin/discord-phoenix
```

Tests: `python3 -m unittest discover -s tests`.

## What it removes

| Channel | What it sent |
|---|---|
| Sentry (`*.ingest.us.sentry.io`) | One event per launch with account id, email, username, a `staff` flag, OS and distro |
| `/api/v9/science` | The usual analytics events (sessions, views, timings) |
| errmon (`phoenix-errmon.vibeyard.tools`) | Hang and performance reports, with a credential embedded in the binary |
| Phoenix reports and updater (`vibeyard.tools`) | Bug reports and builds; both need an employee or tester sign-in |
| Mux and Amplitude | Video and checkout analytics |

Sentry and `/science` were seen in captured traffic. The rest are present in the
binary but were never observed sending anything.

## Limits

- Discord still sees your account, and the client still identifies itself.
  Gateway and API requests carry `design_id: 4` and `native_build_number`, which
  mark it as Phoenix, plus OS, distro, locale and an installation id. These are
  compiled-in values, not endpoints, and this tool does not touch them.
- `discord-desktop-crash-handler` is a separate binary with its own Sentry
  transport. It is not patched.
- Run against one build only, `0.1.0-dev.20261123093910.gb71ec80` for Linux
  x86_64. The patterns are not specific to ELF or to that build, but other builds
  and platforms are untested. A build that adds a new telemetry host needs a
  line in `RULES`.
- The crash reporter still starts ("crash reports on" in the log). It has no
  reachable destination left.
- Third-party loaders such as Sunbird run native code inside the process and can
  undo this.
