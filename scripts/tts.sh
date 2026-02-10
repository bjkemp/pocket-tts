#!/bin/bash
# Wrapper for pocket-tts with corporate firewall workaround (--native-tls).
# Usage: ./tts.sh generate --text "Hello" --voice alba
#        ./tts.sh serve

uv --native-tls run pocket-tts "$@"
