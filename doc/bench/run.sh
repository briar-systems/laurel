#!/usr/bin/env bash
# run the benchmark matrix and write one results file
#
# usage: ./run.sh [duration_seconds]
#
# builds all three servers, starts each on its own loopback port, drives a fixed
# matrix with oha, and writes results/<date>-<hostname>.md.
#
# every server answers the same three routes with the same bodies. a cell that
# returns anything outside 2xx is reported as failed rather than averaged away.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

DURATION="${1:-10}"
CONNECTIONS=(64 256)
OHA_VERSION="v1.16.0"
TOOL_DIR="$here/.tool"
OHA="$TOOL_DIR/oha"

# one port per server variant, all on loopback
PORT_LAUREL=18101
PORT_GO1=18102
PORT_GON=18103
PORT_AXUM1=18104
PORT_AXUMN=18105

work="$(mktemp -d)"
pids=()
cleanup() {
    for pid in "${pids[@]:-}"; do
        [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    rm -rf "$work"
}
trap cleanup EXIT

need() {
    command -v "$1" >/dev/null 2>&1 || { echo "run.sh: $1 is not on PATH" >&2; exit 1; }
}
need python3
need curl

# the load the machine was already carrying before any server started. a busy
# machine makes every row below smaller, so it belongs in the report.
LOAD_BEFORE="$(cut -d' ' -f1 /proc/loadavg)"

# --- the load generator -----------------------------------------------------

if [ ! -x "$OHA" ]; then
    need gh
    echo "run.sh: fetching oha $OHA_VERSION"
    mkdir -p "$TOOL_DIR"
    # this release publishes no musl build; oha-linux-amd64 is the x86_64 Linux
    # asset and is statically enough linked to run here
    gh release download "$OHA_VERSION" --repo hatoo/oha \
        --pattern 'oha-linux-amd64' --output "$OHA" --clobber
    chmod +x "$OHA"
fi
oha_version="$("$OHA" --version | head -n 1)"

# --- build ------------------------------------------------------------------

echo "run.sh: building laurel"
need mach
( cd laurel && [ -d dep/hedge ] || ( cd laurel && mach dep pull ) ) >/dev/null 2>&1 || true
( cd laurel && if [ ! -d dep/hedge ]; then mach dep pull; fi && mach build . --profile release )
laurel_bin="$(find laurel/out -type f -name laurel-bench -perm -u+x | head -n 1)"
[ -n "$laurel_bin" ] || { echo "run.sh: the laurel server was not built" >&2; exit 1; }

echo "run.sh: building go"
need go
( cd go && go build -o go-bench . )

echo "run.sh: building axum"
need cargo
( cd axum && cargo build --release --quiet )

# --- server control ---------------------------------------------------------

wait_ready() {
    local port="$1" tries=0
    while [ "$tries" -lt 100 ]; do
        if curl -sS -o /dev/null --max-time 1 "http://127.0.0.1:$port/json" 2>/dev/null; then
            return 0
        fi
        tries=$((tries + 1))
        sleep 0.1
    done
    echo "run.sh: the server on port $port never became ready" >&2
    return 1
}

# peak resident set and CPU time, read from the kernel rather than sampled
proc_stat() {
    local pid="$1" field="$2"
    case "$field" in
        rss_kb)
            awk '/^VmHWM:/ { print $2 }' "/proc/$pid/status" 2>/dev/null || echo 0
            ;;
        cpu_s)
            # utime + stime in clock ticks, converted with the configured HZ
            awk -v hz="$(getconf CLK_TCK)" \
                '{ printf "%.2f", ($14 + $15) / hz }' "/proc/$pid/stat" 2>/dev/null || echo 0
            ;;
    esac
}

start_server() {
    local name="$1" port="$2"
    shift 2
    case "$name" in
        laurel)
            sed "s|127.0.0.1:8081|127.0.0.1:$port|" laurel/hedge.toml > "$work/laurel-$port.toml"
            "$laurel_bin" "$work/laurel-$port.toml" >"$work/$name.log" 2>&1 &
            ;;
        go1)
            GOMAXPROCS=1 BENCH_ADDR="127.0.0.1:$port" ./go/go-bench >"$work/$name.log" 2>&1 &
            ;;
        gon)
            BENCH_ADDR="127.0.0.1:$port" ./go/go-bench >"$work/$name.log" 2>&1 &
            ;;
        axum1)
            BENCH_THREADS=1 BENCH_ADDR="127.0.0.1:$port" \
                ./axum/target/release/axum-bench >"$work/$name.log" 2>&1 &
            ;;
        axumn)
            BENCH_ADDR="127.0.0.1:$port" \
                ./axum/target/release/axum-bench >"$work/$name.log" 2>&1 &
            ;;
    esac
    local pid=$!
    pids+=("$pid")
    wait_ready "$port" || { echo "run.sh: $name failed to start" >&2; cat "$work/$name.log" >&2; exit 1; }
    echo "$pid"
}

# --- the matrix -------------------------------------------------------------

# route name, method, path, body
routes=(
    "json|GET|/json|"
    "echo|GET|/echo/42|"
    "submit|POST|/submit|name=laurel"
)

# one measured cell
measure() {
    local port="$1" method="$2" path="$3" body="$4" conns="$5" out="$6"
    if [ "$method" = "POST" ]; then
        "$OHA" -z "${DURATION}s" -c "$conns" --no-tui --output-format json \
            -m POST -d "$body" -T 'application/x-www-form-urlencoded' \
            "http://127.0.0.1:$port$path" > "$out" 2>"$out.err"
    else
        "$OHA" -z "${DURATION}s" -c "$conns" --no-tui --output-format json \
            "http://127.0.0.1:$port$path" > "$out" 2>"$out.err"
    fi
}

# a short unmeasured run so the first measured cell is not paying for warmup
warmup() {
    local port="$1" method="$2" path="$3" body="$4"
    if [ "$method" = "POST" ]; then
        "$OHA" -z 2s -c 32 --no-tui --output-format json -m POST -d "$body" \
            -T 'application/x-www-form-urlencoded' \
            "http://127.0.0.1:$port$path" >/dev/null 2>&1 || true
    else
        "$OHA" -z 2s -c 32 --no-tui --output-format json \
            "http://127.0.0.1:$port$path" >/dev/null 2>&1 || true
    fi
}

servers=(
    "laurel|$PORT_LAUREL|Laurel + hedge (single threaded)"
    "go1|$PORT_GO1|Go net/http (GOMAXPROCS=1)"
    "axum1|$PORT_AXUM1|axum (tokio current_thread)"
    "gon|$PORT_GON|Go net/http (all cores)"
    "axumn|$PORT_AXUMN|axum (tokio multi_thread)"
)

results="$work/results.tsv"
: > "$results"
: > "$work/resources.tsv"

for entry in "${servers[@]}"; do
    IFS='|' read -r name port label <<< "$entry"
    echo "run.sh: starting $name on 127.0.0.1:$port"
    pid="$(start_server "$name" "$port")"
    cpu_start="$(proc_stat "$pid" cpu_s)"

    for route in "${routes[@]}"; do
        IFS='|' read -r rname method path body <<< "$route"
        warmup "$port" "$method" "$path" "$body"
        for conns in "${CONNECTIONS[@]}"; do
            echo "run.sh:   $name $rname c=$conns"
            out="$work/$name-$rname-$conns.json"
            measure "$port" "$method" "$path" "$body" "$conns" "$out"
            line="$(python3 parse.py < "$out")"
            printf '%s\t%s\t%s\t%s\n' "$name" "$rname" "$conns" "$line" >> "$results"
        done
    done

    rss="$(proc_stat "$pid" rss_kb)"
    cpu_end="$(proc_stat "$pid" cpu_s)"
    cpu="$(python3 -c "print('%.2f' % ($cpu_end - $cpu_start))")"
    printf '%s\t%s\t%s\n' "$name" "$rss" "$cpu" >> "$work/resources.tsv"

    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    sleep 1
done

# --- the report -------------------------------------------------------------

stamp="$(date +%Y-%m-%d)"
host="$(hostname)"
mkdir -p results
report="results/$stamp-$host.md"

# every one of these is allowed to fail without taking the run with it: the
# numbers are already measured by this point and a missing version string must
# not throw them away
MACH_VERSION="$( { mach info 2>/dev/null || true; } | head -n 1 )"
[ -n "$MACH_VERSION" ] || MACH_VERSION="unknown"
GO_VERSION="$( { go version 2>/dev/null || true; } | head -n 1 )"
[ -n "$GO_VERSION" ] || GO_VERSION="unknown"
RUSTC_VERSION="$( { rustc --version 2>/dev/null || true; } | head -n 1 )"
[ -n "$RUSTC_VERSION" ] || RUSTC_VERSION="unknown"
dep_ref() {
    awk -v want="[dep.$1]" '
        $0 == want { found = 1; next }
        found && /^ref[ \t]*=/ { gsub(/[",]/, "", $3); print $3; exit }
        found && /^\[/ { exit }
    ' laurel/mach.toml
}
LAUREL_VERSION="$(dep_ref laurel)"
HEDGE_VERSION="$(dep_ref hedge)"

python3 report.py \
    --results "$results" \
    --resources "$work/resources.tsv" \
    --duration "$DURATION" \
    --load-before "$LOAD_BEFORE" \
    --oha "$oha_version" \
    --mach "$MACH_VERSION" \
    --laurel "$LAUREL_VERSION" \
    --hedge "$HEDGE_VERSION" \
    --go "$GO_VERSION" \
    --rustc "$RUSTC_VERSION" \
    > "$report"

echo "run.sh: wrote $report"
