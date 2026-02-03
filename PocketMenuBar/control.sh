#!/bin/bash

PROJECT_DIR="/Users/kempb/Projects/pocket-tts"
cd "$PROJECT_DIR"

COMMAND=$1
VALUE=$2

case $COMMAND in
    start)
        ./start_server.sh
        ;;
    stop)
        pkill -f "pocket-tts serve"
        ;;
    voice)
        echo "$VALUE" > .current_voice
        ;;
esac
