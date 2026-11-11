#!/usr/bin/env bash
# End-to-end tests: pyios-firebase in the iOS Simulator, through the real
# Firebase iOS SDK, against the local Firestore, Auth, Functions, Storage and
# Realtime Database emulators (plus Remote Config, App Check, Analytics,
# Crashlytics and Messaging, which need no emulator).
#
# The app is launched twice: the first launch runs the suites and then crashes
# on purpose; the second checks that Crashlytics recorded the crash. While the
# first runs, notification payloads the app asks for are delivered with
# "xcrun simctl push".
#
#   e2e/run_ios_e2e.sh
#
# Needs: Xcode with an iOS simulator, uv (also builds the Python functions'
# venv), firebase-tools, and Java 21+ for the emulators
# (JAVA_HOME, or any JDK java_home can find).
#
# Environment:
#   E2E_DEVICE   simulator name (default "iPhone 17")
#   E2E_TIMEOUT  seconds to wait for results after launch (default 900)
#
# Uses the offline demo-pyios-firebase project: no Firebase account, no
# credentials, nothing leaves the Mac. Exits 0 only if every test passed.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
APP="$HERE/ios"
DEVICE="${E2E_DEVICE:-iPhone 17}"
TIMEOUT="${E2E_TIMEOUT:-900}"
PROJECT_ID="demo-pyios-firebase"
BUNDLE_ID="io.github.pysimpleobjc.pyiosfirebase.e2e"
EMULATOR="127.0.0.1:8080"
AUTH_EMULATOR="127.0.0.1:9099"
FUNCTIONS_EMULATOR="127.0.0.1:5001"
STORAGE_EMULATOR="127.0.0.1:9199"
DATABASE_EMULATOR="127.0.0.1:9000"
DATABASE_NAMESPACE="demo-pyios-firebase-default-rtdb"
# a fixed App Check debug token, passed to the app as FIRAAppCheckDebugToken
APP_CHECK_DEBUG_TOKEN="00000000-e2e0-4000-8000-000000000000"
RESULTS_NAME="pyios-e2e-results.json"
AFTER_CRASH_RESULTS_NAME="pyios-e2e-results-after-crash.json"
PUSH_REQUEST_NAME="pyios-e2e-push.json"
# the kivyforge commit the build is known to work with
KIVYFORGE="git+https://github.com/ElliotGarbus/kivyforge.git@758dc40e6e7f3c430f06f5f25c98023882926e28"
LOGS="$APP/build/e2e"
mkdir -p "$LOGS"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 2; }

kivyforge() { (cd "$APP" && uvx --python 3.15 --from "$KIVYFORGE" kivyforge "$@"); }

EMULATOR_PID=""
APP_PID=""
cleanup() {
  if [[ -n "$APP_PID" ]]; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true  # reaped quietly: no "Terminated" line
  fi
  if [[ -n "${DEVICE_UDID:-}" ]]; then
    xcrun simctl terminate "$DEVICE_UDID" "$BUNDLE_ID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$EMULATOR_PID" ]]; then
    say "stopping the emulator"
    # only the process group this script started (firebase, node, java):
    # other emulators on this Mac are left alone
    kill -TERM -- "-$EMULATOR_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 -- "-$EMULATOR_PID" 2>/dev/null || break
      sleep 0.5
    done
    kill -KILL -- "-$EMULATOR_PID" 2>/dev/null || true
    wait "$EMULATOR_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# ---- 1. Java 21+ for the emulator ---------------------------------------------
java_major() { "$1/bin/java" -version 2>&1 | awk -F'"' '/version/ {split($2, v, "."); print v[1]; exit}'; }
pick_java() {
  local candidates=()
  [[ -n "${JAVA_HOME:-}" ]] && candidates+=("$JAVA_HOME")
  local found
  found="$(/usr/libexec/java_home -v 21+ 2>/dev/null || true)"
  [[ -n "$found" ]] && candidates+=("$found")
  candidates+=(/opt/homebrew/opt/openjdk /usr/local/opt/openjdk)
  for home in "${candidates[@]}"; do
    if [[ -x "$home/bin/java" ]] && (( $(java_major "$home") >= 21 )); then
      echo "$home"; return
    fi
  done
  die "the Firestore emulator needs Java 21+ (set JAVA_HOME, or: brew install openjdk)"
}

# ---- 2. the emulators ---------------------------------------------------------
listening() { curl -s -o /dev/null --max-time 2 "http://$1/"; }
if [[ ! -x "$HERE/functions/venv/bin/python" ]]; then
  # the emulator runs Python functions from functions/venv (runtime python313)
  say "creating the e2e functions' venv"
  (cd "$HERE/functions" && uv venv --quiet --python 3.13 venv \
     && uv pip install --quiet --python venv/bin/python -r requirements.txt)
fi
if listening "$EMULATOR" && listening "$AUTH_EMULATOR" && listening "$FUNCTIONS_EMULATOR" \
   && listening "$STORAGE_EMULATOR" && listening "$DATABASE_EMULATOR"; then
  say "reusing the emulators already running (Firestore, Auth, Functions, Storage, Database)"
else
  command -v firebase >/dev/null || die "firebase-tools not found (npm i -g firebase-tools)"
  JAVA="$(pick_java)"
  say "starting the Firestore, Auth, Functions, Storage and Database emulators (Java: $JAVA)"
  # job control on: the emulator gets its own process group (PGID = its PID),
  # so cleanup can stop exactly what was started here
  set -m
  (cd "$HERE" && JAVA_HOME="$JAVA" PATH="$JAVA/bin:$PATH" \
     firebase emulators:start --only firestore,auth,functions,storage,database --project "$PROJECT_ID" --config firebase.json \
     >"$LOGS/emulator.log" 2>&1) &
  EMULATOR_PID=$!
  set +m
  for _ in $(seq 1 120); do
    grep -q "All emulators ready" "$LOGS/emulator.log" 2>/dev/null && break
    kill -0 "$EMULATOR_PID" 2>/dev/null || { cat "$LOGS/emulator.log"; die "the emulator did not start"; }
    sleep 1
  done
  grep -q "All emulators ready" "$LOGS/emulator.log" || die "the emulator was not ready after 120s"
fi
say "clearing the emulators' data"
curl -fs -X DELETE "http://$EMULATOR/emulator/v1/projects/$PROJECT_ID/databases/(default)/documents" >/dev/null
curl -fs -X DELETE "http://$AUTH_EMULATOR/emulator/v1/projects/$PROJECT_ID/accounts" >/dev/null
# "Bearer owner": the emulator's admin access, past the security rules
curl -fs -X DELETE -H "Authorization: Bearer owner" \
  "http://$DATABASE_EMULATOR/.json?ns=$DATABASE_NAMESPACE" >/dev/null

# ---- 3. the library wheel and the app ------------------------------------------
say "building the pyios-firebase wheel from $ROOT"
rm -rf "$APP/wheels"
(cd "$ROOT" && uv build -q --wheel -o "$APP/wheels")
say "locking the app's iOS dependencies"
kivyforge lock -p ios >"$LOGS/lock.log" 2>&1 || { tail -30 "$LOGS/lock.log"; die "kivyforge lock failed"; }

device_udid() {
  xcrun simctl list devices available -j | python3 -c '
import json, sys
name = sys.argv[1]
devices = [d for runtime in json.load(sys.stdin)["devices"].values() for d in runtime if d["name"] == name]
booted = [d for d in devices if d["state"] == "Booted"]
print((booted or devices or [{"udid": ""}])[0]["udid"])' "$DEVICE"
}
documents_path() {  # documents_path NAME: a file in the app's Documents folder
  local container
  container="$(xcrun simctl get_app_container "$DEVICE_UDID" "$BUNDLE_ID" data 2>/dev/null)" || return 1
  echo "$container/Documents/$1"
}
results_path() { documents_path "$RESULTS_NAME"; }
# a notification payload the app asked for (messaging_tests.py): deliver it
deliver_push() {
  local request
  if request="$(documents_path "$PUSH_REQUEST_NAME")" && [[ -f "$request" ]]; then
    xcrun simctl push "$DEVICE_UDID" "$BUNDLE_ID" "$request" >>"$LOGS/push.log" 2>&1 || true
    rm -f "$request"
  fi
}

DEVICE_UDID="$(device_udid)"
[[ -n "$DEVICE_UDID" ]] || die "no simulator named \"$DEVICE\" (xcrun simctl list devices available)"
# results from an earlier run must not be mistaken for this run's
for name in "$RESULTS_NAME" "$AFTER_CRASH_RESULTS_NAME" "$PUSH_REQUEST_NAME"; do
  if old="$(documents_path "$name")"; then rm -f "$old"; fi
done
: >"$LOGS/push.log"

say "building and launching on $DEVICE ($DEVICE_UDID) — the first build takes a few minutes"
# simctl hands SIMCTL_CHILD_* variables to the launched app, without the prefix
SIMCTL_CHILD_FIRAAppCheckDebugToken="$APP_CHECK_DEBUG_TOKEN" SIMCTL_CHILD_E2E_CRASH_AT_END=1 \
  kivyforge run -p ios --simulator --destination "$DEVICE_UDID" >"$LOGS/app.log" 2>&1 &
APP_PID=$!

# ---- 4. wait for the results ---------------------------------------------------
deadline=$(( $(date +%s) + TIMEOUT ))
results=""
while (( $(date +%s) < deadline )); do
  if path="$(results_path)" && [[ -f "$path" ]]; then results="$path"; break; fi
  deliver_push
  if ! kill -0 "$APP_PID" 2>/dev/null && ! grep -q "PYIOS-E2E START" "$LOGS/app.log"; then
    tail -40 "$LOGS/app.log"; die "the build or launch failed (log: $LOGS/app.log)"
  fi
  sleep 2
done
[[ -n "$results" ]] || { grep "PYIOS-E2E" "$LOGS/app.log" || true; die "no results after ${TIMEOUT}s (log: $LOGS/app.log)"; }

cp "$results" "$LOGS/$RESULTS_NAME"
xcrun simctl io "$DEVICE_UDID" screenshot "$LOGS/screenshot.png" >/dev/null 2>&1 || true

# ---- 5. the second launch: Crashlytics must have the crash -----------------------
say "waiting for the planned crash, then launching again (Crashlytics)"
for _ in $(seq 1 30); do
  grep -q "PYIOS-E2E CRASHING" "$LOGS/app.log" && ! kill -0 "$APP_PID" 2>/dev/null && break
  sleep 1
done
wait "$APP_PID" 2>/dev/null || true
APP_PID=""
xcrun simctl terminate "$DEVICE_UDID" "$BUNDLE_ID" >/dev/null 2>&1 || true
SIMCTL_CHILD_E2E_PHASE=after-crash SIMCTL_CHILD_FIRAAppCheckDebugToken="$APP_CHECK_DEBUG_TOKEN" \
  xcrun simctl launch --console-pty "$DEVICE_UDID" "$BUNDLE_ID" >"$LOGS/app-after-crash.log" 2>&1 &
APP_PID=$!
after_crash=""
deadline=$(( $(date +%s) + 120 ))
while (( $(date +%s) < deadline )); do
  if path="$(documents_path "$AFTER_CRASH_RESULTS_NAME")" && [[ -f "$path" ]]; then after_crash="$path"; break; fi
  sleep 2
done
if [[ -n "$after_crash" ]]; then
  cp "$after_crash" "$LOGS/$AFTER_CRASH_RESULTS_NAME"
else
  echo '{"passed": 0, "failed": 1, "seconds": 0, "results": [{"name": "test_crashlytics_after_crash", "ok": false, "seconds": 0, "detail": "the second launch wrote no results"}]}' \
    >"$LOGS/$AFTER_CRASH_RESULTS_NAME"
fi

python3 - "$LOGS/$RESULTS_NAME" "$LOGS/$AFTER_CRASH_RESULTS_NAME" <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
second = json.load(open(sys.argv[2]))
report["results"] += second["results"]
for key in ("passed", "failed", "skipped"):
    report[key] = report.get(key, 0) + second.get(key, 0)
report["seconds"] = round(report["seconds"] + second["seconds"], 2)
for r in report["results"]:
    if r.get("skipped"):
        mark = "\033[33mSKIP\033[0m"
    else:
        mark = "\033[32mPASS\033[0m" if r["ok"] else "\033[31mFAIL\033[0m"
    print(f"  {mark} {r['name']} ({r['seconds']}s)")
    if not r["ok"] or r.get("skipped"):
        print("       " + r["detail"].strip().replace("\n", "\n       "))
print(f"\n{report['passed']} passed, {report['failed']} failed, {report.get('skipped', 0)} skipped in {report['seconds']}s")
sys.exit(0 if report["failed"] == 0 and report["passed"] > 0 else 1)
PY
