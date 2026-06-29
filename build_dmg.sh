#!/bin/bash
# Kawkab AI — macOS DMG builder
# Requires: create-dmg (brew install create-dmg) or genisoimage

set -e

VERSION="0.13.0"
APP_NAME="KawkabAI"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
DIST_DIR="dist"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"

echo "[DMG] Building ${DMG_NAME}..."

# Create .app bundle structure if not exists
if [ ! -d "${APP_BUNDLE}" ]; then
    mkdir -p "${APP_BUNDLE}/Contents/MacOS"
    mkdir -p "${APP_BUNDLE}/Contents/Resources"

    # Create Info.plist
    cat > "${APP_BUNDLE}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.kawkabai.app</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

    # Copy binary
    if [ -f "${DIST_DIR}/${APP_NAME}" ]; then
        cp "${DIST_DIR}/${APP_NAME}" "${APP_BUNDLE}/Contents/MacOS/"
    else
        echo "Warning: No binary found at dist/${APP_NAME}. Create a symlink to the launcher."
    fi

    chmod +x "${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
fi

# Create DMG using create-dmg or fallback
if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "assets/icon.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 190 \
        "${DIST_DIR}/${DMG_NAME}" \
        "${APP_BUNDLE}"
elif command -v genisoimage &> /dev/null; then
    mkdir -p "${DIST_DIR}/dmg"
    cp -R "${APP_BUNDLE}" "${DIST_DIR}/dmg/"
    ln -s "/Applications" "${DIST_DIR}/dmg/Applications"
    genisoimage -V "${APP_NAME}" -D -R -apple -no-pad \
        -o "${DIST_DIR}/${DMG_NAME}" "${DIST_DIR}/dmg"
    rm -rf "${DIST_DIR}/dmg"
else
    echo "Warning: Neither create-dmg nor genisoimage found. Skipping DMG creation."
    echo "Install create-dmg: brew install create-dmg"
    exit 0
fi

echo "[DMG] ✅ Created ${DIST_DIR}/${DMG_NAME}"
