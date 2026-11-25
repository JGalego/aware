#!/usr/bin/env bash
# Drives real interactive Claude Code sessions through the evaluation tasks, one arm at a time, and records what happened.
# It uses your real Claude login and plan usage. Runs are strictly sequential. See eval/README.md.
#
#   eval/run.sh [--arms "placebo tiers full"] [--tasks "01 02 ..."|all] [--reps 1] [--budget-usd 25] [--model opus]
#               [--effort high] [--sim5h 88] [--sim7d 40] [--seed 1] [--timeout 900] [--guard5h 75] [--guard7d 85]
#               [--out DIR] [--dry-run]
#
# --budget-usd is a hard stop on the summed client-side cost (API-equivalent dollars). After the second run the measured
# average is projected over the remaining runs and the harness stops if that would exceed the budget.
set -u
EVAL=$(cd "$(dirname "$0")" && pwd)
AWARE="$EVAL/../aware"
ARMS="placebo tiers full"; TASKS=all; REPS=1; BUDGET=25; MODEL=opus; EFFORT=high; SIM5=88; SIM7=40; SEED=1; TIMEOUT=900
GUARD5=75; GUARD7=85; OUT=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --arms) ARMS=$2; shift 2 ;; --tasks) TASKS=$2; shift 2 ;; --reps) REPS=$2; shift 2 ;; --budget-usd) BUDGET=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;; --effort) EFFORT=$2; shift 2 ;; --sim5h) SIM5=$2; shift 2 ;; --sim7d) SIM7=$2; shift 2 ;;
    --seed) SEED=$2; shift 2 ;; --timeout) TIMEOUT=$2; shift 2 ;; --guard5h) GUARD5=$2; shift 2 ;; --guard7d) GUARD7=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;; --dry-run) DRY=1; shift ;;
    *) sed -n '2,12p' "$0"; exit 1 ;;
  esac
done
for c in jq tmux claude python3 shuf; do command -v "$c" >/dev/null || { echo "needs $c" >&2; exit 1; }; done
for a in $ARMS; do case $a in full|tiers|facts|placebo|off) ;; *) echo "unknown arm $a" >&2; exit 1 ;; esac; done
if [ "$TASKS" = all ]; then TASKS=$(cd "$EVAL/tasks" && ls | cut -d- -f1 | tr '\n' ' '); fi
task_dir() { ls -d "$EVAL/tasks/$1"-* | head -1; }

[ -n "$OUT" ] || OUT="$EVAL/results/$(date +%Y%m%d-%H%M%S)"
WORKROOT="${AWARE_EVAL_WORK:-$HOME/.cache/aware-eval}"   # outside any git repo, so Claude cannot wander into aware's source
SOCK=aware-eval
read -r -a ARM_LIST <<<"$ARMS"; read -r -a TASK_LIST <<<"$TASKS"
TOTAL_RUNS=$(( ${#ARM_LIST[@]} * ${#TASK_LIST[@]} * REPS ))
case "$MODEL" in opus) PER_RUN=1.4 ;; *) PER_RUN=0.7 ;; esac
echo "plan: ${#TASK_LIST[@]} tasks x ${#ARM_LIST[@]} arms x $REPS reps = $TOTAL_RUNS runs; model $MODEL/$EFFORT; simulated 5h=$SIM5% 7d=$SIM7%"
awk -v n="$TOTAL_RUNS" -v p="$PER_RUN" -v b="$BUDGET" 'BEGIN { printf "assumed cost: ~$%.0f ($%.0f to $%.0f) against a budget of $%s\n", n*p, n*p*0.5, n*p*2, b }'
[ $DRY = 1 ] && exit 0

mkdir -p "$OUT/runs" "$WORKROOT"
SETTINGS="$HOME/.claude/settings.json"
cp "$SETTINGS" "$OUT/settings.backup.json" 2>/dev/null || echo '{}' > "$OUT/settings.backup.json"
restore_defaults() {   # put back only the keys /model and /effort touch, in case a switch left a different default
  [ -f "$SETTINGS" ] || return 0
  jq --slurpfile b "$OUT/settings.backup.json" '
    reduce ("model", "modelSettings", "effortLevel") as $k (.; if ($b[0] | has($k)) then .[$k] = $b[0][$k] else del(.[$k]) end)' \
    "$SETTINGS" > "$SETTINGS.aware-eval.tmp" && mv "$SETTINGS.aware-eval.tmp" "$SETTINGS"
}
cleanup() { tmux -L $SOCK kill-server 2>/dev/null; restore_defaults; }
trap cleanup EXIT; trap 'echo "interrupted" >&2; exit 130' INT TERM

# The sessions under test must be independent of whatever launched the harness (a Claude Code session exports its own
# session id, messaging socket and token, effort, ... to children), so scrub every CLAUDE*/VSCODE_* variable. Login is by file.
SCRUB=(); for v in $(compgen -e | grep -E '^(CLAUDE|VSCODE_)'); do SCRUB+=(-u "$v"); done

TOOLS=(Read Edit Write Glob Grep "Bash(python3:*)" "Bash(python:*)" "Bash(ls:*)" "Bash(cat:*)" "Bash(grep:*)" "Bash(head:*)" "Bash(tail:*)"
       "Bash(wc:*)" "Bash(find:*)" "Bash(sed:*)" "Bash(diff:*)" "Bash(mkdir:*)" "Bash(cd:*)" mcp__aware)

screen() { tmux -L $SOCK capture-pane -p -t "$1" 2>/dev/null; }
press_yes() {   # answer permission/trust dialogs with the default (Yes) and count them
  local scr; scr=$(screen "$1")
  if grep -qE '❯ ?1\. Yes' <<<"$scr"; then
    PERMS=$((PERMS + 1)); echo "$(date -Is) $(grep -E 'Do you want|trust' <<<"$scr" | head -1)" >> "$RUNDIR/permissions.log"
    tmux -L $SOCK send-keys -t "$1" Enter; sleep 2; return 0
  fi
  return 1
}
send_prompt() { tmux -L $SOCK send-keys -t "$1" -l "$(tr '\n' ' ' < "$2")"; sleep 0.6; tmux -L $SOCK send-keys -t "$1" Enter; }
wait_stops() {   # wait_stops PANE N: until the Stop hook has fired N times
  local t0=$SECONDS
  while [ "$(wc -l < "$WORK/stops" 2>/dev/null || echo 0)" -lt "$2" ]; do
    [ $((SECONDS - t0)) -gt "$TIMEOUT" ] && return 1
    tmux -L $SOCK has-session -t "$RID" 2>/dev/null || return 2
    press_yes "$1" >/dev/null; sleep 3
  done
}
settle() {   # wait for queued slash commands (/effort, /model, /compact) to land: the screen stops changing
  local prev="" cur same=0 t0=$SECONDS
  sleep 4
  while [ $((SECONDS - t0)) -lt 75 ]; do
    cur=$(screen "$1"); press_yes "$1" >/dev/null && { same=0; continue; }
    if [ "$cur" = "$prev" ] && ! grep -qiE 'esc to interrupt|compacting|switch model\?' <<<"$cur"; then same=$((same + 1)); else same=0; fi
    [ $same -ge 2 ] && return 0
    prev=$cur; sleep 3
  done
}
check_phase() { (cd "$REPO" && PYTHONPATH="$REPO" timeout 120 python3 "$TASK/check$1.py" >"$RUNDIR/check$1.out" 2>&1) && echo 1 || echo 0; }
newest_json() { ls -t "$1"/*.json 2>/dev/null | grep -v '/pane-' | head -1; }

# real plan usage guard: pause before a window fills, abort for the weekly one
LAST_REAL="$(newest_json "$HOME/.claude/aware")"
guard() {
  [ -n "$LAST_REAL" ] && [ -f "$LAST_REAL" ] || return 0
  local h5 h5r d7 d7r now; now=$(date +%s)
  read -r h5 h5r d7 d7r < <(jq -r '[(.rate_limits.five_hour.used_percentage // 0), (.rate_limits.five_hour.resets_at // 0), (.rate_limits.seven_day.used_percentage // 0), (.rate_limits.seven_day.resets_at // 0)] | @tsv' "$LAST_REAL")
  if [ "${d7%.*}" -ge "$GUARD7" ] && [ "$d7r" -gt "$now" ]; then echo "real 7d usage is ${d7}% (guard $GUARD7%): stopping" >&2; exit 3; fi
  if [ "${h5%.*}" -ge "$GUARD5" ] && [ "$h5r" -gt "$now" ]; then
    echo "real 5h usage is ${h5}% (guard $GUARD5%): waiting $(( (h5r - now + 60) / 60 )) min for the window to reset" >&2
    sleep $((h5r - now + 60))
  fi
}

SPENT=0; DONE=0
run_one() {   # run_one TASK ARM REP
  local tn=$1 arm=$2 rep=$3
  TASK=$(task_dir "$tn"); RID="$(basename "$TASK")-$arm-r$rep"
  RUNDIR="$OUT/runs/$RID"; WORK="$WORKROOT/$RID"; REPO="$WORK/repo"; PERMS=0
  rm -rf "$WORK"; mkdir -p "$RUNDIR/aware" "$REPO/.claude"; cp -r "$TASK/repo/." "$REPO/"
  jq -n --arg cmd "date +%s >> '$WORK/stops'" '{hooks: {Stop: [{hooks: [{type: "command", command: $cmd}]}]}}' > "$REPO/.claude/settings.json"
  : > "$WORK/stops"
  local launch; launch=$(printf '%q ' env ${SCRUB[@]+"${SCRUB[@]}"} -u AWARE_DECIDER_URL -u AWARE_DECIDER_KEY -u AWARE_GATE "AWARE_DIR=$RUNDIR/aware" "AWARE_ARM=$arm" \
    "AWARE_SIM_5H=$SIM5" "AWARE_SIM_7D=$SIM7" AWARE_AUTOCONFIRM=1 AWARE_KEEP_DEFAULT=1 "$AWARE" launch --model "$MODEL" --effort "$EFFORT" --allowedTools "${TOOLS[@]}")
  local t0=$SECONDS status=ok c1=0 c2=0
  tmux -L $SOCK kill-session -t "$RID" 2>/dev/null
  tmux -L $SOCK new-session -d -s "$RID" -x 200 -y 50 -c "$REPO" "$launch" || { echo "tmux failed" >&2; return 1; }
  local pane; pane=$(tmux -L $SOCK list-panes -t "$RID" -F '#{pane_id}')
  local i; for i in $(seq 1 60); do   # ready when the banner shows (answering the trust dialog on the way)
    press_yes "$pane" >/dev/null
    grep -q 'Claude Code v' <<<"$(screen "$pane")" && break; sleep 2
  done
  grep -q 'Claude Code v' <<<"$(screen "$pane")" || status=no_start
  sleep 3
  if [ $status = ok ]; then
    send_prompt "$pane" "$TASK/prompt1.txt"
    wait_stops "$pane" 1; case $? in 1) status=timeout ;; 2) status=died ;; esac
    settle "$pane"; c1=$(check_phase 1)
  fi
  if [ $status = ok ]; then
    send_prompt "$pane" "$TASK/prompt2.txt"
    wait_stops "$pane" 2; case $? in 1) status=timeout ;; 2) status=died ;; esac
    settle "$pane"; c2=$(check_phase 2)
  fi
  screen "$pane" > "$RUNDIR/final-screen.txt"
  tmux -L $SOCK kill-session -t "$RID" 2>/dev/null; sleep 1
  local wall=$((SECONDS - t0)) json sid tr="{}" cost=0
  json=$(newest_json "$RUNDIR/aware")
  if [ -n "$json" ]; then
    sid=$(basename "$json" .json); LAST_REAL=$json
    cost=$(jq -r '.cost.total_cost_usd // 0' "$json")
    local f; f=$(ls "$HOME"/.claude/projects/*/"$sid".jsonl 2>/dev/null | head -1)
    if [ -n "$f" ]; then
      cp "$f" "$RUNDIR/transcript.jsonl"
      tr=$(jq -s '
        [.[] | select(.type == "assistant")] as $a
        | ($a | group_by(.message.id) | map(last)) as $m
        | { assistant_msgs: ($m | length),
            tools: ([$a[] | .message.content[]? | select(.type == "tool_use")] | unique_by(.id) | group_by(.name) | map({key: .[0].name, value: length}) | from_entries),
            out_tokens: ([$m[] | .message.usage.output_tokens // 0] | add // 0),
            in_tokens: ([$m[] | .message.usage.input_tokens // 0] | add // 0),
            cache_read: ([$m[] | .message.usage.cache_read_input_tokens // 0] | add // 0),
            cache_create: ([$m[] | .message.usage.cache_creation_input_tokens // 0] | add // 0)}' "$f" 2>/dev/null || echo '{}')
    fi
  fi
  local moves; moves=$(grep -c . "$RUNDIR/aware/switches.log" 2>/dev/null || echo 0)
  jq -cn --arg id "$RID" --arg task "$(basename "$TASK")" --arg arm "$arm" --argjson rep "$rep" --arg status "$status" \
     --argjson c1 "$c1" --argjson c2 "$c2" --argjson cost "$cost" --argjson wall "$wall" --argjson perms "$PERMS" --argjson moves "$moves" \
     --argjson tr "$tr" --slurpfile st "${json:-/dev/null}" \
     --slurpfile inj <(cat "$RUNDIR/aware/injections.log" 2>/dev/null) \
     '{id: $id, task: $task, arm: $arm, rep: $rep, status: $status, check1: $c1, check2: $c2, cost: $cost, wall_s: $wall, permission_prompts: $perms,
       switch_commands: $moves, transcript: $tr,
       final: ($st[0] // {} | {model: (.model.id // null), effort: (.effort.level // null), context_tokens: .context_window.total_input_tokens,
                              cache_hits: .prompt_cache.hit_ratio, cache_misses: .prompt_cache.misses,
                              real_5h: .rate_limits.five_hour.used_percentage, real_7d: .rate_limits.seven_day.used_percentage}),
       injections: ($inj | length), injected_chars: ([$inj[] | .chars] | add // 0)}' >> "$OUT/runs.jsonl"
  SPENT=$(awk -v a="$SPENT" -v b="$cost" 'BEGIN { printf "%.4f", a + b }'); DONE=$((DONE + 1))
  printf '%-28s %-8s check %s/%s  $%.2f  %4ss  perms=%s moves=%s  [spent $%s of $%s]\n' "$RID" "$status" "$c1" "$c2" "$cost" "$wall" "$PERMS" "$moves" "$SPENT" "$BUDGET"
  rm -rf "$WORK"
}

for rep in $(seq 1 "$REPS"); do
  for tn in "${TASK_LIST[@]}"; do
    # arms in a random order within each block, so drift in time of day or load is spread across arms
    for arm in $(printf '%s\n' "${ARM_LIST[@]}" | shuf --random-source=<(yes "$SEED-$rep-$tn")); do
      if awk -v s="$SPENT" -v b="$BUDGET" 'BEGIN { exit !(s >= b) }'; then echo "budget reached: stopping" >&2; exit 0; fi
      if [ "$DONE" -ge 2 ] && awk -v s="$SPENT" -v d="$DONE" -v n="$TOTAL_RUNS" -v b="$BUDGET" 'BEGIN { exit !(s / d * n > b) }'; then
        awk -v s="$SPENT" -v d="$DONE" -v n="$TOTAL_RUNS" -v b="$BUDGET" 'BEGIN { printf "measured $%.2f per run projects to $%.0f for %d runs, over the $%s budget: stopping (raise --budget-usd or run less)\n", s/d, s/d*n, n, b }' >&2
        exit 0
      fi
      guard
      run_one "$tn" "$arm" "$rep"
    done
  done
done
echo "done: $DONE runs, \$$SPENT. Results in $OUT (analyze with: python3 $EVAL/analyze.py $OUT/runs.jsonl)"
