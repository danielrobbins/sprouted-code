from __future__ import annotations

import json
import shlex
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .commands import CommandRunner
from .config import ConfigError
from .manifest import ReleaseManifest


PROVENANCE_FILE = ".sprouted-build-provenance.json"


@dataclass(frozen=True)
class BuildProvenance:
    schema_version: int
    release: str
    source_tree: str
    platform: str
    architecture: str
    flavor: str
    gulp_target: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")) + "\n"


def expected_provenance(
    manifest: ReleaseManifest,
    *,
    platform: str,
    architecture: str,
    flavor: str,
    gulp_target: str,
) -> BuildProvenance:
    if not manifest.source_tree:
        raise ConfigError(
            "Release manifest build.source_tree is required before building"
        )
    return BuildProvenance(
        schema_version=1,
        release=manifest.release,
        source_tree=manifest.source_tree,
        platform=platform,
        architecture=architecture,
        flavor=flavor,
        gulp_target=gulp_target,
    )


def verify_checkout_provenance(
    checkout: Path,
    manifest: ReleaseManifest,
    runner: CommandRunner,
) -> None:
    if not manifest.source_tree:
        raise ConfigError(
            "Release manifest build.source_tree is required before building"
        )

    status = runner.run(
        ["git", "status", "--porcelain"],
        cwd=checkout,
        capture_output=True,
    )
    tree = runner.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=checkout,
        capture_output=True,
    )
    if runner.dry_run:
        return

    assert status is not None
    assert tree is not None
    if status.stdout.strip():
        raise ConfigError(f"Refusing to build a dirty VS Code checkout: {checkout}")
    actual_tree = tree.stdout.strip()
    if actual_tree != manifest.source_tree:
        raise ConfigError(
            "VS Code source tree does not match the release manifest: "
            f"expected {manifest.source_tree}, found {actual_tree}"
        )


def clean_output_directory(
    output_directory: Path,
    *,
    expected_parent: Path,
    dry_run: bool,
) -> None:
    output_directory = output_directory.resolve()
    expected_parent = expected_parent.resolve()
    if output_directory.parent != expected_parent:
        raise ConfigError(
            f"Refusing to remove build output outside {expected_parent}: "
            f"{output_directory}"
        )
    if not dry_run and output_directory.exists():
        shutil.rmtree(output_directory)


def write_output_provenance(
    output_directory: Path,
    provenance: BuildProvenance,
) -> Path:
    if not output_directory.is_dir():
        raise ConfigError(f"Build output directory not found: {output_directory}")
    path = output_directory / PROVENANCE_FILE
    path.write_text(provenance.to_json(), encoding="utf-8", newline="\n")
    return path


def verify_output_provenance(
    output_directory: Path,
    provenance: BuildProvenance,
) -> None:
    path = output_directory / PROVENANCE_FILE
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(
            f"Build output has no usable provenance receipt: {path}"
        ) from error
    if actual != provenance.to_json():
        raise ConfigError(
            f"Build output provenance does not match this release: {path}"
        )


def shell_checkout_gate(source_tree: str) -> str:
    quoted_tree = json.dumps(source_tree)
    return f"""
expected_source_tree={quoted_tree}
if [ -n "$(git status --porcelain)" ]; then
  echo "Refusing to build a dirty VS Code checkout: $checkout" >&2
  git status --short >&2
  exit 2
fi
actual_source_tree="$(git rev-parse 'HEAD^{{tree}}')"
if [ "$actual_source_tree" != "$expected_source_tree" ]; then
  echo "VS Code source tree does not match the release manifest: expected $expected_source_tree, found $actual_source_tree" >&2
  exit 2
fi
""".strip()


def shell_write_output_provenance(provenance: BuildProvenance) -> str:
    receipt = shlex.quote(provenance.to_json().rstrip("\n"))
    return f"printf '%s\\n' {receipt} > \"$output_dir/{PROVENANCE_FILE}\""


def shell_verify_output_provenance(provenance: BuildProvenance) -> str:
    receipt = shlex.quote(provenance.to_json().rstrip("\n"))
    return f"""
receipt_path="$output_dir/{PROVENANCE_FILE}"
expected_receipt={receipt}
if [ ! -f "$receipt_path" ] || [ "$(cat "$receipt_path")" != "$expected_receipt" ]; then
  echo "Build output provenance does not match this release: $receipt_path" >&2
  exit 2
fi
""".strip()
