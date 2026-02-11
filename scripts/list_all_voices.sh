#!/bin/bash
# scripts/list_all_voices.sh
# Spiders tts-voices and returns a list of unique voice names.
# Prioritizes .safetensors over .wav to avoid duplicates and loading errors.

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
VOICES_DIR="$PROJECT_DIR/tts-voices"

{
    # Start with hardcoded defaults (predefined in the model)
    echo "alba"
    echo "marius"
    echo "javert"
    echo "jean"
    echo "fantine"
    echo "cosette"
    echo "eponine"
    echo "azelma"

    if [ -d "$VOICES_DIR" ]; then
        # Find all valid files > 1KB
        find "$VOICES_DIR" -type f \( -name "*.wav" -o -name "*.safetensors" \) -size +1k -not -path "*/.*" | while read -r file; do
            basename=$(basename "$file")
            
            if [[ "$basename" == *".safetensors" ]]; then
                # For safetensors, extract the name before the FIRST dot
                # e.g. "ASEN.wav.1e68beda@240.safetensors" -> "ASEN"
                echo "${basename%%.*}"
            else
                # For wav, check if a safetensors version already exists
                name="${basename%.*}"
                # If we find any safetensors file starting with this name, skip the wav
                if ! find "$VOICES_DIR" -name "${name}*.safetensors" -size +1k | grep -q .; then
                    echo "$name"
                fi
            fi
        done
    fi
} | sort -u
