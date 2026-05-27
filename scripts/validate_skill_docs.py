#!/usr/bin/env python3
"""Validate image_api public skill documentation and runtime surfaces.

This validator is intentionally deterministic and offline. It checks Hermes skill
frontmatter, underscore-safe identity, provider-agnostic public docs, generated
artifact hygiene, and CLI surfaces that commonly leak local model/provider data.
It does not validate live provider credentials.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is expected in Hermes envs.
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "image_api.py"

PUBLIC_DOCS = [
    ROOT / "SKILL.md",
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CHANGELOG.zh-CN.md",
    ROOT / ".env.example",
]
PUBLIC_DOCS.extend(sorted((ROOT / "references").rglob("*.md")))

CANONICAL_NAME = "image_api"
HYPHENATED_IDENTITY = CANONICAL_NAME.replace("_", "-")
SECRET_LIKE_PREFIX_PATTERN = re.compile(r"\bsk-[A-Za-z0-9._-]+", re.IGNORECASE)
PROVIDER_SPECIFIC_MODEL_PATTERN = re.compile(r"\bgpt-[A-Za-z0-9][A-Za-z0-9._-]*\b", re.IGNORECASE)

# Patterns that indicate local/private configuration leaked into public docs.
# Keep this list generic: do not encode real private providers, model routes, or keys.
FORBIDDEN_PUBLIC_PATTERNS = {
    "provider-specific model route": PROVIDER_SPECIFIC_MODEL_PATTERN,
    "secret-like key placeholder": SECRET_LIKE_PREFIX_PATTERN,
    "old env placeholder": re.compile(r"\byour[-_]api[-_]key[-_]here\b", re.IGNORECASE),
    "non-generic provider host placeholder": re.compile(r"https://your-provider\.com", re.IGNORECASE),
    "private absolute root path": re.compile(r"/root/"),
    "hyphenated runtime skill identity": re.compile(r"\b" + re.escape(HYPHENATED_IDENTITY) + r"\b"),
    "stale branded output directory": re.compile(r"/tmp/[A-Za-z0-9_-]*gpt[A-Za-z0-9_-]*", re.IGNORECASE),
    "stale JSON model output field in docs": re.compile(r"\bused_params\.model\b"),
}

# Runtime CLI surfaces should also stay provider-agnostic. Tests may mention fake
# provider values, but the shipped execution script must not have a provider-specific
# fallback or emit private endpoint metadata in JSON.
FORBIDDEN_RUNTIME_PATTERNS = {
    "hyphenated runtime skill identity": re.compile(r"\b" + re.escape(HYPHENATED_IDENTITY) + r"\b"),
    "non-empty IMAGE_MODEL hardcoded fallback": re.compile(
        r"DEFAULT_MODEL\s*=\s*os\.environ\.get\(\s*['\"]IMAGE_MODEL['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)"
    ),
}

GENERATED_DIR_NAMES = {"__pycache__", ".pytest_cache"}
GENERATED_SUFFIXES = {".pyc", ".pyo"}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def iter_hits(path: Path, patterns: dict[str, re.Pattern[str]]) -> Iterable[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for label, pattern in patterns.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            yield f"{path.relative_to(ROOT)}:{line}: {label}"


def validate_frontmatter() -> None:
    path = ROOT / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        fail("SKILL.md must start with YAML frontmatter at byte 0")
    match = re.search(r"\n---\s*\n", content[3:])
    if not match:
        fail("SKILL.md frontmatter must close with a standalone ---")
    frontmatter_text = content[3 : match.start() + 3]
    body = content[match.end() + 3 :]
    if not body.strip():
        fail("SKILL.md body must be non-empty")
    if yaml is None:
        fail("PyYAML is required for frontmatter validation")
    data = yaml.safe_load(frontmatter_text)
    if not isinstance(data, dict):
        fail("SKILL.md frontmatter must parse as a mapping")
    required = ["name", "description", "version", "author", "license", "metadata"]
    missing = [key for key in required if key not in data]
    if missing:
        fail(f"SKILL.md missing frontmatter keys: {', '.join(missing)}")
    if data["name"] != "image_api":
        fail("SKILL.md name must be exactly image_api")
    description = str(data["description"])
    if not description.startswith("Use when "):
        fail("description must start with 'Use when '")
    if len(description) > 1024:
        fail("description must be <= 1024 chars")
    hermes = (data.get("metadata") or {}).get("hermes") or {}
    if not hermes.get("tags"):
        fail("metadata.hermes.tags must be present")
    if "hermes-agent-skill-authoring" not in hermes.get("related_skills", []):
        fail("metadata.hermes.related_skills must include hermes-agent-skill-authoring")
    if len(content) > 100_000:
        fail("SKILL.md exceeds 100,000 chars")


def validate_public_docs() -> None:
    missing = [str(path.relative_to(ROOT)) for path in PUBLIC_DOCS if not path.exists()]
    if missing:
        fail(f"Missing public docs: {', '.join(missing)}")
    errors: list[str] = []
    provider_model_allowed = {
        ROOT / "references" / "providers" / "openai-image-models.md",
        ROOT / "references" / "providers" / "openai-image-models.zh-CN.md",
    }
    for path in PUBLIC_DOCS:
        patterns = dict(FORBIDDEN_PUBLIC_PATTERNS)
        if path in provider_model_allowed:
            patterns.pop("provider-specific model route", None)
        errors.extend(iter_hits(path, patterns))
    if errors:
        print("Public-surface validation errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


def validate_runtime_surfaces() -> None:
    if not SCRIPT.exists():
        fail("scripts/image_api.py is missing")
    errors = list(iter_hits(SCRIPT, FORBIDDEN_RUNTIME_PATTERNS))
    if errors:
        print("Runtime-surface validation errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


def validate_cli_help_surface() -> None:
    private_model = "PRIVATE_PROVIDER_MODEL_SHOULD_NOT_APPEAR"
    env = os.environ.copy()
    env["IMAGE_MODEL"] = private_model
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--help"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0:
        fail(f"image_api --help failed with exit code {result.returncode}: {combined[:500]}")
    if private_model in combined:
        fail("image_api --help exposed the current IMAGE_MODEL environment value")


def validate_identity() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    required_phrases = [
        "name: image_api",
        "python3 ~/.hermes/skills/image_api/scripts/image_api.py",
        "/skill image_api",
        "underscore",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in skill]
    if missing:
        fail(f"SKILL.md missing identity/runtime phrases: {', '.join(missing)}")


def validate_skill_structure() -> None:
    """Guard Skill Creator progressive-disclosure structure."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    required_sections = [
        "## Overview",
        "## When to Use",
        "## Runtime Authority",
        "## Workflow",
        "## Quick Recipes",
        "## Resource Map",
        "## Troubleshooting Escalation",
        "## Common Pitfalls",
        "## Verification Checklist",
    ]
    missing_sections = [section for section in required_sections if section not in skill]
    if missing_sections:
        fail(f"SKILL.md missing structural sections: {', '.join(missing_sections)}")

    required_resources = [
        "scripts/image_api.py",
        "scripts/validate_skill_docs.py",
        "tests/test_responses_mode.py",
        "references/api/fields.md",
        "references/providers/responses-api-compatibility.md",
        "references/troubleshooting/image-delivery-debugging.md",
        "README.md",
        "README.zh-CN.md",
        ".env.example",
    ]
    missing_resources = [resource for resource in required_resources if resource not in skill]
    if missing_resources:
        fail(f"SKILL.md Resource Map missing entries: {', '.join(missing_resources)}")

    if "## Detailed References" in skill:
        fail("SKILL.md should use grouped Resource Map instead of a flat Detailed References section")


def validate_generated_artifacts() -> None:
    generated: list[str] = []
    for path in ROOT.rglob("*"):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in GENERATED_DIR_NAMES for part in rel_parts):
            generated.append(str(path.relative_to(ROOT)))
            continue
        if path.is_file() and path.suffix in GENERATED_SUFFIXES:
            generated.append(str(path.relative_to(ROOT)))
    if generated:
        preview = ", ".join(sorted(generated)[:20])
        fail(f"Generated cache artifacts must not ship in the skill tree: {preview}")


def main() -> int:
    validate_frontmatter()
    validate_public_docs()
    validate_runtime_surfaces()
    validate_cli_help_surface()
    validate_identity()
    validate_skill_structure()
    validate_generated_artifacts()
    print("image_api skill docs validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
