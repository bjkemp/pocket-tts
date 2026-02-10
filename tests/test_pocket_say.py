import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def test_env():
    """Sets up a temporary environment for testing pocket-say."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        # Copy pocket-say to tmp_dir
        pocket_say_src = Path(__file__).parent.parent / "pocket-say"
        pocket_say_dest = tmp_path / "pocket-say"
        shutil.copy(pocket_say_src, pocket_say_dest)
        pocket_say_dest.chmod(0o755)

        # Create scripts dir and a dummy start_server.sh
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        start_server = scripts_dir / "start_server.sh"
        start_server.write_text("#!/bin/bash\nexit 0")
        start_server.chmod(0o755)

        # Create dummy curl
        curl_mock = bin_dir / "curl"
        curl_mock.write_text("""#!/bin/bash
while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            # Create a dummy wav file
            echo "RIFF....WAVE" > "$2"
            shift 2
            ;;
        --data-urlencode)
            if [[ "$2" == voice_url=* ]]; then
                echo "VOICE: ${2#voice_url=}" >> "$TEST_LOG"
            fi
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done
exit 0
""")
        curl_mock.chmod(0o755)

        # Create dummy afplay
        afplay_mock = bin_dir / "afplay"
        afplay_mock.write_text("#!/bin/bash\necho \"PLAYING\" >> \"$TEST_LOG\"\nexit 0")
        afplay_mock.chmod(0o755)

        # Create dummy system_profiler
        system_profiler_mock = bin_dir / "system_profiler"
        system_profiler_mock.write_text("""#!/bin/bash
cat "$AUDIO_STATE_FILE"
exit 0
""")
        system_profiler_mock.chmod(0o755)

        # State files
        audio_state_file = tmp_path / "audio_state.txt"
        test_log = tmp_path / "test_log.txt"

        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        env["AUDIO_STATE_FILE"] = str(audio_state_file)
        env["TEST_LOG"] = str(test_log)

        yield {
            "tmp_path": tmp_path,
            "pocket_say": str(pocket_say_dest),
            "audio_state_file": audio_state_file,
            "test_log": test_log,
            "env": env,
        }


def test_pocket_say_basic_play(test_env):
    """Test that pocket-say plays audio by default."""
    subprocess.run([test_env["pocket_say"], "hello"], env=test_env["env"], check=True)

    log_content = test_env["test_log"].read_text()
    assert "PLAYING" in log_content


def test_pocket_say_headphones_only_enabled_with_headphones(test_env):
    """Test that pocket-say plays audio if headphones_only is on and headphones are connected."""
    # Enable headphones only
    (test_env["tmp_path"] / ".headphones_only").write_text("1")

    # Mock headphones connected
    test_env["audio_state_file"].write_text("""
        Benjamin's Pixel Buds Pro 2:
          Default Output Device: Yes
          Transport: Bluetooth
""")

    subprocess.run([test_env["pocket_say"], "hello"], env=test_env["env"], check=True)

    log_content = test_env["test_log"].read_text()
    assert "PLAYING" in log_content


def test_pocket_say_headphones_only_enabled_with_speakers(test_env):
    """Test that pocket-say DOES NOT play audio if headphones_only is on and speakers are connected."""
    # Enable headphones only
    (test_env["tmp_path"] / ".headphones_only").write_text("1")

    # Mock speakers connected
    test_env["audio_state_file"].write_text("""
        MacBook Pro Speakers:
          Default Output Device: Yes
          Transport: Built-in
""")

    subprocess.run([test_env["pocket_say"], "hello"], env=test_env["env"], check=True)

    if test_env["test_log"].exists():
        log_content = test_env["test_log"].read_text()
        assert "PLAYING" not in log_content


def test_pocket_say_headphones_only_disabled_with_speakers(test_env):
    """Test that pocket-say plays audio if headphones_only is off, even with speakers."""
    # No .headphones_only file

    # Mock speakers connected
    test_env["audio_state_file"].write_text("""
        MacBook Pro Speakers:
          Default Output Device: Yes
          Transport: Built-in
""")

    subprocess.run([test_env["pocket_say"], "hello"], env=test_env["env"], check=True)

    log_content = test_env["test_log"].read_text()
    assert "PLAYING" in log_content


def test_pocket_say_headphones_only_enabled_with_wired_headphones(test_env):
    """Test that pocket-say plays audio if headphones_only is on and wired headphones are connected."""
    # Enable headphones only
    (test_env["tmp_path"] / ".headphones_only").write_text("1")

    # Mock wired headphones
    test_env["audio_state_file"].write_text("""
        External Headphones:
          Default Output Device: Yes
          Transport: Built-in
""")

    subprocess.run([test_env["pocket_say"], "hello"], env=test_env["env"], check=True)

    log_content = test_env["test_log"].read_text()
    assert "PLAYING" in log_content


def test_pocket_say_via_symlink(test_env):
    """Test that pocket-say correctly identifies PROJECT_DIR when called via a symlink."""
    # Create a .current_voice file in the real project dir
    (test_env["tmp_path"] / ".current_voice").write_text("azelma")
    
    # Create a symlink in a different directory
    other_bin = test_env["tmp_path"] / "other_bin"
    other_bin.mkdir()
    symlink_path = other_bin / "pocket-say-link"
    os.symlink(test_env["pocket_say"], symlink_path)
    
    # Run via symlink
    subprocess.run([str(symlink_path), "hello"], env=test_env["env"], check=True)
    
    log_content = test_env["test_log"].read_text()
    # If symlink resolution fails, it will use the default 'alba' because it won't find .current_voice
    assert "VOICE: azelma" in log_content
