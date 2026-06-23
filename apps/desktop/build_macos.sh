#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV=".venv/bin"
PYINSTALLER="$VENV/pyinstaller"
SPEC="swuift_app.spec"
DIST_DIR="dist"
TARGET_ARCH="${1:-arm64}"

echo "========================================"
echo " SWUIFT macOS build (Apple Silicon)"
echo " Target architecture: $TARGET_ARCH"
echo "========================================"

if [ "$TARGET_ARCH" != "arm64" ]; then
    echo "ERROR: only arm64 (Apple Silicon) is supported."
    exit 1
fi

if [ ! -f SWUIFT.ico ]; then
    echo "Generating SWUIFT.ico from SWUIFT.icns …"
    "$VENV/python" -c "
from PIL import Image
img = Image.open('SWUIFT.icns')
img.save('SWUIFT.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('  SWUIFT.ico created')
"
fi

echo ""
echo "── Building for arm64 …"
arch -arm64 "$PYINSTALLER" "$SPEC" --noconfirm --clean

APP_PATH="${DIST_DIR}/SWUIFT.app"
DMG_PATH="${DIST_DIR}/SWUIFT_macOS_arm64.dmg"

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: $APP_PATH not found after build."
    exit 1
fi

echo ""
echo "── Creating DMG …"
STAGE=$(mktemp -d)
cp -R "$APP_PATH" "$STAGE/"
hdiutil create \
    -volname "SWUIFT" \
    -srcfolder "$STAGE" \
    -ov \
    -format UDZO \
    "$DMG_PATH"
rm -rf "$STAGE"

echo ""
echo "── Build complete:"
echo "   $APP_PATH"
echo "   $DMG_PATH"
echo "========================================"
