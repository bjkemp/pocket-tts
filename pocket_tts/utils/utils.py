import hashlib
import logging
import time
from pathlib import Path

import requests
import safetensors.torch
import torch
from huggingface_hub import hf_hub_download
from torch import nn

PROJECT_ROOT = Path(__file__).parent.parent.parent

_voices_names = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
PREDEFINED_VOICES = {
    # don't forget to change this
    x: f"hf://kyutai/pocket-tts-without-voice-cloning/embeddings/{x}.safetensors@d4fdd22ae8c8e1cb3634e150ebeff1dab2d16df3"
    for x in _voices_names
}


def make_cache_directory() -> Path:
    cache_dir = Path.home() / ".cache" / "pocket_tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def print_nb_parameters(model: nn.Module, model_name: str):
    logger = logging.getLogger(__name__)
    state_dict = model.state_dict()
    total = 0
    for key, value in state_dict.items():
        logger.info("%s: %,d", key, value.numel())
        total += value.numel()
    logger.info("Total number of parameters in %s: %,d", model_name, total)


def size_of_dict(state_dict: dict) -> int:
    total_size = 0
    for value in state_dict.values():
        if isinstance(value, torch.Tensor):
            total_size += value.numel() * value.element_size()
        elif isinstance(value, dict):
            total_size += size_of_dict(value)
    return total_size


class display_execution_time:
    def __init__(self, task_name: str, print_output: bool = True):
        self.task_name = task_name
        self.print_output = print_output
        self.start_time = None
        self.elapsed_time_ms = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self.start_time = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.monotonic()
        self.elapsed_time_ms = int((end_time - self.start_time) * 1000)
        if self.print_output:
            self.logger.info("%s took %d ms", self.task_name, self.elapsed_time_ms)
        return False  # Don't suppress exceptions


def download_if_necessary(file_path: str) -> Path:
    if file_path.startswith("http://") or file_path.startswith("https://") or file_path.startswith("hf://"):
        local_path = None
        if file_path.startswith("hf://"):
            # hf://repo/path/to/file@revision
            repo_and_path = file_path.removeprefix("hf://")
            
            path_parts = repo_and_path.split('/')
            # repo is parts[0]/parts[1]
            # file_path_in_repo is parts[2:]
            if len(path_parts) > 2:
                file_path_in_repo = "/".join(path_parts[2:])
                if '@' in file_path_in_repo:
                    file_path_in_repo = file_path_in_repo.split('@')[0]

                project_root = Path(__file__).parent.parent.parent
                # Look for the file with its subdirectory structure inside tts-voices
                local_path = project_root / "tts-voices" / file_path_in_repo
            else: # top-level file in repo (e.g. tokenizer.model)
                filename = path_parts[-1]
                if '@' in filename:
                    filename = filename.split('@')[0]
                project_root = Path(__file__).parent.parent.parent
                local_path = project_root / "tts-voices" / filename
        else: # http/https
            filename = Path(file_path).name
            project_root = Path(__file__).parent.parent.parent
            local_path = project_root / "tts-voices" / filename

        if local_path and local_path.exists():
            logging.info(f"Found local file for {file_path}: {local_path}")
            return local_path
        
        raise FileNotFoundError(f"Could not find local file at '{local_path}'. Please make sure all model files are present in the tts-voices directory, maintaining the subdirectory structure from the original repository (e.g., 'embeddings/azelma.safetensors').")
    else:
        return Path(file_path)


def load_predefined_voice(voice_name: str) -> torch.Tensor:
    if voice_name not in PREDEFINED_VOICES:
        raise ValueError(
            f"Predefined voice '{voice_name}' not found"
            f", available voices are {list(PREDEFINED_VOICES)}."
        )
    voice_file = download_if_necessary(PREDEFINED_VOICES[voice_name])
    # There is only one tensor in the file.
    return safetensors.torch.load_file(voice_file)["audio_prompt"]
