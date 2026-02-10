#!/bin/bash

# setup_launch_agent.sh: Sets up the Pocket TTS server to run on login
# This script creates a macOS Launch Agent.

PLIST_NAME="com.pocket.tts.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
PROJECT_DIR="/Users/kempb/Projects/pocket-tts"
UV_PATH="/Users/kempb/.local/bin/uv"

echo "Creating Launch Agent plist..."

cat <<EOF > "$PLIST_NAME"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pocket.tts</string>
    <key>ProgramArguments</key>
    <array>
        <string>$UV_PATH</string>
        <string>--native-tls</string>
        <string>run</string>
        <string>pocket-tts</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/server.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/server.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/kempb/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "Plist created at ./$PLIST_NAME"
echo "You can now run: sudo mv $PLIST_NAME $PLIST_DEST && launchctl load $PLIST_DEST"

# Make it executable just in case they want to run it directly
chmod +x setup_launch_agent.sh
