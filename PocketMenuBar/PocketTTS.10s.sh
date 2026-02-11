#!/bin/bash

# <bitbar.title>Pocket TTS Controller</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>
# <bitbar.author>Gemini</bitbar.author>
# <bitbar.desc>Controls Pocket TTS local server and voices</bitbar.desc>

# Get the directory where this script is located, resolving symlinks
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
# Since this script is in PocketMenuBar/, PROJECT_DIR is the parent
PROJECT_DIR="$( cd -P "$( dirname "$SOURCE" )/.." && pwd )"
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
    echo "Test Voice | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=test terminal=false"
else
    echo "Start Service | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=start terminal=false"
    echo "Test Voice | color=gray"
fi

MUTE_CHECK=""
if [ -f ".muted" ]; then MUTE_CHECK="✅ "; fi
echo "$MUTE_CHECK""Mute | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=mute terminal=false"

HP_CHECK=""
if [ -f ".headphones_only" ]; then HP_CHECK="✅ "; fi
echo "$HP_CHECK""Headphones Only | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=headphones terminal=false"

echo "---"
echo "Default Voice"

CURRENT_VOICE="alba"
if [ -f ".current_voice" ]; then
    CURRENT_VOICE=$(cat .current_voice)
fi

# Dynamically populate voices from tts-voices directory
VOICES=()
VOICE_DIRS=$(find "$PROJECT_DIR/tts-voices" -mindepth 1 -maxdepth 1 -type d -not -name ".git")
for dir in $VOICE_DIRS; do
    VOICES+=("$(basename "$dir")")
done

for v in "${VOICES[@]}"; do
    CHECK=""
    if [ "$v" == "$CURRENT_VOICE" ]; then CHECK="✅ "; fi
    echo "$CHECK$v | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=voice param2=$v terminal=false"
done

echo "---"
echo "Default Persona"

CURRENT_PERSONA="narrator"
if [ -f ".current_persona" ]; then
    CURRENT_PERSONA=$(cat .current_persona)
fi

# Dynamically populate personas from personas directory
PERSONAS=()
PERSONA_FILES=$(find "$PROJECT_DIR/personas" -name "*.md")
for file in $PERSONA_FILES; do
    PERSONAS+=("$(basename "$file" .md)")
done

for p in "${PERSONAS[@]}"; do
    CHECK=""
    if [ "$p" == "$CURRENT_PERSONA" ]; then CHECK="✅ "; fi
    echo "$CHECK$p | bash=$PROJECT_DIR/PocketMenuBar/control.sh param1=persona param2=$p terminal=false"
done

echo "---"
echo "Refresh | refresh=true"
