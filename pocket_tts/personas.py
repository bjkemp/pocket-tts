import os
from pathlib import Path
import yaml
import re

def load_persona(persona_name: str, personas_dir: Path | None = None):
    """
    Loads a persona from a Markdown file with YAML frontmatter.

    Args:
        persona_name: The name of the persona to load (without the .md extension).
        personas_dir: The directory where personas are stored. Defaults to './personas'.

    Returns:
        A dictionary of the persona's parameters.
    """
    if personas_dir is None:
        personas_dir_str = os.environ.get("POCKET_TTS_PERSONAS_DIR")
        if personas_dir_str:
            personas_dir = Path(personas_dir_str)
        else:
            personas_dir = Path.cwd() / "personas"

    persona_file = personas_dir / f"{persona_name}.md"

    if not persona_file.exists():
        raise FileNotFoundError(f"Persona '{persona_name}' not found at '{persona_file}'")

    text = persona_file.read_text()

    # Regex to find YAML frontmatter
    match = re.match(r"---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    frontmatter = match.group(1)
    persona_data = yaml.safe_load(frontmatter)
    return persona_data

def list_personas(personas_dir: Path | None = None) -> list[str]:
    """
    Lists all available personas in the personas directory.

    Args:
        personas_dir: The directory where personas are stored.

    Returns:
        A list of persona names.
    """
    if personas_dir is None:
        personas_dir_str = os.environ.get("POCKET_TTS_PERSONAS_DIR")
        if personas_dir_str:
            personas_dir = Path(personas_dir_str)
        else:
            personas_dir = Path.cwd() / "personas"

    if not personas_dir.exists():
        return []

    return sorted([f.stem for f in personas_dir.glob("*.md")])
