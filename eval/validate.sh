#!/usr/bin/env bash
# Checks the evaluation tasks themselves, without Claude: every hidden check must fail on the buggy repo, phase 1's check must
# pass (and phase 2's still fail) with the phase 1 reference solution, and both must pass with the phase 2 reference solution.
# Usage: eval/validate.sh [TASK...]   (default: all)
set -u
cd "$(dirname "$0")/tasks" || exit 1
tasks=("$@"); [ ${#tasks[@]} -gt 0 ] || tasks=(*/)
bad=0
for t in "${tasks[@]}"; do
  t=${t%/}; w=$(mktemp -d)
  run() { (cd "$w" && PYTHONPATH="$w" python3 "$OLDPWD/$t/$1" >/dev/null 2>&1); }
  cp -r "$t/repo/." "$w/"
  if run check1.py; then echo "FAIL $t: check1 passes on the buggy repo"; bad=1; fi
  if run check2.py; then echo "FAIL $t: check2 passes on the buggy repo"; bad=1; fi
  cp -r "$t/ref1/." "$w/"
  run check1.py || { echo "FAIL $t: check1 fails with ref1"; bad=1; }
  if run check2.py; then echo "FAIL $t: check2 passes with ref1 only"; bad=1; fi
  cp -r "$t/ref2/." "$w/"
  run check1.py || { echo "FAIL $t: check1 fails with ref2"; bad=1; }
  run check2.py || { echo "FAIL $t: check2 fails with ref2"; bad=1; }
  rm -rf "$w"; echo "ok   $t"
done
exit $bad
