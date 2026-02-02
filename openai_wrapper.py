#!/usr/bin/env python3
"""
OpenAI-compatible API wrapper for Pocket TTS
Makes Pocket TTS compatible with OpenClaw's TTS system
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
import uvicorn

app = FastAPI(title="Pocket TTS OpenAI Wrapper")

POCKET_TTS_URL = "http://localhost:8000/tts"


class TTSRequest(BaseModel):
    model: str  # Ignored, Pocket TTS only has one model
    input: str
    voice: str  # Ignored for now, Pocket TTS uses preset voice


@app.post("/v1/audio/speech")
async def create_speech(request: TTSRequest):
    """OpenAI-compatible TTS endpoint that forwards to Pocket TTS"""
    try:
        async with httpx.AsyncClient() as client:
            # Forward to Pocket TTS
            response = await client.post(
                POCKET_TTS_URL,
                data={"text": request.input},
                timeout=30.0,
            )
            response.raise_for_status()

            # Return the audio file with correct content type
            return Response(
                content=response.content,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": 'inline; filename="speech.wav"'
                }
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Pocket TTS error: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "backend": "pocket-tts"}


if __name__ == "__main__":
    print("Starting OpenAI-compatible wrapper for Pocket TTS on port 8001")
    print("Pocket TTS backend: http://localhost:8000")
    print("OpenAI endpoint: http://localhost:8001/v1/audio/speech")
    uvicorn.run(app, host="127.0.0.1", port=8001)
