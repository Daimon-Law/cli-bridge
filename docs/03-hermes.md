# 3. Connect Hermes to cli-bridge

This points Hermes at a running cli-bridge. Do [01-install.md](01-install.md)
first, and confirm the bridge is up and answering:

```text
cli-bridge status     should say "Running ... answering /health"
cli-bridge test       should say "Success - your CLI replied through the bridge"
```

> Read [../DISCLAIMER.md](../DISCLAIMER.md) before connecting anything.

The bridge is assumed to be at **`http://127.0.0.1:18800/v1`** (the default). If
you chose a different port during setup, substitute it.

---

## Add cli-bridge as a provider

In Hermes, add cli-bridge as a custom OpenAI-compatible provider:

1. Run Hermes setup (`hermes`) and, when asked how to set up, choose **Full setup**.
2. At **Select provider**, choose **Custom endpoint (enter URL manually)** (number
   30 in the list at the time of writing).
3. Enter these values when prompted:

   | Prompt | Value |
   |---|---|
   | API base URL | `http://127.0.0.1:18800/v1` |
   | API key | leave blank (the bridge does not use one) |
   | Model | one of your `CLI_BRIDGE_MODELS`, for example `claude-opus-4-8` |

   Not sure which model names the bridge serves? Run `cli-bridge status`, or open
   `http://127.0.0.1:18800/v1/models`.

That is the whole connection. Send a message in Hermes; it now routes through
cli-bridge to your local CLI.

> Keep the `/v1` on the end of the URL. (cli-bridge also answers without it, so
> either form works, but `/v1` is the convention Hermes expects.)

## If the bridge runs on a different machine than Hermes

Whatever runs Hermes must be able to reach the bridge. If they are on the same
machine, `http://127.0.0.1:18800/v1` is correct. If the bridge is on another
machine, run it there, use that machine's address in place of `127.0.0.1`, and
reach it over a private network (for example a VPN). Do not expose the bridge to
the open internet.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` / no response | The bridge is not running. Run `cli-bridge status`, then `cli-bridge start`. |
| 404 / "not found" from the endpoint | The base URL is wrong. Use `http://127.0.0.1:18800/v1`. |
| Model not found / empty list | The model name must match one the bridge serves. Check `cli-bridge status` or `http://127.0.0.1:18800/v1/models`. |
| A reply never comes | First confirm the bridge works on its own: `cli-bridge test`. If that fails, your CLI may need sign-in (run it once to log in, then `cli-bridge restart`). |
| Hermes still uses its old model | Make sure the provider and model change was saved, and start a fresh Hermes session. |
