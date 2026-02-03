#!/bin/bash

# <bitbar.title>Pocket TTS Controller</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>
# <bitbar.author>Gemini</bitbar.author>
# <bitbar.desc>Controls Pocket TTS local server and voices</bitbar.desc>

PROJECT_DIR="/Users/kempb/Projects/pocket-tts"
cd "$PROJECT_DIR"

# Check status
if curl -s http://localhost:8000/health > /dev/null; then
    echo "🎙️ | color=green"
    RUNNING=true
else
    echo "🚫 | color=red"
    RUNNING=false
fi

echo "---"

if [ "$RUNNING" = true ]; then
    echo "Stop Service | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=stop terminal=false"
else
    echo "Start Service | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=start terminal=false"
fi

echo "---"
echo "Active Voice"

CURRENT_VOICE="alba"
if [ -f ".current_voice" ]; then
    CURRENT_VOICE=$(cat .current_voice)
fi

VOICES=("alba" "marius" "javert" "jean" "fantine" "cosette" "eponine" "azelma")

for v in "${VOICES[@]}"; do
    CHECK=""
    if [ "$v" == "$CURRENT_VOICE" ]; then CHECK="✅ "; fi
    echo "$CHECK$v | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=voice param2=$v terminal=false"
done

echo "---"
echo "Refresh | refresh=true"
