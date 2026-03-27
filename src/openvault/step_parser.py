"""Regex-based STEP file metadata parser.

Extracts header metadata from ISO 10303-21 (STEP) files without
requiring any CAD dependencies.  The parser reads only the
FILE_DESCRIPTION, FILE_NAME, and FILE_SCHEMA header entities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StepMetadata:
    """Metadata extracted from a STEP file header."""

    file_path: str = ""
    description: str = ""
    name: str = ""
    author: str = ""
    organization: str = ""
    preprocessor_version: str = ""
    originating_system: str = ""
    authorization: str = ""
    schema: str = ""
    timestamp: str = ""

    def summary(self) -> str:
        """One-line human-readable summary."""
        parts: list[str] = []
        if self.name:
            parts.append(self.name)
        if self.originating_system:
            parts.append(f"({self.originating_system})")
        if self.author:
            parts.append(f"by {self.author}")
        if self.timestamp:
            parts.append(f"[{self.timestamp}]")
        return " ".join(parts) if parts else "(no metadata)"

    def as_dict(self) -> dict[str, str]:
        """Return non-empty fields as a dict."""
        return {
            k: v
            for k, v in {
                "description": self.description,
                "name": self.name,
                "author": self.author,
                "organization": self.organization,
                "preprocessor_version": self.preprocessor_version,
                "originating_system": self.originating_system,
                "authorization": self.authorization,
                "schema": self.schema,
                "timestamp": self.timestamp,
            }.items()
            if v
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_QUOTED_STRING = re.compile(r"'([^']*)'")
_TIMESTAMP = re.compile(r"'(\d{4}-\d{2}-\d{2}T[\d:+-]+)'")


def _extract_quoted(text: str, index: int = 0) -> str:
    """Return the *index*-th single-quoted value in *text*, or ''."""
    matches = _QUOTED_STRING.findall(text)
    if index < len(matches):
        return matches[index]
    return ""


def _extract_paren_tuple(text: str) -> list[str]:
    """Return the content of the first parenthesised tuple of quoted strings."""
    m = re.search(r"\(([^)]*)\)", text)
    if not m:
        return []
    return _QUOTED_STRING.findall(m.group(1))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_step_header(content: str) -> StepMetadata:
    """Parse STEP header section from *content* and return metadata."""
    meta = StepMetadata()

    # Normalise: collapse newlines so entities that span lines still match.
    header_match = re.search(
        r"HEADER\s*;(.*?)END(?:SEC|_HEADER)\s*;",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if not header_match:
        return meta

    header = header_match.group(1)

    # FILE_DESCRIPTION
    fd = re.search(
        r"FILE_DESCRIPTION\s*\((.*?)\)\s*;", header, re.DOTALL | re.IGNORECASE
    )
    if fd:
        meta.description = _extract_quoted(fd.group(1))

    # FILE_NAME
    fn = re.search(r"FILE_NAME\s*\((.*?)\)\s*;", header, re.DOTALL | re.IGNORECASE)
    if fn:
        body = fn.group(1)
        quoted = _QUOTED_STRING.findall(body)
        if len(quoted) >= 1:
            meta.name = quoted[0]
        if len(quoted) >= 2:
            meta.timestamp = quoted[1]

        # Author and org are tuple-of-strings inside parens.
        paren_tuples = re.findall(r"\(([^)]*)\)", body)
        if len(paren_tuples) >= 1:
            authors = _QUOTED_STRING.findall(paren_tuples[0])
            meta.author = ", ".join(authors) if authors else ""
        if len(paren_tuples) >= 2:
            orgs = _QUOTED_STRING.findall(paren_tuples[1])
            meta.organization = ", ".join(orgs) if orgs else ""

        # Remaining quoted strings after the tuples: preprocessor, system, auth
        remaining = body
        for pt in paren_tuples:
            remaining = remaining.replace(f"({pt})", "", 1)
        remaining_quoted = _QUOTED_STRING.findall(remaining)
        # First two are name and timestamp (already captured).
        extra = remaining_quoted[2:] if len(remaining_quoted) > 2 else []
        if len(extra) >= 1:
            meta.preprocessor_version = extra[0]
        if len(extra) >= 2:
            meta.originating_system = extra[1]
        if len(extra) >= 3:
            meta.authorization = extra[2]

    # FILE_SCHEMA
    fs = re.search(r"FILE_SCHEMA\s*\((.*?)\)\s*;", header, re.DOTALL | re.IGNORECASE)
    if fs:
        schemas = _QUOTED_STRING.findall(fs.group(1))
        meta.schema = ", ".join(schemas) if schemas else ""

    return meta


def parse_step_file(path: str | Path) -> StepMetadata:
    """Read a STEP file from disk and extract header metadata."""
    p = Path(path)
    # STEP headers are typically within the first few KB.
    content = p.read_text(encoding="utf-8", errors="replace")[:32768]
    meta = parse_step_header(content)
    meta.file_path = str(p)
    return meta


def is_step_file(path: str | Path) -> bool:
    """Return True if *path* looks like a STEP file by extension."""
    return Path(path).suffix.lower() in {".step", ".stp"}
