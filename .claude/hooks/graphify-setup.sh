#!/usr/bin/env bash
# SessionStart hook: make sure the graphify CLI exists on this machine and the
# committed knowledge graph matches the checked-out code. Never blocks the session.

export PATH="$HOME/.local/bin:$PATH"

if ! command -v graphify >/dev/null 2>&1; then
  echo "[graphify] CLI not found, installing graphifyy..." >&2
  if command -v uv >/dev/null 2>&1; then
    uv tool install graphifyy >&2 || true
  elif command -v pipx >/dev/null 2>&1; then
    pipx install graphifyy >&2 || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m pip install --user graphifyy >&2 || true
  elif command -v python >/dev/null 2>&1; then
    python -m pip install --user graphifyy >&2 || true
  fi
fi

if ! command -v graphify >/dev/null 2>&1; then
  echo "[graphify] install skipped: needs Python 3.10+ and uv/pipx. See GRAPHIFY.md" >&2
  exit 0
fi

# Persist PATH for the rest of the session (Claude Code provides CLAUDE_ENV_FILE).
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo "export PATH=\"$HOME/.local/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi

# Refresh the graph after a pull on another machine (AST only, no LLM cost).
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if [ -f graphify-out/graph.json ]; then
  GRAPHIFY_BACKEND=none graphify update . >/dev/null 2>&1 || true
fi

exit 0
