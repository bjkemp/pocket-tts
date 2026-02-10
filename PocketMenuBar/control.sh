#!/bin/bash

# Get the directory where this script is located
# Since this script is in PocketMenuBar/, PROJECT_DIR is the parent
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_DIR"

COMMAND=$1
VALUE=$2

case $COMMAND in
    start)
        ./scripts/start_server.sh
        ;;
    stop)
        pkill -f "pocket-tts serve"
        ;;
    voice)
        echo "$VALUE" > .current_voice
        ;;
    headphones)
        if [ -f .headphones_only ]; then
            rm .headphones_only
        else
            echo "1" > .headphones_only
        fi
        ;;
    test)
        ./pocket-say "Pocket TTS, it really whips the llama's ass!"
        ;;
esac
