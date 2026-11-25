#!/usr/bin/env bash
# aware sense: how many Claude Code sessions are active on this plan (updated in the last 10 minutes).
# Plan limits are shared, so several sessions burn them faster than one session's pace suggests.
# Output: LEVEL READING | ADVICE. Warns from AWARE_SESSIONS_WARN (3) sessions.
dir="${AWARE_DIR:-$HOME/.claude/aware}"
n=$(find "$dir" -maxdepth 1 -name '*.json' ! -name 'pane-*' -mmin -10 2>/dev/null | wc -l)
if [ "$n" -ge "${AWARE_SESSIONS_WARN:-3}" ]; then
  echo "warn $n active sessions on this plan | the plan limits are shared, so usage runs faster than this session's pace shows"
else
  echo "ok $n active session$([ "$n" = 1 ] || echo s)"
fi
