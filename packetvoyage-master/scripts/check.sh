#!/usr/bin/env bash
set -euo pipefail

# プロジェクトルートディレクトリに移動
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo " Running Local CI Checks for packetvoyage "
echo "=========================================="

echo -e "\n[1/3] Running Ruff (Lint & Formatting)..."
uv run ruff check .
uv run ruff format --check .

echo -e "\n[2/3] Running Pytest..."
uv run pytest

echo -e "\n[3/3] Building package (Wheel & Sdist)..."
uv build

echo -e "\n=========================================="
echo " All local checks passed successfully!"
echo "=========================================="
