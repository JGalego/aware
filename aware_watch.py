#!/usr/bin/env python3
"""aware watch: a live terminal dashboard for the session aware is tracking.

Usage (via the aware script): aware watch [--once]
Reads `aware show --json` twice a second and the switch log, and redraws in place. Standard library
only. --once prints a single frame and exits (also what you get when stdout is not a terminal).
Set NO_COLOR=1 for plain output. Ctrl-C quits.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
if os.environ.get("AWARE_WATCH_COLOR") == "1":
    COLOR = True

# One quiet palette: GitHub-dark neutrals plus four signal colors that match the tiers.
BG = (13, 17, 23)
FG = (201, 209, 217)
MUTED = (110, 118, 129)
FAINT = (48, 54, 61)
GREEN = (63, 185, 80)
YELLOW = (227, 179, 65)
ORANGE = (240, 136, 62)
RED = (248, 81, 73)
BLUE = (88, 166, 255)
TEAL = (57, 197, 207)

TIERS = ["normal", "lean", "conserve", "critical"]
TIER_COLOR = {"normal": GREEN, "lean": YELLOW, "conserve": ORANGE, "critical": RED}
TIER_NOTE = {
    "normal": "all clear",
    "lean": "trim effort, delegate bulk work, keep replies short",
    "conserve": "step effort and model down, compact at the next break",
    "critical": "wrap up, summarize state, ask before starting anything new",
}

DIGITS = {
    "0": ("┏━┓", "┃ ┃", "┗━┛"), "1": (" ╻ ", " ┃ ", " ╹ "), "2": ("╺━┓", "┏━┛", "┗━╸"),
    "3": ("╺━┓", " ━┫", "╺━┛"), "4": ("╻ ╻", "┗━┫", "  ╹"), "5": ("┏━╸", "┗━┓", "╺━┛"),
    "6": ("┏━╸", "┣━┓", "┗━┛"), "7": ("╺━┓", "  ┃", "  ╹"), "8": ("┏━┓", "┣━┫", "┗━┛"),
    "9": ("┏━┓", "┗━┫", "╺━┛"), "%": ("◦ ╱", " ╱ ", "╱ ◦"), "?": ("╺━┓", " ╺┛", " ╹ "),
}


def paint(s, fg=None, bg=None, bold=False, dim=False):
    if not COLOR:
        return s
    codes = []
    if bold:
        codes.append("1")
    if dim:
        codes.append("2")
    if fg:
        codes.append("38;2;%d;%d;%d" % fg)
    if bg:
        codes.append("48;2;%d;%d;%d" % bg)
    return "\x1b[%sm%s\x1b[0m" % (";".join(codes), s) if codes else s


def mix(c, f):
    """c faded toward the background by factor f (1 = unchanged, 0 = background)."""
    return tuple(int(BG[i] + (c[i] - BG[i]) * f) for i in range(3))


def vis_len(s):
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def pad(s, n):
    return s + " " * max(0, n - vis_len(s))


def zone(pos, marks):
    """Signal color for a position (0-100) given (lean, warn, crit-or-None) thresholds."""
    lean, warn, crit = marks
    if crit is not None and pos >= crit:
        return RED
    if pos >= warn:
        return ORANGE
    if pos >= lean:
        return YELLOW
    return GREEN


def bar(pct, width, marks, thick=False):
    """A progress track whose unfilled part shows the zones as a faint gradient."""
    p = 0 if pct is None else max(0.0, min(100.0, pct))
    eighths = round(p / 100 * width * 8)
    full, part = divmod(eighths, 8)
    out = []
    for i in range(width):
        col = zone((i + 0.5) / width * 100, marks)
        if i < full:
            out.append(paint("█", fg=col))
        elif i == full and part:
            out.append(paint(" ▏▎▍▌▋▊▉"[part], fg=col, bg=mix(col, 0.22)))
        else:
            out.append(paint("█", fg=mix(col, 0.22)))
    return "".join(out)


def thin(pct, width, marks):
    p = 0 if pct is None else max(0.0, min(100.0, pct))
    filled = round(p / 100 * width)
    out = []
    for i in range(width):
        col = zone((i + 0.5) / width * 100, marks)
        out.append(paint("━", fg=col) if i < filled else paint("─", fg=FAINT))
    return "".join(out)


def big(text):
    rows = ["", "", ""]
    for ch in text:
        g = DIGITS.get(ch, DIGITS["?"])
        for r in range(3):
            rows[r] += g[r] + " "
    return rows


def spark(vals, width, ceiling):
    ticks = "▁▂▃▄▅▆▇█"
    vals = vals[-width:]
    top = ceiling or 100
    return "".join(ticks[min(7, int(v / top * 7.999))] for v in vals)


def short_model(model, models):
    m = (model or "?").lower()
    for name in models or []:
        if name in m:
            return name
    return model or "?"


def ktok(n):
    return "?" if n is None else ("%dk" % (n / 1000) if n >= 1000 else str(int(n)))


def read_events(path, pane, limit):
    """Moves aware made (switches.log) plus stuck warnings and measured effects (events.log), oldest first."""
    out = []
    for fname, pattern in (("switches.log", r"(\S+) (autoconfirmed )?(/\w+)(?: (\S+))? pane=(\S+)"),
                           ("events.log", r"(\S+) (stuck|effect|gate) pane=(\S+) (.*)")):
        try:
            with open(os.path.join(os.path.dirname(path), fname)) as fh:
                lines = fh.readlines()[-200:]
        except OSError:
            continue
        for line in lines:
            m = re.match(pattern, line.strip())
            if not m:
                continue
            if fname == "events.log":
                (ts, cmd, p, arg), auto = m.groups(), ""
            else:
                ts, auto, cmd, arg, p = m.groups()
            if pane and p != pane:
                continue
            try:
                when = datetime.fromisoformat(ts)
            except ValueError:
                continue
            out.append((when, bool(auto), cmd, arg or ""))
    out.sort(key=lambda e: e[0])
    return out[-limit:]


class Tracker:
    """Remembers the previous reading so changes can be highlighted for a few seconds."""

    def __init__(self):
        self.prev = {}
        self.changed = {}   # key -> (when, old value)
        self.hist = []

    def update(self, st, now):
        models = st.get("models") or []
        cur = {"tier": st.get("tier"), "model": short_model(st.get("model"), models), "effort": st.get("effort")}
        for k, v in cur.items():
            if k in self.prev and self.prev[k] != v:
                self.changed[k] = (now, self.prev[k])
        ctx = st.get("ctx")
        if ctx is not None:
            if self.hist and self.hist[-1] - ctx >= 1 and ctx < self.hist[-1] * 0.6:
                self.changed["ctx"] = (now, self.hist[-1])
            self.hist.append(ctx)
            self.hist = self.hist[-30:]
        self.prev = cur

    def recent(self, key, now, secs=12):
        c = self.changed.get(key)
        return c if c and now - c[0] < secs else None


def chip(label, value, hot=None, color=FG):
    """A small labelled pill; while a value is new it shows `old ▸ new`."""
    body = paint(" %s " % value, fg=BG, bg=color, bold=True) if hot else paint(" %s " % value, fg=FG, bg=FAINT)
    prefix = paint("%s " % label, fg=MUTED)
    if hot:
        return prefix + paint(" %s " % hot, fg=MUTED, bg=FAINT) + paint(" ▸ ", fg=MUTED) + body
    return prefix + body


def frame(st, tr, events, now, width, once=False, senses=None):
    L = []
    w = width
    if not st:
        return ["", "  " + paint("aware", fg=TEAL, bold=True),
                "",
                "  " + paint("waiting for a Claude session...", fg=MUTED),
                "  " + paint("start one with: aware launch --watch", fg=FAINT)]
    tier = st.get("tier") or "normal"
    tcol = TIER_COLOR.get(tier, FG)
    lim = st.get("limits") or {}
    plan = (lim.get("lean", 50), lim.get("warn", 80), lim.get("crit", 95))
    cmark = (lim.get("ctx_lean", 50), lim.get("ctx_warn", 70), None)

    pulse = "●" if int(now * 2) % 2 == 0 else "○"
    head = paint("aware", fg=TEAL, bold=True) + paint("  live " + pulse, fg=MUTED)
    L.append("")
    L.append("  " + head)
    L.append("")

    # Tier ladder: the current tier is a solid badge, the others are quiet. The badge blinks briefly on a change.
    flash = tr.recent("tier", now, 3)
    steps = []
    for t in TIERS:
        name = t.upper()
        if t == tier:
            inv = flash and int(now * 4) % 2 == 1
            steps.append(paint(" ● %s " % name, fg=tcol, bg=None, bold=True) if inv else
                         paint(" ● %s " % name, fg=BG, bg=tcol, bold=True))
        else:
            steps.append(paint(" %s " % name, fg=FAINT if TIERS.index(t) > TIERS.index(tier) else MUTED))
    L.append("  " + paint(" ─ ", fg=FAINT).join(steps))
    L.append("  " + paint(TIER_NOTE.get(tier, ""), fg=MUTED))
    L.append("")

    # Context: a big numeral next to a thick two-row track, thresholds named underneath.
    ctx = st.get("ctx")
    num = big("?" if ctx is None else "%d%%" % int(ctx))
    nw = 4 * 4 + 1
    bw = max(20, w - nw - 6)
    hist = spark(tr.hist, 16, 100)   # full 0-100 scale: a calm line unless the context really moves
    cx = tr.recent("ctx", now)
    extra = paint("compacted ↓ from %d%%" % cx[1], fg=GREEN, bold=True) if cx else paint("%s tokens" % ktok(st.get("ctx_tokens")), fg=MUTED)
    L.append("  " + pad(paint("CONTEXT", fg=MUTED, bold=True), nw + 2) + extra + "   " + paint(hist, fg=MUTED))
    track = bar(ctx, bw, cmark)
    ticks = [" "] * bw
    end = 0
    for label, at in (("lean", cmark[0]), ("warn", cmark[1])):
        pos = max(end, min(bw - len(label), int(at / 100 * bw)))   # never overlap the previous label
        for i, ch in enumerate(label):
            ticks[pos + i] = ch
        end = pos + len(label) + 1
    for i, row in enumerate(num):
        paint_num = paint(row, fg=tcol if i == 1 else FG, bold=True)
        mid = track if i < 2 else paint("".join(ticks), fg=MUTED)
        L.append("  " + pad(paint_num, nw + 2) + mid)
    L.append("")

    # Plan windows: thin bars with pace.
    pw = max(20, w - 32)
    for key, label in (("h5", "5H"), ("d7", "7D")):
        win = st.get(key) or {}
        u, pace = win.get("u"), win.get("p")
        pct = "  ?  " if u is None else "%3d%%" % int(u)
        pace_s = "" if pace is None else "pace %.1fx" % pace
        pcol = RED if (pace or 0) > 1 else MUTED
        L.append("  " + paint(label, fg=MUTED, bold=True) + "  " + thin(u, pw, plan) + "  " + paint(pct, fg=FG, bold=True) + "  " + paint(pace_s, fg=pcol))
    L.append("")

    # Model, effort, cache.
    m, e = tr.prev.get("model"), tr.prev.get("effort")
    mc, ec = tr.recent("model", now), tr.recent("effort", now)
    warm = st.get("warm")
    cache = {True: ("warm", GREEN), False: ("cold", MUTED)}.get(warm, ("unknown", MUTED))
    chips = [chip("model", m, mc[1] if mc else None, BLUE), chip("effort", e, ec[1] if ec else None, TEAL),
             paint("cache ", fg=MUTED) + paint(" %s " % cache[0], fg=cache[1] if warm else FG, bg=FAINT)]
    line = "  " + "    ".join(chips)
    if vis_len(line) > w:   # a change is being shown (old ▸ new): keep the cache chip on its own line
        L.append("  " + "    ".join(chips[:2]))
        L.append("  " + chips[2])
    else:
        L.append(line)
    L.append("")

    # Senses: the user's own readings, one row each.
    if senses:
        L.append("  " + paint("SENSES", fg=MUTED, bold=True) + " " + paint("─" * max(4, w - 8), fg=FAINT))
        for sn in senses:
            if "level" not in sn:
                L.append("  " + paint("○", fg=FAINT) + " " + paint(pad(sn["name"], 10), fg=MUTED) + paint(sn.get("error", ""), fg=FAINT))
                continue
            col = {"ok": GREEN, "warn": ORANGE, "crit": RED}.get(sn["level"], MUTED)
            row = "  " + paint("●", fg=col) + " " + paint(pad(sn["name"], 10), fg=FG if sn["level"] != "ok" else MUTED)
            L.append(row + paint(sn["reading"], fg=FG if sn["level"] != "ok" else MUTED))
        L.append("")

    # Activity feed: what aware actually did, newest last.
    L.append("  " + paint("ACTIVITY", fg=MUTED, bold=True) + " " + paint("─" * max(4, w - 10), fg=FAINT))
    icons = {"/effort": ("effort", TEAL), "/model": ("model", BLUE), "/compact": ("compact", ORANGE),
             "stuck": ("stuck", RED), "effect": ("effect", GREEN), "gate": ("gate", ORANGE)}
    shown = 0
    for when, auto, cmd, arg in events[-5:]:
        name, col = icons.get(cmd, (cmd, FG))
        text = {"/effort": "effort set to %s" % arg, "/model": ("model dialog confirmed: %s" if auto else "model set to %s") % arg,
                "/compact": "compacting the conversation"}.get(cmd, arg if cmd in ("stuck", "effect", "gate") else cmd)
        L.append("  " + paint(when.strftime("%H:%M:%S"), fg=MUTED) + "  " + paint("▸", fg=col) + " " + paint(text, fg=FG))
        shown += 1
    if not shown:
        L.append("  " + paint("quiet so far", fg=FAINT))
    return L


def fetch(self_path):
    try:
        r = subprocess.run([self_path, "show", "--json"], capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def fetch_senses(self_path):
    try:
        r = subprocess.run([self_path, "senses", "--json"], capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else []
        return data if isinstance(data, list) else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def main():
    args = sys.argv[1:]
    self_path = args[0] if args and not args[0].startswith("--") else "aware"
    once = "--once" in args or not sys.stdout.isatty()
    logdir = os.environ.get("AWARE_DIR") or os.path.expanduser("~/.claude/aware")
    log = os.path.join(logdir, "switches.log")
    pane = os.environ.get("AWARE_WATCH_PANE", "")
    start = datetime.now().astimezone()
    tr = Tracker()

    senses = []

    def render(st, now):
        cols = shutil.get_terminal_size((80, 24)).columns
        events = read_events(log, pane, 5 if once else 200)
        if not once:
            events = [ev for ev in events if ev[0] >= start]
        return frame(st, tr, events, now, max(46, min(cols - 4, 76)), once, senses)

    if once:
        senses = fetch_senses(self_path)
        st = fetch(self_path)
        if st:
            tr.update(st, time.time())
        print("\n".join(render(st, time.time())))
        return 0

    sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
    try:
        st, last, last_senses = None, 0.0, 0.0
        while True:
            now = time.time()
            if now - last >= 0.5:
                st, last = fetch(self_path), now
                if st:
                    tr.update(st, now)
            if now - last_senses >= 5:     # senses run user scripts: poll them slowly
                senses, last_senses = fetch_senses(self_path), now
            lines = render(st, now)
            sys.stdout.write("\x1b[H" + "".join(row + "\x1b[K\n" for row in lines) + "\x1b[J")
            sys.stdout.flush()
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
