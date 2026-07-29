from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(
    artifact_directory: Path,
    *,
    output_file: str = "checksums.txt",
) -> Path:
    artifact_directory = artifact_directory.resolve()
    if not artifact_directory.is_dir():
        raise FileNotFoundError(f"Artifact directory not found: {artifact_directory}")

    output_path = artifact_directory / output_file
    files = sorted(
        path
        for path in artifact_directory.iterdir()
        if path.is_file() and path.name != output_file
    )
    contents = "".join(f"{sha256_file(path)}  {path.name}\n" for path in files)

    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(contents, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
    return output_path
