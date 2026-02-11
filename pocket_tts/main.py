import io
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path
from queue import Queue

# Disable SSL verification for corporate firewalls
# Add project root's 'tools' directory to path to import the patch
project_root = Path(__file__).parent.parent
tools_dir = project_root / "tools"
if tools_dir.is_dir():
    sys.path.insert(0, str(tools_dir))
    try:
        import disable_ssl_verify  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        # clean up path if import fails
        if sys.path[0] == str(tools_dir):
            sys.path.pop(0)
        pass  # Patch file not present, continue without it

import typer
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing_extensions import Annotated

from pocket_tts.personas import load_persona, list_personas

from pocket_tts.data.audio import stream_audio_chunks
from pocket_tts.default_parameters import (
    DEFAULT_AUDIO_PROMPT,
    DEFAULT_EOS_THRESHOLD,
    DEFAULT_FRAMES_AFTER_EOS,
    DEFAULT_LSD_DECODE_STEPS,
    DEFAULT_NOISE_CLAMP,
    DEFAULT_TEMPERATURE,
    DEFAULT_VARIANT,
    MAX_TOKEN_PER_CHUNK,
)
from pocket_tts.models.tts_model import TTSModel
from pocket_tts.utils.logging_utils import enable_logging
from pocket_tts.utils.utils import PREDEFINED_VOICES, size_of_dict

logger = logging.getLogger(__name__)

cli_app = typer.Typer(
    help="Kyutai Pocket TTS - Text-to-Speech generation tool", pretty_exceptions_show_locals=False
)


# ------------------------------------------------------
# The pocket-tts server implementation
# ------------------------------------------------------

# Global model instance
tts_model: TTSModel | None = None
global_model_state = None

web_app = FastAPI(
    title="Kyutai Pocket TTS API", description="Text-to-Speech generation API", version="1.0.0"
)
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://pod1-10007.internal.kyutai.org",
        "https://kyutai.org",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpeechRequest(BaseModel):
    model: str = "pocket-tts"
    input: str
    voice: str | None = None
    persona: str | None = None
    response_format: str = "wav"
    speed: float = 1.0


@web_app.get("/")
async def root():
    """Serve the frontend."""
    static_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(static_path)


@web_app.get("/health")
async def health():
    return {"status": "healthy"}


@web_app.post("/v1/audio/speech")
async def openai_speech(request: SpeechRequest):
    """OpenAI-compatible TTS endpoint."""
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    persona_data = {}
    if request.persona:
        try:
            persona_data = load_persona(request.persona)
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail=f"Persona '{request.persona}' not found.")

    final_voice = request.voice if request.voice is not None else persona_data.get("voice")

    if not final_voice:
        project_dir = Path(__file__).parent.parent
        current_voice_path = project_dir / ".current_voice"
        if current_voice_path.exists():
            final_voice = current_voice_path.read_text().strip()
        else:
            final_voice = DEFAULT_AUDIO_PROMPT
    
    # Use azelma as a fallback default if no voice is found
    if not final_voice:
        final_voice = "azelma"

    model_state = tts_model._cached_get_state_for_audio_prompt(final_voice)

    return StreamingResponse(
        generate_data_with_state(request.input, model_state),
        media_type="audio/wav",
    )


def write_to_queue(queue, text_to_generate, model_state):
    """Allows writing to the StreamingResponse as if it were a file."""

    class FileLikeToQueue(io.IOBase):
        def __init__(self, queue):
            self.queue = queue

        def write(self, data):
            self.queue.put(data)

        def flush(self):
            pass

        def close(self):
            self.queue.put(None)

    audio_chunks = tts_model.generate_audio_stream(
        model_state=model_state, text_to_generate=text_to_generate
    )
    stream_audio_chunks(FileLikeToQueue(queue), audio_chunks, tts_model.config.mimi.sample_rate)


def generate_data_with_state(text_to_generate: str, model_state: dict):
    queue = Queue()

    # Run your function in a thread
    thread = threading.Thread(target=write_to_queue, args=(queue, text_to_generate, model_state))
    thread.start()

    # Yield data as it becomes available
    i = 0
    while True:
        data = queue.get()
        if data is None:
            break
        i += 1
        yield data

    thread.join()


@web_app.post("/tts")
def text_to_speech(
    text: str = Form(...),
    voice_url: str | None = Form(None),
    voice_wav: UploadFile | None = File(None),
    persona: str | None = Form(None),
):
    """
    Generate speech from text using the pre-loaded voice prompt or a custom voice.

    Args:
        text: Text to convert to speech
        voice_url: Optional voice URL (http://, https://, or hf://)
        voice_wav: Optional uploaded voice file (mutually exclusive with voice_url)
        persona: Optional persona name
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    if voice_url is not None and voice_wav is not None:
        raise HTTPException(status_code=400, detail="Cannot provide both voice_url and voice_wav")

    persona_data = {}
    if persona:
        try:
            persona_data = load_persona(persona)
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail=f"Persona '{persona}' not found.")

    final_voice_url = voice_url if voice_url is not None else persona_data.get("voice")

    # Use the appropriate model state
    if final_voice_url is not None:
        # If the voice is a simple name (no path separators), search for it in the tts-voices directory
        if "/" not in final_voice_url and "\\" not in final_voice_url:
            voices_dir = Path(__file__).parent.parent / "tts-voices"
            found_voice = None
            
            # 1. Search for .safetensors first (most efficient and reliable)
            for f in voices_dir.glob(f"**/{final_voice_url}*.safetensors"):
                if f.is_file() and f.stat().st_size > 1000: # Skip LFS pointers
                    found_voice = f
                    break
            
            # 2. Fallback to audio files only if no safetensors found
            if not found_voice:
                for ext in ["wav", "mp3", "flac", "ogg", "aiff"]:
                    for f in voices_dir.glob(f"**/{final_voice_url}.{ext}"):
                        if f.is_file() and f.stat().st_size > 1000:
                            found_voice = f
                            break
                    if found_voice:
                        break
            
            if found_voice:
                final_voice_url = str(found_voice)
                logging.info(f"Found voice file '{final_voice_url}'")

        voice_path = Path(final_voice_url)
        if voice_path.is_dir():
            logging.info(f"'{final_voice_url}' is a directory, searching for voice file.")
            # If a directory is provided, find the first suitable file
            found_voice = None
            # Try audio files first
            for ext in ["wav", "mp3", "flac", "ogg", "aiff"]:
                files = sorted([f for f in voice_path.glob(f"*.{ext}") if f.stat().st_size > 1000])
                if files:
                    found_voice = files[0]
                    break
            
            # Then safetensors
            if not found_voice:
                files = sorted([f for f in voice_path.glob("*.safetensors") if f.stat().st_size > 1000])
                if files:
                    found_voice = files[0]
            
            if found_voice:
                final_voice_url = str(found_voice)
                logging.info(f"Found voice file '{final_voice_url}'")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No supported voice file found in directory '{final_voice_url}' (found files may be Git LFS pointers)"
                )

        is_url = final_voice_url.startswith(("http://", "https://", "hf://"))
        is_predefined = final_voice_url in PREDEFINED_VOICES
        # Path.is_file() handles the check for existence.
        is_file = Path(final_voice_url).is_file()

        if not (is_url or is_predefined or is_file):
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{final_voice_url}' not found. It must be a valid URL, a predefined voice name, a local file path, or a directory containing a voice file."
            )
        model_state = tts_model._cached_get_state_for_audio_prompt(final_voice_url)
        logging.warning("Using voice: %s", final_voice_url)
    elif voice_wav is not None:
        # Use uploaded voice file - preserve extension for format detection
        suffix = Path(voice_wav.filename).suffix if voice_wav.filename else ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = voice_wav.file.read()
            temp_file.write(content)
            temp_file.flush()
            temp_file_path = temp_file.name

        # Close the file before reading it back (required on Windows)
        try:
            model_state = tts_model.get_state_for_audio_prompt(Path(temp_file_path), truncate=True)
        finally:
            os.unlink(temp_file_path)
    else:
        # Use default global model state
        model_state = global_model_state

    return StreamingResponse(
        generate_data_with_state(text, model_state),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=generated_speech.wav",
            "Transfer-Encoding": "chunked",
        },
    )


@cli_app.command()
def serve(
    voice: Annotated[
        str, typer.Option(help="Path to voice prompt audio file (voice to clone)")
    ] = DEFAULT_AUDIO_PROMPT,
    host: Annotated[str, typer.Option(help="Host to bind to")] = "localhost",
    port: Annotated[int, typer.Option(help="Port to bind to")] = 8000,
    reload: Annotated[bool, typer.Option(help="Enable auto-reload")] = False,
    config: Annotated[
        str,
        typer.Option(
            help="Path to locally-saved model config .yaml file or model variant signature"
        ),
    ] = DEFAULT_VARIANT,
):
    """Start the FastAPI server."""

    global tts_model, global_model_state
    tts_model = TTSModel.load_model(config)

    # Pre-load the voice prompt
    global_model_state = tts_model.get_state_for_audio_prompt(voice)
    logger.info(f"The size of the model state is {size_of_dict(global_model_state) // 1e6} MB")

    uvicorn.run("pocket_tts.main:web_app", host=host, port=port, reload=reload)


@cli_app.command(name="list-personas")
def list_personas_command():
    """List all available personas."""
    personas = list_personas()
    if not personas:
        print("No personas found.")
        return
    print("Available personas:")
    for persona in personas:
        print(f"- {persona}")



# ------------------------------------------------------
# The pocket-tts single generation CLI implementation
# ------------------------------------------------------

# ... (rest of the imports)

# ... (code before generate function)

@cli_app.command()
def generate(
    text: Annotated[
        str, typer.Option(help="Text to generate")
    ] = "Hello world. I am Kyutai's Pocket TTS. I'm fast enough to run on small CPUs. I hope you'll like me.",
    voice: Annotated[
        str, typer.Option(help="Path to audio conditioning file (voice to clone)")
    ] = None,
    persona: Annotated[
        str, typer.Option(help="Name of the persona to use")
    ] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Disable logging output")] = False,
    config: Annotated[
        str, typer.Option(help="Model signature or path to config .yaml file")
    ] = DEFAULT_VARIANT,
    lsd_decode_steps: Annotated[
        int, typer.Option(help="Number of generation steps")
    ] = None,
    temperature: Annotated[
        float, typer.Option(help="Temperature for generation")
    ] = None,
    speed: Annotated[
        float, typer.Option(help="Playback speed of the generated audio.")
    ] = None,
    noise_clamp: Annotated[float, typer.Option(help="Noise clamp value")] = None,
    eos_threshold: Annotated[float, typer.Option(help="EOS threshold")] = None,
    frames_after_eos: Annotated[
        int, typer.Option(help="Number of frames to generate after EOS")
    ] = None,
    output_path: Annotated[
        str, typer.Option(help="Output path for generated audio")
    ] = "./tts_output.wav",
    device: Annotated[str, typer.Option(help="Device to use")] = "cpu",
    max_tokens: Annotated[
        int, typer.Option(help="Maximum number of tokens per chunk.")
    ] = MAX_TOKEN_PER_CHUNK,
):
    """Generate speech using Kyutai Pocket TTS."""
    # Load persona data if specified
    persona_data = {}
    if persona:
        try:
            persona_data = load_persona(persona)
        except FileNotFoundError as e:
            logger.error(e)
            raise typer.Exit(code=1)

    # Determine final parameters with precedence: CLI > persona > default
    final_voice = voice if voice is not None else persona_data.get("voice", DEFAULT_AUDIO_PROMPT)
    final_lsd_decode_steps = lsd_decode_steps if lsd_decode_steps is not None else persona_data.get("lsd_decode_steps", DEFAULT_LSD_DECODE_STEPS)
    final_temperature = temperature if temperature is not None else persona_data.get("temperature", DEFAULT_TEMPERATURE)
    final_speed = speed if speed is not None else persona_data.get("speed", 1.0)
    final_noise_clamp = noise_clamp if noise_clamp is not None else persona_data.get("noise_clamp", DEFAULT_NOISE_CLAMP)
    final_eos_threshold = eos_threshold if eos_threshold is not None else persona_data.get("eos_threshold", DEFAULT_EOS_THRESHOLD)
    final_frames_after_eos = frames_after_eos if frames_after_eos is not None else persona_data.get("frames_after_eos", DEFAULT_FRAMES_AFTER_EOS)

    if "cuda" in device:
        # Cuda graphs capturing does not play nice with multithreading.
        os.environ["NO_CUDA_GRAPH"] = "1"

    log_level = logging.ERROR if quiet else logging.INFO
    with enable_logging("pocket_tts", log_level):
        tts_model = TTSModel.load_model(
            config, final_temperature, final_lsd_decode_steps, final_noise_clamp, final_eos_threshold
        )
        tts_model.to(device)

        model_state_for_voice = tts_model.get_state_for_audio_prompt(final_voice)
        # Stream audio generation directly to file or stdout
        audio_chunks = tts_model.generate_audio_stream(
            model_state=model_state_for_voice,
            text_to_generate=text,
            frames_after_eos=final_frames_after_eos,
            max_tokens=max_tokens,
        )

        stream_audio_chunks(output_path, audio_chunks, tts_model.config.mimi.sample_rate, speed=final_speed)

        # Only print the result message if not writing to stdout
        if output_path != "-":
            logger.info("Results written in %s", output_path)
        logger.info("-" * 20)
        logger.info(
            "If you want to try multiple voices and prompts quickly, try the `serve` command."
        )
        logger.info(
            "If you like Kyutai projects, comment, like, subscribe at https://x.com/kyutai_labs"
        )


# ----------------------------------------------
# export audio to safetensors CLI implementation
# ----------------------------------------------


@cli_app.command()
def export_voice(
    audio_path: Annotated[
        str, typer.Argument(help="Audio file or directory to convert and export")
    ],
    export_path: Annotated[str, typer.Argument(help="Output file or directory")],
    truncate: Annotated[
        bool, typer.Option("-tr", "--truncate", help="Truncate long audio")
    ] = False,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Disable logging output")] = False,
    config: Annotated[str, typer.Option(help="Model config path or signature")] = DEFAULT_VARIANT,
    lsd_decode_steps: Annotated[
        int, typer.Option(help="Number of generation steps")
    ] = DEFAULT_LSD_DECODE_STEPS,
    temperature: Annotated[
        float, typer.Option(help="Temperature for generation")
    ] = DEFAULT_TEMPERATURE,
    noise_clamp: Annotated[float, typer.Option(help="Noise clamp value")] = DEFAULT_NOISE_CLAMP,
    eos_threshold: Annotated[float, typer.Option(help="EOS threshold")] = DEFAULT_EOS_THRESHOLD,
    frames_after_eos: Annotated[
        int, typer.Option(help="Number of frames to generate after EOS")
    ] = DEFAULT_FRAMES_AFTER_EOS,
    device: Annotated[str, typer.Option(help="Device to use")] = "cpu",
):
    """Convert and save audio to .safetensors file"""
    import re

    def url(path):
        return path.startswith(("http:", "https:", "hf:"))

    def normalize_url(url):
        # utils.py expects urls to be xxx:// so normalize them
        return re.sub(r"^(http|https|hf)\:\/*(.+)$", r"\1://\2", url)

    def likely_file(path):
        return not url(path) and not likely_dir(path)

    def likely_dir(path):
        return not url(path) and (path.endswith(("/", "\\")) or path == ".")

    def convert_one(in_path, out_path, join_path):
        """helper convert function"""
        voice = in_path.stem
        if url(str(in_path)):
            in_path = normalize_url(str(in_path))
        if join_path:
            out_path = out_path / f"{voice}.safetensors"
        else:
            # ensure output file has correct extension
            out_path = out_path.with_suffix(".safetensors")
        try:
            tts_model.save_audio_prompt(in_path, out_path, truncate)
        except Exception as e:
            logger.error(f"❌ Unable to export voice '{in_path}': {e}")
            return False
        logger.info(f"✅ Successfully exported voice '{voice}' to '{out_path}'")
        return True

    if "cuda" in device:
        # Cuda graphs capturing does not play nice with multithreading.
        os.environ["NO_CUDA_GRAPH"] = "1"

    log_level = logging.ERROR if quiet else logging.INFO
    success_count = 0

    with enable_logging("pocket_tts", log_level):
        tts_model = TTSModel.load_model(
            config, temperature, lsd_decode_steps, noise_clamp, eos_threshold
        )
        tts_model.to(device)

        in_path = Path(audio_path)
        out_path = Path(export_path)
        if likely_dir(export_path):
            # make sure output dir exists
            out_path.mkdir(parents=True, exist_ok=True)

        if likely_dir(audio_path):  # batch convert whole directory
            if not in_path.is_dir():
                logger.error(f"Input dir '{audio_path}' does not exists")
                exit(1)
            if not likely_dir(export_path):
                # batch convert, output path must be directory, not file
                out_path = Path("./")
            for path in Path(in_path).iterdir():
                if path.is_file() and path.suffix.lower() in [
                    ".wav",
                    ".mp3",
                    ".flac",
                    ".ogg",
                    ".aiff",
                ]:
                    if convert_one(path, out_path, True):
                        success_count += 1
        else:  # convert single file
            if likely_file(audio_path) and not in_path.exists():
                logger.error(f"Input file '{in_path}'' does not exists")
                exit(1)
            if convert_one(in_path, out_path, likely_dir(export_path)):
                success_count += 1

        if success_count > 0:
            logger.info(f"🎉 Successfully exported {success_count} voices.")


if __name__ == "__main__":
    cli_app()
