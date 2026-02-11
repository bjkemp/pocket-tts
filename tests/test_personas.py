import tempfile
from pathlib import Path
import pytest
from pocket_tts.personas import load_persona, list_personas

def test_load_persona():
    persona_content = """---
name: Test Persona
voice: test_voice.wav
temperature: 0.8
speed: 1.2
---
This is a test persona.
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        persona_dir = Path(tmpdir) / "personas"
        persona_dir.mkdir()
        persona_file = persona_dir / "test.md"
        persona_file.write_text(persona_content)

        persona_data = load_persona("test", persona_dir)

        assert persona_data["name"] == "Test Persona"
        assert persona_data["voice"] == "test_voice.wav"
        assert persona_data["temperature"] == 0.8
        assert persona_data["speed"] == 1.2

def test_load_persona_not_found():
    with pytest.raises(FileNotFoundError):
        load_persona("non_existent_persona")

def test_list_personas():
    with tempfile.TemporaryDirectory() as tmpdir:
        persona_dir = Path(tmpdir) / "personas"
        persona_dir.mkdir()
        (persona_dir / "persona1.md").write_text("---\nname: P1\n---\n")
        (persona_dir / "persona2.md").write_text("---\nname: P2\n---\n")
        (persona_dir / "not_a_persona.txt").write_text("Hello")

        personas = list_personas(persona_dir)
        assert len(personas) == 2
        assert "persona1" in personas
        assert "persona2" in personas
        assert "not_a_persona" not in personas
