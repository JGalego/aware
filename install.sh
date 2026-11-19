#!/usr/bin/env bash
# Installs aware: clones the repo and links `aware` into ~/.local/bin.
# Usage: curl -fsSL https://raw.githubusercontent.com/JGalego/aware/main/install.sh | bash
# Env: AWARE_REPO (git URL), AWARE_HOME (checkout dir), AWARE_BIN (link dir).
set -euo pipefail

REPO="${AWARE_REPO:-https://github.com/JGalego/aware.git}"
HOME_DIR="${AWARE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/aware}"
BIN_DIR="${AWARE_BIN:-$HOME/.local/bin}"

for cmd in git bash jq tmux python3 claude; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "aware: missing required command: $cmd" >&2; exit 1; }
done

if [ -d "$HOME_DIR/.git" ]; then
  echo "Updating $HOME_DIR"
  git -C "$HOME_DIR" pull --ff-only --quiet
else
  echo "Cloning into $HOME_DIR"
  git clone --depth 1 --quiet "$REPO" "$HOME_DIR"
fi

mkdir -p "$BIN_DIR"
ln -sfn "$HOME_DIR/aware" "$BIN_DIR/aware"
echo "Linked $BIN_DIR/aware"

case ":$PATH:" in
  *":$BIN_DIR:"*) echo "Done. Run: aware launch" ;;
  *) echo "Done. Add $BIN_DIR to your PATH (export PATH=\"$BIN_DIR:\$PATH\"), then run: aware launch" ;;
esac
