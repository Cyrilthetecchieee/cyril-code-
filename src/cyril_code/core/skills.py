"""Skill management and installation logic."""

import base64
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from loguru import logger


def get_global_skills_dir() -> Path:
    """Return the global skills directory for claude-code."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "claude-code" / "skills"
        return Path.home() / "AppData" / "Roaming" / "claude-code" / "skills"

    # Mac / Linux
    return Path.home() / ".config" / "claude-code" / "skills"


def get_bundled_skills_repo() -> Path:
    """Return the path to the bundled awesome-claude-skills repository."""
    base_dir = Path(__file__).parent.parent
    return base_dir / "assets" / ".skills_repo"


def extract_yaml_frontmatter(content: str) -> dict[str, str]:
    """Simple parser for YAML frontmatter to extract name and description."""
    data = {}
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return data

    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip().strip("'\"")
    return data


def list_available_skills() -> list[dict[str, Any]]:
    """List all skills available in the bundled repository."""
    repo_dir = get_bundled_skills_repo()
    skills = []

    if not repo_dir.exists():
        logger.warning(f"Bundled skills repo not found at {repo_dir}")
        return skills

    global_dir = get_global_skills_dir()

    for skill_file in repo_dir.rglob("SKILL.md"):
        item = skill_file.parent
        # Skip if any part of the path starts with '.'
        if any(part.startswith(".") for part in item.relative_to(repo_dir).parts):
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
            metadata = extract_yaml_frontmatter(content)

            name = metadata.get("name", item.name)
            description = metadata.get("description", "No description available.")

            rel_path_str = str(item.relative_to(repo_dir)).replace("\\", "/")
            skill_id = base64.urlsafe_b64encode(rel_path_str.encode("utf-8")).decode(
                "utf-8"
            )

            # Check if installed globally
            is_installed = (global_dir / name).exists()

            skills.append(
                {
                    "id": skill_id,
                    "name": name,
                    "description": description,
                    "installed": is_installed,
                }
            )
        except Exception as exc:
            logger.error(f"Failed to parse skill {item.name}: {exc}")

    # Sort alphabetically by name
    return sorted(skills, key=lambda s: s["name"].lower())


def install_skill(skill_id: str) -> bool:
    """Install a skill by copying it to the global skills directory."""
    repo_dir = get_bundled_skills_repo()

    try:
        rel_path_str = base64.urlsafe_b64decode(skill_id.encode("utf-8")).decode(
            "utf-8"
        )
    except Exception:
        raise ValueError("Invalid skill ID format.") from None

    source_dir = repo_dir / rel_path_str

    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"Skill not found in the repository at {rel_path_str}.")

    skill_file = source_dir / "SKILL.md"
    if not skill_file.exists():
        raise ValueError(f"Skill {skill_id} is missing SKILL.md.")

    content = skill_file.read_text(encoding="utf-8")
    metadata = extract_yaml_frontmatter(content)
    skill_name = metadata.get("name", source_dir.name)

    global_dir = get_global_skills_dir()
    global_dir.mkdir(parents=True, exist_ok=True)

    target_dir = global_dir / skill_name

    # Overwrite if exists
    if target_dir.exists():
        shutil.rmtree(target_dir)

    # Ignore git files when copying
    shutil.copytree(source_dir, target_dir, ignore=shutil.ignore_patterns(".git*"))
    logger.info(f"Successfully installed skill {skill_name} to {target_dir}")
    return True
