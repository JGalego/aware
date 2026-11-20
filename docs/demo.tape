# Demo recording for the README. Regenerate from the repo root with: vhs docs/demo.tape
# Needs claude, tmux and jq, plus TYPESAFE_API_KEY (in the environment or in .env) for the Jev step.
# It uses your real Claude login and plan usage, and sends only usage numbers and the one sample task
# below to the Jev API. tmux runs on a throwaway socket dir.

Output docs/demo.gif

Require claude
Require tmux
Require jq

Set Shell "bash"
Set Theme "GitHub Dark"
Set FontSize 18
Set Width 1600
Set Height 900
Set Padding 24
Set Framerate 10
Set TypingSpeed 35ms

# Off camera: put this checkout's aware on PATH and isolate tmux from any server you already run. The
# Jev key is exported here (never typed on camera); the fresh tmux server inherits it from this shell.
Hide
Type `export PATH="$PWD:$PATH" TMUX_TMPDIR="$(mktemp -d)" COLORTERM=truecolor PS1='$ '`
Enter
Type `export AWARE_DECIDER_TIMEOUT=5 AWARE_DECIDER_KEY="${TYPESAFE_API_KEY:-$(grep '^TYPESAFE_API_KEY=' .env | cut -d= -f2- | tr -d "\"'")}"; clear`
Enter
Sleep 500ms
Show

Type "AWARE_AUTOCONFIRM=1 AWARE_DECIDER_URL=https://api.typesafe.ai AWARE_DECIDER_MODEL=jev-latest AWARE_DECIDER_MODE=advise aware launch --model sonnet"
Sleep 700ms
Enter
Wait+Screen@40s /Claude Code v/
# Off camera: hide tmux's status bar so Claude Code has the whole screen
Hide
Ctrl+B
Type ":set -g status off"
Enter
Sleep 1s
Show
Sleep 3s

# 1. Claude reads its own usage (get_usage), then asks the decision model (Jev) about a sample task
Type `How much of my plan is left? Then run: aware decide --prompt "fix a typo in the README". Finish with one line: JEV: effort <level>, model <name> (what the decision model said).`
Sleep 500ms
Enter
Wait+Screen@120s /JEV: effort [a-z]+/
Sleep 8s

# 2. Claude applies the suggestion with its own tools, then compacts. The switches run once the turn
#    ends, and the "Switch model?" dialog is confirmed by aware (AWARE_AUTOCONFIRM=1).
Type "Apply that with the aware tools (skip anything that is null), then compact."
Sleep 500ms
Enter
Wait+Screen@180s /Compacted/
Sleep 8s

# Off camera: exit Claude and shut down the demo's tmux server
Hide
Ctrl+C
Sleep 300ms
Ctrl+C
Sleep 2s
Type "tmux kill-server"
Enter
Sleep 500ms
