#!/usr/bin/env python3
"""aware senses: user-defined readings, stuck detection and intervention feedback. Standard library only.

Called by the aware script; not meant to be run by hand except `aware senses`.

  list [--json]       run the enabled senses once and print them
  hook-extra SID      lines for the prompt hook: sense changes and the measured effect of aware's own moves
  tool-hook           PostToolUse hook: reads the event on stdin, may print an additionalContext reply
  enable NAME | disable NAME

A sense is an executable in the senses folder ($AWARE_DIR/senses, or $AWARE_SENSES_DIR). It prints one line,
`LEVEL READING | ADVICE`, where LEVEL is ok, warn or crit and the part after `|` is optional. It runs with a
short timeout, gets AWARE_FILE (the session's JSON) and AWARE_SESSION_ID in its environment, and its output is
sanitized and length-capped before Claude sees it.
"""
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime

DIR = os.environ.get("AWARE_DIR") or os.path.expanduser("~/.claude/aware")
SENSES = os.environ.get("AWARE_SENSES_DIR") or os.path.join(DIR, "senses")
SHIPPED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "senses")
TIMEOUT = float(os.environ.get("AWARE_SENSE_TIMEOUT") or 2)
LEVELS = ("ok", "warn", "crit")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")


def clean(text, limit):
    """Strip ANSI escapes and control characters, collapse whitespace, cap the length."""
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", str(text))
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def parse(line):
    """`LEVEL READING | ADVICE` -> (level, reading, advice) or None."""
    m = re.match(r"^\s*(ok|warn|crit)\b\s*(.*)$", line.strip())
    if not m:
        return None
    reading, _, advice = m.group(2).partition("|")
    return m.group(1), clean(reading, 80), clean(advice, 120)


def trusted(path):
    """Only run files the user owns that nobody else can write to."""
    try:
        st = os.stat(path)
    except OSError:
        return "unreadable"
    if st.st_uid != os.geteuid():
        return "not owned by you"
    if st.st_mode & 0o022:
        return "writable by others"
    if not os.access(path, os.X_OK):
        return "not executable"
    return None


def discover():
    out = []
    try:
        names = sorted(os.listdir(SENSES))
    except OSError:
        return out
    for name in names:
        path = os.path.join(SENSES, name)
        if name.startswith(".") or not NAME_RE.match(name) or os.path.isdir(path):
            continue
        out.append((name, path))
    return out


def run_one(name, path, env):
    err = trusted(os.path.realpath(path))
    if err:
        return {"name": name, "error": "skipped: " + err}
    try:
        r = subprocess.run([path], capture_output=True, text=True, timeout=TIMEOUT, env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"name": name, "error": "timed out after %gs" % TIMEOUT}
    except OSError as e:
        return {"name": name, "error": "could not run: " + clean(e, 60)}
    first = (r.stdout.strip().splitlines() or [""])[0]
    parsed = parse(first)
    if r.returncode != 0 or not parsed:
        return {"name": name, "error": "bad output (expected: ok|warn|crit READING | ADVICE)"}
    level, reading, advice = parsed
    return {"name": name, "level": level, "reading": reading, "advice": advice}


def run_all(sid="", session_file=""):
    env = dict(os.environ, AWARE_DIR=DIR, AWARE_SESSION_ID=sid, AWARE_FILE=session_file)
    items = discover()
    if not items:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(items))) as ex:
        return list(ex.map(lambda it: run_one(it[0], it[1], env), items[:16]))


def load(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save(path, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


def log_event(kind, text, pane=None):
    """events.log feeds the activity list in `aware watch`."""
    try:
        os.makedirs(DIR, exist_ok=True)
        with open(os.path.join(DIR, "events.log"), "a") as fh:
            fh.write("%s %s pane=%s %s\n" % (datetime.now().astimezone().isoformat(timespec="seconds"), kind,
                                             pane or os.environ.get("TMUX_PANE", "-"), clean(text, 200)))
    except OSError:
        pass


def sense_line(s):
    tail = ". " + s["advice"] if s.get("advice") else ""
    return "sense %s (%s): %s%s" % (s["name"], s["level"], s["reading"], tail)


# ---- intervention feedback ---------------------------------------------------------------------

def session_pane(sid):
    pane = os.environ.get("TMUX_PANE")
    if pane:
        return pane
    try:
        for n in os.listdir(DIR):
            if n.startswith("pane-") and load(os.path.join(DIR, n), {}).get("session_id") == sid:
                return "%" + n[5:-5]
    except OSError:
        pass
    return None


def read_hist(sid):
    rows = []
    try:
        with open(os.path.join(DIR, sid + ".hist")) as fh:
            for line in fh:
                p = line.split()
                if len(p) >= 2:
                    # third column (cache misses so far) is absent in older history files
                    rows.append((float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else None))
    except (OSError, ValueError):
        pass
    return rows


def interventions(pane, since):
    out = []
    try:
        with open(os.path.join(DIR, "switches.log")) as fh:
            lines = fh.readlines()[-300:]
    except OSError:
        return out
    for line in lines:
        m = re.match(r"(\S+) (/\w+)(?: (\S+))? pane=(\S+)", line.strip())
        if not m or m.group(4) != pane:
            continue
        try:
            ts = datetime.fromisoformat(m.group(1))
        except ValueError:
            continue
        if ts.timestamp() >= since:
            out.append((ts.timestamp(), m.group(1), m.group(2), m.group(3) or ""))
    return out


def effects(sid):
    """Compare cost per turn before and after each of aware's own moves; return unreported lines."""
    rows = read_hist(sid)
    if len(rows) < 4:
        return []
    deltas = [(rows[i][0], rows[i][1] - rows[i - 1][1]) for i in range(1, len(rows)) if rows[i][1] > rows[i - 1][1]]
    pane = session_pane(sid)
    if not pane:
        return []
    state_path = os.path.join(DIR, sid + ".fb")
    done = load(state_path, [])
    out = []
    for ts, iso, cmd, arg in interventions(pane, rows[0][0]):
        if iso in done:
            continue
        before = [d for t, d in deltas if t <= ts][-3:]
        after = [d for t, d in deltas if t > ts + 1]
        if cmd in ("/model", "/compact"):
            after = after[1:]        # the first turn after a switch or compact pays for the cache rebuild
        after = after[:3]
        if len(before) < 2 or len(after) < 2:
            continue
        b, a = sum(before) / len(before), sum(after) / len(after)
        pct = (a - b) / b * 100 if b else 0
        verdict = "" if pct <= -10 else "; no clear drop yet"
        if cmd == "/effort":
            # An effort change should keep the prompt cache. If the cache-miss counter rose right after it,
            # say so: on this setup the change was not free.
            seen = [(t, m) for t, _, m in rows if m is not None]
            pre = [m for t, m in seen if t <= ts]
            post = [m for t, m in seen if ts < t <= ts + 120]
            if pre and post and max(post) > pre[-1]:
                verdict += "; cache misses rose by %d right after it, so here an effort change is not free" % (max(post) - pre[-1])
        text = "effect of %s: cost per turn $%.2f -> $%.2f (%+.0f%%, %d turns before, %d after)%s" % (
            (cmd + " " + arg).strip(), b, a, pct, len(before), len(after), verdict)
        out.append(text)
        done.append(iso)
        log_event("effect", text, pane)
    if out:
        save(state_path, done[-50:])
    return out


# ---- stuck detection ---------------------------------------------------------------------------

def tool_hook():
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        return 0
    sid = ev.get("session_id")
    tool = ev.get("tool_name") or "?"
    if not sid:
        return 0
    ti = ev.get("tool_input") or {}
    # Claude words a fresh `description` for every call, so leave it (and other labels) out of the fingerprint.
    core = {k: v for k, v in ti.items() if k not in ("description", "timeout")} if isinstance(ti, dict) else ti
    fp = hashlib.sha1(json.dumps([tool, core, ev.get("tool_response")], sort_keys=True, default=str).encode()).hexdigest()[:12]
    target = ti.get("file_path") if tool in EDIT_TOOLS and isinstance(ti, dict) else None
    path = os.path.join(DIR, sid + ".tools")
    st = load(path, {"n": 0, "calls": [], "last": {}})
    st["n"] += 1
    st["calls"] = (st["calls"] + [{"fp": fp, "tool": tool, "file": target}])[-12:]
    calls, last, msg = st["calls"], st["last"], None

    def due(key, gap):
        return st["n"] - last.get(key, -99) >= gap

    same = 0
    for c in reversed(calls):
        if c["fp"] != fp:
            break
        same += 1
    if same >= 3 and due("same:" + fp, 3):
        last["same:" + fp] = st["n"]
        msg = ("stuck? the same %s call ran %d times in a row with identical results. "
               "Read the result, question an assumption, then change approach or ask the user." % (tool, same))
    elif target:
        count = sum(1 for c in calls[-8:] if c.get("file") == target)
        if count >= 5 and due("edit:" + target, 4):
            last["edit:" + target] = st["n"]
            msg = ("stuck? %d edits to %s in the last 8 tool calls. Step back: re-read the failure, "
                   "then change approach or ask the user." % (count, os.path.basename(target)))
    st["last"] = {k: v for k, v in last.items() if st["n"] - v < 200}
    save(path, st)
    if msg:
        log_event("stuck", msg)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "[aware] " + msg}}))
    return 0


# ---- commands ------------------------------------------------------------------------------------

def hook_extra(sid):
    """Lines for the prompt hook. Remembers each sense's last level so only changes are reported."""
    path = os.path.join(DIR, sid + ".senses")
    prev = load(path, {})
    cur, lines = {}, []
    for s in run_all(sid, os.path.join(DIR, sid + ".json")):
        if "level" not in s:
            continue
        cur[s["name"]] = s["level"]
        before = prev.get(s["name"], "ok")
        if s["level"] != "ok" and (s["level"] != before or s["level"] == "crit"):
            lines.append(sense_line(s))
        elif s["level"] == "ok" and before != "ok":
            lines.append("sense %s: ok again (%s)" % (s["name"], s["reading"]))
    save(path, cur)
    lines += effects(sid)
    for line in lines:
        print("[aware] " + line)
    return 0


def cmd_list(as_json):
    res = run_all(os.environ.get("AWARE_SESSION_ID", ""), os.environ.get("AWARE_FILE", ""))
    if as_json:
        print(json.dumps(res))
        return 0
    enabled = {s["name"] for s in res}
    for s in res:
        if "error" in s:
            print("%-10s %-5s %s" % (s["name"], "-", s["error"]))
        else:
            print("%-10s %-5s %s%s" % (s["name"], s["level"], s["reading"], (" | " + s["advice"]) if s["advice"] else ""))
    try:
        extra = [n[:-3] if n.endswith(".sh") else n for n in sorted(os.listdir(SHIPPED))]
    except OSError:
        extra = []
    extra = [n for n in extra if n not in enabled]
    if not res:
        print("no senses enabled (folder: %s)" % SENSES)
    if extra:
        print("available: %s  (aware senses enable NAME)" % " ".join(extra))
    return 0


def cmd_enable(name):
    src = None
    for cand in (name, name + ".sh"):
        if os.path.isfile(os.path.join(SHIPPED, cand)):
            src = os.path.join(SHIPPED, cand)
            break
    if not NAME_RE.match(name) or not src:
        print("no such shipped sense: %s" % name, file=sys.stderr)
        return 1
    os.makedirs(SENSES, exist_ok=True)
    link = os.path.join(SENSES, name)
    if os.path.lexists(link):
        os.remove(link)
    os.symlink(src, link)
    print("enabled %s" % name)
    return 0


def cmd_disable(name):
    link = os.path.join(SENSES, name)
    if not NAME_RE.match(name) or not os.path.islink(link):
        print("not an enabled shipped sense: %s (remove your own scripts by hand)" % name, file=sys.stderr)
        return 1
    os.remove(link)
    print("disabled %s" % name)
    return 0


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "list":
        return cmd_list("--json" in argv)
    if cmd == "hook-extra" and len(argv) > 1:
        return hook_extra(argv[1])
    if cmd == "tool-hook":
        return tool_hook()
    if cmd == "enable" and len(argv) > 1:
        return cmd_enable(argv[1])
    if cmd == "disable" and len(argv) > 1:
        return cmd_disable(argv[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
