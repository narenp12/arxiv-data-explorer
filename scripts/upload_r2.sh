#!/usr/bin/env bash
# Upload search + detail SQLite DBs to a Cloudflare R2 bucket.
#
# Prereqs (one-time):
#   1. npm install -g wrangler && wrangler login
#   2. wrangler r2 bucket create arxiv-explorer-data
#   3. Enable public access (r2.dev URL) in the Cloudflare dashboard:
#      R2 → arxiv-explorer-data → Settings → Public access → Allow
#   4. Apply CORS rules: dashboard → bucket → Settings → CORS policy →
#      paste contents of infra/r2-cors.json
#
# wrangler `r2 object put` rejects files over ~300MB, so large files need
# rclone with R2's S3 API instead. rclone config (~/.config/rclone/rclone.conf):
#   [r2]
#   type = s3
#   provider = Cloudflare
#   access_key_id = <R2 API token key id>
#   secret_access_key = <R2 API token secret>
#   endpoint = https://<account-id>.r2.cloudflarestorage.com
# (Create the API token under R2 → Manage R2 API Tokens → Object Read & Write.)

set -euo pipefail
cd "$(dirname "$0")/.."

BUCKET="${1:-arxiv-explorer-data}"

if ! command -v rclone >/dev/null; then
  echo "rclone not found. Install: brew install rclone" >&2
  exit 1
fi

for f in static/data/search_*.db static/data/detail_*.db; do
  [ -e "$f" ] || continue
  echo "Uploading $(basename "$f") ($(du -h "$f" | cut -f1 | tr -d ' '))..."
  rclone copyto "$f" "r2:${BUCKET}/$(basename "$f")" --s3-upload-cutoff 100M --s3-chunk-size 100M --progress
done

echo "Done. Files served at: https://<public-r2-dev-subdomain>.r2.dev/<name>.db"
echo "Set VITE_DATA_BASE_URL to that base URL when building the site."
