#!/usr/bin/env bash
# One-time setup per machine (macOS / Linux).
# Installs the graphify CLI and registers the /graphify skill in ~/.claude
# so it works in every project on this computer, not only this repository.
set -e

if ! command -v uv >/dev/null 2>&1 && ! command -v pipx >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if command -v uv >/dev/null 2>&1; then
  uv tool install --upgrade graphifyy
  uv tool update-shell || true
else
  pipx install graphifyy || pipx upgrade graphifyy
fi

export PATH="$HOME/.local/bin:$PATH"
graphify install
graphify --version
echo "Done. Restart your terminal / Claude Code, then type /graphify . in any project."
