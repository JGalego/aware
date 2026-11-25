#!/usr/bin/env bash
# aware sense: free memory and CPU load on this machine.
# Output: LEVEL READING | ADVICE. Tune with AWARE_MACHINE_WARN_MB (2000) and AWARE_MACHINE_CRIT_MB (1000).
[ -r /proc/meminfo ] || { echo "ok n/a"; exit 0; }
free_mb=$(awk '/MemAvailable/ { print int($2 / 1024) }' /proc/meminfo)
load=$(cut -d' ' -f1 /proc/loadavg)
cpus=$(nproc 2>/dev/null || echo 1)
gb=$(awk -v m="$free_mb" 'BEGIN { printf "%.1f", m / 1024 }')
reading="${gb}G RAM free, load $load on $cpus cpus"
busy=$(awk -v l="$load" -v c="$cpus" 'BEGIN { print (l > c) ? 1 : 0 }')
if [ "$free_mb" -lt "${AWARE_MACHINE_CRIT_MB:-1000}" ]; then
  echo "crit $reading | do not start heavy jobs (builds, recordings, full test runs); free memory first or ask the user"
elif [ "$free_mb" -lt "${AWARE_MACHINE_WARN_MB:-2000}" ] || [ "$busy" = 1 ]; then
  echo "warn $reading | defer or cap heavy jobs (builds, recordings, full test runs)"
else
  echo "ok $reading"
fi
