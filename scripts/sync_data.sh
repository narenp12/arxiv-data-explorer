#!/usr/bin/env bash
set -euo pipefail

# Cross-machine sync for arXiv data pipeline
# Usage:
#   ./scripts/sync_data.sh push    # MacBook → GPU box (git + papers.parquet)
#   ./scripts/sync_data.sh pull    # GPU box → MacBook (fulltext, embeddings, ML)
#
# Set GPU_HOST env var (default: gpu-box)

GPU_HOST="${GPU_HOST:-gpu-box}"
REMOTE_DIR="${GPU_HOST}:~/arxiv-data-explorer"

case "${1:-help}" in
  push)
    echo "=== Syncing git and metadata to GPU box ==="
    git push origin daft-pipeline
    ssh "$GPU_HOST" "cd ~/arxiv-data-explorer && git fetch origin && git checkout daft-pipeline"
    echo "Done. On GPU box, run: uv run python scripts/build_data.py --no-incremental --fulltext --embeddings --ml"
    ;;
  pull)
    echo "=== Syncing artifacts from GPU box ==="
    rsync -avz --progress \
      "$REMOTE_DIR/static/data/fulltext/" \
      "static/data/fulltext/"
    rsync -avz --progress \
      "$REMOTE_DIR/static/data/embeddings/" \
      "static/data/embeddings/"
    rsync -avz --progress \
      "$REMOTE_DIR/static/data/topics.json" \
      "static/data/topics.json"
    rsync -avz --progress \
      "$REMOTE_DIR/static/data/recommendations.json" \
      "static/data/recommendations.json"
    echo "Done. Artifacts synced from GPU box."
    ;;
  full)
    echo "=== Full pipeline on GPU box ==="
    "$0" push
    ssh "$GPU_HOST" "cd ~/arxiv-data-explorer && \
      uv run python scripts/build_data.py --no-incremental --fulltext --embeddings --ml"
    "$0" pull
    echo "Full pipeline complete."
    ;;
  *)
    echo "Usage: $0 {push|pull|full}"
    echo ""
    echo "Commands:"
    echo "  push    Sync git repo + metadata to GPU box"
    echo "  pull    Sync artifacts (fulltext, embeddings, ML) from GPU box"
    echo "  full    Push, run full pipeline on GPU box, pull results"
    echo ""
    echo "Environment:"
    echo "  GPU_HOST   GPU box hostname (default: gpu-box)"
    ;;
esac
