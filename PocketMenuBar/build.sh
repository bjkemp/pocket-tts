#!/bin/bash

# Build script for Pocket TTS Menu Bar app
# Compiles the Swift code into a standalone macOS app bundle

APP_NAME="PocketTTSBar"
BUILD_DIR="build"
CONTENTS_DIR="$BUILD_DIR/$APP_NAME.app/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Clean up
rm -rf "$BUILD_DIR"

# Create structure
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

echo "Compiling Objective-C source..."
clang -fobjc-arc -framework AppKit -framework Foundation -o "$MACOS_DIR/$APP_NAME" menu.m

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>org.kyutai.pocket-tts-bar</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

echo "Build complete! You can find the app in PocketMenuBar/build/$APP_NAME.app"
echo "To run it: open PocketMenuBar/build/$APP_NAME.app"
