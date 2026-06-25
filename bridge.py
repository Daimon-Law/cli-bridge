#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daimon Legal
"""cli-bridge: an OpenAI-compatible HTTP front-end for a local coding-CLI.

What it does
------------
Some terminal coding assistants ship as a command-line program that you sign
into with your own subscription. This little server lets any tool that already
speaks the OpenAI Chat Completions API talk to that command-line program as if
it were a normal hosted model.

    your agent framework  ──HTTP──▶  cli-bridge (127.0.0.1:PORT)
    (OpenAI API client)                   │
                                          ▼
                              your local CLI, run once per request
                              (--print, streamed back as it types)

The bridge is stateless. It does not store your conversation, it holds no
credentials of its own, and it adds no model logic. Each request shells out to
your CLI exactly once, streams the answer back as standard OpenAI
Server-Sent-Events, and exits. Your framework stays in charge of memory, tools,
sessions and the agent loop; the CLI is treated as a plain single-turn
text-in / text-out backend.

Tool calling
------------
If your framework sends OpenAI `tools`, the bridge exposes them to the CLI over
a tiny per-request stdio MCP server (see mcp_bridge.py). When the CLI decides to
call one, the bridge captures the call, hands it back to your framework in
OpenAI shape, and stops the CLI. Your framework runs the tool itself and sends
the result on the next request. The CLI never executes your tools.

Configuration is entirely through environment variables (all prefixed
CLI_BRIDGE_). See .env.example and docs/01-install.md. Nothing here needs
editing to run.

PLEASE READ DISCLAIMER.md BEFORE USING THIS. Routing an interactive,
subscription-based CLI through a programmatic API may breach the terms of
service of whoever provides that CLI, and can put your account at risk. You use
this entirely at your own risk.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REQUIREMENTS = BASE_DIR / "requirements.txt"

# ─────────────────────────────────────────────────────────────────────────────
#  Zero-setup startup. The only things you should ever need to type are
#  `python3 bridge.py setup` and `python3 bridge.py`. Before anything else we make
#  sure the Python is recent enough and that our single dependency is importable.
#  If it is not, we explain what is needed, ASK before installing anything, and
#  only then build a local .venv, install into it, and re-exec ourselves there.
#  That clears the "externally managed environment" (PEP 668) wall on Homebrew and
#  Debian Python with no pip or virtual-environment knowledge required, and with
#  nothing installed behind the user's back.
# ─────────────────────────────────────────────────────────────────────────────

if sys.version_info < (3, 10):
    sys.exit(
        f"cli-bridge needs Python 3.10 or newer; this one is "
        f"{sys.version_info.major}.{sys.version_info.minor}. Install a current "
        "Python from https://www.python.org/downloads/ and run it again."
    )


def _in_our_venv() -> bool:
    """True when the running interpreter is this project's own .venv. Compares
    sys.prefix, not the executable path: a venv's python3 is a symlink back to
    the system Python, so comparing resolved binaries gives false positives."""
    try:
        return Path(sys.prefix).resolve() == (BASE_DIR / ".venv").resolve()
    except OSError:
        return False


def _pip_install(python: str) -> None:
    target = Path(python).parent.parent
    print(f"\n  Installing aiohttp into {target}", flush=True)
    print(f"  Running: {Path(python).name} -m pip install -r requirements.txt", flush=True)
    print("  (pip's own output follows so you can see exactly what is downloaded)\n", flush=True)
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.exit(
            f"\ncli-bridge: the install did not finish ({exc}).\n"
            "You can do it by hand and run the same command again:\n"
            f"    {python} -m pip install -r {REQUIREMENTS}"
        )
    print("\n  Dependency installed.\n", flush=True)


def _consent_to_install() -> bool:
    """Show exactly what would be installed and where, and ask first. Returns
    True only on an explicit yes; without one we install nothing."""
    print()
    print("First run: cli-bridge needs one third-party package before it can start.")
    print()
    print("    aiohttp   the async HTTP server library it is built on (from PyPI),")
    print("              plus the few small libraries aiohttp itself depends on.")
    print()
    print("It is NOT installed system-wide. Everything goes into a local virtual")
    print("environment in this folder (./.venv), which you can delete at any time to")
    print("undo it. pip's full output is shown below so you can see what lands.")
    print()
    try:
        answer = input("Install it now? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def _ensure_deps() -> None:
    """Guarantee aiohttp is importable with no manual setup, but never install
    anything without explicit consent. On first run we explain, ask, then build a
    local .venv, install into it, and re-exec there."""
    try:
        import aiohttp  # noqa: F401
        return
    except ImportError:
        pass

    win = os.name == "nt"
    venv_py = BASE_DIR / ".venv" / ("Scripts" if win else "bin") / ("python.exe" if win else "python3")
    in_venv = os.environ.get("CLI_BRIDGE_BOOTSTRAPPED") == "1" or _in_our_venv()

    # The local environment already exists and we are on the system Python:
    # nothing new to install, just hand off to it. No prompt, no surprises.
    if not in_venv and venv_py.exists():
        os.environ["CLI_BRIDGE_BOOTSTRAPPED"] = "1"
        sys.exit(subprocess.run([str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]]).returncode)

    # From here on we would actually install something, so ask before touching anything.
    if not _consent_to_install():
        sys.exit(
            "\nNothing was installed and nothing was changed. Run the same command\n"
            "again and choose yes when you're ready, or set it up yourself:\n"
            f"    python3 -m venv .venv && .venv/bin/python -m pip install -r {REQUIREMENTS}"
        )

    if in_venv:
        _pip_install(sys.executable)
        try:
            import aiohttp  # noqa: F401
            return
        except ImportError:
            sys.exit("cli-bridge: the dependency is still not importable after install; please report this.")

    print("Creating a local environment in ./.venv ...", flush=True)
    try:
        subprocess.run([sys.executable, "-m", "venv", str(BASE_DIR / ".venv")], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.exit(
            f"cli-bridge: could not create a virtual environment ({exc}).\n"
            "On Debian or Ubuntu you may first need:  sudo apt install python3-venv"
        )
    _pip_install(str(venv_py))
    os.environ["CLI_BRIDGE_BOOTSTRAPPED"] = "1"
    print("Launching cli-bridge from ./.venv ...\n", flush=True)
    sys.exit(subprocess.run([str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]]).returncode)


if __name__ == "__main__":
    _ensure_deps()

import asyncio
import html
import json
import logging
import re
import shutil
import signal
import tempfile
import time
import uuid
from typing import Any

from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError

logging.basicConfig(
    level=os.environ.get("CLI_BRIDGE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("cli-bridge")

ENV_FILE = BASE_DIR / ".env"


def _load_env_file(path: Path) -> None:
    """Populate os.environ from a KEY=VALUE .env file (no override, no deps).

    Lets `python3 bridge.py` pick up settings written by `setup` without needing
    python-dotenv or a process manager to inject them.
    """
    try:
        text = path.read_text()
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(ENV_FILE)

# Configuration: every value is read from an environment variable, normally the
# .env file written by `setup`. Defaults let the server boot unconfigured; the
# only value with no usable default is CLI_BRIDGE_BIN.
BIND_HOST = os.environ.get("CLI_BRIDGE_HOST", "127.0.0.1")           # interface to bind
BIND_PORT = int(os.environ.get("CLI_BRIDGE_PORT", "18800"))         # port to listen on
CLI_BIN = os.environ.get("CLI_BRIDGE_BIN", "")                      # CLI: PATH name or absolute path
PYTHON_BIN = os.environ.get("CLI_BRIDGE_PYTHON", sys.executable or "python3")
MODELS = tuple(m.strip() for m in os.environ.get("CLI_BRIDGE_MODELS", "").split(",") if m.strip())
DEFAULT_MODEL = os.environ.get("CLI_BRIDGE_DEFAULT_MODEL", "") or (MODELS[0] if MODELS else "")
SANDBOX_DIR = Path(os.environ.get("CLI_BRIDGE_SANDBOX", str(BASE_DIR / "sandbox")))
MCP_BRIDGE_PATH = Path(os.environ.get("CLI_BRIDGE_MCP_BRIDGE", str(BASE_DIR / "mcp_bridge.py")))
CALL_TIMEOUT_S = int(os.environ.get("CLI_BRIDGE_TIMEOUT", "600"))
STREAM_IDLE_TIMEOUT_S = int(os.environ.get("CLI_BRIDGE_STREAM_IDLE_TIMEOUT", str(CALL_TIMEOUT_S)))
STREAM_BUFFER_LIMIT = int(os.environ.get("CLI_BRIDGE_STREAM_BUFFER_LIMIT", str(8 * 1024 * 1024)))
MAX_PROMPT_CHARS = int(os.environ.get("CLI_BRIDGE_MAX_PROMPT_CHARS", "60000"))
TEXT_GUARD_HOLD_CHARS = int(os.environ.get("CLI_BRIDGE_TEXT_GUARD_HOLD_CHARS", "256"))
MAX_CONCURRENCY = int(os.environ.get("CLI_BRIDGE_MAX_CONCURRENCY", "4"))     # cap on simultaneous CLI subprocesses
MAX_BODY_BYTES = int(os.environ.get("CLI_BRIDGE_MAX_BODY_BYTES", str(64 * 1024 * 1024)))  # request body cap

# The CLI is a multi-turn agent by nature; here it must behave as a single-turn
# backend. This system text tells it to answer once and stop.
GUARD_PROMPT = """You are a single-turn inference backend for an external agent framework.
The conversation so far is given to you only as reference inside
<conversation_history>. Produce only your own next single assistant reply.
Never output the tokens [user], [assistant], [tool_call], or [tool_result].
Never simulate further turns, never write another participant's message, never
invent tool results. If you need a tool, emit a real tool call and stop;
otherwise answer normally and stop."""

DEFAULT_SYSTEM_PROMPT = (
    "You are a raw single-turn inference backend. The calling framework owns "
    "tools, files, session state, and the agent loop."
)

# The CLI's own built-in tools are switched off so it acts as pure inference;
# the calling framework supplies any tools it wants via the OpenAI `tools` field.
DENY_BUILTINS = (
    "Bash BashOutput KillShell Edit MultiEdit Read Write NotebookEdit "
    "NotebookRead WebFetch WebSearch Grep Glob TodoWrite Task Agent "
    "ExitPlanMode EnterPlanMode Skill SlashCommand AskUserQuestion "
    "ScheduleWakeup ShareOnboardingGuide ListMcpResourcesTool "
    "ReadMcpResourceTool ToolSearch EnterWorktree ExitWorktree "
    "Monitor PushNotification RemoteTrigger"
)

CONTINUATION_RE = re.compile(
    # Hard-stop forbidden transcript/tool markers anywhere, even if quoted.
    r"\[(?:user|assistant|tool_call|tool_result)\b"
    r"|\n\s*<turn\b"
    r"|</conversation_history>"
    r"|\n\s*(?:user|assistant)\s*:"
    r"|\btoolu_[A-Za-z]{6,}\b",
    re.IGNORECASE | re.MULTILINE,
)

TOOL_PREFIX = "mcp__bridge__"


_semaphore: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    return _semaphore


def child_env() -> dict[str, str]:
    # Don't leak the bridge's own config (CLI_BRIDGE_*) into the CLI subprocess.
    return {k: v for k, v in os.environ.items() if not k.startswith("CLI_BRIDGE_")}


def ensure_sandbox() -> None:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    # Make sure no project-level config in the working dir leaks into the CLI.
    for name in ("CLAUDE.md", "AGENTS.md", "settings.json", ".env"):
        try:
            (SANDBOX_DIR / name).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("could not remove sandbox %s", name)


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if not isinstance(p, dict):
                parts.append(str(p))
                continue
            typ = p.get("type")
            if typ in ("text", "input_text"):
                parts.append(str(p.get("text") or ""))
            elif typ in ("image_url", "input_image"):
                pass  # images are sent separately via stream-json input, not inline text
            elif typ == "tool_result":
                parts.append(str(p.get("content") or ""))
            elif "text" in p:
                parts.append(str(p.get("text") or ""))
        return "\n".join(x for x in parts if x)
    return str(content)


def extract_images(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Collect (media_type, base64) from OpenAI image_url content blocks.

    Only inline data: URLs are supported (stream-json input takes inline base64,
    not remote URLs). Remote URLs are skipped and logged.
    """
    out: list[tuple[str, str]] = []
    for m in messages:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for p in content:
            if not (isinstance(p, dict) and p.get("type") == "image_url"):
                continue
            iu = p.get("image_url")
            url = (iu.get("url") if isinstance(iu, dict) else iu) or ""
            if not isinstance(url, str) or not url.startswith("data:"):
                if url:
                    logger.warning("skipping non-data image_url (remote URLs unsupported in stream-json input)")
                continue
            header, _, b64 = url.partition(",")
            media_type = header[5:].split(";")[0].strip() or "image/png"
            b64 = b64.strip()
            if b64:
                out.append((media_type, b64))
    return out


def build_image_stdin(user_prompt: str, images: list[tuple[str, str]]) -> str:
    """Build one stream-json user-message line carrying images then text."""
    content: list[dict[str, Any]] = [
        {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}
        for mt, data in images
    ]
    content.append({"type": "text", "text": user_prompt})
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + chr(10)


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def render_history_turn(m: dict[str, Any]) -> str:
    role = m.get("role", "user")
    text = content_to_text(m.get("content"))
    if role == "assistant":
        extras: list[str] = []
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            args = fn.get("arguments") or "{}"
            extras.append(f"(past tool call: name={name} args={args})")
        body = text
        if extras:
            body = (body + "\n" if body else "") + "\n".join(extras)
        return f'<turn role="assistant">{esc(body)}</turn>'
    if role == "tool":
        tcid = esc(str(m.get("tool_call_id") or ""))
        return f'<turn role="tool_result" for="{tcid}">{esc(text)}</turn>'
    return f'<turn role="{esc(str(role))}">{esc(text)}</turn>'


def bounded_history(turns: list[str]) -> str:
    if not turns:
        return "<conversation_history>\n</conversation_history>"
    joined = "\n".join(turns)
    wrapper_extra = len("<conversation_history>\n\n</conversation_history>")
    budget = max(0, MAX_PROMPT_CHARS // 2 - wrapper_extra)
    if MAX_PROMPT_CHARS <= 0 or len(joined) <= budget:
        kept = joined
    else:
        first = turns[0]
        marker = f'<turn role="system_note">omitted older reference turns to keep history under {budget} chars.</turn>'
        tail: list[str] = []
        used = len(first) + len(marker) + 2
        for turn in reversed(turns[1:]):
            if used + len(turn) + 1 <= budget:
                tail.append(turn)
                used += len(turn) + 1
            else:
                break
        tail.reverse()
        kept = "\n".join([first, marker, *tail])
        if len(kept) > budget:
            kept = kept[-budget:]
    return f"<conversation_history>\n{kept}\n</conversation_history>"


def build_prompts(messages: list[dict[str, Any]]) -> tuple[str, str]:
    sys_parts: list[str] = []
    non_system: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "system":
            text = content_to_text(m.get("content"))
            if text:
                sys_parts.append(text)
        else:
            non_system.append(m)

    last_user_idx = -1
    for i, m in enumerate(non_system):
        if m.get("role") == "user":
            last_user_idx = i

    if last_user_idx >= 0:
        history_msgs = non_system[:last_user_idx]
        current = content_to_text(non_system[last_user_idx].get("content"))
        pending_msgs = non_system[last_user_idx + 1:]
    elif non_system:
        history_msgs = non_system[:-1]
        current = content_to_text(non_system[-1].get("content"))
        pending_msgs = []
    else:
        history_msgs = []
        current = "(no user message)"
        pending_msgs = []

    system = GUARD_PROMPT + "\n\n" + ("\n\n".join(sys_parts).strip() or DEFAULT_SYSTEM_PROMPT)
    history = bounded_history([render_history_turn(m) for m in history_msgs])
    pending = "\n".join(render_history_turn(m) for m in pending_msgs)
    user_prompt = f"{history}\n\nCurrent user request:\n{current}\n"
    if pending:
        user_prompt += (
            "\nWork already done on this request so far "
            "(your prior tool calls and their results, read these before acting):\n"
            f"{pending}\n"
        )
    user_prompt += "\nRespond with your single next assistant message now."
    if MAX_PROMPT_CHARS > 0 and len(user_prompt) > MAX_PROMPT_CHARS:
        keep = MAX_PROMPT_CHARS - 200
        user_prompt = "[cli-bridge: prompt was char-trimmed; recent content follows]\n" + user_prompt[-keep:]
    return system, user_prompt


def setup_tools_workspace(tools: list[dict[str, Any]]) -> tuple[Path | None, list[str]]:
    if not tools:
        return None, []
    ws = Path(tempfile.mkdtemp(prefix="cli-bridge-req-"))
    manifest = ws / "tools.json"
    manifest.write_text(json.dumps(tools, separators=(",", ":")))
    config = {
        "mcpServers": {
            "bridge": {
                "command": PYTHON_BIN,
                "args": [str(MCP_BRIDGE_PATH), str(manifest)],
            }
        }
    }
    (ws / "mcp_config.json").write_text(json.dumps(config, separators=(",", ":")))
    allowed: list[str] = []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) and t.get("type") == "function" else t
        if isinstance(fn, dict) and fn.get("name"):
            allowed.append(f"{TOOL_PREFIX}{fn['name']}")
    return ws, allowed


def cleanup_workspace(ws: Path | None) -> None:
    if ws:
        shutil.rmtree(ws, ignore_errors=True)


def strip_tool_name(name: str) -> str:
    return name[len(TOOL_PREFIX):] if name.startswith(TOOL_PREFIX) else name


def sse_frame(d: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(d, separators=(',', ':'))}\n\n".encode("utf-8")


def map_stop_reason(stop_reason: str | None) -> str:
    return {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
    }.get(stop_reason or "", "stop")


def terminate_proc_group(proc: asyncio.subprocess.Process, sig: int = signal.SIGTERM) -> None:
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return
    except Exception:
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def build_cli_cmd(system: str, model: str, workspace: Path | None, allowed_tools: list[str], stream_json_input: bool = False) -> list[str]:
    cmd = [
        CLI_BIN,
        "--print",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--input-format", "stream-json" if stream_json_input else "text",
        "--system-prompt", system,
        "--disable-slash-commands",
        "--no-session-persistence",
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--disallowed-tools", DENY_BUILTINS,
        "--permission-mode", "bypassPermissions",
    ]
    if workspace is not None and allowed_tools:
        cmd += ["--mcp-config", str(workspace / "mcp_config.json"), "--allowed-tools", " ".join(allowed_tools)]
    if model:
        cmd += ["--model", model]
    return cmd


async def wait_for_exit(proc: asyncio.subprocess.Process) -> str:
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        terminate_proc_group(proc, signal.SIGKILL)
        await proc.wait()
    if proc.stderr is not None:
        try:
            return (await proc.stderr.read()).decode("utf-8", "replace")[-4000:]
        except Exception:
            return ""
    return ""


async def run_streaming(request: web.Request, cmd: list[str], stdin_text: str, model: str, allowed_tools: list[str]) -> web.StreamResponse:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(SANDBOX_DIR),
        start_new_session=True,
        limit=STREAM_BUFFER_LIMIT,
        env=child_env(),
    )
    assert proc.stdin is not None
    proc.stdin.write(stdin_text.encode("utf-8"))
    await proc.stdin.drain()
    proc.stdin.close()

    chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    resp = web.StreamResponse(status=200, headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"})
    await resp.prepare(request)

    blocks: dict[int, dict[str, Any]] = {}
    block_to_tc: dict[int, int] = {}
    tool_seq = 0
    final_stop_reason: str | None = None
    usage_in = usage_out = cache_read = cache_create = 0
    cost_usd: float | None = None
    session_id: str | None = None
    killed_for_tool = False
    killed_for_guard = False
    timed_out = False
    disconnected = False
    pending_text = ""

    async def write_chunk(delta: dict[str, Any], finish_reason: str | None = None, usage: dict[str, int] | None = None) -> None:
        chunk: dict[str, Any] = {"id": chat_id, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
        if usage is not None:
            chunk["usage"] = usage
        await resp.write(sse_frame(chunk))

    async def flush_text(force: bool = False) -> None:
        nonlocal pending_text
        if not pending_text:
            return
        if force:
            out, pending_text = pending_text, ""
        elif len(pending_text) > TEXT_GUARD_HOLD_CHARS:
            out, pending_text = pending_text[:-TEXT_GUARD_HOLD_CHARS], pending_text[-TEXT_GUARD_HOLD_CHARS:]
        else:
            return
        if out:
            await write_chunk({"content": out})

    async def accept_text(text: str) -> None:
        nonlocal pending_text, killed_for_guard
        if not text or killed_for_guard:
            return
        pending_text += text
        m = CONTINUATION_RE.search(pending_text)
        if m:
            safe = pending_text[:m.start()]
            pending_text = ""
            if safe:
                await write_chunk({"content": safe})
            killed_for_guard = True
            logger.warning("continuation guard stopped model output at marker %r", m.group(0)[:80])
            terminate_proc_group(proc)
            return
        await flush_text(False)

    assert proc.stdout is not None
    stderr_text = ""
    try:
        await write_chunk({"role": "assistant"})
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=STREAM_IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                timed_out = True
                terminate_proc_group(proc)
                break
            if not line:
                break
            try:
                evt = json.loads(line.decode("utf-8").strip())
            except json.JSONDecodeError:
                continue
            etype = evt.get("type")
            if etype == "system" and evt.get("subtype") == "init":
                session_id = evt.get("session_id")
                continue
            if etype == "result":
                u = evt.get("usage") or {}
                usage_in = u.get("input_tokens", usage_in)
                usage_out = u.get("output_tokens", usage_out)
                cache_read = u.get("cache_read_input_tokens", cache_read)
                cache_create = u.get("cache_creation_input_tokens", cache_create)
                cost_usd = evt.get("total_cost_usd", cost_usd)
                if evt.get("is_error"):
                    await accept_text(f"\n\n[cli-bridge error] {evt.get('result') or '(cli error)'}")
                continue
            if etype != "stream_event":
                continue
            ev = evt.get("event") or {}
            ev_type = ev.get("type")
            if ev_type == "content_block_start":
                idx = ev.get("index", 0)
                cb = ev.get("content_block") or {}
                cb_type = cb.get("type")
                blocks[idx] = {"type": cb_type, "json": ""}
                if cb_type == "tool_use":
                    await flush_text(True)
                    tc_idx = tool_seq
                    tool_seq += 1
                    block_to_tc[idx] = tc_idx
                    tool_name = strip_tool_name(cb.get("name", ""))
                    tool_id = cb.get("id") or f"call_{uuid.uuid4().hex[:16]}"
                    blocks[idx].update({"name": tool_name, "id": tool_id})
                    await write_chunk({"tool_calls": [{"index": tc_idx, "id": tool_id, "type": "function", "function": {"name": tool_name, "arguments": ""}}]})
            elif ev_type == "content_block_delta":
                idx = ev.get("index", 0)
                delta = ev.get("delta") or {}
                state = blocks.get(idx) or {}
                if delta.get("type") == "text_delta" and state.get("type") == "text":
                    await accept_text(delta.get("text", ""))
                    if killed_for_guard:
                        break
                elif delta.get("type") == "input_json_delta" and state.get("type") == "tool_use":
                    partial = delta.get("partial_json", "")
                    state["json"] = state.get("json", "") + partial
                    tc_idx = block_to_tc.get(idx)
                    if tc_idx is not None and partial:
                        await write_chunk({"tool_calls": [{"index": tc_idx, "function": {"arguments": partial}}]})
            elif ev_type == "message_delta":
                d = ev.get("delta") or {}
                final_stop_reason = d.get("stop_reason", final_stop_reason)
                u = ev.get("usage") or {}
                usage_in = u.get("input_tokens", usage_in)
                usage_out = u.get("output_tokens", usage_out)
                if final_stop_reason == "tool_use":
                    killed_for_tool = True
                    terminate_proc_group(proc)
                    break
    except asyncio.CancelledError:
        terminate_proc_group(proc)
        raise
    except (ConnectionResetError, RuntimeError, ClientConnectionResetError):
        disconnected = True
        terminate_proc_group(proc)
        logger.info("client disconnected")
    finally:
        stderr_text = await wait_for_exit(proc)

    if disconnected:
        return resp

    try:
        if timed_out:
            await accept_text(f"\n\n[cli-bridge error] streaming idle-timeout after {STREAM_IDLE_TIMEOUT_S}s" + (f"\nstderr tail:\n{stderr_text}" if stderr_text else ""))
        elif not killed_for_tool and not killed_for_guard and proc.returncode not in (0, None):
            await accept_text(f"\n\n[cli-bridge error] process exited rc={proc.returncode}" + (f"\nstderr tail:\n{stderr_text}" if stderr_text else ""))
        await flush_text(True)
        finish = "tool_calls" if killed_for_tool else "stop" if killed_for_guard else map_stop_reason(final_stop_reason)
        usage = {"prompt_tokens": usage_in, "completion_tokens": usage_out, "total_tokens": usage_in + usage_out}
        final_chunk: dict[str, Any] = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
            "usage": usage,
            "cli_bridge": {"session_id": session_id, "total_cost_usd": cost_usd, "cache_read_input_tokens": cache_read, "cache_creation_input_tokens": cache_create},
        }
        await resp.write(sse_frame(final_chunk))
        await resp.write(b"data: [DONE]\n\n")
        await resp.write_eof()
    except (ConnectionResetError, RuntimeError, ClientConnectionResetError):
        logger.info("client disconnected before final chunk")
    return resp


async def run_blocking(cmd: list[str], stdin_text: str, model: str) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(SANDBOX_DIR),
        start_new_session=True,
        limit=STREAM_BUFFER_LIMIT,
        env=child_env(),
    )
    assert proc.stdin is not None
    proc.stdin.write(stdin_text.encode("utf-8"))
    await proc.stdin.drain()
    proc.stdin.close()

    text_parts: list[str] = []
    blocks: dict[int, dict[str, Any]] = {}
    final_stop_reason: str | None = None
    usage_in = usage_out = 0
    session_id: str | None = None
    cost_usd: float | None = None
    killed_for_guard = False

    assert proc.stdout is not None
    try:
        while True:
            try:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=STREAM_IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                terminate_proc_group(proc)
                text_parts.append(f"\n\n[cli-bridge error] streaming idle-timeout after {STREAM_IDLE_TIMEOUT_S}s")
                break
            if not raw:
                break
            try:
                evt = json.loads(raw.decode("utf-8").strip())
            except json.JSONDecodeError:
                continue
            etype = evt.get("type")
            if etype == "system" and evt.get("subtype") == "init":
                session_id = evt.get("session_id")
            elif etype == "result":
                u = evt.get("usage") or {}
                usage_in = u.get("input_tokens", usage_in)
                usage_out = u.get("output_tokens", usage_out)
                cost_usd = evt.get("total_cost_usd", cost_usd)
            elif etype == "stream_event":
                ev = evt.get("event") or {}
                t = ev.get("type")
                if t == "content_block_start":
                    idx = ev.get("index", 0)
                    cb = ev.get("content_block") or {}
                    blocks[idx] = {"type": cb.get("type"), "json": "", "name": strip_tool_name(cb.get("name", "")), "id": cb.get("id") or f"call_{uuid.uuid4().hex[:16]}"}
                elif t == "content_block_delta":
                    idx = ev.get("index", 0)
                    d = ev.get("delta") or {}
                    st = blocks.get(idx) or {}
                    if d.get("type") == "text_delta" and st.get("type") == "text":
                        text_parts.append(d.get("text", ""))
                        full = "".join(text_parts)
                        m = CONTINUATION_RE.search(full)
                        if m:
                            text_parts = [full[:m.start()]]
                            killed_for_guard = True
                            terminate_proc_group(proc)
                            break
                    elif d.get("type") == "input_json_delta" and st.get("type") == "tool_use":
                        st["json"] = st.get("json", "") + d.get("partial_json", "")
                elif t == "message_delta":
                    final_stop_reason = (ev.get("delta") or {}).get("stop_reason", final_stop_reason)
                    u = ev.get("usage") or {}
                    usage_in = u.get("input_tokens", usage_in)
                    usage_out = u.get("output_tokens", usage_out)
                    if final_stop_reason == "tool_use":
                        terminate_proc_group(proc)
                        break
            if killed_for_guard:
                break
    finally:
        stderr_text = await wait_for_exit(proc)

    tool_calls: list[dict[str, Any]] = []
    for idx in sorted(blocks):
        st = blocks[idx]
        if st.get("type") == "tool_use":
            tool_calls.append({"id": st.get("id"), "type": "function", "function": {"name": st.get("name", ""), "arguments": st.get("json") or "{}"}})

    if proc.returncode not in (0, None) and not tool_calls and not killed_for_guard:
        text_parts.append(f"\n\n[cli-bridge error] process exited rc={proc.returncode}" + (f"\nstderr tail:\n{stderr_text}" if stderr_text else ""))

    finish = "tool_calls" if tool_calls else "stop" if killed_for_guard else map_stop_reason(final_stop_reason)
    message: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts) or None}
    if tool_calls:
        message["tool_calls"] = tool_calls
        if not message["content"]:
            message["content"] = None
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": usage_in, "completion_tokens": usage_out, "total_tokens": usage_in + usage_out},
        "cli_bridge": {"session_id": session_id, "total_cost_usd": cost_usd},
    }


async def chat_completions(request: web.Request) -> web.StreamResponse | web.Response:
    try:
        body = await request.json()
    except Exception as exc:
        return web.json_response({"error": {"message": f"invalid JSON body: {exc}", "type": "invalid_request_error"}}, status=400)

    # Forward whatever model id the caller sent; tolerate a "provider/model"
    # prefix some frameworks prepend (e.g. "cli-bridge/the-model" -> "the-model").
    raw_model = body.get("model") or DEFAULT_MODEL
    model = raw_model.split("/")[-1] if isinstance(raw_model, str) else DEFAULT_MODEL
    messages = body.get("messages") or []
    if not isinstance(messages, list):
        return web.json_response({"error": {"message": "messages must be an array", "type": "invalid_request_error"}}, status=400)
    tools = body.get("tools") or []
    wants_stream = bool(body.get("stream"))

    ensure_sandbox()
    system, user_prompt = build_prompts(messages)
    images = extract_images(messages)
    workspace, allowed_tools = setup_tools_workspace(tools)
    cmd = build_cli_cmd(system, model, workspace, allowed_tools, stream_json_input=bool(images))
    stdin_payload = build_image_stdin(user_prompt, images) if images else user_prompt
    logger.info("request model=%s stream=%s tools=%d images=%d prompt_chars=%d", model, wants_stream, len(tools), len(images), len(user_prompt))

    try:
        async with get_semaphore():
            if wants_stream:
                return await run_streaming(request, cmd, stdin_payload, model, allowed_tools)
            result = await asyncio.wait_for(run_blocking(cmd, stdin_payload, model), timeout=CALL_TIMEOUT_S)
            return web.json_response(result)
    except asyncio.TimeoutError:
        return web.json_response({"error": {"message": f"CLI timed out after {CALL_TIMEOUT_S}s", "type": "timeout"}}, status=504)
    except Exception as exc:
        logger.exception("invocation failed")
        return web.json_response({"error": {"message": f"cli-bridge: {exc}", "type": "internal_error"}}, status=500)
    finally:
        cleanup_workspace(workspace)


async def models(request: web.Request) -> web.Response:
    return web.json_response({"object": "list", "data": [{"id": m, "object": "model", "owned_by": "cli-bridge"} for m in MODELS]})


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "version": "1.0.0", "host": BIND_HOST, "port": BIND_PORT, "cli_bin": CLI_BIN, "sandbox": str(SANDBOX_DIR), "models": list(MODELS)})


def make_app() -> web.Application:
    app = web.Application(client_max_size=MAX_BODY_BYTES)
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat_completions)
    # Also serve without the /v1 prefix, so a base URL given with or without /v1
    # both resolve (a common client-config footgun, e.g. Hermes' "add /v1?" prompt).
    app.router.add_get("/models", models)
    app.router.add_post("/chat/completions", chat_completions)
    return app


def interpret_auth_check(returncode: int, output: str) -> tuple[bool, str]:
    """Pure helper: turn a CLI `auth status` result into (ok, message)."""
    if returncode == 0:
        return True, "CLI reports a signed-in account."
    last = ""
    if output and output.strip():
        last = output.strip().splitlines()[-1].strip()
    msg = "CLI does not look signed in; sign in before use or requests will fail"
    if last:
        msg = msg + " (" + last + ")"
    return False, msg + "."


def check_cli_login(resolved: str) -> None:
    """Best-effort startup login check for Claude-style CLIs. Never blocks startup."""
    if "claude" not in Path(resolved).name.lower():
        return
    try:
        r = subprocess.run([resolved, "auth", "status"], capture_output=True, text=True, timeout=15)
    except Exception as exc:
        logger.warning("login check skipped (%s); make sure the CLI is signed in before use", exc)
        return
    ok, msg = interpret_auth_check(r.returncode, (r.stdout or "") + (r.stderr or ""))
    (logger.info if ok else logger.warning)("login check: %s", msg)


def preflight() -> None:
    """Fail fast with a friendly message if the CLI isn't configured/found."""
    if not CLI_BIN:
        logger.error("Not set up yet. Run:  cli-bridge setup   (see docs/01-install.md)")
        sys.exit(1)
    resolved = shutil.which(CLI_BIN) or (CLI_BIN if Path(CLI_BIN).is_file() else None)
    if not resolved:
        finder = "where.exe" if os.name == "nt" else "command -v"
        logger.error("Command not found: %r. Find its full path with `%s %s`, then run `cli-bridge setup` again with it.", CLI_BIN, finder, CLI_BIN)
        sys.exit(1)
    check_cli_login(resolved)
    if not MODELS:
        logger.warning("No model names configured. GET /v1/models will be empty. Re-run `setup` to add some.")
    logger.info("cli-bridge listening on http://%s:%d  (command=%s)", BIND_HOST, BIND_PORT, resolved)


# ─────────────────────────────────────────────────────────────────────────────
#  Interactive setup:  python3 bridge.py setup
# ─────────────────────────────────────────────────────────────────────────────

# Convenience model-name preset for the tested CLI; the user can edit/replace it.
CLAUDE_PRESET_MODELS = "claude-opus-4-8,claude-sonnet-4-6,claude-haiku-4-5"


def _ask(question: str, default: str = "") -> str:
    # On a real terminal, pre-fill the default so the user can press Enter to keep
    # it or edit it in place. When input isn't a terminal (piped/logged), show a
    # [bracketed] hint instead, since the pre-fill wouldn't be visible.
    prefilled = False
    if default and sys.stdin.isatty():
        try:
            import readline
            readline.set_startup_hook(lambda: readline.insert_text(default))
            prefilled = True
        except Exception:
            pass
    suffix = "" if (prefilled or not default) else f" [{default}]"
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except EOFError:
        answer = ""
    finally:
        if prefilled:
            import readline
            readline.set_startup_hook()
    return answer or default


def _yes(answer: str) -> bool:
    return answer.strip().lower() in ("y", "yes")


# ─────────────────────────────────────────────────────────────────────────────
#  Light terminal styling for setup: colored section headers, (●)/(○) menus, and
#  green check lines. It all degrades to plain ASCII when output is not a
#  terminal, when NO_COLOR is set, or when the console cannot do ANSI.
# ─────────────────────────────────────────────────────────────────────────────

def _stdout_tty() -> bool:
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


_TTY = _stdout_tty()


def _ansi_ok() -> bool:
    if os.environ.get("NO_COLOR") or not _TTY:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            handle = k.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if not k.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            k.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            return False
    return True


_COLOR = _ansi_ok()
_RESET = "\033[0m" if _COLOR else ""
_DIM = "\033[2m" if _COLOR else ""
_BOLD = "\033[1m" if _COLOR else ""
_CYAN = "\033[36m" if _COLOR else ""
_YELLOW = "\033[33m" if _COLOR else ""
_GREEN = "\033[32m" if _COLOR else ""
_DOT_ON = "(●)" if _TTY else "(*)"   # (●)
_DOT_OFF = "(○)" if _TTY else "( )"  # (○)
_CHECK = "✓" if _TTY else "+"        # ✓


def _header(text: str) -> None:
    print(f"\n{_CYAN}{_BOLD}--- {text} ---{_RESET}")


def _ok(text: str) -> None:
    print(f"{_GREEN}{_CHECK} {text}{_RESET}")


def _choose(title: str, options: list[str], default: int = 1) -> int:
    """Show a (●)/(○) numbered menu and return the chosen 1-based index."""
    print(f"\n{_YELLOW}{title}{_RESET}")
    print(f"{_DIM}Select by number, Enter to confirm.{_RESET}\n")
    for i, opt in enumerate(options, 1):
        dot = f"{_GREEN}{_DOT_ON}{_RESET}" if i == default else _DOT_OFF
        print(f"  {dot}  {i}. {opt}")
    raw = _ask("Choice", str(default))
    try:
        n = int(raw.strip())
        if 1 <= n <= len(options):
            return n
    except ValueError:
        pass
    return default


def _confirm(question: str, default_yes: bool = True) -> bool:
    """A (●)/(○) Yes/No menu. Returns True for Yes."""
    return _choose(question, ["Yes", "No"], default=1 if default_yes else 2) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Run it for the user: start the server in the background, confirm it answers,
#  and hand the shell back. Subcommands: start / stop / status. The foreground
#  server (no subcommand) is what `start` launches detached and what a boot
#  service execs directly.
# ─────────────────────────────────────────────────────────────────────────────

SERVER_LOG = BASE_DIR / "cli-bridge.log"
PID_FILE = BASE_DIR / ".cli-bridge.pid"


def _health_ok(host: str, port: str, timeout: float = 10.0) -> bool:
    import urllib.request
    where = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://{where}:{port}/health", timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def _smoke_test(host: str, port: str, model: str) -> tuple[bool, str]:
    """POST one tiny chat request through the bridge to confirm the CLI actually
    replies. Returns (ok, detail) - detail is the reply text or an error summary."""
    import urllib.request
    where = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with just: ok"}],
    }).encode()
    req = urllib.request.Request(
        f"http://{where}:{port}/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
    except Exception as exc:
        return False, str(exc)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return False, json.dumps(data)[:300]
    return (True, content.strip()) if content and content.strip() else (False, json.dumps(data)[:300])


def run_smoke_command() -> None:
    model = DEFAULT_MODEL or (MODELS[0] if MODELS else "")
    if not model:
        print("No model configured yet. Run  cli-bridge setup  first.")
        return
    if not _health_ok(BIND_HOST, str(BIND_PORT), timeout=3.0):
        print("cli-bridge doesn't seem to be running. Start it with:  cli-bridge start")
        return
    print(f"Sending a test message as '{model}' ...")
    ok, detail = _smoke_test(BIND_HOST, str(BIND_PORT), model)
    if ok:
        print("Success - your CLI replied through the bridge.")
    else:
        print("No reply came back.")
        print(f"  {detail[:200]}")
        print("If the CLI needs sign-in, run it once to log in, then  cli-bridge restart.")


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # On Windows, os.kill(pid, 0) would TERMINATE the process, so query it
        # through the Win32 API instead of signalling it.
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def start_background(host: str, port: str) -> bool:
    """Launch the foreground server detached, wait until it answers /health, and
    report. Returns True if it came up healthy."""
    running = _read_pid()
    if running and _alive(running):
        print(f"  Already running (PID {running}) at http://{host}:{port}")
        return True
    log = open(SERVER_LOG, "a")
    if os.name == "nt":
        kwargs = {"creationflags": 0x00000008 | 0x00000200}  # DETACHED_PROCESS | NEW_GROUP
    else:
        kwargs = {"start_new_session": True}
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve())],
        stdout=log, stderr=log, stdin=subprocess.DEVNULL, **kwargs,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"  Starting in the background (PID {proc.pid}) ...", flush=True)
    if _health_ok(host, port, timeout=20.0):
        _ok(f"Up and answering at http://{host}:{port}")
        return True
    print(f"  Started, but no /health response yet. See the log: {SERVER_LOG}")
    return False


def stop_background() -> None:
    pid = _read_pid()
    if not pid or not _alive(pid):
        print("Not running (no live background process recorded).")
        PID_FILE.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"Could not stop PID {pid}: {exc}")
        return
    for _ in range(25):
        if not _alive(pid):
            break
        time.sleep(0.2)
    PID_FILE.unlink(missing_ok=True)
    print(f"Stopped cli-bridge (PID {pid}).")


def status_background(host: str, port: str) -> None:
    pid = _read_pid()
    if pid and _alive(pid):
        healthy = _health_ok(host, port, timeout=3.0)
        tail = "answering /health." if healthy else f"not answering /health yet; see {SERVER_LOG}"
        print(f"Running (PID {pid}) at http://{host}:{port} — {tail}")
    else:
        print("Not running. Start it with:  cli-bridge start")


# ─────────────────────────────────────────────────────────────────────────────
#  Optional "start on boot" install, offered at the end of setup. It writes the
#  right service file for this OS, filled in with real paths, and enables it.
#  Best effort: any failure prints a pointer to the hand-install templates and
#  never stops setup.
# ─────────────────────────────────────────────────────────────────────────────

def _install_systemd(repo: Path, python: str) -> tuple[str, bool]:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit = unit_dir / "cli-bridge.service"
    unit.write_text(
        "[Unit]\n"
        "Description=cli-bridge, an OpenAI-compatible front-end for a local coding CLI\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={repo}\n"
        f"EnvironmentFile={repo}/.env\n"
        f"ExecStart={python} {repo}/bridge.py\n"
        "Restart=on-failure\n"
        "RestartSec=3\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "cli-bridge.service"], check=True)
    return (
        f"Installed and started: {unit}\n"
        "Check it:  systemctl --user status cli-bridge.service\n"
        "Keep it running after logout:  sudo loginctl enable-linger \"$USER\"",
        True,
    )


def _install_launchd(repo: Path, python: str) -> tuple[str, bool]:
    def esc(s: object) -> str:
        return html.escape(str(s), quote=False)

    agents = Path.home() / "Library" / "LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    plist = agents / "com.daimonlegal.cli-bridge.plist"
    plist.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        "  <key>Label</key>\n  <string>com.daimonlegal.cli-bridge</string>\n"
        "  <key>ProgramArguments</key>\n  <array>\n"
        f"    <string>{esc(python)}</string>\n"
        f"    <string>{esc(repo / 'bridge.py')}</string>\n"
        "  </array>\n"
        f"  <key>WorkingDirectory</key>\n  <string>{esc(repo)}</string>\n"
        "  <key>RunAtLoad</key>\n  <true/>\n"
        "  <key>KeepAlive</key>\n  <true/>\n"
        "  <key>StandardOutPath</key>\n  <string>/tmp/cli-bridge.log</string>\n"
        "  <key>StandardErrorPath</key>\n  <string>/tmp/cli-bridge.log</string>\n"
        "</dict>\n</plist>\n"
    )
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], check=True)
    return (f"Installed and loaded: {plist}\nCheck it:  launchctl list | grep cli-bridge", True)


def _install_windows(repo: Path, python: str) -> tuple[str, bool]:
    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    launcher = startup / "cli-bridge.cmd"
    launcher.write_text(f'@echo off\ncd /d "{repo}"\n"{python}" bridge.py\n')
    return (
        f"Installed a Startup launcher: {launcher}\n"
        "It runs at your next login; delete that file to stop it.",
        False,
    )


def offer_service_install() -> bool:
    """Offer to also run cli-bridge on boot. Returns True only if the service is
    now actively running (so setup should not also start a background copy).
    Best effort: never raises out of setup."""
    if sys.platform.startswith("linux"):
        label, tool, install = "a systemd user service", "systemctl", _install_systemd
    elif sys.platform == "darwin":
        label, tool, install = "a launchd agent", "launchctl", _install_launchd
    elif sys.platform.startswith("win"):
        label, tool, install = "a Windows Startup launcher", "", _install_windows
    else:
        return False

    print("Keep it running after a reboot? (optional)")
    print(f"I can install cli-bridge as {label} so it comes back on its own after")
    print("you log out or reboot.")
    if not _confirm("Install it as a service?", default_yes=False):
        print("  Skipped (this is only about reboots; I'll still start it now).\n")
        return False
    if tool and not shutil.which(tool):
        print(f"  '{tool}' isn't available here, so I can't install it automatically.")
        print("  See docs/01-install.md to set it up by hand.\n")
        return False
    try:
        report, started_now = install(BASE_DIR, sys.executable or "python3")
    except Exception as exc:
        print(f"  Could not finish the install: {exc}")
        print("  See docs/01-install.md to set it up by hand.\n")
        return False
    for line in report.splitlines():
        print(f"  {line}")
    print()
    return started_now


def install_shortcut() -> bool:
    """Drop a `cli-bridge` launcher on PATH so commands can be run as
    `cli-bridge <command>`. Returns True if it's immediately usable (installed
    and its directory is already on PATH). Best effort; never raises."""
    bindir = Path.home() / ".local" / "bin"
    python = sys.executable or "python3"
    script = str(Path(__file__).resolve())
    try:
        bindir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            launcher = bindir / "cli-bridge.cmd"
            launcher.write_text(f'@echo off\n"{python}" "{script}" %*\n')
        else:
            launcher = bindir / "cli-bridge"
            launcher.write_text(f'#!/bin/sh\nexec "{python}" "{script}" "$@"\n')
            launcher.chmod(0o755)
    except OSError as exc:
        print(f"  Could not create the shortcut ({exc}).")
        return False
    print(f"  Installed: {launcher}")
    on_path = str(bindir) in os.environ.get("PATH", "").split(os.pathsep)
    if on_path:
        print("  Try it:  cli-bridge status")
    else:
        print(f"  {bindir} isn't on your PATH yet. Add it, then restart your shell:")
        if os.name == "nt":
            print(f'    setx PATH "%PATH%;{bindir}"')
        else:
            print("    echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.zshrc   # or ~/.bashrc")
    print(f"  Remove it any time by deleting {launcher}")
    return on_path


def _write_env(cli_bin: str, models: str, port: str, host: str) -> None:
    ENV_FILE.write_text(
        "# Written by `cli-bridge setup`. Re-run setup or edit by hand.\n"
        f"CLI_BRIDGE_BIN={cli_bin}\n"
        f"CLI_BRIDGE_MODELS={models}\n"
        f"CLI_BRIDGE_PORT={port}\n"
        f"CLI_BRIDGE_HOST={host}\n"
    )


def find_cli(name: str) -> str | None:
    """Look for `name` on PATH, as a literal path, and in common install dirs
    that are often missing from a shell's PATH (npm global bins, ~/.local/bin,
    Homebrew). Returns a full path, or None."""
    hit = shutil.which(name)
    if hit:
        return hit
    if Path(name).is_file():
        return str(Path(name).resolve())
    home = Path.home()
    if os.name == "nt":
        dirs = [home / ".local" / "bin"]  # where the native installer puts claude.exe
        if os.environ.get("APPDATA"):
            dirs.append(Path(os.environ["APPDATA"]) / "npm")  # npm global
        if os.environ.get("LOCALAPPDATA"):
            dirs.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps")
        exts = [".exe", ".cmd", ".bat", ""]
    else:
        dirs = [home / ".local" / "bin", Path("/usr/local/bin"), Path("/opt/homebrew/bin"),
                home / ".npm-global" / "bin", home / "bin"]
        exts = [""]
    for d in dirs:
        for ext in exts:
            try:
                cand = d / (name + ext)
                if cand.is_file():
                    return str(cand)
            except OSError:
                pass
    return None


def setup() -> None:
    """Ask a handful of questions and write a .env. Safe to re-run."""
    _header("cli-bridge setup")
    print("A few questions, then I write the config, check it, and start the bridge")
    print("for you. Re-run this any time to change your answers.")
    print(f"{_DIM}Tip: each answer is pre-filled with a sensible default. Press Enter to")
    print(f"keep it, or edit/replace the text.{_RESET}")

    # 1/5: risk
    _header("Step 1/5 - The risk")
    print("Connecting your AI program to a bot may break that program's rules and")
    print("could get your account suspended. Please read DISCLAIMER.md first.")
    if not _confirm("Have you read DISCLAIMER.md and do you accept the risk?", default_yes=False):
        print("\nNothing changed. Read DISCLAIMER.md, then run setup again when ready.")
        return

    # 2/5: which program
    if _choose(
        "Step 2/5 - Which program are you connecting?",
        ["claude        the tested, supported option",
         "other/custom  any other command (advanced)"],
    ) == 2:
        print(f"{_DIM}  Note: cli-bridge currently understands only the way the supported")
        print(f"  program talks. A different one works only if it behaves the same way.{_RESET}")
        default_bin, default_models = "", ""
    else:
        default_bin, default_models = "claude", CLAUDE_PRESET_MODELS

    # 3/5: the command
    _header("Step 3/5 - The command that starts your AI CLI")
    print("The terminal program the bridge runs for each reply, for example  claude")
    print("(this is your AI CLI, not the bot or app that connects to the bridge).")
    finder = "where.exe" if os.name == "nt" else "command -v"
    print(f"{_DIM}Not sure where it is? Run  {finder} {default_bin or 'claude'}  in another terminal.{_RESET}")
    cli_bin = ""
    while not cli_bin:
        cli_bin = _ask("Command name or full path", default_bin)
        if not cli_bin:
            print("  A command is required.")
            continue
        resolved = shutil.which(cli_bin) or (cli_bin if Path(cli_bin).is_file() else None)
        if resolved:
            _ok(f"found it: {resolved}")
        else:
            print(f"  heads-up: '{cli_bin}' isn't on your PATH right now. I'll save it anyway,")
            print("  just make sure it's installed and signed in before you start the bridge.")

    # 4/5: models
    _header("Step 4/5 - Model name(s)")
    print("Comma-separated; the first one is used by default.")
    models = _ask("Model name(s)", default_models)

    # 5/5: network
    _header("Step 5/5 - Network (the defaults are right for almost everyone)")
    port = _ask("Port to listen on", "18800")
    host = _ask("Interface to bind", "127.0.0.1")

    if ENV_FILE.exists() and not _confirm(f"{ENV_FILE.name} already exists. Overwrite it?", default_yes=False):
        print("Left your existing .env untouched. Nothing saved.")
        return

    _write_env(cli_bin, models, port, host)
    _ok(f"Saved {ENV_FILE}")

    resolved = shutil.which(cli_bin) or (cli_bin if Path(cli_bin).is_file() else None)
    if not resolved:
        found = find_cli(cli_bin)
        if found:
            print(f"\n'{cli_bin}' isn't on your PATH, but it IS installed here:")
            print(f"    {found}")
            print("I'll use that full path and save it.")
            cli_bin = found
            _write_env(cli_bin, models, port, host)
            resolved = found
        else:
            finder = "where.exe" if os.name == "nt" else "command -v"
            print(f"\nI checked your PATH and the usual install spots, but couldn't find '{cli_bin}'.")
            if cli_bin == "claude":
                installer = ("irm https://claude.ai/install.ps1 | iex" if os.name == "nt"
                             else "curl -fsSL https://claude.ai/install.sh | bash")
                print("It isn't installed yet. Install the official CLI and sign in:")
                print(f"  1. Install:  {installer}")
                print("  2. Sign in:  run  claude  once and follow the browser prompt.")
                print("  3. Reopen this terminal, then run:  cli-bridge setup")
            else:
                print("It doesn't look installed yet. Do this, then you're set:")
                print("  1. Install your AI CLI and sign in (run it once by hand to log in).")
                print(f"  2. Confirm it shows up:    {finder} {cli_bin}")
                print("  3. Run onboarding again:   cli-bridge setup")
            print("Already installed somewhere unusual? Run  cli-bridge setup  and paste its full path.")
            print("More in docs/01-install.md.")
            return
    _ok(f"Checked your CLI: {resolved}")

    running_as_service = offer_service_install()
    if running_as_service:
        bridge_up = _health_ok(host, port)
        _ok(f"cli-bridge is running as a service at http://{host}:{port}")
    else:
        _header("Starting cli-bridge")
        bridge_up = start_background(host, port)

    first_model = models.split(",")[0].strip() if models else ""
    if bridge_up and first_model:
        print(f"\nSending a quick test message as '{first_model}' to confirm it works ...")
        ok, detail = _smoke_test(host, port, first_model)
        if ok:
            _ok("Success - your CLI replied through the bridge.")
        else:
            print("  Hmm - the bridge is up, but the test didn't come back.")
            print(f"  {detail[:160]}")
            print("  Likely the CLI isn't signed in: run it once to log in, then  cli-bridge restart.")
            print("  Full error in:  cli-bridge logs")

    print(f"\n{_DIM}A 'cli-bridge' command lets you run it from anywhere.{_RESET}")
    if _confirm("Add the cli-bridge shortcut?", default_yes=True):
        install_shortcut()

    _header("You're all set")
    print("cli-bridge is running in the background; your terminal is free.")
    print(f"  {_BOLD}cli-bridge status{_RESET}   is it running and healthy?")
    print(f"  {_BOLD}cli-bridge test{_RESET}     send a request through to confirm a reply")
    print(f"  {_BOLD}cli-bridge logs{_RESET}     recent output")
    print(f"  {_BOLD}cli-bridge stop{_RESET}     stop it")

    conn_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    _header("Connect your bot")
    print("Add the bridge as a custom / OpenAI-compatible provider, with:")
    print(f"  base URL:  {_BOLD}http://{conn_host}:{port}/v1{_RESET}")
    print(f"  model:     {_BOLD}{first_model or '(a name from cli-bridge status)'}{_RESET}")
    print("  API key:   none (leave it blank)")
    print()
    print(f"For Hermes: run  {_BOLD}hermes model{_RESET} , pick \"Custom endpoint (enter URL")
    print("manually)\", and paste the base URL above. Full steps in docs/03-hermes.md.")


def print_help() -> None:
    print(
        "cli-bridge - an OpenAI-compatible front-end for a local AI CLI.\n\n"
        "Commands:\n"
        "  cli-bridge setup      Configure it, then check and start it.\n"
        "  cli-bridge start      Start it in the background.\n"
        "  cli-bridge status     Show whether it's running and healthy.\n"
        "  cli-bridge test       Send one request through to confirm the CLI replies.\n"
        "  cli-bridge stop       Stop it.            (aliases: exit, quit)\n"
        "  cli-bridge restart    Stop it, then start it again.\n"
        "  cli-bridge logs       Show the log location and recent lines.\n"
        "  cli-bridge run        Run in the foreground (Ctrl-C to stop).\n"
        "  cli-bridge shortcut   Put the 'cli-bridge' command on your PATH.\n"
        "  cli-bridge help       Show this list.     (aliases: --help, -h)\n"
    )


def show_logs() -> None:
    if not SERVER_LOG.exists():
        print(f"No log yet at {SERVER_LOG}.")
        print("Start the bridge first:  cli-bridge start")
        return
    print(f"Log file: {SERVER_LOG}\n")
    for line in SERVER_LOG.read_text(errors="replace").splitlines()[-20:]:
        print(line)


def main() -> None:
    arg = sys.argv[1].lstrip("-").lower() if len(sys.argv) > 1 else ""
    if arg in ("help", "h", "?"):
        print_help()
        return
    if arg in ("setup", "init", "configure"):
        setup()
        return
    if arg == "start":
        start_background(BIND_HOST, str(BIND_PORT))
        return
    if arg in ("stop", "exit", "quit"):
        stop_background()
        return
    if arg in ("status", "health"):
        status_background(BIND_HOST, str(BIND_PORT))
        return
    if arg in ("test", "check"):
        run_smoke_command()
        return
    if arg == "restart":
        stop_background()
        start_background(BIND_HOST, str(BIND_PORT))
        return
    if arg in ("logs", "log"):
        show_logs()
        return
    if arg == "shortcut":
        install_shortcut()
        return
    if arg not in ("", "run", "serve", "foreground"):
        print(f"Unknown command: {sys.argv[1]!r}\n")
        print_help()
        return
    # run / serve / foreground / no subcommand: the foreground server. This is what
    # `start` launches detached and what a boot service (systemd/launchd) execs.
    if sys.stdin.isatty():
        print("Running in the foreground; press Ctrl-C to stop.")
        print("(To run in the background instead:  cli-bridge start)\n")
    preflight()
    ensure_sandbox()
    web.run_app(make_app(), host=BIND_HOST, port=BIND_PORT, access_log=None, print=None)


if __name__ == "__main__":
    main()
