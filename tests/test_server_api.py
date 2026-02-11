import textwrap
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest
from pathlib import Path

from pocket_tts.main import web_app

# A known voice URL for testing
other_voice = "https://huggingface.co/kyutai/tts-voices/resolve/main/expresso/ex01-ex02_default_001_channel1_168s.wav"

@pytest.fixture
def mock_tts_model(monkeypatch):
    """Mocks the global tts_model."""
    mock_model = MagicMock()
    mock_model.config.mimi.sample_rate = 24000
    # Make the generate_audio_stream method return an empty generator to avoid type violations
    mock_model.generate_audio_stream.return_value = (i for i in [])
    
    # Mock the state-related methods
    dummy_state = {"dummy_state": True}
    mock_model._cached_get_state_for_audio_prompt.return_value = dummy_state
    mock_model.get_state_for_audio_prompt.return_value = dummy_state
    
    monkeypatch.setattr("pocket_tts.main.tts_model", mock_model)
    # Also need to mock global_model_state which is set during server startup
    monkeypatch.setattr("pocket_tts.main.global_model_state", dummy_state)
    return mock_model

def test_openai_speech_with_persona(tmp_path, monkeypatch, mock_tts_model):
    """Test the /v1/audio/speech endpoint with a persona."""
    # Create persona file
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    persona_file = personas_dir / "test.md"
    persona_file.write_text(f"""---
name: Test Persona
voice: "{other_voice}"
temperature: 0.75
---
A test persona.
""")
    monkeypatch.setenv("POCKET_TTS_PERSONAS_DIR", str(personas_dir))

    client = TestClient(web_app)
    response = client.post("/v1/audio/speech", json={"input": "hello", "persona": "test"})

    assert response.status_code == 200
    # The voice from the persona should be used
    mock_tts_model._cached_get_state_for_audio_prompt.assert_called_with(other_voice)

def test_tts_endpoint_with_persona(tmp_path, monkeypatch, mock_tts_model):
    """Test the /tts endpoint with a persona."""
    # Create persona file
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    persona_file = personas_dir / "test.md"
    persona_file.write_text(f"""---
name: Test Persona
voice: "{other_voice}"
---
A test persona.
""")
    monkeypatch.setenv("POCKET_TTS_PERSONAS_DIR", str(personas_dir))

    client = TestClient(web_app)
    response = client.post("/tts", data={"text": "hello", "persona": "test"})

    assert response.status_code == 200
    # The voice from the persona should be used
    mock_tts_model._cached_get_state_for_audio_prompt.assert_called_with(other_voice)

