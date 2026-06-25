# 2. OpenClaw does not need cli-bridge

You do not need this bridge for OpenClaw.

OpenClaw can run a terminal AI CLI directly as its own **CLI backend**, so it
talks to the CLI without anything in between. Routing it through cli-bridge would
just add a hop that buys you nothing.

Point OpenClaw at the CLI using its built-in CLI backend. See OpenClaw's own
documentation for how to configure it.

If you are using **Hermes**, that is different: Hermes has no native CLI backend,
so it does need the bridge. See [03-hermes.md](03-hermes.md).
