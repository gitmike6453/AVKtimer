#!/bin/bash
# Builds the macOS .app bundle and packages it into a .dmg.
# Must run on macOS (Apple does not allow cross-compiling .app bundles).
# Run from the repository root: bash packaging/macos/build_mac.sh
set -euo pipefail

APP_NAME="AVKtimer"
VERSION="${1:-1.7}"

pip3 install --quiet --upgrade pyinstaller screeninfo flask psutil requests pillow tkmacosx

python3 -m PyInstaller --noconfirm --onefile --windowed \
    --name "$APP_NAME" \
    --icon "assets/app.icns" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --add-data "assets/alarme.mp3:." \
    --add-data "assets/alarme1.mp3:." \
    --add-data "assets/alarme2.mp3:." \
    "avktimer.py"

# Removes the macOS quarantine flag so the unsigned build launches without a Gatekeeper block.
xattr -cr "dist/${APP_NAME}.app"

DMG_DIR="dist/dmg_root"
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"
cp -R "dist/${APP_NAME}.app" "$DMG_DIR/"
ln -s /Applications "$DMG_DIR/Applications"

hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_DIR" -ov -format UDZO \
    "dist/${APP_NAME}_v${VERSION}.dmg"

echo "Built dist/${APP_NAME}_v${VERSION}.dmg"
