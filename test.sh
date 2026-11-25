#!/usr/bin/env bash
# Self-contained tests: fake HOME, throwaway tmux server. Touches nothing real.
set -u
ROOT=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'tmux -L awaretest kill-server 2>/dev/null; [ -n "${STUB:-}" ] && kill $STUB 2>/dev/null; rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME/.claude" "$HOME/.local/bin"
echo '{"model":"sonnet","tui":"fullscreen"}' > "$HOME/.claude/settings.json"
A="$ROOT/aware"; pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok   $1"; }
bad() { fail=$((fail+1)); echo "  FAIL $1"; }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }
now=$(date +%s); export AWARE_NOW=$now   # pin aware's clock so pace/projection math is deterministic
json() { echo "{\"session_id\":\"$1\",\"model\":{\"display_name\":\"Sonnet 5.5\"},\"effort\":{\"level\":\"xhigh\"},\"cost\":{\"total_cost_usd\":3.2},\"context_window\":{\"used_percentage\":38},\"rate_limits\":{\"five_hour\":{\"used_percentage\":$2,\"resets_at\":$((now+3600))},\"seven_day\":{\"used_percentage\":$3,\"resets_at\":$((now+200000))}}}"; }

echo "statusline / hook / show"
out=$(json s1 42 61 | "$A" statusline)
check "statusline prints one line" '[[ "$out" == "[usage] 5h 42%"* && $(echo "$out" | wc -l) -eq 1 ]]'
check "hook prints status" '[[ "$(echo "{\"session_id\":\"s1\"}" | "$A" hook)" == *"7d 61%"* ]]'
json s1 42 86 | "$A" statusline >/dev/null
check "advisory fires at 86%" 'echo "{\"session_id\":\"s1\"}" | "$A" hook | grep -q "tier=conserve"'
check "quiet mode silent when low" '[[ -z "$(json s2 10 10 | "$A" statusline >/dev/null; echo "{\"session_id\":\"s2\"}" | AWARE_QUIET=1 "$A" hook)" ]]'
check "hook silent for unknown session" '[[ -z "$(echo "{\"session_id\":\"nope\"}" | "$A" hook)" ]]'
json s3 5 5 | TMUX_PANE=%77 "$A" statusline >/dev/null
check "pane file written" '[ -f "$HOME/.claude/aware/pane-77.json" ]'
check "show prefers this pane" '[[ "$(TMUX_PANE=%77 "$A" show)" == *"5h 5%"* ]]'

echo "tiers / pace / cache"
# fx <sid> <5h%> <7d%> <ctx%> <5h resets in s> <7d resets in s> <cache warm: true|false|null>
fx() { jq -cn --arg s "$1" --argjson h "$2" --argjson d "$3" --argjson c "$4" --argjson hr "$5" --argjson dr "$6" --argjson w "$7" --argjson now "$now" \
  '{session_id:$s, model:{id:"claude-opus-5-5",display_name:"Opus 5.5"}, effort:{level:"high"}, cost:{total_cost_usd:1.5},
    context_window:{used_percentage:$c,total_input_tokens:120000},
    prompt_cache:{warm:$w,expires_at:($now+600),recache_tokens_if_cold:118000},
    rate_limits:{five_hour:{used_percentage:$h,resets_at:($now+$hr)},seven_day:{used_percentage:$d,resets_at:($now+$dr)}}}'; }
# view <fixture args...>: feed the statusline, then print what `aware show` says for that session
view() { fx "$@" | "$A" statusline >/dev/null; env -u TMUX_PANE "$A" show; }
v=$(view n1 20 10 10 3600 500000 true)
check "normal: no advice line"                 '[ "$(echo "$v" | wc -l)" = 1 ]'
check "normal: pace shown with one decimal"    '[[ "$v" == *"5h 20% (resets "*", pace 0.3x)"* ]]'
check "normal: cache state shown"              '[[ "$v" == *"| cache warm |"* ]]'
check "lean by 7d usage"                       '[[ "$(view n2 20 55 10 3600 100000 true)" == *"tier=lean (7d 55%)"* ]]'
v=$(view n3 40 10 10 14400 500000 true)   # 40% used after 1h of 5h -> pace 2.0x
check "lean by pace alone"                     '[[ "$v" == *"tier=lean (5h pace 2.0x, out ~"* ]]'
check "projection shown when pace > 1"         '[[ "$v" == *"pace 2.0x, out ~"*")"* ]]'
check "lean advice: delegate by task"          '[[ "$v" == *"cheaper-model subagents (haiku for search, reads, summaries; sonnet when judgment is needed)"* ]]'
check "no pace when window barely started"     '[[ "$(view n4 40 10 10 17500 500000 true | cut -d"|" -f1)" != *pace* ]]'
check "no pace when usage tiny"                '[[ "$(view n5 3 10 10 3600 500000 true | cut -d"|" -f1)" != *pace* ]]'
v=$(view n6 85 10 20 3600 500000 true)
check "conserve at 85%"                        '[[ "$v" == *"tier=conserve (5h 85%"* ]]'
check "conserve: warm cache -> switch cost"    '[[ "$v" == *"re-reads ~118k tokens"* ]]'
check "conserve: fallback commands for no-MCP" '[[ "$v" == *"/effort medium"* ]]'
check "conserve: cold cache -> switch is free" '[[ "$(view n7 85 10 20 3600 500000 false)" == *"| cache cold |"*"costs nothing extra"* ]]'
v=$(view n8 30 10 75 3600 500000 true)
check "conserve by context"                    '[[ "$v" == *"tier=conserve (ctx 75%)"* ]]'
check "high context -> advise compact"         '[[ "$v" == *"compact at the next natural break"* ]]'
check "default limits: no custom-limits note"  '[[ "$v" != *"custom limits"* ]]'
check "custom limits are announced"            '[[ "$(AWARE_CTX_WARN=3 view n8b 30 10 4 3600 500000 true)" == *"tier=conserve (ctx 4%)"*"custom limits (plan 50/80/95%, context 50/3%)"* ]]'
check "conserve names the effort call"         '[[ "$v" == *"call set_effort medium now (currently high"* ]]'
check "conserve names the model step (opus)"   '[[ "$(view n6 85 10 20 3600 500000 true)" == *"call set_model sonnet (a switch re-reads ~118k"* ]]'
v=$(fx n14 97 10 10 600 500000 true | "$A" statusline >/dev/null; env -u TMUX_PANE "$A" show)
check "reset soon: waiting beats downgrading"  '[[ "$v" == *"the 5h limit (97%) resets in 10m, so waiting beats downgrading"* && "$v" != *set_effort* && "$v" != *set_model* ]]'
check "reset soon: critical still wraps up"    '[[ "$v" == *"tier=critical"*"ask the user before starting anything new"* ]]'
check "reset soon: state rules hold back"      '[[ "$("$A" show --json | jq -c "[.rules.effort, .rules.model]")" == "[null,null]" ]]'
check "reset far: normal downgrade advice"     '[[ "$(AWARE_RESET_SOON=5 env -u TMUX_PANE "$A" show)" == *"set_effort low"* ]]'
v=$(fx n15 97 85 10 600 500000 true | "$A" statusline >/dev/null; env -u TMUX_PANE "$A" show)
check "reset soon but 7d still high: downgrade" '[[ "$v" == *"set_effort low"* && "$v" != *"waiting beats"* ]]'
check "lean leaves effort high alone"          '[[ "$(view n3 40 10 10 14400 500000 true)" != *set_effort* ]]'
check "lean steps xhigh down to high"          '[[ "$(fx n12 60 10 10 3600 500000 true | jq -c ".effort.level=\"xhigh\"" | "$A" statusline >/dev/null; env -u TMUX_PANE "$A" show)" == *"call set_effort high now"* ]]'
check "critical on sonnet -> haiku"            '[[ "$(fx n13 97 10 10 3600 500000 true | jq -c ".model.id=\"claude-sonnet-5-5\"" | "$A" statusline >/dev/null; env -u TMUX_PANE "$A" show)" == *"set_effort low"*"set_model haiku"* ]]'

echo "effort and the cache"
# em <sid> <model id> [ENV=val ...]: conserve-tier advice for that model (cache warm unless WARM=false is passed first)
em() { local sid=$1 mid=$2; shift 2
  fx "$sid" 85 10 10 3600 500000 true | jq -c ".model.id=\"$mid\"" | "$A" statusline >/dev/null
  env -u TMUX_PANE "$@" "$A" show; }
KEEPS='call set_effort medium now (currently high; effort changes keep the cache)'
DROPS='at the next natural break call set_effort medium (currently high; on this setup an effort change drops the prompt cache and re-reads ~118k tokens uncached)'
for m in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5 claude-fable-5-2 claude-fable-5-1 claude-opus-5-6; do
  check "$m: effort change keeps the cache" '[[ "$(em ec1 $m)" == *"$KEEPS"* ]]'
done
for m in claude-opus-4-8 claude-sonnet-4-5-20250929 claude-fable-5-0 claude-sonnet-5-4 claude-opus-5 mystery-model; do
  check "$m: effort change drops it, so wait for a break" '[[ "$(em ec2 $m)" == *"$DROPS"* && "$(em ec2 $m)" != *"set_effort medium now"* ]]'
done
check "Bedrock: effort change drops the cache"    '[[ "$(em ec3 claude-opus-5-5 CLAUDE_CODE_USE_BEDROCK=1)" == *"$DROPS"* ]]'
check "Vertex: effort change drops the cache"     '[[ "$(em ec3 claude-opus-5-5 CLAUDE_CODE_USE_VERTEX=1)" == *"$DROPS"* ]]'
check "gateway URL: effort change drops the cache" '[[ "$(em ec3 claude-opus-5-5 ANTHROPIC_BASE_URL=https://gw.example.com/v1)" == *"$DROPS"* ]]'
check "api.anthropic.com URL: still keeps"        '[[ "$(em ec3 claude-opus-5-5 ANTHROPIC_BASE_URL=https://api.anthropic.com/)" == *"$KEEPS"* ]]'
check "AWARE_EFFORT_CACHE=yes overrides"          '[[ "$(em ec4 claude-opus-4-8 AWARE_EFFORT_CACHE=yes)" == *"$KEEPS"* ]]'
check "AWARE_EFFORT_CACHE=no overrides"           '[[ "$(em ec4 claude-opus-5-5 AWARE_EFFORT_CACHE=no)" == *"$DROPS"* ]]'
fx ec5 85 10 10 3600 500000 false | jq -c '.model.id="claude-opus-4-8"' | "$A" statusline >/dev/null
check "cold cache: the wait advice says it is free" '[[ "$(env -u TMUX_PANE "$A" show)" == *"set_effort medium (currently high; on this setup an effort change drops the prompt cache and costs nothing extra now: the cache is cold)"* ]]'
check "state: effkeeps true on a 5.5 model"       '[ "$(em ec6 claude-opus-5-5 >/dev/null; env -u TMUX_PANE "$A" show --json | jq .effkeeps)" = true ]'
check "state: effkeeps false on an older model"   '[ "$(em ec6 claude-opus-4-8 >/dev/null; env -u TMUX_PANE "$A" show --json | jq .effkeeps)" = false ]'
check "state: rules still target medium either way" '[ "$(env -u TMUX_PANE "$A" show --json | jq -r .rules.effort)" = medium ]'
check "nothing cached yet -> switch is free"   '[[ "$(fx n14 85 10 10 3600 500000 true | jq -c ".prompt_cache.recache_tokens_if_cold=0" | "$A" statusline >/dev/null; env -u TMUX_PANE "$A" show)" == *"nothing is cached yet"* ]]'
# AWARE_MODELS (cheapest to most expensive) drives both the step-down chain and the delegation hint
vm() { fx "$1" "$2" 10 "$3" 3600 500000 true | jq -c ".model.id=\"$4\"" | "$A" statusline >/dev/null; AWARE_MODELS="$5" env -u TMUX_PANE "$A" show; }
check "custom list: two models, no mid tier"   '[[ "$(vm m1 55 10 claude-opus-5-5 "sonnet opus" | tail -1)" != *"when judgment"* && "$(vm m1 55 10 claude-opus-5-5 "sonnet opus" | tail -1)" == *"(sonnet for search"* ]]'
check "custom list: conserve steps top down"   '[[ "$(vm m2 85 10 claude-opus-5-5 "sonnet opus")" == *"call set_model sonnet"* ]]'
check "custom list: conserve leaves middle"    '[[ "$(vm m3 85 10 claude-sonnet-5-5 "haiku sonnet opus")" != *set_model* ]]'
check "custom list: critical from middle"      '[[ "$(vm m4 97 10 claude-sonnet-5-5 "haiku sonnet opus")" == *"call set_model haiku"* ]]'
check "custom list: cheapest never steps down" '[[ "$(vm m5 97 10 claude-haiku-5-5 "haiku sonnet opus")" != *set_model* ]]'
check "custom list: unlisted model left alone" '[[ "$(vm m6 97 10 claude-fable-5-2 "haiku sonnet opus")" != *set_model* ]]'
check "critical at 97%"                        '[[ "$(view n9 97 10 20 600 500000 true)" == *"tier=critical"*"ask the user"* ]]'
check "thresholds configurable (AWARE_WARN)"   '[[ "$(fx n10 35 10 10 3600 500000 true | "$A" statusline >/dev/null; AWARE_WARN=30 env -u TMUX_PANE "$A" show)" == *"tier=conserve"* ]]'
check "no rate limits (API key): still renders" '[[ "$(export AWARE_DIR=$T/apikey; echo "{\"session_id\":\"n11\",\"model\":{\"id\":\"x\"}}" | "$A" statusline)" == "[usage] 5h ? | 7d ? | ctx ? | x | effort n/a | \$0" ]]'

echo "hook: speaks only on change"
hk() { echo "{\"session_id\":\"$1\"}" | env "${@:2}" "$A" hook; }
# startup: Claude Code runs the statusline before the first response, without usage numbers
start='{"session_id":"d0","model":{"id":"claude-opus-5-5"},"effort":{"level":"high"}}'
check "silent before anything is measured"     '[ -z "$(export AWARE_DIR=$T/empty; echo "$start" | "$A" statusline >/dev/null; hk d0)" ]'
check "unknown -> first numbers speaks"        '[[ "$(export AWARE_DIR=$T/empty; fx d0 3 4 2 3600 500000 true | "$A" statusline >/dev/null; hk d0)" == *"5h 3%"* ]]'
fx other 44 22 30 3600 500000 true | "$A" statusline >/dev/null; echo "$start" | jq -c '.session_id="d00"' | "$A" statusline >/dev/null
check "first prompt borrows account-wide limits" '[[ "$(hk d00)" == "[usage] 5h 44%"*"| ctx ? |"* ]]'
fx stale 66 22 30 -60 500000 true | "$A" statusline >/dev/null; echo "$start" | jq -c '.session_id="d01"' | "$A" statusline >/dev/null
check "...but skips sessions whose window reset" '[[ "$(hk d01)" == "[usage] 5h 44%"* ]]'
fx d1 20 10 10 3600 500000 true | "$A" statusline >/dev/null
check "first prompt gets the status"           '[[ "$(hk d1)" == "[usage]"* ]]'
check "same numbers -> silent"                 '[ -z "$(hk d1)" ]'
fx d1 24 10 10 3600 500000 true | "$A" statusline >/dev/null
check "move within a 10% band -> silent"       '[ -z "$(hk d1)" ]'
fx d1 31 10 10 3600 500000 true | "$A" statusline >/dev/null
check "crossing a 10% band -> speaks"          '[[ "$(hk d1)" == *"5h 31%"* ]]'
fx d1 31 10 10 3600 500000 true | jq -c '.effort.level="low"' | "$A" statusline >/dev/null
check "effort change -> speaks"                '[[ "$(hk d1)" == *"effort low"* ]]'
check "AWARE_EVERY_TURN=1 -> always speaks"    '[ -n "$(hk d1 AWARE_EVERY_TURN=1)" ]'
fx d2 97 10 10 600 500000 true | "$A" statusline >/dev/null; hk d2 >/dev/null
check "critical repeats every prompt"          '[[ "$(hk d2)" == *"tier=critical"* ]]'
fx d3 85 10 10 3600 500000 true | "$A" statusline >/dev/null
check "quiet mode: advice only"                '[[ "$(hk d3 AWARE_QUIET=1)" == "[aware] tier=conserve"* ]]'

echo "decider (pluggable decision model)"
cat > "$T/stub.py" <<'PY'
import http.server, os
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        open(os.environ['STUB_REQ'], 'wb').write(body)
        open(os.environ['STUB_REQ'] + '.hdr', 'w').write(str(self.headers))
        data = open(os.environ['STUB_RESP'], 'rb').read()
        self.send_response(200 if self.path == '/v1/systemone' else 404)
        self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass
s = http.server.HTTPServer(('127.0.0.1', 0), H); print(s.server_address[1], flush=True); s.serve_forever()
PY
export STUB_REQ="$T/req.json" STUB_RESP="$T/resp.json"
python3 -I "$T/stub.py" > "$T/port" & STUB=$!
for _ in $(seq 1 50); do [ -s "$T/port" ] && break; sleep 0.1; done
URL="http://127.0.0.1:$(cat "$T/port")"
# ans <effort> <ec> <model> <mc> <compact>: canned decider answer
ans() { printf '{"answers":{"effort":{"choice":"%s","confidence":%s},"model":{"choice":"%s","confidence":%s},"compact":{"noul":%s}}}' "$@" > "$STUB_RESP"; }
# dstate <sid> <5h%> <ctx%> <effort> <model>: a session on the "latest" slot, then decide
dstate() { fx "$1" "$2" 10 "$3" 3600 500000 true | jq -c ".effort.level=\"$4\" | .model.id=\"$5\"" | "$A" statusline >/dev/null; }
dec() { env -u TMUX_PANE AWARE_DECIDER_URL="$URL" "$@" "$A" decide; }

dstate q1 85 20 high claude-opus-5-5
check "no decider: rules decide (conserve -> medium + sonnet)" '[ "$(env -u TMUX_PANE "$A" decide | jq -c "[.source,.effort,.model]")" = "[\"rules\",\"medium\",\"sonnet\"]" ]'
ans low 0.9 haiku 0.9 0.2
d=$(dec env)
check "decider answers are used when confident"  '[ "$(echo "$d" | jq -c "[.source,.effort,.model,.compact]")" = "[\"decider\",\"low\",\"haiku\",false]" ]'
check "request: three typed questions"           '[ "$(jq -c "[.questions.effort.type,.questions.model.type,.questions.compact.type]" "$STUB_REQ")" = "[\"choice\",\"choice\",\"noul\"]" ]'
check "request: options come from AWARE_EFFORTS/MODELS" '[ "$(jq -c "[(.questions.effort.criteria|keys),(.questions.model.criteria|keys)]" "$STUB_REQ")" = "[[\"high\",\"low\",\"max\",\"medium\",\"xhigh\"],[\"haiku\",\"opus\",\"sonnet\"]]" ]'
check "request: state has the numbers"           'jq -e ".state|test(\"5h 85%\") and test(\"model claude-opus-5-5\") and test(\"effort high\") and test(\"cache warm\")" "$STUB_REQ" >/dev/null'
check "request: no prompt text by default"       '! grep -q "secret refactor" "$STUB_REQ"'
ans high 0.4 opus 0.4 0.5
check "low confidence falls back to the rules"   '[ "$(dec env | jq -c "[.source,.effort,.model]")" = "[\"decider\",\"medium\",\"sonnet\"]" ]'
ans medium 0.9 opus 0.9 0.5
check "answer equal to current -> no change"     '[ "$(dec env | jq -c "[.effort,.model]")" = "[\"medium\",null]" ]'
dstate q2 85 20 low claude-sonnet-5-5
ans high 0.7 opus 0.7 0.5
check "step up needs UP_CONF (0.7 < 0.85)"       '[ "$(dec env | jq -c "[.effort,.model]")" = "[null,null]" ]'
check "raw choice is kept when a step up is held back" '[ "$(dec env | jq -c ".said")" = "{\"effort\":\"high\",\"model\":\"opus\"}" ]'
ans high 0.9 opus 0.9 0.5
check "step up allowed at high confidence"       '[ "$(dec env | jq -c "[.effort,.model]")" = "[\"high\",\"opus\"]" ]'
dstate q2n 20 10 low claude-sonnet-5-5
ans high 0.7 opus 0.7 0.5
check "normal tier: step up needs only MIN_CONF"   '[ "$(dec env | jq -c "[.tier,.effort,.model]")" = "[\"normal\",\"high\",\"opus\"]" ]'
ans high 0.5 opus 0.5 0.5
check "normal tier: below MIN_CONF still held back" '[ "$(dec env | jq -c "[.effort,.model]")" = "[null,null]" ]'
dstate q2 85 20 low claude-sonnet-5-5
ans high 0.9 opus 0.9 0.5
check "thresholds configurable (UP_CONF)"        '[ "$(dec env AWARE_DECIDER_UP_CONF=0.95 | jq -c "[.effort,.model]")" = "[null,null]" ]'
ans turbo 0.99 gpt 0.99 0.5
dstate q2b 85 20 high claude-opus-5-5
check "unknown option names are ignored (rules)"  '[ "$(dec env | jq -c "[.effort,.model]")" = "[\"medium\",\"sonnet\"]" ]'
printf '{"answers":{"effort":{"choice":"low","probabilities":{"low":0.8,"high":0.2}},"model":{"choice":"haiku","confidence":0.9},"compact":0.9}}' > "$STUB_RESP"
dstate q3 85 20 high claude-opus-5-5
check "confidence from probabilities; plain-number noul" '[ "$(dec env | jq -c "[.effort,.compact]")" = "[\"low\",true]" ]'
check "unreachable decider -> rules + error"     '[ "$(env -u TMUX_PANE AWARE_DECIDER_URL=http://127.0.0.1:9 "$A" decide | jq -c "[.source,(.error|test(\"unreachable\"))]")" = "[\"rules\",true]" ]'
# hosted deciders: bearer key + model name
ans low 0.9 haiku 0.9 0.2; dstate q4 85 20 high claude-opus-5-5
dec env AWARE_DECIDER_KEY=sk-test-123 AWARE_DECIDER_MODEL=jev-latest >/dev/null
check "key sent as Authorization: Bearer"         'grep -qi "^authorization: Bearer sk-test-123" "$STUB_REQ.hdr"'
check "model name sent when set"                  '[ "$(jq -r .model "$STUB_REQ")" = jev-latest ]'
dec env >/dev/null
check "no key / no model: neither is sent"        '! grep -qi "^authorization" "$STUB_REQ.hdr" && [ "$(jq "has(\"model\")" "$STUB_REQ")" = false ]'
check "key never appears in the decision output"  '! dec env AWARE_DECIDER_KEY=sk-test-123 | grep -q sk-test-123'
dec env >/dev/null; env -u TMUX_PANE AWARE_DECIDER_URL="$URL" "$A" decide --prompt "fix a typo in the README" >/dev/null
check "decide --prompt sends the task text"       'jq -e ".state|test(\"Latest user request: fix a typo in the README\")" "$STUB_REQ" >/dev/null'
env -u TMUX_PANE AWARE_DECIDER_URL="$URL" "$A" decide --prompt "$(printf 'x%.0s' $(seq 1 500))" >/dev/null
check "decide --prompt is cut to 300 characters"  '[ "$(jq -r ".state" "$STUB_REQ" | grep -o "x*$" | head -1 | wc -c)" -le 302 ]'
check "key file removed after the call"           '[ -z "$(ls -A "$HOME/.claude/aware" | grep "^.hdr")" ]'
echo 'not json' > "$STUB_RESP"
check "garbled answer -> rules + error"          '[ "$(dec env | jq -c "[.source,.error]")" = "[\"rules\",\"decider answer not understood\"]" ]'

# hook: dry-run logs, advise advises, the prompt is only sent on request
ans low 0.9 haiku 0.9 0.9
hkd() { echo "{\"session_id\":\"$1\",\"prompt\":\"my secret refactor plan\"}" | env "${@:2}" "$A" hook; }
rm -f "$HOME/.claude/aware/decisions.log"
dstate hq 85 20 high claude-opus-5-5
base=$(hkd hq)
dstate hq2 85 20 high claude-opus-5-5
dry=$(hkd hq2 AWARE_DECIDER_URL="$URL")
check "dry mode: hook output unchanged"          '[ "$dry" = "$base" ]'
check "dry mode: decision logged"                '[ "$(jq -c "[.sid,.mode,.source,.effort,.model,.compact]" "$HOME/.claude/aware/decisions.log")" = "[\"hq2\",\"dry\",\"decider\",\"low\",\"haiku\",true]" ]'
dstate hq3 85 20 high claude-opus-5-5
adv=$(hkd hq3 AWARE_DECIDER_URL="$URL" AWARE_DECIDER_MODE=advise)
check "advise mode: decider's steps replace the rules'" '[[ "$adv" == *"(decider): call set_effort low now; at the next natural break call set_model haiku; call compact at the next natural break; delegate"* && "$adv" != *"set_effort medium"* ]]'
check "advise mode: usage line kept"             '[[ "$adv" == "[usage]"* ]]'
dstate hq4 85 20 high claude-opus-5-5
hkd hq4 AWARE_DECIDER_URL="$URL" >/dev/null
check "prompt not sent by default"               '! grep -q "secret refactor" "$STUB_REQ"'
dstate hq5 85 20 high claude-opus-5-5
hkd hq5 AWARE_DECIDER_URL="$URL" AWARE_DECIDER_PROMPT=1 >/dev/null
check "AWARE_DECIDER_PROMPT=1 sends it"          'jq -e ".state|test(\"Latest user request: my secret refactor plan\")" "$STUB_REQ" >/dev/null'
dstate hq6 85 20 high claude-opus-5-5
check "decider down: hook still gives the rules advice" '[[ "$(hkd hq6 AWARE_DECIDER_URL=http://127.0.0.1:9 AWARE_DECIDER_MODE=advise)" == *"tier=conserve"*"set_effort medium"* ]]'
dstate hq7 20 10 high claude-opus-5-5
ans high 0.99 opus 0.99 0.1
check "normal tier + nothing to change: silent line" '[[ "$(hkd hq7 AWARE_DECIDER_URL="$URL" AWARE_DECIDER_MODE=advise | wc -l)" = 1 ]]'
ans low 0.9 haiku 0.9 0.2
dstate hq8 85 20 high claude-opus-5-5
check "advise mode: decider effort waits for a break where it drops the cache" '[[ "$(hkd hq8 AWARE_DECIDER_URL="$URL" AWARE_DECIDER_MODE=advise CLAUDE_CODE_USE_BEDROCK=1)" == *"(decider): at the next natural break call set_effort low (on this setup it drops the prompt cache)"* ]]'

echo "switch: validation"
for v in "haiku; rm -rf ~" $'haiku\nrm' "fable" "" "../x" '$(id)'; do
  TMUX_PANE=%1 "$A" switch model "$v" >/dev/null 2>&1; rc=$?
  check "refuses model '${v//$'\n'/\\n}' (rc=$rc)" '[ $rc -eq 2 ]'
done
TMUX_PANE=%1 "$A" switch effort "ultra" >/dev/null 2>&1; check "refuses effort ultra" '[ $? -eq 2 ]'
env -u TMUX_PANE "$A" switch model haiku >/dev/null 2>&1; check "no tmux -> rc 3" '[ $? -eq 3 ]'
env -u TMUX_PANE "$A" switch model haiku 2>&1 | grep -q "ask the user"; check "no tmux message tells user the command" '[ $? -eq 0 ]'
env -u TMUX_PANE "$A" compact >/dev/null 2>&1; check "compact: no tmux -> rc 3" '[ $? -eq 3 ]'
AWARE_ALLOW_COMPACT=0 TMUX_PANE=%1 "$A" compact >/dev/null 2>&1; check "compact: AWARE_ALLOW_COMPACT=0 -> rc 2" '[ $? -eq 2 ]'

echo "switch: real tmux keystrokes"
tmux -L awaretest -f /dev/null new-session -d -s t -x 200 -y 20 "cat > $T/keys.txt"
pane=$(tmux -L awaretest list-panes -t t -F '#{pane_id}')
tmux -L awaretest new-session -d -s keep -x 200 -y 20 "cat > /dev/null"   # stays alive for later tests
live=$(tmux -L awaretest list-panes -t keep -F '#{pane_id}')
# aware talks to the default tmux server, so shim `tmux` to the private test socket (never the real server).
mkdir -p "$T/shim"; printf '#!/bin/sh\nexec %s -L awaretest "$@"\n' "$(command -v tmux)" > "$T/shim/tmux"; chmod +x "$T/shim/tmux"
PATH="$T/shim:$PATH" TMUX_PANE=$pane "$A" switch model haiku >/dev/null; sleep 0.5
PATH="$T/shim:$PATH" TMUX_PANE=$pane "$A" switch effort medium >/dev/null; sleep 0.5
PATH="$T/shim:$PATH" TMUX_PANE=$pane "$A" compact >/dev/null; sleep 0.5
tmux -L awaretest send-keys -t "$pane" C-d; sleep 0.3
check "pane received '/model haiku'"  'grep -qx "/model haiku" "$T/keys.txt"'
check "pane received '/effort medium'" 'grep -qx "/effort medium" "$T/keys.txt"'
check "pane received '/compact'"      'grep -qx "/compact" "$T/keys.txt"'
check "pane received nothing else"     '[ "$(wc -l < "$T/keys.txt")" = 3 ]'
check "switch log written" '[ $(wc -l < "$HOME/.claude/aware/switches.log") -ge 3 ]'

echo "switch model: user's default model is preserved"
sim_save() { sleep 1.2; jq '.model="haiku"' "$HOME/.claude/settings.json" > "$T/s.tmp" && mv "$T/s.tmp" "$HOME/.claude/settings.json"; }  # what the TUI does on /model
echo '{"model":"sonnet","tui":"fullscreen"}' > "$HOME/.claude/settings.json"
PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch model haiku >/dev/null; sim_save; sleep 3
check "default restored to sonnet"  '[ "$(jq -r .model "$HOME/.claude/settings.json")" = sonnet ]'
check "other keys untouched"        '[ "$(jq -r .tui "$HOME/.claude/settings.json")" = fullscreen ]'
fx sw1 85 10 10 3600 500000 true | TMUX_PANE=$live "$A" statusline >/dev/null
check "switch effort: says it keeps the cache on a 5.5 model" '[[ "$(PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch effort medium)" == *"it keeps the prompt cache"* ]]'
fx sw1 85 10 10 3600 500000 true | jq -c '.model.id="claude-opus-4-8"' | TMUX_PANE=$live "$A" statusline >/dev/null
check "switch effort: does not promise it on an older model"  '[[ "$(PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch effort medium)" == *"may drop the prompt cache"* ]]'
echo '{"tui":"fullscreen"}' > "$HOME/.claude/settings.json"
PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch model opus >/dev/null; sleep 0.3; jq '.model="opus"' "$HOME/.claude/settings.json" > "$T/s.tmp" && mv "$T/s.tmp" "$HOME/.claude/settings.json"; sleep 3
check "no-default case: key removed again" '[ "$(jq "has(\"model\")" "$HOME/.claude/settings.json")" = false ]'
echo '{"model":"sonnet"}' > "$HOME/.claude/settings.json"
AWARE_KEEP_DEFAULT=0 PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch model haiku >/dev/null; sim_save; sleep 2.5
check "AWARE_KEEP_DEFAULT=0 leaves it changed" '[ "$(jq -r .model "$HOME/.claude/settings.json")" = haiku ]'
echo '{"model":"sonnet","tui":"fullscreen"}' > "$HOME/.claude/settings.json"

echo "switch effort: user's default effort is preserved"
eff_save() { sleep 1.2; jq ".modelSettings[\"claude-opus-5-5\"].effortLevel=\"$1\"" "$HOME/.claude/settings.json" > "$T/s.tmp" && mv "$T/s.tmp" "$HOME/.claude/settings.json"; }  # what /effort does (2.1.328)
echo '{"modelSettings":{"claude-opus-5-5":{"effortLevel":"high"},"claude-haiku-5-5":{"effortLevel":"low"}},"tui":"fullscreen"}' > "$HOME/.claude/settings.json"
fx sw2 85 10 10 3600 500000 true | TMUX_PANE=$live "$A" statusline >/dev/null
check "effort result mentions the cache is kept" '[[ "$(PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch effort medium)" == *"keeps the prompt cache"* ]]'
eff_save medium; sleep 2
check "effort default restored to high"  '[ "$(jq -r ".modelSettings[\"claude-opus-5-5\"].effortLevel" "$HOME/.claude/settings.json")" = high ]'
check "other models + keys untouched"    '[ "$(jq -c "[.modelSettings[\"claude-haiku-5-5\"].effortLevel, .tui]" "$HOME/.claude/settings.json")" = "[\"low\",\"fullscreen\"]" ]'
echo '{"tui":"fullscreen"}' > "$HOME/.claude/settings.json"
PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch effort low >/dev/null; eff_save low; sleep 2
check "no-default case: modelSettings removed again" '[ "$(jq "has(\"modelSettings\")" "$HOME/.claude/settings.json")" = false ]'
echo '{"model":"sonnet","tui":"fullscreen"}' > "$HOME/.claude/settings.json"

echo "autoconfirm (opt-in)"
cat > "$T/dlg.sh" <<'SH'
#!/bin/sh
# fake pane: show a "Switch model?" dialog for $1 after 1.5s (or nothing if $1 empty), then record all input
sleep 1.5
[ -n "$1" ] && printf 'Switch model?\n  1. Yes, switch to %s 5.5\n  2. No, go back\n' "$1"
cat > "$2"
SH
chmod +x "$T/dlg.sh"
# run <name> <dialog-model> <env-assignment|-> : switch to haiku in a fresh fake pane, return number of lines it received
ac_case() {
  tmux -L awaretest new-session -d -s "$1" -x 200 -y 20 "$T/dlg.sh '$2' $T/$1.txt"
  local p; p=$(tmux -L awaretest list-panes -t "$1" -F '#{pane_id}')
  env AWARE_KEEP_DEFAULT=0 AWARE_CONFIRM_WAIT=5 ${3:+$3} PATH="$T/shim:$PATH" TMUX_PANE=$p "$A" switch model haiku >/dev/null
  sleep 6.5; tmux -L awaretest send-keys -t "$p" C-d; sleep 0.4; wc -l < "$T/$1.txt"
}
check "dialog for haiku -> Enter sent (2 lines)"      '[ "$(ac_case a Haiku AWARE_AUTOCONFIRM=1)" = 2 ]'
check "autoconfirm logged"                             'grep -q "autoconfirmed /model haiku" "$HOME/.claude/aware/switches.log"'
check "dialog names OTHER model -> no Enter (1 line)" '[ "$(ac_case b Opus AWARE_AUTOCONFIRM=1)" = 1 ]'
check "no opt-in -> no Enter (1 line)"                 '[ "$(ac_case c Haiku)" = 1 ]'
check "opt-in but no dialog -> no Enter (1 line)"     '[ "$(ac_case d "" AWARE_AUTOCONFIRM=1)" = 1 ]'
check "result text says auto-confirm when on"  '[[ "$(AWARE_KEEP_DEFAULT=0 AWARE_AUTOCONFIRM=1 AWARE_CONFIRM_WAIT=1 PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch model haiku)" == *"confirm it automatically"* ]]'
check "result text asks user when off"          '[[ "$(AWARE_KEEP_DEFAULT=0 PATH="$T/shim:$PATH" TMUX_PANE=$live "$A" switch model haiku)" == *"USER must confirm"* ]]'

echo "launch forwards AWARE_* env"
mkdir -p "$T/stub"; printf '#!/bin/sh\necho "FWD=$AWARE_AUTOCONFIRM/$AWARE_WARN"\n' > "$T/stub/claude"; chmod +x "$T/stub/claude"
check "env reaches claude" '[ "$(AWARE_AUTOCONFIRM=1 AWARE_WARN=55 TMUX=fake PATH="$T/stub:$PATH" "$A" launch)" = "FWD=1/55" ]'
printf '#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = --mcp-config ] && echo "$2"; shift; done\n' > "$T/stub/claude"
printf '#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = --settings ] && echo "$2"; shift; done\n' > "$T/stub/claude"
check "launch: tool hook registered"          '[[ "$(TMUX=fake PATH="$T/stub:$PATH" "$A" launch | jq -r ".hooks.PostToolUse[0].hooks[0].command")" == *" tool-hook" ]]'
printf '#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = --mcp-config ] && echo "$2"; shift; done\n' > "$T/stub/claude"
check "launch: MCP server is alwaysLoad" '[ "$(TMUX=fake PATH="$T/stub:$PATH" "$A" launch | jq .mcpServers.aware.alwaysLoad)" = true ]'
printf '#!/bin/sh\necho "FWD=$AWARE_AUTOCONFIRM/$AWARE_WARN"\n' > "$T/stub/claude"
printf '#!/bin/sh\nprintf "%%s\\n" "$@" > %s\nexec /usr/bin/env "$@"\n' "$T/envargs" > "$T/stub/env"; chmod +x "$T/stub/env"
printf '#!/bin/sh\necho "KEY=$AWARE_DECIDER_KEY"\n' > "$T/stub/claude"
check "launch: decider key inherited, not an argument" '[[ "$(AWARE_DECIDER_KEY=sk-secret AWARE_WARN=55 TMUX=fake PATH="$T/stub:$PATH" "$A" launch)" == "KEY=sk-secret" ]] && ! grep -q sk-secret "$T/envargs" && grep -qx "AWARE_WARN=55" "$T/envargs"'
printf '#!/bin/sh\necho "FWD=$AWARE_AUTOCONFIRM/$AWARE_WARN"\n' > "$T/stub/claude"; rm -f "$T/stub/env"
check "launch works with no AWARE_* set" '[ "$(env -u AWARE_AUTOCONFIRM -u AWARE_WARN TMUX=fake PATH="$T/stub:$PATH" "$A" launch)" = "FWD=/" ]'

echo "mcp"
rpc=$(printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_usage","arguments":{}}}' \
 '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"set_model","arguments":{"model":"evil; id"}}}' \
 '{"jsonrpc":"2.0","id":5,"method":"nope"}' \
 '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"compact","arguments":{}}}' | env -u TMUX_PANE "$A" mcp)
check "initialize ok"      'echo "$rpc" | jq -es ".[]|select(.id==1).result.serverInfo.name==\"aware\"" >/dev/null'
check "instructions carry the policy" 'echo "$rpc" | jq -es ".[]|select(.id==1).result.instructions|test(\"haiku\") and test(\"natural break\")" >/dev/null'
check "policy: match model to task"   'echo "$rpc" | jq -es ".[]|select(.id==1).result.instructions|test(\"Match the model to the task\") and test(\"sonnet\\\" when the work needs judgment\")" >/dev/null'
check "policy follows AWARE_MODELS"   '[[ "$(printf "%s\n" "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}" | AWARE_MODELS="sonnet opus" "$A" mcp | jq -r .result.instructions)" == *"\"sonnet\" for mechanical work"* ]]'
check "tools marked alwaysLoad"  'echo "$rpc" | jq -es "[.[]|select(.id==2).result.tools[]._meta[\"anthropic/alwaysLoad\"]]|all" >/dev/null'
check "4 tools listed"     '[ "$(echo "$rpc" | jq -s "[.[]|select(.id==2).result.tools[].name]|sort|join(\",\")")" = "\"compact,get_usage,set_effort,set_model\"" ]'
check "get_usage returns data" 'echo "$rpc" | jq -es ".[]|select(.id==3).result.content[0].text|test(\"usage\")" >/dev/null'
check "set_model rejects bad value" 'echo "$rpc" | jq -es ".[]|select(.id==4).result.isError==true" >/dev/null'
check "unknown method -> error" 'echo "$rpc" | jq -es ".[]|select(.id==5).error.code==-32601" >/dev/null'
check "compact without tmux -> error naming /compact" 'echo "$rpc" | jq -es ".[]|select(.id==6).result|.isError==true and (.content[0].text|test(\"/compact\"))" >/dev/null'
check "exactly 6 replies (notification unanswered)" '[ "$(echo "$rpc" | wc -l)" = 6 ]'

echo "help"
check "help lists compact and tiers" '"$A" 2>&1 | grep -q "aware compact" && "$A" 2>&1 | grep -q "AWARE_CRIT"'

echo "install / uninstall round trip"
cp "$HOME/.claude/settings.json" "$T/orig.json"
"$A" install >/dev/null
check "hook + statusline added" 'jq -e ".hooks.UserPromptSubmit and .statusLine" "$HOME/.claude/settings.json" >/dev/null'
"$A" install >/dev/null
check "tool hook added too" 'jq -e ".hooks.PostToolUse[0].hooks[0].command | endswith(\"aware tool-hook\")" "$HOME/.claude/settings.json" >/dev/null'
check "reinstall idempotent" '[ "$(jq ".hooks.UserPromptSubmit|length" "$HOME/.claude/settings.json")" = 1 ] && [ "$(jq ".hooks.PostToolUse|length" "$HOME/.claude/settings.json")" = 1 ]'
"$A" uninstall >/dev/null
check "uninstall restores original" 'diff <(jq -S . "$HOME/.claude/settings.json") <(jq -S . "$T/orig.json") >/dev/null'

echo "senses (your own awareness entries)"
SD="$HOME/.claude/aware/senses"; rm -rf "$SD"
check "no senses: says so and lists examples"  '[[ "$("$A" senses)" == *"no senses enabled"*"available: machine sessions"* ]]'
"$A" senses enable machine >/dev/null
check "enable a shipped sense"                 '[ -L "$SD/machine" ] && [[ "$("$A" senses | grep "^machine ")" =~ ^machine\ +(ok|warn|crit)\  ]]'
check "enable unknown sense fails"             '! "$A" senses enable nope 2>/dev/null'
check "disable removes the link"               '"$A" senses disable machine >/dev/null && [ ! -e "$SD/machine" ]'
check "disable refuses your own scripts"       'mkdir -p "$SD" && printf "#!/bin/sh\necho ok x\n" > "$SD/mine" && chmod +x "$SD/mine" && ! "$A" senses disable mine 2>/dev/null && [ -f "$SD/mine" ]'
rm -f "$SD/mine"
fx sx 20 10 10 3600 500000 true | "$A" statusline >/dev/null
sense() { printf '#!/bin/sh\n%s\n' "$2" > "$SD/$1"; chmod 755 "$SD/$1"; }
hk() { echo '{"session_id":"sx"}' | "$A" hook; }
sense demo 'echo "warn 42 units | do the thing"'
v=$(hk)
check "hook: warn sense is reported"           '[[ "$v" == *"[aware] sense demo (warn): 42 units. do the thing"* ]]'
check "hook: usage line still there"           '[[ "$v" == "[usage]"* ]]'
check "hook: unchanged sense stays silent"     '[ -z "$(hk)" ]'
sense demo 'echo "ok 1 unit"'
check "hook: recovery is announced once"       '[[ "$(hk)" == *"sense demo: ok again (1 unit)"* && -z "$(hk)" ]]'
sense demo 'echo "crit 99 units | stop"'
check "hook: crit repeats every prompt"        '[[ "$(hk)" == *"(crit): 99 units"* && "$(hk)" == *"(crit): 99 units"* ]]'
sense demo 'echo "ok fine"'; hk >/dev/null
sense demo 'printf "warn \033[31mred\033[0m\tand\001 long %0300d | adv\n" 0'
v=$(hk)
check "sanitized: no escapes or controls"      '! grep -q "[[:cntrl:]]" <<<"$(grep sense <<<"$v")"'
check "capped: readings are short"             '[ "$(grep sense <<<"$v" | wc -c)" -lt 300 ]'
sense demo 'echo "ok fine"'; hk >/dev/null
sense demo 'echo "warn sid=$AWARE_SESSION_ID file=$(basename "$AWARE_FILE")"'
check "sense gets session id and file"         '[[ "$(hk)" == *"sid=sx file=sx.json"* ]]'
sense demo 'echo "ok fine"'; hk >/dev/null
sense slow 'sleep 5; echo "warn late"'
SECONDS=0; v=$(AWARE_SENSE_TIMEOUT=0.5 hk); t=$SECONDS
check "slow sense times out, hook stays quick" '[ $t -le 3 ] && [[ "$v" != *late* ]]'
check "timeout shows up in aware senses"       '[[ "$(AWARE_SENSE_TIMEOUT=0.5 "$A" senses)" == *"slow"*"timed out"* ]]'
rm -f "$SD/slow"
sense bad 'echo "total nonsense"'
check "bad output is listed, never injected"   '[[ "$("$A" senses)" == *"bad"*"bad output"* && "$(hk)" != *nonsense* ]]'
rm -f "$SD/bad"
sense open 'echo "warn open"'; chmod 777 "$SD/open"
check "world-writable sense is not run"        '[[ "$("$A" senses)" == *"open"*"writable by others"* && "$(hk)" != *"sense open"* ]]'
rm -f "$SD/open"
sense demo 'echo "warn visible | to get_usage"'
check "show lists non-ok senses"               '[[ "$(env -u TMUX_PANE "$A" show)" == *"[aware] sense demo (warn): visible. to get_usage"* ]]'
rm -f "$SD/demo"
mkdir -p "$T/sd"; printf 'x' > "$T/sd/pane-1.json"
for n in a b c; do printf '{}' > "$T/sd/$n.json"; done
check "sessions sense counts active sessions"  '[[ "$(AWARE_DIR=$T/sd "$ROOT/senses/sessions.sh")" == "warn 3 active sessions"* && "$(AWARE_DIR=$T/sd AWARE_SESSIONS_WARN=9 "$ROOT/senses/sessions.sh")" == "ok 3 active sessions" ]]'
check "machine sense: levels follow thresholds" '[[ "$(AWARE_MACHINE_WARN_MB=999999999 "$ROOT/senses/machine.sh")" == "warn "* && "$(AWARE_MACHINE_CRIT_MB=999999999 "$ROOT/senses/machine.sh")" == "crit "* && "$(AWARE_MACHINE_WARN_MB=0 AWARE_MACHINE_CRIT_MB=0 "$ROOT/senses/machine.sh")" =~ ^(ok|warn)\  ]]'

echo "stuck detection (tool-hook)"
th() { jq -cn --arg s "$1" --arg t "$2" --arg c "$3" --arg r "$4" '{session_id:$s,tool_name:$t,tool_input:{command:$c,file_path:$c},tool_response:{stdout:$r}}' | "$A" tool-hook; }
rm -f "$HOME/.claude/aware/events.log"
o1=$(th t1 Bash "make test" "fail"); o2=$(th t1 Bash "make test" "fail"); o3=$(th t1 Bash "make test" "fail")
check "third identical call is flagged"        '[ -z "$o1" ] && [ -z "$o2" ] && [[ "$(jq -r .hookSpecificOutput.additionalContext <<<"$o3")" == "[aware] stuck? the same Bash call ran 3 times"* ]]'
check "reply is a valid PostToolUse hook JSON" '[ "$(jq -r .hookSpecificOutput.hookEventName <<<"$o3")" = PostToolUse ]'
check "no nagging on the 4th and 5th"          '[ -z "$(th t1 Bash "make test" "fail")" ] && [ -z "$(th t1 Bash "make test" "fail")" ]'
check "flagged again on the 6th"               '[[ "$(th t1 Bash "make test" "fail")" == *"6 times"* ]]'
check "changed output is progress, not stuck"  '[ -z "$(th t2 Bash "make test" "fail 1")$(th t2 Bash "make test" "fail 2")$(th t2 Bash "make test" "fail 3")$(th t2 Bash "make test" "fail 4")" ]'
for i in 1 2 3 4; do th t3 Edit "/x/a.py" "edit $i" >/dev/null; done
check "five edits to one file are flagged"     '[[ "$(th t3 Edit "/x/a.py" "edit 5")" == *"5 edits to a.py in the last 8 tool calls"* ]]'
check "edits spread over files are fine"       '[ -z "$(for f in a b c d e f; do th t4 Edit "/x/$f.py" "e"; done)" ]'
check "stuck events reach the watch feed"      'grep -q " stuck pane=" "$HOME/.claude/aware/events.log"'
thd() { jq -cn --arg s "$1" --arg d "$2" '{session_id:$s,tool_name:"Bash",tool_input:{command:"echo same",description:$d},tool_response:{stdout:"same",stderr:"",interrupted:false}}' | "$A" tool-hook; }
check "descriptions do not hide a repeat"      '[ -z "$(thd t5 first)$(thd t5 second)" ] && [[ "$(thd t5 third)" == *"same Bash call ran 3 times"* ]]'
check "garbage on stdin is ignored"            'echo "not json" | "$A" tool-hook; [ $? -eq 0 ]'

echo "intervention feedback"
now_t=$(date +%s); ts() { date -Is -d "@$1"; }
fb() { # fb SID PANE: write a cost history (turns of $0.30, then of $0.10 after a move at base+135) and a switch log line
  local base=$1 sid=$2 cmd=$3 after=$4
  : > "$HOME/.claude/aware/$sid.hist"
  local c=100 t=$((base+100)); printf '%s %s\n' "$t" "1.00" >> "$HOME/.claude/aware/$sid.hist"
  for i in 1 2 3; do t=$((t+10)); printf '%s 1.%s\n' "$t" "$((i*3))0" >> "$HOME/.claude/aware/$sid.hist"; done
  local cost=190; for i in 1 2 3 4; do t=$((t+10)); cost=$((cost+after)); printf '%s %s.%02d\n' "$t" "$((cost/100))" "$((cost%100))" >> "$HOME/.claude/aware/$sid.hist"; done
  printf '%s %s pane=%%7\n' "$(ts $((base+135)))" "$cmd" >> "$HOME/.claude/aware/switches.log"
  fx "$sid" 20 10 10 3600 500000 true | "$A" statusline >/dev/null
}
: > "$HOME/.claude/aware/switches.log"; rm -f "$HOME/.claude/aware/events.log"
fb $((now_t-1000)) fb1 "/effort medium" 10
v=$(echo '{"session_id":"fb1"}' | TMUX_PANE=%7 "$A" hook)
check "effect: a cost drop is measured"        '[[ "$v" == *"[aware] effect of /effort medium: cost per turn \$0.30 -> \$0.10 (-67%, 3 turns before, 3 after)"* ]]'
check "effect: reported once"                  '[[ "$(echo "{\"session_id\":\"fb1\"}" | TMUX_PANE=%7 "$A" hook)" != *effect* ]]'
check "effect: lands in the watch feed"        'grep -q " effect pane=%7 effect of /effort medium" "$HOME/.claude/aware/events.log"'
: > "$HOME/.claude/aware/switches.log"
fb $((now_t-1000)) fb2 "/effort medium" 30
v=$(echo '{"session_id":"fb2"}' | TMUX_PANE=%7 "$A" hook)
check "effect: no drop is said plainly"        '[[ "$v" == *"effect of /effort medium"*"no clear drop yet"* ]]'
: > "$HOME/.claude/aware/switches.log"
fb $((now_t-1000)) fb3 "/model sonnet" 10
v=$(echo '{"session_id":"fb3"}' | TMUX_PANE=%7 "$A" hook)
check "effect: model switch skips rebuild turn" '[[ "$v" == *"effect of /model sonnet"*"3 turns before, 3 after"* ]]'
: > "$HOME/.claude/aware/switches.log"
printf '%s /effort low pane=%%7\n' "$(ts $((now_t-1000+135)))" >> "$HOME/.claude/aware/switches.log"
fb_old=$(echo '{"session_id":"fb1"}' | TMUX_PANE=%9 "$A" hook)
check "effect: other panes are not mixed in"   '[[ "$fb_old" != *effect* ]]'
withmiss() { # withmiss SID MOVE_TS PRE POST: add a cache-miss column to a two-column history
  local f="$HOME/.claude/aware/$1.hist"; awk -v mv="$2" -v pre="$3" -v post="$4" 'NF==2{print $0, ($1>mv)?post:pre; next}1' "$f" > "$f.tmp" && mv "$f.tmp" "$f"; }
: > "$HOME/.claude/aware/switches.log"
fb $((now_t-1000)) fb4 "/effort medium" 10; withmiss fb4 $((now_t-1000+135)) 2 3
v=$(echo '{"session_id":"fb4"}' | TMUX_PANE=%7 "$A" hook)
check "effect: cache misses after /effort are called out" '[[ "$v" == *"effect of /effort medium"*"cache misses rose by 1 right after it, so here an effort change is not free"* ]]'
: > "$HOME/.claude/aware/switches.log"
fb $((now_t-1000)) fb5 "/effort medium" 10; withmiss fb5 $((now_t-1000+135)) 2 2
v=$(echo '{"session_id":"fb5"}' | TMUX_PANE=%7 "$A" hook)
check "effect: no misses, no cache remark"     '[[ "$v" == *"effect of /effort medium"* && "$v" != *"cache misses"* ]]'
: > "$HOME/.claude/aware/switches.log"
fb $((now_t-1000)) fb6 "/model sonnet" 10; withmiss fb6 $((now_t-1000+135)) 2 3
v=$(echo '{"session_id":"fb6"}' | TMUX_PANE=%7 "$A" hook)
check "effect: a model switch is expected to miss, not flagged" '[[ "$v" == *"effect of /model sonnet"* && "$v" != *"cache misses"* ]]'

echo "watch (live dashboard)"
view n9 30 10 75 3600 500000 true >/dev/null
check "show --json carries limits"             '"$A" show --json | jq -e ".limits.warn == 80 and .limits.ctx_warn == 70 and .tier == \"conserve\"" >/dev/null'
w=$("$A" watch --once)
check "watch --once: tier ladder, current marked" '[[ "$w" == *"● CONSERVE"* && "$w" == *"NORMAL"* && "$w" == *"CRITICAL"* ]]'
check "watch --once: bars and thresholds"      '[[ "$w" == *"CONTEXT"* && "$w" == *"lean"* && "$w" == *"warn"* && "$w" == *"5H"* && "$w" == *"7D"* ]]'
check "watch --once: model, effort, cache"     '[[ "$w" == *"model "*"effort "*"cache "* ]]'
check "watch --once: plain when not a tty"     '! grep -q $(printf "\033") <<<"$w"'
printf '%s /effort medium pane=%%3\n%s autoconfirmed /model sonnet pane=%%3\n' "$(date -Is)" "$(date -Is)" > "$HOME/.claude/aware/switches.log"
w=$("$A" watch --once)
check "watch --once: activity feed"            '[[ "$w" == *"effort set to medium"* && "$w" == *"model dialog confirmed: sonnet"* ]]'
check "watch --once: filters by pane"          '[[ "$(AWARE_WATCH_PANE=%4 "$A" watch --once)" == *"quiet so far"* ]]'
check "watch --once: no session yet"           '[[ "$(HOME=$T/empty "$A" watch --once)" == *"waiting for a Claude session"* ]]'
sense demo 'echo "warn 42 units | adv"'; sense calm 'echo "ok all quiet"'
w=$("$A" watch --once)
check "watch --once: senses block"             '[[ "$w" == *"SENSES"*"calm"*"all quiet"*"demo"*"42 units"* ]]'
printf '%s stuck pane=%%3 stuck? the same Bash call ran 3 times\n' "$(date -Is)" >> "$HOME/.claude/aware/events.log"
check "watch --once: stuck shows in the feed"  '[[ "$(AWARE_WATCH_PANE=%3 "$A" watch --once)" == *"stuck? the same Bash call ran 3 times"* ]]'
check "watch --once: effect shows in the feed" '[[ "$(AWARE_WATCH_PANE=%7 "$A" watch --once)" == *"effect of /effort"* ]]'
rm -f "$SD/demo" "$SD/calm"
check "watch --once: no senses, no block"      '[[ "$("$A" watch --once)" != *SENSES* ]]'
mkdir -p "$T/stub2"; printf '#!/bin/sh\necho "$@" >> "%s/tmuxargs"\n' "$T" > "$T/stub2/tmux"; chmod +x "$T/stub2/tmux"
rm -f "$T/tmuxargs"; TMUX=fake TMUX_PANE=%9 AWARE_WARN=55 PATH="$T/stub2:$T/stub:$PATH" "$A" launch --watch >/dev/null
check "launch --watch splits a pane beside claude" 'grep -q "split-window -d -h -l 40%" "$T/tmuxargs" && grep -q "AWARE_WATCH_PANE=%9" "$T/tmuxargs" && grep -q "AWARE_WARN=55" "$T/tmuxargs"'
rm -f "$T/tmuxargs"; TMUX=fake TMUX_PANE=%9 PATH="$T/stub2:$T/stub:$PATH" "$A" launch >/dev/null
check "launch without --watch splits nothing"  '[ ! -e "$T/tmuxargs" ]'

echo "experiment arms"
IL="$HOME/.claude/aware/injections.log"; rm -f "$IL"
# armhook <arm> <sid> [ENV=val ...]: a conserve-tier session, then what the hook says for that arm
armhook() { local arm=$1 sid=$2; shift 2
  fx "$sid" 85 20 85 3600 500000 true | "$A" statusline >/dev/null
  echo "{\"session_id\":\"$sid\"}" | env AWARE_ARM="$arm" "$@" "$A" hook; }
v=$(armhook full ar1)
check "full: readout, tier and the tool calls"   '[[ "$v" == "[usage]"* && "$v" == *"tier=conserve"*"call set_effort medium now"*"call compact at the next natural break"* ]]'
v=$(armhook tiers ar2)
check "tiers: readout and tier advice"           '[[ "$v" == "[usage]"* && "$v" == *"tier=conserve"*"delegate bulk work"* ]]'
check "tiers: no tool calls are mentioned"       '[[ "$v" != *set_effort* && "$v" != *set_model* && "$v" != *"call compact"* && "$v" != *"Without the aware tools"* ]]'
v=$(armhook facts ar3)
check "facts: the readout line only"             '[[ "$v" == "[usage]"* && "$(echo "$v" | wc -l)" = 1 && "$v" != *tier=* ]]'
v=$(armhook placebo ar4)
check "placebo: one unrelated sentence, no numbers" '[[ "$v" == "[note] Keep commit messages short"* && "$(echo "$v" | wc -l)" = 1 && "$v" != *"[usage]"* && "$v" != *%* ]]'
check "placebo: text is configurable"            '[[ "$(armhook placebo ar5 AWARE_PLACEBO_TEXT="Water the plants.")" == "[note] Water the plants." ]]'
check "off: nothing is injected"                 '[ -z "$(armhook off ar6)" ]'
check "placebo keeps the schedule: silent when nothing changed" '[ -z "$(echo "{\"session_id\":\"ar4\"}" | AWARE_ARM=placebo "$A" hook)" ]'
fx ar4 97 20 85 3600 500000 true | "$A" statusline >/dev/null
check "placebo keeps the schedule: speaks on a tier change" '[[ "$(echo "{\"session_id\":\"ar4\"}" | AWARE_ARM=placebo "$A" hook)" == "[note]"* ]]'
check "injections are logged with arm and size"  '[ "$(jq -s "map(select(.arm==\"placebo\" and .chars > 0)) | length" "$IL")" = 3 ] && [ "$(jq -s "map(select(.arm==\"off\")) | length" "$IL")" = 0 ]'
check "stuck detection is full-only"             '[ -z "$(AWARE_ARM=facts thd ar7 a)$(AWARE_ARM=facts thd ar7 b)$(AWARE_ARM=facts thd ar7 c)" ]'
arm_mcp() { printf '#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = --mcp-config ] && echo "$2"; shift; done\n' > "$T/stubarm/claude"; }
mkdir -p "$T/stubarm"; arm_mcp; chmod +x "$T/stubarm/claude"
check "launch full: MCP tools registered"        '[ "$(AWARE_ARM=full TMUX=fake PATH="$T/stubarm:$PATH" "$A" launch | jq -r ".mcpServers | keys | join(\",\")")" = aware ]'
for arm in tiers facts placebo off; do
  check "launch $arm: no MCP tools"              '[ "$(AWARE_ARM=$arm TMUX=fake PATH="$T/stubarm:$PATH" "$A" launch | jq -c .mcpServers)" = "{}" ]'
done
check "launch: unknown arm is refused"           '! AWARE_ARM=bogus TMUX=fake PATH="$T/stubarm:$PATH" "$A" launch 2>"$T/arm.err" >/dev/null && grep -q "AWARE_ARM must be" "$T/arm.err"'

echo "simulated usage (test-only overlay)"
fx sim1 5 5 10 3600 500000 true | "$A" statusline >/dev/null
check "no overlay: real numbers"                 '[[ "$(env -u TMUX_PANE "$A" show)" == *"5h 5%"* ]]'
sv() { fx sim1 5 5 10 3600 500000 true | "$A" statusline >/dev/null; env -u TMUX_PANE AWARE_SIM_5H=88 AWARE_SIM_7D=40 "$@" "$A" show; }
v=$(sv)
check "overlay: readout shows the made-up 5h/7d" '[[ "$v" == *"5h 88% (resets "*", pace 1.5x, out ~"*"7d 40%"* ]]'
check "overlay: conserve tier, effort advice"    '[[ "$v" == *"tier=conserve"*"call set_effort medium now"* ]]'
check "overlay: real numbers stay in the stored JSON" '[ "$(jq .rate_limits.five_hour.used_percentage "$HOME/.claude/aware/sim1.json")" = 5 ]'
check "overlay: 97% -> critical"                 '[[ "$(sv AWARE_SIM_5H=97)" == *"tier=critical"* ]]'

echo "subagent gate"
gh() { jq -cn --arg s "$1" --arg t "$2" '{session_id:$s,tool_name:$t,tool_input:{}}' | env "${@:3}" "$A" gate-hook; }
fx gx 97 10 10 3600 500000 true | "$A" statusline >/dev/null
fx gy 85 10 10 3600 500000 true | "$A" statusline >/dev/null
d=$(gh gx Agent AWARE_GATE=1)
check "critical: Agent is denied"                '[ "$(echo "$d" | jq -r .hookSpecificOutput.permissionDecision)" = deny ] && [ "$(echo "$d" | jq -r .hookSpecificOutput.hookEventName)" = PreToolUse ]'
check "denial says why and who can lift it"      '[[ "$(echo "$d" | jq -r .hookSpecificOutput.permissionDecisionReason)" == *"critical (5h 97% of the limit)"*"aware gate allow"*"do not run that yourself"* ]]'
check "critical: Task and Workflow are denied too" '[ "$(gh gx Task AWARE_GATE=1 | jq -r .hookSpecificOutput.permissionDecision)" = deny ] && [ "$(gh gx Workflow AWARE_GATE=1 | jq -r .hookSpecificOutput.permissionDecision)" = deny ]'
check "critical: other tools pass"               '[ -z "$(gh gx Bash AWARE_GATE=1)" ]'
check "below critical: Agent passes"             '[ -z "$(gh gy Agent AWARE_GATE=1)" ]'
check "gate off (no AWARE_GATE): Agent passes"   '[ -z "$(gh gx Agent AWARE_GATE=0)" ]'
check "unknown session: Agent passes"            '[ -z "$(gh nope Agent AWARE_GATE=1)" ]'
check "gate works in every arm"                  '[ "$(gh gx Agent AWARE_GATE=1 AWARE_ARM=off | jq -r .hookSpecificOutput.permissionDecision)" = deny ]'
check "gate status: on"                          '[[ "$("$A" gate status)" == "on"* ]]'
"$A" gate allow 10 >/dev/null
check "gate allow: Agent passes while lifted"    '[ -z "$(gh gx Agent AWARE_GATE=1)" ] && [[ "$("$A" gate status)" == "lifted until"* ]]'
echo $((now - 5)) > "$HOME/.claude/aware/gate.allow"
check "gate allow: expires"                      '[ "$(gh gx Agent AWARE_GATE=1 | jq -r .hookSpecificOutput.permissionDecision)" = deny ]'
"$A" gate allow 10 >/dev/null; "$A" gate revoke >/dev/null
check "gate revoke: denies again"                '[ "$(gh gx Agent AWARE_GATE=1 | jq -r .hookSpecificOutput.permissionDecision)" = deny ]'
check "gate allow rejects a non-number"          '! "$A" gate allow soon 2>/dev/null'
printf '#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = --settings ] && echo "$2"; shift; done\n' > "$T/stubarm/claude"
check "launch with AWARE_GATE=1: PreToolUse gate registered" '[ "$(AWARE_GATE=1 TMUX=fake PATH="$T/stubarm:$PATH" "$A" launch | jq -r ".hooks.PreToolUse[0] | .matcher + \" \" + .hooks[0].command")" = "Agent|Task|Workflow $ROOT/aware gate-hook" ]'
check "launch without it: no PreToolUse hook"    '[ "$(TMUX=fake PATH="$T/stubarm:$PATH" "$A" launch | jq ".hooks | has(\"PreToolUse\")")" = false ]'
gh gx Agent AWARE_GATE=1 TMUX_PANE=%3 >/dev/null
check "watch --once: a refusal shows in the feed" '[[ "$(AWARE_WATCH_PANE=%3 "$A" watch --once)" == *"refused Agent at 5h 97%"* ]]'

echo; echo "$pass passed, $fail failed"; [ $fail -eq 0 ]
