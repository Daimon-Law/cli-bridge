# 1. Install and run cli-bridge

This guide gets cli-bridge running on your laptop, a VM, or a VPS. It assumes
**no prior experience.** Follow it top to bottom.

> **Before anything else:** read [../DISCLAIMER.md](../DISCLAIMER.md). Running this
> software can put the account behind your AI CLI at risk. You use it entirely at
> your own risk.

---

## What you need

1. **A terminal.** Terminal on macOS, PowerShell on Windows, your shell on Linux.
2. **Python 3.10 or newer.** Check with `python3 --version` (`python --version` on
   Windows). If it is missing or older, install a current Python from
   <https://www.python.org/downloads/>.
3. **Your AI CLI, installed and signed in.** cli-bridge runs a terminal AI CLI you
   have already set up. If you have not installed one yet, setup tells you the
   exact command to install it (see Step 2).

---

## Step 1. Get the code

```bash
git clone https://github.com/Daimon-Law/cli-bridge.git cli-bridge
cd cli-bridge
```

No `git`? Download the repository as a ZIP from its web page, unzip it, and open
a terminal in the unzipped folder.

## Step 2. Run setup

From inside the folder:

```bash
./cli-bridge setup
```

On **Windows PowerShell**, run `.\cli-bridge.cmd setup` instead. You only need the
leading `./` (or `.\`) this first time, from the project folder; setup adds a
`cli-bridge` command to your PATH, so after that you just type `cli-bridge ...`
from anywhere.

The first time, setup:

1. **Asks to install its one dependency** (a single Python package) into a local
   `.venv` folder. Answer `y`. Nothing is installed system-wide, and you can undo
   it by deleting the `.venv` folder.
2. **Asks a few short questions**, each pre-filled with a sensible default (press
   Enter to keep it):
   - confirm you have read the disclaimer
   - which program you are connecting (the tested option, or your own command)
   - the command that starts your AI CLI (for example `claude`)
   - the model name(s) to expose
   - the port and interface (the defaults suit almost everyone)
3. **Checks your CLI.** If it is installed but not on your PATH, setup finds it and
   uses the full path. If it is not installed, setup prints the exact command to
   install it; run it, sign in, then run `cli-bridge setup` again.
4. **Starts the bridge in the background**, confirms it is healthy, and **sends one
   test message through to your CLI** so you know it actually works.

When it finishes, the bridge is running and your terminal is free.

## Step 3. Manage it

cli-bridge runs in the background. The commands:

```text
cli-bridge status     is it running and healthy?
cli-bridge test       send a request through to confirm a reply
cli-bridge logs       show recent output
cli-bridge restart    stop, then start again
cli-bridge stop       stop it
cli-bridge start      start it in the background
cli-bridge run        run in the foreground (Ctrl-C to stop)
cli-bridge help       show this list
```

## Step 4. Keep it running after a reboot (optional)

During setup you are offered the option to install cli-bridge as a background
service that starts again on its own after you log out or reboot: a systemd user
service on Linux, a launchd agent on macOS, a Startup launcher on Windows. You
can also set this up by hand later from the `bridge.service`, `bridge.plist`, and
`bridge.cmd` templates included in this repo.

## Step 5. Connect your app

Point your bot at the bridge. For Hermes, see [03-hermes.md](03-hermes.md).

---

## A word on security

By default the bridge binds to **`127.0.0.1`**, reachable only from the same
machine. That is what you want: your app runs on the same box and talks to it
locally. The bridge has no password of its own, so do not change the interface to
`0.0.0.0` or a public address unless you have deliberately put a firewall and
authentication in front of it.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `cli-bridge: command not found` | You are not in the project folder, or the shortcut is not on your PATH yet. Run it as `./cli-bridge ...` (`.\cli-bridge.cmd ...` on Windows) from the folder, or finish `setup` to add the shortcut. |
| Setup cannot find your AI CLI | Install it and sign in, then run `cli-bridge setup` again. If it is installed in an unusual place, re-run setup and paste its full path. |
| `cli-bridge status` says not running | Start it with `cli-bridge start`, then `cli-bridge test`. |
| `cli-bridge test` gets no reply | Your CLI may not be signed in. Run it once by hand to log in, then `cli-bridge restart`. Check `cli-bridge logs`. |
| Replies time out on long tasks | Raise `CLI_BRIDGE_TIMEOUT` in `.env`, then `cli-bridge restart`. |

Want more detail when something is wrong? Run `cli-bridge logs`.
