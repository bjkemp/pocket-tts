"""Integration tests for the CLI generate command using real implementation."""

import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pocket_tts.data.audio import audio_read
from pocket_tts.default_parameters import DEFAULT_VARIANT
from pocket_tts.main import cli_app

other_voice = "https://huggingface.co/kyutai/tts-voices/resolve/main/expresso/ex01-ex02_default_001_channel1_168s.wav"

runner = CliRunner()

IS_CI = os.environ.get("CI") == "true"
CI_SKIP_REASON = "Voice cloning is not publicly available, skipping in the CI"


def test_generate_basic_usage(tmp_path):
    """Test basic generate command with default parameters."""
    output_file = tmp_path / "test_output.wav"

    result = runner.invoke(
        cli_app,
        ["generate", "--text", "Hello world, this is a test.", "--output-path", str(output_file)],
    )

    assert result.exit_code == 0
    # Verify output file was created and contains audio
    assert output_file.exists()
    assert output_file.stat().st_size > 0

    # Verify it's a valid audio file
    audio, sample_rate = audio_read(str(output_file))
    assert audio.shape[0] == 1  # Mono channel
    assert audio.shape[1] > 0  # Has audio samples
    assert sample_rate == 24000  # Expected sample rate


@pytest.mark.skipif(IS_CI, reason=CI_SKIP_REASON)
def test_generate_with_custom_voice(tmp_path):
    """Test generate command with custom voice prompt."""
    output_file = tmp_path / "custom_voice_test.wav"

    result = runner.invoke(
        cli_app,
        [
            "generate",
            "--text",
            "Testing custom voice.",
            "--voice",
            other_voice,
            "--output-path",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()

    # Verify audio content
    audio, sample_rate = audio_read(str(output_file))
    assert audio.shape[0] == 1  # Mono channel
    assert audio.shape[1] > 0  # Has audio samples
    assert sample_rate == 24000


def test_generate_with_custom_parameters(tmp_path):
    """Test generate command with custom generation parameters."""
    output_file = tmp_path / "custom_params_test.wav"

    result = runner.invoke(
        cli_app,
        [
            "generate",
            "--text",
            "Testing custom parameters.",
            "--config",
            DEFAULT_VARIANT,
            "--temperature",
            "0.8",
            "--lsd-decode-steps",
            "2",
            "--eos-threshold",
            "-3.0",
            "--frames-after-eos",
            "7",
            "--output-path",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()

    audio, sample_rate = audio_read(str(output_file))
    assert audio.shape[0] == 1  # Mono channel
    assert audio.shape[1] > 0  # Has audio samples
    assert sample_rate == 24000


def test_generate_verbose_mode(tmp_path):
    """Test generate command with verbose logging."""
    output_file = tmp_path / "verbose_test.wav"

    result = runner.invoke(
        cli_app,
        ["generate", "--text", "Testing verbose mode.", "-q", "--output-path", str(output_file)],
    )

    assert result.exit_code == 0
    assert output_file.exists()


def test_generate_default_text(tmp_path):
    """Test generate command with default text when no text provided."""
    output_file = tmp_path / "default_text_test.wav"

    result = runner.invoke(cli_app, ["generate", "--output-path", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()

    audio, sample_rate = audio_read(str(output_file))
    assert audio.shape[0] == 1  # Mono channel
    assert audio.shape[1] > 0  # Has audio samples
    assert sample_rate == 24000


def test_generate_long_text(tmp_path):
    """Test generate command with longer text."""
    long_text = "This is a longer text to test the TTS system. " * 5
    output_file = tmp_path / "long_text_test.wav"

    result = runner.invoke(
        cli_app, ["generate", "--text", long_text, "--output-path", str(output_file)]
    )

    assert result.exit_code == 0
    assert output_file.exists()

    audio, sample_rate = audio_read(str(output_file))
    assert audio.shape[0] == 1  # Mono channel
    assert audio.shape[1] > 0  # Has audio samples
    assert sample_rate == 24000
    # Longer text should produce longer audio
    assert audio.shape[1] > 24000 * 10  # At least 10 second of audio


def test_generate_multiple_runs(tmp_path):
    """Test multiple consecutive generate commands."""
    for i in range(3):
        output_file = tmp_path / f"test_run_{i + 1}.wav"

        result = runner.invoke(
            cli_app,
            [
                "generate",
                "--text",
                f"This is test run number {i + 1}.",
                "--output-path",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        audio, sample_rate = audio_read(str(output_file))
        assert audio.shape[0] == 1  # Mono channel
        assert audio.shape[1] > 0  # Has audio samples
        assert sample_rate == 24000

def test_generate_with_persona(tmp_path, monkeypatch):
    """Test generate command with a persona using a local voice."""
    # Create a dummy voice file
    voices_dir = tmp_path / "tts-voices"
    voices_dir.mkdir()
    dummy_voice_file = voices_dir / "local_test_voice.wav"
    # Create a minimal valid WAV file header
    dummy_voice_file.write_bytes(b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\xbb\x00\x00\x00\xee\x02\x00\x04\x00\x10\x00data\x00\x00\x00\x00')

    # Create persona file pointing to the local voice by name
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    persona_file = personas_dir / "local_test.md"
    persona_file.write_text("""
---
name: Local Test Persona
voice: "local_test_voice"
---
""")

    monkeypatch.setenv("POCKET_TTS_PERSONAS_DIR", str(personas_dir))
    monkeypatch.setenv("POCKET_TTS_VOICES_DIR", str(voices_dir))

    output_file = tmp_path / "persona_test.wav"
    result = runner.invoke(
        cli_app,
        [
            "generate",
            "--persona",
            "local_test",
            "--output-path",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()

    audio, sample_rate = audio_read(str(output_file))
    assert audio.shape[0] == 1
    assert audio.shape[1] > 0
    assert sample_rate == 24000

def test_list_personas_cli(tmp_path, monkeypatch):
    """Test the list-personas CLI command."""
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    (personas_dir / "test1.md").write_text("---\nname: T1\n---\n")
    (personas_dir / "test2.md").write_text("---\nname: T2\n---\n")

    monkeypatch.setenv("POCKET_TTS_PERSONAS_DIR", str(personas_dir))

    result = runner.invoke(cli_app, ["list-personas"])

    assert result.exit_code == 0
    assert "test1" in result.stdout
    assert "test2" in result.stdout

def test_generate_with_speed(tmp_path):
    """Test generate command with speed parameter."""
    output_file_normal = tmp_path / "normal_speed.wav"
    output_file_fast = tmp_path / "fast_speed.wav"

    # Generate at normal speed
    result_normal = runner.invoke(
        cli_app,
        ["generate", "--text", "This is a test sentence.", "--output-path", str(output_file_normal)],
    )
    assert result_normal.exit_code == 0
    audio_normal, _ = audio_read(str(output_file_normal))

    # Generate at faster speed
    with patch('torchaudio.functional.speed') as mock_speed:
        result_fast = runner.invoke(
            cli_app,
            ["generate", "--text", "This is a test sentence.", "--speed", "1.5", "--output-path", str(output_file_fast)],
        )
        assert result_fast.exit_code == 0
        mock_speed.assert_called_once()

    audio_fast, _ = audio_read(str(output_file_fast))

    # The faster audio should be shorter
    assert audio_fast.shape[1] < audio_normal.shape[1]
