# cli-bridge

cli-bridge is a small local server that lets a bot framework such as Hermes, or any OpenAI-compatible client, run on a terminal AI CLI you've already paid for.

> **v0.1.0, early days.** It works, but expect the odd rough edge. Issues and fixes welcome.

## Warning

Routing a personal, subscription-based AI CLI through an API may breach its provider's terms and put your account at risk: throttling, suspension, or a permanent ban, with no warning and no refund. Nobody can promise you it is allowed. **<u>You use this at your own risk</u>**.

Read [DISCLAIMER.md](DISCLAIMER.md) before you start; using this software means you accept it. This project is independent and is not affiliated with or endorsed by any AI provider or app.

## Getting started

The [docs](docs/) walk through everything step by step, even if you have never run a server before:

1. [docs/01-install.md](docs/01-install.md): install and run cli-bridge.
2. [docs/03-hermes.md](docs/03-hermes.md): point Hermes at it.
3. [docs/02-openclaw.md](docs/02-openclaw.md): why OpenClaw does not need the bridge.

The short version:

```bash
# Clone the repo
git clone https://github.com/Daimon-Law/cli-bridge.git cli-bridge
cd cli-bridge

# Configure, check, and start it, all in one command.
# (Windows PowerShell: .\cli-bridge.cmd setup)
./cli-bridge setup
```

## Pointing your bot at the bridge

Your bot will not find the bridge on its own. You add it by hand as a "custom" or "OpenAI-compatible" provider, which Hermes and other OpenAI-compatible clients support. You give it three things:

- The address: `http://127.0.0.1:18800/v1` (keep the `/v1` on the end).
- An API key: any text. The bridge ignores it, but most tools insist on something, so type a placeholder like `local`.
- A model id: one of the names you set during `bridge.py setup`. It is a name you chose, not a model picked from a menu. The bridge lists the ones it accepts at `http://127.0.0.1:18800/v1/models`.

The exact commands for Hermes are in [docs/03-hermes.md](docs/03-hermes.md). OpenClaw does not need the bridge; see [docs/02-openclaw.md](docs/02-openclaw.md) for why.

## Requirements

- Python 3.10 or newer.
- A terminal AI CLI account, already installed and signed in.

## How it works

You install a terminal AI CLI, the kind you sign into with your own account. A bot framework like Hermes normally reaches a model over the web; cli-bridge sits in between and, to it, looks like an ordinary AI service. It takes each message from your bot, runs your CLI once to get a reply, and passes that reply back. So your bot runs on the CLI you already pay for.

The bridge keeps nothing of its own: no saved chats, no API keys. Your CLI's own sign-in does the work. It runs your CLI fresh for each message, so the CLI needs to be installed and signed in, not already running. If a request includes tools, the bridge hands the tool call back to your bot to run, so your bot stays in charge.

## Licence

[MIT](LICENSE): free to use, change, and share. It also comes with the risk notice in [DISCLAIMER.md](DISCLAIMER.md) and the [Terms of Use for Daimon Law Contributions and Repositories](https://github.com/Daimon-Law/Terms-of-Use-for-Daimon-Law-Repositories). These do not reduce the freedoms MIT gives you; they spell out the risks.
