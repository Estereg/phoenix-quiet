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

`patch` never overwrites its input, keeps every replacement the same length as
the original, and writes nothing if the binary doesn't match the layout it
knows. `check` lists whatever is still present in a binary:

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

- Discord still sees your account. The gateway and API requests carry
  `design_id: 4`, which marks the client as Phoenix, and it is not a patchable
  string.
- `discord-desktop-crash-handler` is a separate binary with its own Sentry
  transport. It is not patched.
- Checked against build `0.1.0-dev.20261123093910.gb71ec80` for Linux x86_64. A
  different build will most likely be rejected until the patterns are updated.
- Third-party loaders such as Sunbird run native code inside the process and can
  undo this.
