#!/bin/bash

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
        rm -f .current_persona
        ;;
    persona)
        echo "$VALUE" > .current_persona
        rm -f .current_voice
        ;;
    headphones)
        if [ -f .headphones_only ]; then
            rm .headphones_only
        else
            echo "1" > .headphones_only
        fi
        ;;
    mute)
        if [ -f .muted ]; then
            rm .muted
        else
            echo "1" > .muted
        fi
        ;;
    test)
        ./pocket-say "Pocket TTS, it really whips the llama's ass!"
        if [ $? -ne 0 ]; then
            echo "1" > .error
        else
            rm -f .error
        fi
        ;;
esac
