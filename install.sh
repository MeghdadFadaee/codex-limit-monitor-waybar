#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
CONFIGURE_WAYBAR=false
SECTION=""
RESTART=false

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --configure-waybar       Add the module to ~/.config/waybar/config.jsonc
  --section SECTION        Placement: left, center, or right
  --restart                Restart Waybar after configuration
  -h, --help               Show this help
EOF
}

while (($#)); do
  case "$1" in
    --configure-waybar) CONFIGURE_WAYBAR=true ;;
    --section)
      SECTION="${2:-}"
      shift
      ;;
    --restart) RESTART=true ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

install -d "$BIN_DIR"
install -m 0755 "$ROOT/bin/codex-waybar" "$BIN_DIR/codex-waybar"
install -m 0755 "$ROOT/bin/codex-waybar-configure" "$BIN_DIR/codex-waybar-configure"
echo "Installed codex-waybar commands in $BIN_DIR"

if [[ "$CONFIGURE_WAYBAR" == true ]]; then
  if [[ -z "$SECTION" ]]; then
    read -r -p "Waybar section [right]: " SECTION
    SECTION="${SECTION:-right}"
  fi
  case "$SECTION" in
    left|center|right) ;;
    *)
      echo "Section must be left, center, or right" >&2
      exit 2
      ;;
  esac
  "$BIN_DIR/codex-waybar-configure" --section "$SECTION"
fi

if [[ "$RESTART" == true ]]; then
  if command -v omarchy >/dev/null 2>&1; then
    omarchy restart waybar
  else
    pkill -SIGUSR2 waybar
  fi
fi
