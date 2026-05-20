#!/usr/bin/env bash
# scripts/download_data.sh
# Downloads the CMU Movie Summary Corpus into data/raw (project root).
# Cluster: export RAW_DIR=/space_mounts/pars/data/raw before running.
# Run from project root: bash scripts/download_data.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RAW_DIR="${RAW_DIR:-$ROOT_DIR/data/raw}"
mkdir -p "$RAW_DIR"

URL="http://www.cs.cmu.edu/~ark/personas/data/MovieSummaries.tar.gz"
TARBALL="$RAW_DIR/MovieSummaries.tar.gz"

echo "==> Downloading CMU Movie Summary Corpus..."
if command -v wget &> /dev/null; then
    wget -O "$TARBALL" "$URL"
else
    curl -L -o "$TARBALL" "$URL"
fi

echo "==> Extracting..."
tar -xzf "$TARBALL" -C "$RAW_DIR"

# Flatten the extracted MovieSummaries/ subfolder
EXTRACTED="$RAW_DIR/MovieSummaries"
if [ -d "$EXTRACTED" ]; then
    mv "$EXTRACTED"/* "$RAW_DIR/"
    rmdir "$EXTRACTED"
fi

echo "==> Done. Files in $RAW_DIR:"
ls -lh "$RAW_DIR"
