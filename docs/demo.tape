# Demo recording for the README. Regenerate from the repo root with: vhs docs/demo.tape
# Uses your real Claude Code login and plan usage; tmux runs on a throwaway socket dir.

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
Set Framerate 15
Set TypingSpeed 35ms

# Off camera: put this checkout's aware on PATH and isolate tmux from any server you already run.
Hide
Type `export PATH="$PWD:$PATH" TMUX_TMPDIR="$(mktemp -d)" COLORTERM=truecolor PS1='$ '; clear`
Enter
Sleep 500ms
Show

Type "AWARE_AUTOCONFIRM=1 aware launch --model sonnet"
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

# 1. Claude reads its own usage through the get_usage tool
Type "Before I start a big refactor: how much of my plan can I still use today?"
Sleep 500ms
Enter
Wait+Screen@120s /for \d+s · done/
Sleep 5s

# 2. Claude compacts and steps down a model; both run once the turn ends, and the
#    "Switch model?" dialog is confirmed by aware (AWARE_AUTOCONFIRM=1)
Type "Plan's set. Compact, then switch to haiku for the grunt work."
Sleep 500ms
Enter
Wait+Screen@180s /Compacted/
Wait+Screen@60s /Haiku 5\.5 \| effort/
Sleep 6s

# Off camera: exit Claude and shut down the demo's tmux server
Hide
Ctrl+C
Sleep 300ms
Ctrl+C
Sleep 2s
Type "tmux kill-server"
Enter
Sleep 500ms
