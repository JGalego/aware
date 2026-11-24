# Demo: aware watch beside Claude while a session fills its context. Regenerate from the repo root with:
#   vhs docs/demo.tape
# Needs claude, tmux and jq. It uses your real Claude login and plan usage. tmux runs on a throwaway socket dir.
# Context is capped at 200k tokens (CLAUDE_CODE_DISABLE_1M_CONTEXT) and the limits are lowered (AWARE_CTX_*) so
# the tiers change within three prompts instead of after a long session; the prompts never mention aware, its tools or the tiers.

Output docs/demo.gif

Require claude
Require tmux
Require jq

Set Shell "bash"
Set Theme "GitHub Dark"
Set FontSize 14
Set Width 1200
Set Height 700
Set Padding 16
Set Framerate 12
Set TypingSpeed 15ms

# Off camera: put this checkout's aware on PATH and isolate tmux from any server you already run
Hide
Type `export PATH="$PWD:$PATH" TMUX_TMPDIR="$(mktemp -d)" COLORTERM=truecolor CLAUDE_CODE_DISABLE_1M_CONTEXT=1 PS1='$ '; clear`
Enter
Sleep 500ms
Show

Type "AWARE_CTX_LEAN=26 AWARE_CTX_WARN=36 AWARE_AUTOCONFIRM=1 aware launch --watch --model opus --effort high --allowedTools mcp__aware"
Sleep 600ms
Enter
Wait+Screen@40s /Claude Code v/
# Off camera: hide tmux's status bar so both panes get the whole screen
Hide
Ctrl+B
Type ":set -g status off"
Enter
Sleep 800ms
Show
Sleep 2s

# 1. Real work that fills the context: the meter climbs and the tier leaves "normal"
Type "Read the whole of ./aware yourself, no skimming. One line on how the tier is computed, then a line saying only the sum of 1234 and 3333."
Sleep 400ms
Enter
Wait+Screen@120s / 4567 +│/
Sleep 2s

# 2. More reading: the meter keeps climbing
Type "Now read all of ./test.sh and ./README.md yourself. One line on what the decider tests cover, then a line saying only the sum of 2222 and 3939."
Sleep 400ms
Enter
Wait+Screen@120s / 6161 +│/
Sleep 2s

# 3. A natural break: Claude acts on the hook's advice (effort, model, compact) and the meter drops
Type "Summarize what you found in one sentence."
Sleep 400ms
Enter
Wait+Screen@240s /Compacted/
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
