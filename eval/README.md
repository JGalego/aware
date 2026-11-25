# Evaluation harness

Does telling Claude Code about its plan usage help? This runs real interactive sessions through eight small tasks under different aware arms (see the main README, "Measuring it") and records cost, success and behaviour. It uses your real Claude login and plan usage.

```sh
eval/validate.sh                       # checks the tasks themselves (no Claude, free)
eval/run.sh --dry-run --arms "placebo tiers full" --tasks all --reps 3
eval/run.sh --arms "placebo tiers full" --tasks "01 03 05 07" --reps 1 --budget-usd 25
python3 eval/analyze.py eval/results/<run>/runs.jsonl
```

## What a run is

- Eight tasks (`eval/tasks/NN-name/`): a small Python repo with a bug, two prompts (fix the bug, then a follow-up feature), hidden checks for each phase that Claude never sees, and reference solutions used only by `validate.sh`. Tasks 01-04 are easy, 05-08 medium.
- Each run starts a fresh copy outside any git repo, launches `aware launch` in tmux with `AWARE_ARM` set and the 5h/7d windows pretended to be 88% / 40% used (`AWARE_SIM_5H` / `AWARE_SIM_7D`; the stored numbers stay real), sends both prompts, waits for each turn to finish with a project-level Stop hook, runs the hidden checks, and collects the final cost, cache numbers, switch log, injection log and the transcript.
- Arms run in a random order within each task and repeat, one session at a time. The harness pauses when real 5h usage passes 75% and stops at 85% weekly, stops at `--budget-usd`, and after two runs projects the measured cost over the remaining runs and stops if it would not fit.
- It answers permission dialogs with Yes (counted and logged), so the tool allowlist is deliberately narrow: edits and a handful of read-only shell commands in the throwaway directory, plus aware's tools.

## What it can and cannot tell you

It measures behaviour under simulated pressure, not real quota savings: the readout says 88%, the plan does not. With a few runs per arm only large effects are visible. `analyze.py` ends with the decision rule fixed before the first run (cost ratio at most 0.75 against the placebo, no more than one task-equivalent fewer resolved, and the advised `set_effort` made in at least 70% of `full` runs).

## Side effects

`/model` and `/effort` write to `~/.claude/settings.json`; aware restores the defaults after each switch, and the harness restores them again on exit. Claude Code adds each throwaway directory to `~/.claude.json` and keeps its transcript under `~/.claude/projects/`; the work directories are `~/.cache/aware-eval/*` (removed after each run), so entries are easy to spot.
