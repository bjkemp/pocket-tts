#!/bin/bash
# scripts/list_all_voices.sh
# Optimized version to spider tts-voices quickly

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
VOICES_DIR="$PROJECT_DIR/tts-voices"

{
    # Predefined voices
    printf "alba\nmarius\njavert\njean\nfantine\ncosette\neponine\nazelma\n"

    if [ -d "$VOICES_DIR" ]; then
        # Faster approach: find all safetensors first, then wavs
        # Use sed to extract the name (text before the first dot)
        find "$VOICES_DIR" -type f -size +1k -name "*.safetensors" -not -path "*/.*" -exec basename {} \; | sed 's/\..*//'
        
        # Then find wavs that don't have a matching safetensors
        # Actually, let's just grab all valid names and let sort -u handle duplicates
        find "$VOICES_DIR" -type f -size +1k -name "*.wav" -not -path "*/.*" -exec basename {} \; | sed 's/\.wav//'
    fi
} | sort -u
