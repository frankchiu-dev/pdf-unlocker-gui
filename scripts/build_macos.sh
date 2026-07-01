#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRY="$ROOT/pdf_unlocker.py"
ICON="$ROOT/assets/pdf_unlocker.icns"
DIST="$ROOT/dist"
BUILD="$ROOT/build/pyinstaller"
SPEC="$ROOT/build/spec"

ICON_ARGS=()
if [[ -f "$ICON" ]]; then
  ICON_ARGS=(--icon "$ICON")
fi

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "PDFUnlocker" \
  "${ICON_ARGS[@]}" \
  --add-data "$ROOT/assets/pdf_unlocker.ico:." \
  --collect-data customtkinter \
  --collect-all tkinterdnd2 \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  --specpath "$SPEC" \
  "$ENTRY"

if [[ -d "$DIST/PDFUnlocker.app" ]]; then
  ditto -c -k --sequesterRsrc --keepParent "$DIST/PDFUnlocker.app" "$DIST/PDFUnlocker-macOS.zip"
  echo "Done: $DIST/PDFUnlocker.app"
  echo "Zip:  $DIST/PDFUnlocker-macOS.zip"
else
  echo "Build finished, but $DIST/PDFUnlocker.app was not found." >&2
  exit 1
fi
