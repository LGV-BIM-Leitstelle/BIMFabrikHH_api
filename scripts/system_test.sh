#!/usr/bin/env bash
#
# System / integration test for the BIMFabrikHH OGC API - Processes service.
#
# Discovers all available processes via GET /ogc/processes, discovers the
# valid level_of_geom (LoD) values per process via GET /ogc/processes/{id},
# submits one execution per (process, LoD) pair with a fixed small bounding box,
# polls job status, downloads the resulting IFC file(s), and prints a
# console summary of successes/failures to CLI and to log file.
#
# Usage:
#   ./scripts/system_test.sh
#   BASE_URL=http://localhost:8083 ./scripts/system_test.sh
#
# Environment overrides:
#   BASE_URL           API base URL (default: http://localhost:8083)
#   POLL_INTERVAL      Seconds between status polls (default: 5)
#   MAX_WAIT_SECONDS   Overall polling budget in seconds (default: 600)

set -u -o pipefail

BASE_URL="${BASE_URL:-http://localhost:8083}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-600}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/system_test_output"
LOG_FILE="$OUTPUT_DIR/system_test_$(date '+%Y-%m-%d_%H-%M-%S').log"
WORKDIR="$(mktemp -d)"

# Small valid Hamburg bbox in a different location; this keeps the test within
# the service's 1 km² / 0.1 km² area limits while still exercising a new area.
BBOX_MIN_X=9.9720
BBOX_MIN_Y=53.5480
BBOX_MAX_X=9.9745
BBOX_MAX_Y=53.5505

cleanup() {
    rm -rf "$WORKDIR"
}
trap cleanup EXIT

mkdir -p "$OUTPUT_DIR"

# --- small helpers -----------------------------------------------------

log() {
    echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command '$1' not found on PATH"
}

require_cmd curl
require_cmd python3

# http_get URL OUTFILE -> prints http status code
http_get() {
    curl -s -o "$2" -w '%{http_code}' --max-time 30 "$1"
}

# http_post URL DATA_FILE OUTFILE -> prints http status code
http_post() {
    curl -s -o "$3" -w '%{http_code}' --max-time 30 \
        -X POST -H 'Content-Type: application/json' \
        --data-binary "@$2" "$1"
}

# http_download URL OUTFILE -> prints http status code
http_download() {
    curl -s -o "$2" -w '%{http_code}' --max-time 60 "$1"
}

# --- connectivity check --------------------------------------------------

log "Checking API connectivity at $BASE_URL ..."
health_file="$WORKDIR/health.json"
health_code="$(http_get "$BASE_URL/ogc/processes" "$health_file")"
if [[ "$health_code" != "200" ]]; then
    die "Cannot reach $BASE_URL/ogc/processes (HTTP $health_code). Is the API running? (poetry run python main.py --db sqlite)"
fi

# --- phase 1: discover processes -----------------------------------------

log "Discovering available processes ..."
mapfile -t PROCESS_IDS < <(python3 - "$health_file" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

for proc in data.get("processes", []):
    print(proc["id"])
PY
)

if [[ "${#PROCESS_IDS[@]}" -eq 0 ]]; then
    die "No processes discovered from $BASE_URL/ogc/processes"
fi

log "Found ${#PROCESS_IDS[@]} processes: ${PROCESS_IDS[*]}"

# --- phase 2: discover LoD matrix -----------------------------------------

# Parallel arrays; one row per (process, lod) test case. LOD_ROWS entry is
# empty string for processes that do not support level_of_geom.
PROC_ROWS=()
LOD_ROWS=()

for process_id in "${PROCESS_IDS[@]}"; do
    desc_file="$WORKDIR/desc_${process_id}.json"
    desc_code="$(http_get "$BASE_URL/ogc/processes/$process_id" "$desc_file")"
    if [[ "$desc_code" != "200" ]]; then
        log "WARNING: could not fetch description for $process_id (HTTP $desc_code); skipping"
        continue
    fi

    lod_values="$(python3 - "$desc_file" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

# Mirror TestProcessesEndpoints._lod_enum in tests/test_api_endpoints.py:
# the LoD enum (if any) lives in the second anyOf branch of the
# `containers` input schema.
try:
    any_of = data["inputs"]["containers"]["schema"]["items"]["anyOf"]
except (KeyError, TypeError):
    any_of = []

if len(any_of) < 2:
    sys.exit(0)

try:
    enum = any_of[1]["properties"]["components"]["properties"]["level_of_geom"][
        "properties"
    ]["value"]["enum"]
except (KeyError, TypeError):
    sys.exit(0)

print(" ".join(str(v) for v in enum))
PY
)"

    if [[ -z "$lod_values" ]]; then
        PROC_ROWS+=("$process_id")
        LOD_ROWS+=("")
    else
        for lod in $lod_values; do
            PROC_ROWS+=("$process_id")
            LOD_ROWS+=("$lod")
        done
    fi
done

TOTAL_ROWS="${#PROC_ROWS[@]}"
if [[ "$TOTAL_ROWS" -eq 0 ]]; then
    die "No test cases could be built from discovered processes"
fi

log "Built $TOTAL_ROWS test case(s) (process x LoD)"

# --- phase 3: submit all jobs ----------------------------------------------

JOBID_ROWS=()
OUTCOME_ROWS=()
DETAIL_ROWS=()

for ((i = 0; i < TOTAL_ROWS; i++)); do
    process_id="${PROC_ROWS[$i]}"
    lod="${LOD_ROWS[$i]}"

    payload_file="$WORKDIR/payload_${i}.json"
    python3 - "$process_id" "$lod" "$BBOX_MIN_X" "$BBOX_MIN_Y" "$BBOX_MAX_X" "$BBOX_MAX_Y" \
        > "$payload_file" <<'PY'
import json
import sys

process_id, lod, min_x, min_y, max_x, max_y = sys.argv[1:7]

payload = {
    "inputs": {
        "bbox": {
            "min_x": float(min_x),
            "min_y": float(min_y),
            "max_x": float(max_x),
            "max_y": float(max_y),
        }
    }
}

if lod:
    payload["inputs"]["containers"] = [
        {
            "containerId": "level_of_geometry",
            "containerTitle": "Level Of Geometry",
            "components": {
                "level_of_geom": {"title": "Level Of Geometry", "value": int(lod)}
            },
        }
    ]

print(json.dumps(payload))
PY

    resp_file="$WORKDIR/submit_${i}.json"
    submit_code="$(http_post "$BASE_URL/ogc/processes/$process_id/execution" "$payload_file" "$resp_file")"

    lod_label="${lod:-none}"

    if [[ "$submit_code" != "201" ]]; then
        JOBID_ROWS+=("")
        OUTCOME_ROWS+=("SUBMIT_FAILED")
        detail="$(cat "$resp_file" 2>/dev/null)"
        DETAIL_ROWS+=("HTTP $submit_code: $detail")
        log "SUBMIT FAILED: $process_id lod=$lod_label (HTTP $submit_code)"
        continue
    fi

    jobid="$(python3 - "$resp_file" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

print(data.get("id", ""))
PY
)"

    if [[ -z "$jobid" ]]; then
        JOBID_ROWS+=("")
        OUTCOME_ROWS+=("SUBMIT_FAILED")
        DETAIL_ROWS+=("HTTP 201 but response contained no job id: $(cat "$resp_file" 2>/dev/null)")
        log "SUBMIT FAILED: $process_id lod=$lod_label (no job id in response)"
        continue
    fi

    JOBID_ROWS+=("$jobid")
    OUTCOME_ROWS+=("PENDING")
    DETAIL_ROWS+=("")
    log "Submitted $process_id lod=$lod_label -> job $jobid"
done

# --- phase 4: poll all jobs -------------------------------------------------

log "Polling job status (interval=${POLL_INTERVAL}s, budget=${MAX_WAIT_SECONDS}s) ..."

elapsed=0
while (( elapsed < MAX_WAIT_SECONDS )); do
    all_terminal=true

    for ((i = 0; i < TOTAL_ROWS; i++)); do
        [[ "${OUTCOME_ROWS[$i]}" == "PENDING" ]] || continue
        jobid="${JOBID_ROWS[$i]}"
        [[ -n "$jobid" ]] || continue

        status_file="$WORKDIR/status_${i}.json"
        status_code="$(http_get "$BASE_URL/ogc/jobs/$jobid" "$status_file")"

        if [[ "$status_code" != "200" ]]; then
            all_terminal=false
            continue
        fi

        read -r job_status job_message < <(python3 - "$status_file" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

status = data.get("status", "")
message = data.get("message", "") or ""
# Keep this on one line for the bash `read` above.
print(status, message.replace("\n", " "))
PY
)

        case "$job_status" in
            successful)
                OUTCOME_ROWS[$i]="JOB_SUCCESSFUL"
                ;;
            failed)
                OUTCOME_ROWS[$i]="FAILED"
                DETAIL_ROWS[$i]="$job_message"
                ;;
            dismissed)
                OUTCOME_ROWS[$i]="DISMISSED"
                DETAIL_ROWS[$i]="$job_message"
                ;;
            accepted|running)
                all_terminal=false
                ;;
            *)
                all_terminal=false
                ;;
        esac
    done

    if $all_terminal; then
        break
    fi

    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
done

# Anything still PENDING after the budget is a timeout.
for ((i = 0; i < TOTAL_ROWS; i++)); do
    if [[ "${OUTCOME_ROWS[$i]}" == "PENDING" ]]; then
        OUTCOME_ROWS[$i]="TIMEOUT"
        DETAIL_ROWS[$i]="Job did not reach a terminal state within ${MAX_WAIT_SECONDS}s"
    fi
done

# --- phase 5: fetch + download results --------------------------------------

log "Fetching results for successful jobs ..."

for ((i = 0; i < TOTAL_ROWS; i++)); do
    [[ "${OUTCOME_ROWS[$i]}" == "JOB_SUCCESSFUL" ]] || continue

    process_id="${PROC_ROWS[$i]}"
    lod="${LOD_ROWS[$i]}"
    lod_label="${lod:-none}"
    jobid="${JOBID_ROWS[$i]}"

    results_file="$WORKDIR/results_${i}.json"
    results_code="$(http_get "$BASE_URL/ogc/jobs/$jobid/results" "$results_file")"

    if [[ "$results_code" != "200" ]]; then
        detail="$(python3 - "$results_file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(data.get("detail", "") or data)
except Exception as exc:
    print(f"<unreadable response: {exc}>")
PY
)"
        OUTCOME_ROWS[$i]="RESULTS_ERROR"
        DETAIL_ROWS[$i]="HTTP $results_code: $detail"
        continue
    fi

    read -r url_http result_message < <(python3 - "$results_file" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

url_http = data.get("url-http", "") or ""
message = data.get("message", "") or ""
print(url_http, message.replace("\n", " "))
PY
)

    if [[ -z "$url_http" ]]; then
        OUTCOME_ROWS[$i]="SUCCESS_NO_DATA"
        DETAIL_ROWS[$i]="$result_message"
        continue
    fi

    out_file="$OUTPUT_DIR/${process_id}_lod${lod_label}_${jobid}.ifc"
    download_code="$(http_download "$url_http" "$out_file")"
    file_size=0
    [[ -f "$out_file" ]] && file_size="$(stat -c '%s' "$out_file" 2>/dev/null || stat -f '%z' "$out_file" 2>/dev/null || echo 0)"

    if [[ "$download_code" == "200" && "$file_size" -gt 0 ]]; then
        OUTCOME_ROWS[$i]="SUCCESS_WITH_DATA"
        DETAIL_ROWS[$i]="$out_file ($file_size bytes)"
    else
        OUTCOME_ROWS[$i]="DOWNLOAD_FAILED"
        DETAIL_ROWS[$i]="HTTP $download_code downloading $url_http (file size: $file_size)"
    fi
done

# --- phase 6: console summary ------------------------------------------------

declare -A OUTCOME_COUNTS
FAILURE_COUNT=0

{
echo
echo "=================================================================="
echo " BIMFabrikHH OGC API system test summary"
echo "=================================================================="
echo "Base URL:            $BASE_URL"
echo "Processes discovered: ${#PROCESS_IDS[@]}"
echo "Test cases started:   $TOTAL_ROWS"
echo

for ((i = 0; i < TOTAL_ROWS; i++)); do
    process_id="${PROC_ROWS[$i]}"
    lod="${LOD_ROWS[$i]}"
    lod_label="${lod:-none}"
    jobid="${JOBID_ROWS[$i]:-<none>}"
    outcome="${OUTCOME_ROWS[$i]}"
    detail="${DETAIL_ROWS[$i]}"

    printf '%-32s lod=%-5s jobid=%-38s -> %s\n' "$process_id" "$lod_label" "$jobid" "$outcome"

    case "$outcome" in
        SUCCESS_WITH_DATA|SUCCESS_NO_DATA)
            ;;
        *)
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
            if [[ -n "$detail" ]]; then
                echo "    detail: $detail"
            fi
            ;;
    esac

    OUTCOME_COUNTS["$outcome"]=$(( ${OUTCOME_COUNTS["$outcome"]:-0} + 1 ))
done

echo
echo "------------------------------------------------------------------"
echo "Totals by outcome:"
for outcome in "${!OUTCOME_COUNTS[@]}"; do
    printf '  %-20s %d\n' "$outcome" "${OUTCOME_COUNTS[$outcome]}"
done
echo "------------------------------------------------------------------"
echo "Downloaded files (if any): $OUTPUT_DIR"
echo

# Remove generated IFC artifacts after the summary so the smoke test does not
# leave downloaded output behind in the workspace.
find "$OUTPUT_DIR" -maxdepth 1 -type f -name '*.ifc' -delete
printf 'Cleaned generated IFC files from %s\n' "$OUTPUT_DIR"

if [[ $FAILURE_COUNT -gt 0 ]]; then
    echo "RESULT: FAIL ($FAILURE_COUNT of $TOTAL_ROWS test case(s) did not succeed)"
else
    echo "RESULT: PASS (all $TOTAL_ROWS test case(s) succeeded)"
fi
} | tee -a "$LOG_FILE"

exit_code=0
[[ $FAILURE_COUNT -gt 0 ]] && exit_code=1
exit $exit_code
