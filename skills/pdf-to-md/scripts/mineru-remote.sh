#!/bin/bash
# mineru-remote: Parse local PDF on l40 via shared vllm server
#
# Server lifecycle:
#   - First call starts vllm server on best idle GPU (~4min cold start)
#   - Concurrent calls reuse the same server (no extra cold start, no extra GPU)
#   - Server shuts down automatically after last task finishes
#
# Usage: mineru-remote <pdf_path> [-l lang]

set -e

REMOTE_HOST="l40"
REMOTE_MINERU="/home/hyr/.local/bin/mineru"
REMOTE_SERVER="/home/hyr/.local/bin/mineru-vllm-server"
REMOTE_PORT=30000
MIN_FREE_MB=24000

LANG_ARG=""

usage() {
    echo "Usage: mineru-remote <pdf_path> [-l lang]"
    echo "Lang: ch | en | ch_lite | ..."
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -l|--lang) LANG_ARG="-l $2"; shift 2 ;;
        -h|--help) usage ;;
        -*) echo "Unknown option: $1" >&2; usage ;;
        *) break ;;
    esac
done

[[ $# -lt 1 ]] && usage

PDF_PATH="$(realpath "$1")"
[[ ! -f "$PDF_PATH" ]] && { echo "Error: not found: $PDF_PATH" >&2; exit 1; }

LOCAL_DIR="$(dirname "$PDF_PATH")"
FILENAME="$(basename "$PDF_PATH")"
STEM="${FILENAME%.pdf}"
REMOTE_TMPDIR="/tmp/mineru_remote_$$"

# ---------------------------------------------------------------------------
# release_server: decrement refcount; stop server if it reaches 0
# ---------------------------------------------------------------------------
release_server() {
    local _max_retries=3
    local _attempt=0
    while (( _attempt < _max_retries )); do
        if ssh -o ConnectTimeout=10 "$REMOTE_HOST" bash <<'RELEASE' 2>/dev/null; then
PIDFILE=/tmp/mineru_server.pid
REFFILE=/tmp/mineru_server.ref
FLOCK=/tmp/mineru_server.flock
(
    flock -x -w 10 9 || exit 1
    REF=$(cat "$REFFILE" 2>/dev/null || echo 1)
    REF=$((REF - 1))
    if [[ $REF -le 0 ]]; then
        PID=$(cat "$PIDFILE" 2>/dev/null || true)
        [[ -n "$PID" ]] && kill "$PID" 2>/dev/null && echo "  WARNING: vllm server stopped (refcount=0), next call will cold-start (~2min)"
        rm -f "$PIDFILE" "$REFFILE" /tmp/mineru_server.gpu
    else
        echo "$REF" > "$REFFILE"
        echo "  Active tasks remaining: $REF"
    fi
) 9>>"$FLOCK"
RELEASE
            break
        fi
        _attempt=$((_attempt + 1))
        echo "  WARN: release_server SSH failed (attempt $_attempt/$_max_retries), retrying in 2s..." >&2
        sleep 2
    done
    if (( _attempt >= _max_retries )); then
        echo "  ERROR: release_server failed after $_max_retries attempts, refcount may leak" >&2
    fi
    ssh -o ConnectTimeout=10 "$REMOTE_HOST" "rm -rf '$REMOTE_TMPDIR'" 2>/dev/null || true
}

echo "=== MinerU Remote (l40) ==="
echo "  PDF:     $PDF_PATH"
echo "  Output:  $LOCAL_DIR/$STEM.md + ${STEM}_images/"
echo ""

# ---------------------------------------------------------------------------
# Acquire server: start if needed (atomic via flock), wait until ready, inc ref
# ---------------------------------------------------------------------------
echo "[0/4] Acquiring vllm server..."
ssh "$REMOTE_HOST" bash << ACQUIRE
set -e
RPORT=$REMOTE_PORT
MIN_FREE=$MIN_FREE_MB
RSERVER="$REMOTE_SERVER"
PIDFILE=/tmp/mineru_server.pid
REFFILE=/tmp/mineru_server.ref
FLOCK=/tmp/mineru_server.flock

# Phase 1: start server if not already running (brief exclusive lock)
(
    flock -x 9
    PID=\$(cat "\$PIDFILE" 2>/dev/null || echo "")
    if [[ -n "\$PID" ]] && kill -0 "\$PID" 2>/dev/null; then
        echo "  Server already running (PID \$PID)"
    else
        # Pick GPU: enough free VRAM, lowest utilization
        GPU_ID=\$(python3 -c "
import subprocess, sys
MIN_FREE = \$MIN_FREE
r = subprocess.run(
    ['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu','--format=csv,noheader,nounits'],
    capture_output=True, text=True)
gpus = [(int(p[0]),int(p[1]),int(p[2])) for line in r.stdout.strip().split('\n') for p in [[x.strip() for x in line.split(',')]]]
eligible = sorted([(i,f,u) for i,f,u in gpus if f >= MIN_FREE], key=lambda x: x[2])
if not eligible:
    sys.stderr.write('ERROR: No GPU with >=' + str(MIN_FREE) + 'MB free VRAM\n'); sys.exit(1)
sys.stderr.write('  -> GPU ' + str(eligible[0][0]) + ': ' + str(eligible[0][1]) + 'MB free, ' + str(eligible[0][2]) + '% util\n')
print(eligible[0][0])
") || exit 1
        echo "  Starting vllm server on GPU \$GPU_ID (port \$RPORT)..."
        # Pass model path directly to skip ~2.5min HuggingFace auto-download check
        # Add --enforce-eager to skip CUDA graph capture (~10s)
        MODEL_PATH="/home/hyr/.cache/huggingface/hub/models--opendatalab--MinerU2.5-2509-1.2B/snapshots/879e58bdd9566632b27a8a81f0e2961873311f67"
        # 9>&- closes the inherited flock fd in the child process
        CUDA_VISIBLE_DEVICES=\$GPU_ID nohup "\$RSERVER" \
            --port "\$RPORT" \
            --model "\$MODEL_PATH" \
            --enforce-eager \
            9>&- > /tmp/mineru_server.log 2>&1 &
        echo \$! > "\$PIDFILE"
        echo \$GPU_ID > /tmp/mineru_server.gpu
    fi
) 9>>"\$FLOCK"

# Phase 2: wait for server ready (no lock; parallel tasks wait concurrently)
for i in \$(seq 150); do
    curl -sf "http://127.0.0.1:\${RPORT}/health" > /dev/null 2>&1 && break
    [[ \$i -eq 1 ]] && echo "  Waiting for vllm to initialize (~4min first time)..."
    sleep 2
done
curl -sf "http://127.0.0.1:\${RPORT}/health" > /dev/null 2>&1 \
    || { echo "Server failed to start; see /tmp/mineru_server.log" >&2; exit 1; }
echo "  Server ready"

# Phase 3: increment refcount (brief exclusive lock)
(
    flock -x 9
    REF=\$(cat "\$REFFILE" 2>/dev/null || echo 0)
    echo \$((REF + 1)) > "\$REFFILE"
    echo "  Active tasks: \$((REF + 1))"
) 9>>"\$FLOCK"
ACQUIRE

trap "release_server" EXIT

# 1. Upload
echo "[1/4] Uploading PDF..."
ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_TMPDIR'"
scp -q "$PDF_PATH" "$REMOTE_HOST:$REMOTE_TMPDIR/$FILENAME"

# 2. Run mineru (connects to shared vllm server, no per-task cold start)
echo "[2/4] Running mineru → shared vllm server..."
START=$(date +%s)
ssh "$REMOTE_HOST" "HF_HUB_OFFLINE=1 $REMOTE_MINERU \
    -p '$REMOTE_TMPDIR/$FILENAME' \
    -o '$REMOTE_TMPDIR/output' \
    -b hybrid-http-client \
    -u 'http://127.0.0.1:$REMOTE_PORT' \
    $LANG_ARG"
echo "      Done in $(($(date +%s) - START))s"

# 3. Download only md and images, output to PDF's directory
echo "[3/4] Downloading results..."
BACKEND_SUBDIR=$(ssh "$REMOTE_HOST" "ls '$REMOTE_TMPDIR/output/$STEM/' 2>/dev/null | head -1")
[[ -z "$BACKEND_SUBDIR" ]] && { echo "Error: mineru produced no output" >&2; exit 1; }

# Download md
rsync -az "$REMOTE_HOST:$REMOTE_TMPDIR/output/$STEM/$BACKEND_SUBDIR/$STEM.md" "$LOCAL_DIR/"

# Download images
rsync -az "$REMOTE_HOST:$REMOTE_TMPDIR/output/$STEM/$BACKEND_SUBDIR/images/" "$LOCAL_DIR/${STEM}_images/" 2>/dev/null || true

echo ""
echo "Done!  $LOCAL_DIR/"
ls "$LOCAL_DIR/$STEM.md" 2>/dev/null && echo "  + ${STEM}_images/"
