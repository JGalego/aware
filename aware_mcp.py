#!/usr/bin/env python3
"""Minimal stdio MCP server for aware. Stdlib only. Every tool shells out to the
`aware` script, which owns validation and the tmux keystroke injection."""
import json
import os
import subprocess
import sys

AWARE = sys.argv[1] if len(sys.argv) > 1 else "aware"

# AWARE_MODELS is ordered cheapest to most expensive (same as the aware script).
_MODELS = os.environ.get("AWARE_MODELS", "haiku sonnet opus").split() or ["haiku"]
CHEAP = _MODELS[0]
MID = _MODELS[1] if len(_MODELS) > 2 else None

# Sent once at initialize; Claude Code places it in the (cached) system prompt, so it costs
# almost nothing per turn, unlike text injected by the hook.
MID_RULE = f"; \"{MID}\" when the work needs judgment (code review, exploring unfamiliar code, drafting)" if MID else "."
if MID:
    MID_RULE += "."
INSTRUCTIONS = f"""\
aware: spend this session's plan usage and context deliberately while pursuing the user's goal.

Signals. A "[usage]" line arrives with a prompt whenever something meaningful changed; between those, assume nothing changed. It shows 5h/7d plan usage with pace (share used / share of the window elapsed; above 1x the limit runs out before it resets), context %, model, effort and whether the prompt cache is warm. An "[aware] tier=..." line follows when the tier is lean, conserve or critical. When it names a call (e.g. "call set_effort medium now"), make that call first, in the same turn, before working on the request, unless the user has told you otherwise; then follow the rest of its advice. Call get_usage before committing to a large piece of work or when you need fresh numbers, not every turn. Other "[aware]" lines are facts about your situation, not requests: "sense NAME" reports a reading the user chose to track (follow its advice), "stuck?" means you are repeating yourself (change approach or ask), and "effect of ..." tells you what your last switch saved.

Cheapest moves first:
1. Delegate bulk work to subagents on a cheaper model: only their short report enters this context. Ask them for conclusions, not dumps. Match the model to the task: "{CHEAP}" for mechanical work (search, file reads, extraction, summaries){MID_RULE} Keep the hardest reasoning in this session. A weak subagent answer that you must redo costs more than it saved, so step up a model when a result looks thin.
2. Keep your own reads and outputs small: read the lines you need, don't re-read what you already have, keep replies short.
3. Use effort as the main knob (set_effort): lower it for routine steps and raise it only for genuinely hard reasoning, saying why.
4. Switch model (set_model) only at a natural break, when substantial work remains. A switch re-reads the whole context uncached, so it is cheapest when context is small (early on, or right after compact) or when the cache is already cold. Never switch back and forth; stepping up to a costlier model needs a stated reason.
5. Compact (compact) when context is high and you reach a natural break (a task done, before a new phase). It replaces the history with a summary, so first state the goal, next steps and key file paths in your reply.

At tier critical: finish the current step, summarize where things stand, and ask the user before starting anything new.
set_model, set_effort and compact take effect after your current turn ends. Tell the user in one short line whenever you use them.
"""

TOOLS = [
    {
        "name": "get_usage",
        "description": "Fresh usage readout: 5-hour and 7-day plan usage with pace and reset times, context-window %, "
                       "model, effort, prompt-cache state and session cost, plus the current tier and advice "
                       "(lean/conserve/critical) when it is not normal, plus any user-defined sense that is not ok.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_model",
        "description": "Switch THIS session's model (types /model <name> into the terminal). Takes effect "
                       "after the current turn ends; a 'Switch model?' dialog then appears (confirmed automatically only if the user enabled AWARE_AUTOCONFIRM, otherwise the user must press Enter). "
                       "Switching drops the prompt cache (the next reply re-reads the whole history), so it "
                       "only pays off for long remaining work or when usage is high; do not switch back and forth. "
                       "Stepping up to a costlier model needs a stated reason.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": {"type": "string", "enum": ["haiku", "sonnet", "opus"]}},
            "required": ["model"],
        },
    },
    {
        "name": "set_effort",
        "description": "Change THIS session's effort level (types /effort <level> into the terminal). "
                       "Takes effect after the current turn ends. Lower effort saves tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {"level": {"type": "string", "enum": ["low", "medium", "high", "xhigh", "max"]}},
            "required": ["level"],
        },
    },
    {
        "name": "compact",
        "description": "Compact THIS session's context (types /compact into the terminal). Runs after the current "
                       "turn ends and replaces the history with a summary, so first write the goal, next steps and "
                       "key file paths in your reply. Use at a natural break when context is high; a model switch "
                       "right after compacting is cheap.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# Never defer these behind tool search: a tool the model must first discover is a tool it skips.
for _t in TOOLS:
    _t["_meta"] = {"anthropic/alwaysLoad": True}


def run(args):
    p = subprocess.run([AWARE, *args], capture_output=True, text=True, timeout=15)
    out = (p.stdout + p.stderr).strip()
    return out or f"(exit {p.returncode})", p.returncode != 0


def call(name, a):
    if name == "get_usage":
        return run(["show"])
    if name == "set_model":
        return run(["switch", "model", str(a.get("model", ""))])
    if name == "set_effort":
        return run(["switch", "effort", str(a.get("level", ""))])
    if name == "compact":
        return run(["compact"])
    return f"unknown tool: {name}", True


def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, id_ = m.get("method"), m.get("id")
        if id_ is None:  # notification (e.g. notifications/initialized)
            continue
        if method == "initialize":
            reply(id_, {
                "protocolVersion": (m.get("params") or {}).get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aware", "version": "0.2.0"},
                "instructions": INSTRUCTIONS,
            })
        elif method == "tools/list":
            reply(id_, {"tools": TOOLS})
        elif method == "tools/call":
            p = m.get("params") or {}
            try:
                text, is_err = call(p.get("name", ""), p.get("arguments") or {})
            except Exception as e:  # noqa: BLE001
                text, is_err = f"aware error: {e}", True
            reply(id_, {"content": [{"type": "text", "text": text}], "isError": is_err})
        elif method == "ping":
            reply(id_, {})
        else:
            reply(id_, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
