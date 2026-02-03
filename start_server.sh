#!/bin/bash

# Starts the pocket-tts server in the background
# Usage: ./start_server.sh

# Check if already running
if curl -s http://localhost:8000/health > /dev/null; then
    echo "Server is already running."
    exit 0
fi

echo "Starting pocket-tts server in background..."
uv --native-tls run pocket-tts serve > server.log 2>&1 &

# Wait for server to be ready
echo "Waiting for server to initialize (this may take a few seconds)..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "Server is ready!"
        exit 0
    fi
    sleep 1
done

echo "Server failed to start within 30 seconds. Check server.log for details."
exit 1
