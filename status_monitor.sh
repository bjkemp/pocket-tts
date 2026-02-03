#!/bin/bash

# Simple background monitor for Pocket TTS
# Notifies you when server starts or stops

PREV_STATUS="unknown"

while true; do
    if curl -s http://localhost:8000/health > /dev/null; then
        STATUS="running"
    else
        STATUS="stopped"
    fi

    if [ "$STATUS" != "$PREV_STATUS" ]; then
        if [ "$STATUS" == "running" ]; then
            osascript -e 'display notification "Pocket TTS server is now active." with title "Pocket TTS" subtitle "Smooth Mode Enabled"'
        else
            osascript -e 'display notification "Pocket TTS server has stopped." with title "Pocket TTS" subtitle "Slow Mode (Loading per call)"'
        fi
        PREV_STATUS="$STATUS"
    fi
    
    sleep 10
done
