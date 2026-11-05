"""Cryptographic Source Content Manifest Utility (Stage 8).

Computes deterministic SHA-256 digests over all tracked research prototype source files,
catalogs, service definitions, database schemas, and evaluation fixtures.
Guarantees evaluation results are tied to an exact, verifiable repository state.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

from nextrace_lab.logging_utils import utc_now_iso

MANIFEST_VERSION = "v1"

INCLUDED_GLOBS = [
    "nextrace_lab/**/*.py",
    "services/**/*.py",
    "db/**/*.sql",
    "docker-compose.yml",
    "pyproject.toml",
]

EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    "var",
    "artifacts",
    ".gemini",
    ".venv",
    "venv",
}


def _sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_content_manifest(repo_root: Optional[Path] = None) -> dict[str, Any]:
    """Compute deterministic SHA-256 digests over all tracked project sources."""
    root = (repo_root or Path(__file__).resolve().parent.parent).resolve()
    file_digests: dict[str, str] = {}

    for pattern in INCLUDED_GLOBS:
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            if any(part in p.parts for part in EXCLUDED_PARTS):
                continue
            rel = str(p.relative_to(root)).replace("\\", "/")
            file_digests[rel] = _sha256_file(p)

    sorted_entries = sorted(file_digests.items())
    agg = hashlib.sha256()
    for rel_path, digest in sorted_entries:
        agg.update(f"{rel_path}:{digest}\n".encode("utf-8"))
    manifest_digest = agg.hexdigest()

    return {
        "manifest_version": MANIFEST_VERSION,
        "generated_at_utc": utc_now_iso(),
        "repo_root": str(root),
        "file_count": len(file_digests),
        "manifest_digest_sha256": manifest_digest,
        "files": dict(sorted_entries),
    }


def verify_content_manifest(
    expected_manifest: dict[str, Any],
    repo_root: Optional[Path] = None,
) -> tuple[bool, list[str]]:
    """Verify that current repository files match `expected_manifest`."""
    current = compute_content_manifest(repo_root)
    mismatches: list[str] = []

    expected_files = expected_manifest.get("files", {})
    current_files = current.get("files", {})

    for path, exp_hash in expected_files.items():
        if path not in current_files:
            mismatches.append(f"missing_file:{path}")
        elif current_files[path] != exp_hash:
            mismatches.append(f"hash_mismatch:{path} (expected {exp_hash[:8]}, got {current_files[path][:8]})")

    for path in current_files:
        if path not in expected_files:
            mismatches.append(f"extra_untracked_file:{path}")

    is_match = (len(mismatches) == 0) and (
        current["manifest_digest_sha256"] == expected_manifest.get("manifest_digest_sha256")
    )
    return is_match, mismatches
