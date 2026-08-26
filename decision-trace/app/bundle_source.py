"""Neutral local source transport for frozen DecisionTrace bundles.

This module deliberately knows only how to present documents.  It does not
interpret lifecycle status, authority scope, roles, or relationships.  The
same interface can be backed by GitHub or a local bundle without changing the
downstream extraction/resolution stages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


_URL_RE = re.compile(r"https?://[^\s)\]>`]+")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_ARTIFACT_RE = re.compile(r"artifact_(\d{3})\.md\Z")


@dataclass(frozen=True)
class BundleArtifact:
    """One source document with transport metadata only.

    Metadata is derived from the artifact bytes.  In particular, the local
    filename never becomes a title or a status-bearing field.
    """

    source_id: str
    source_type: str
    source_url: str | None
    title: str | None
    content: str
    timestamp: str | None


class SourceBundle(Protocol):
    """Minimal source transport consumed by the generic bundle ingester."""

    def requested_change(self) -> str: ...

    def list_artifacts(self) -> tuple[BundleArtifact, ...]: ...


class BundleInputError(ValueError):
    """Raised when a bundle contains files outside the fair input boundary."""


class LocalBundleSource:
    """Read only the neutral bundle presentation.

    A valid root contains exactly ``requested_change.txt`` and an
    ``artifacts/`` directory containing ``artifact_NNN.md`` files.  Rejecting
    every other path is the enforcement point that keeps TASK.md, graders,
    sanity patches, and ledger metadata out of extraction.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise BundleInputError(f"bundle root is not a directory: {root}")
        self._validate_layout()

    def _validate_layout(self) -> None:
        allowed = {Path("requested_change.txt")}
        for path in self.root.rglob("*"):
            relative = path.relative_to(self.root)
            if path.is_symlink():
                raise BundleInputError(f"symlinks are not allowed: {relative}")
            if path.is_dir():
                if relative != Path("artifacts"):
                    raise BundleInputError(f"unexpected directory: {relative}")
                continue
            if relative not in allowed and not (
                relative.parent == Path("artifacts")
                and _ARTIFACT_RE.fullmatch(relative.name)
            ):
                raise BundleInputError(f"file outside bundle allowlist: {relative}")
        if not (self.root / "requested_change.txt").is_file():
            raise BundleInputError("requested_change.txt is required")
        artifacts = self.root / "artifacts"
        if not artifacts.is_dir():
            raise BundleInputError("artifacts/ directory is required")
        if not any(artifacts.glob("artifact_*.md")):
            raise BundleInputError("at least one neutral artifact is required")

    def requested_change(self) -> str:
        return (self.root / "requested_change.txt").read_text(encoding="utf-8")

    @staticmethod
    def _metadata(source_id: str, content: str) -> tuple[str | None, str | None, str | None]:
        urls = _URL_RE.findall(content)
        source_url = urls[0].rstrip(".,;") if urls else None
        title = next(
            (line[1:].strip() for line in content.splitlines() if line.startswith("# ") and line[2:].strip()),
            None,
        )
        timestamp = next(iter(_DATE_RE.findall(content)), None)
        return source_url, title, timestamp

    def list_artifacts(self) -> tuple[BundleArtifact, ...]:
        artifacts: list[BundleArtifact] = []
        for path in sorted((self.root / "artifacts").glob("artifact_*.md")):
            match = _ARTIFACT_RE.fullmatch(path.name)
            if match is None:
                raise BundleInputError(f"non-neutral artifact name: {path.name}")
            content = path.read_text(encoding="utf-8")
            source_id = f"artifact_{match.group(1)}"
            source_url, title, timestamp = self._metadata(source_id, content)
            artifacts.append(BundleArtifact(
                source_id=source_id,
                source_type="document",
                source_url=source_url,
                title=title,
                content=content,
                timestamp=timestamp,
            ))
        return tuple(artifacts)
