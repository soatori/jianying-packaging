#!/usr/bin/env python3
"""Find project-specific path, identifier, and media references in reusable Skill files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".txt", ".csv"}
DEFAULT_EXCLUDES = {"generic_content_impl.py"}
PATTERNS = {
    "absolute_path": re.compile(r"(?i)(?:[A-Z]:[\\/]|\\\\)"),
    "draft_path": re.compile(r"(?i)jianyingpro[\\/].*(?:drafts|timelines|draft_content\.json)"),
    "guid": re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])"),
    "media_filename": re.compile(r"(?i)(?:^|[\\/\s\"'])[^<>\\/\s\"']+\.(?:mp4|mov|mkv|avi|wav|mp3|m4a|png|jpg|jpeg|webp)\b"),
}


def scan(
    roots: list[Path],
    excludes: set[str] | None = None,
    forbidden_literals: list[str] | None = None,
) -> list[str]:
    excludes = DEFAULT_EXCLUDES | (excludes or set())
    forbidden_literals = [item for item in (forbidden_literals or []) if isinstance(item, str) and item]
    findings: list[str] = []
    for root in roots:
        if root.is_file():
            files = [root]
        else:
            files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES]
        for path in files:
            if path.name in excludes or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for name, pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{path}: {name}")
            for literal in forbidden_literals:
                if literal in text:
                    findings.append(f"{path}: forbidden_literal:{literal}")
    return findings
