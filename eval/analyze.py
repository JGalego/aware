#!/usr/bin/env python3
"""Summarize eval/run.sh results (runs.jsonl). Standard library only.

  analyze.py RUNS.jsonl [--baseline placebo] [--seed 1]

Per arm: runs, resolved (hidden phase 2 check passed), cost per resolved task, median cost, turns, tool use, whether the model made the advised
switch, and how much aware injected. Then each arm against the baseline, paired by (task, rep): median cost ratio with a bootstrap 95% interval.
Finally the pre-registered decision rule for `full` against the baseline. Samples here are small; read the intervals, not the point estimates.
"""
import json
import random
import statistics
import sys


def load(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def tool_count(r, *names):
    t = (r.get("transcript") or {}).get("tools") or {}
    return sum(v for k, v in t.items() if k in names)


def boot_ratio_ci(pairs, seed, n=5000):
    """pairs: [(cost_arm, cost_base)]. Median of per-pair ratios and a bootstrap 95% interval."""
    ratios = [a / b for a, b in pairs if b > 0]
    if len(ratios) < 2:
        return (med(ratios), float("nan"), float("nan"))
    rnd = random.Random(seed)
    meds = sorted(med([rnd.choice(ratios) for _ in ratios]) for _ in range(n))
    return (med(ratios), meds[int(0.025 * n)], meds[int(0.975 * n) - 1])


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    path, base, seed = argv[0], "placebo", 1
    if "--baseline" in argv:
        base = argv[argv.index("--baseline") + 1]
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])
    rows = load(path)
    ok = [r for r in rows if r["status"] == "ok"]
    bad = [r for r in rows if r["status"] != "ok"]
    arms = sorted({r["arm"] for r in rows}, key=lambda a: ["off", "placebo", "facts", "tiers", "full"].index(a))
    print("runs: %d (%d ok, %d not ok%s)\n" % (len(rows), len(ok), len(bad), ": " + ", ".join("%s=%s" % (r["id"], r["status"]) for r in bad) if bad else ""))

    hdr = "%-8s %4s %8s %10s %8s %6s %6s %7s %8s %9s" % ("arm", "n", "resolved", "$/resolved", "med $", "turns", "agents", "effort", "inj chars", "perm asks")
    print(hdr)
    print("-" * len(hdr))
    for a in arms:
        rs = [r for r in ok if r["arm"] == a]
        if not rs:
            continue
        res = sum(r["check2"] for r in rs)
        total = sum(r["cost"] for r in rs)
        print("%-8s %4d %5d/%-2d %10s %8.2f %6.0f %6.1f %7.1f %8.0f %9d" % (
            a, len(rs), res, len(rs), ("%.2f" % (total / res)) if res else "-", med([r["cost"] for r in rs]),
            med([(r.get("transcript") or {}).get("assistant_msgs", float("nan")) for r in rs]),
            statistics.mean(tool_count(r, "Agent", "Task", "Workflow") for r in rs),
            statistics.mean(tool_count(r, "mcp__aware__set_effort") for r in rs),
            statistics.mean(r["injected_chars"] for r in rs), sum(r["permission_prompts"] for r in rs)))
    print("\n(turns = assistant messages; agents = subagent/workflow calls per run; effort = set_effort calls per run)\n")

    by = {(r["task"], r["rep"], r["arm"]): r for r in ok}
    if any(r["arm"] == base for r in ok):
        print("paired against %s (same task and rep):" % base)
        for a in arms:
            if a == base:
                continue
            keys = [(t, rp) for (t, rp, arm) in by if arm == a and (t, rp, base) in by]
            if not keys:
                continue
            pairs = [(by[(t, rp, a)]["cost"], by[(t, rp, base)]["cost"]) for t, rp in keys]
            m, lo, hi = boot_ratio_ci(pairs, seed)
            dres = sum(by[(t, rp, a)]["check2"] - by[(t, rp, base)]["check2"] for t, rp in keys)
            print("  %-8s %2d pairs  median cost ratio %.2f (95%% CI %.2f to %.2f)  resolved %+d" % (a, len(keys), m, lo, hi, dres))

        full = [r for r in ok if r["arm"] == "full"]
        keys = [(t, rp) for (t, rp, arm) in by if arm == "full" and (t, rp, base) in by]
        if full and keys:
            pairs = [(by[(t, rp, "full")]["cost"], by[(t, rp, base)]["cost"]) for t, rp in keys]
            m, lo, hi = boot_ratio_ci(pairs, seed)
            dres = sum(by[(t, rp, "full")]["check2"] - by[(t, rp, base)]["check2"] for t, rp in keys)
            allowed = len(keys) / 8.0
            comply = sum(1 for r in full if tool_count(r, "mcp__aware__set_effort") >= 1) / len(full)
            print("\ndecision rule (full vs %s, fixed before any run; %d pairs, so only large effects are visible):" % (base, len(keys)))
            print("  cost ratio <= 0.75 ........ %.2f (CI %.2f to %.2f)  %s" % (m, lo, hi, "PASS" if m <= 0.75 else "FAIL"))
            print("  resolved drop <= %.1f ...... %+d  %s" % (allowed, dres, "PASS" if dres >= -allowed else "FAIL"))
            print("  advised set_effort made in >= 70%% of runs ... %.0f%%  %s" % (comply * 100, "PASS" if comply >= 0.7 else "FAIL"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
