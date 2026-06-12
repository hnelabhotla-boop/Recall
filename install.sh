#!/usr/bin/env bash
# install.sh — symlink `recall` into ~/.local/bin and do an initial index.
#
# Works on macOS and Linux (the indexing source modules auto-skip what isn't
# available; the install itself is platform-agnostic).

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_NAME="recall"
SOURCE="$HERE/recall.py"

# pick a target dir that's likely already in $PATH
TARGET_DIR="$HOME/.local/bin"
mkdir -p "$TARGET_DIR"
TARGET="$TARGET_DIR/$BIN_NAME"

echo "==> installing recall to $TARGET"

# write a small wrapper so `recall` works as a flat command
cat > "$TARGET" <<EOF
#!/usr/bin/env bash
exec python3 "$SOURCE" "\$@"
EOF
chmod +x "$TARGET"

# if ~/.local/bin isn't on PATH, print a friendly hint
case ":$PATH:" in
  *":$TARGET_DIR:"*) ;;
  *)
    echo ""
    echo "  ! $TARGET_DIR is not on your PATH."
    echo "    add this to ~/.zshrc (or ~/.bashrc):"
    echo ""
    echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    ;;
esac

# initial index (best-effort)
echo "==> running initial index (this may take 10-30s)"
python3 "$SOURCE" index || echo "  (initial index had warnings — that's ok)"

# optional: install a global hotkey on macOS via Shortcuts CLI
if [[ "$(uname)" == "Darwin" ]]; then
  echo ""
  echo "  To bind a global hotkey (⌘⇧Space) to open the recall UI:"
  echo "    1. Open the Shortcuts app"
  echo "    2. Create a new shortcut named 'recall' with a single 'Run Shell Script' action:"
  echo "         $SOURCE ui &"
  echo "    3. Add a keyboard shortcut in Shortcuts → Settings → Keyboard: ⌘⇧Space"
  echo ""
  echo "  Or just run:  recall ui  whenever you want the search box."
fi

echo ""
echo "==> done. try:"
echo "      recall status         # see what got indexed"
echo "      recall \"hello world\"  # search the CLI"
echo "      recall ui             # open the web UI"
