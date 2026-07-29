from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """Raised when a release manifest cannot drive a reproducible build."""


@dataclass(frozen=True)
class PatchSource:
    name: str
    source_repo: str
    source_ref: str
    source_commit: str | None

    @property
    def is_file(self) -> bool:
        return self.source_ref.endswith(".patch")


@dataclass(frozen=True)
class ArtifactRecord:
    platform: str
    builder: str
    product_commit: str
    artifact: str
    sha256: str
    tests: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseManifest:
    path: Path
    release: str
    base_repo: str
    base_commit: str
    base_branch: str
    patches: tuple[PatchSource, ...]
    source_tree: str | None = None
    build_flavor: str = "release"
    require_provenance_receipt: bool = False
    builds: tuple[ArtifactRecord, ...] = ()


def _required_string(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{context}.{key} must be a non-empty string")
    return value


def load_release_manifest(path: Path) -> ReleaseManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ManifestError(
            f"Unable to read release manifest {path}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise ManifestError(
            f"Invalid JSON in release manifest {path}: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ManifestError("Release manifest root must be an object")
    base = data.get("base")
    if not isinstance(base, dict):
        raise ManifestError("Release manifest must contain a base object")
    raw_patches = data.get("patches")
    if not isinstance(raw_patches, list):
        raise ManifestError("Release manifest must contain a patches array")

    patches: list[PatchSource] = []
    for index, raw_patch in enumerate(raw_patches):
        context = f"patches[{index}]"
        if not isinstance(raw_patch, dict):
            raise ManifestError(f"{context} must be an object")
        source_commit = raw_patch.get("source_commit") or None
        if source_commit is not None and not isinstance(source_commit, str):
            raise ManifestError(f"{context}.source_commit must be a string")
        patch = PatchSource(
            name=_required_string(raw_patch, "name", context),
            source_repo=_required_string(raw_patch, "source_repo", context),
            source_ref=_required_string(raw_patch, "source_ref", context),
            source_commit=source_commit,
        )
        if not patch.is_file:
            raise ManifestError(
                f"{context}.source_ref must identify a local .patch file; "
                "Sprouted Code builds do not fetch patch branches"
            )
        patches.append(patch)

    build = data.get("build", {})
    if not isinstance(build, dict):
        raise ManifestError("manifest.build must be an object")
    source_tree = build.get("source_tree") or None
    if source_tree is not None and (
        not isinstance(source_tree, str)
        or len(source_tree) != 40
        or any(character not in "0123456789abcdef" for character in source_tree)
    ):
        raise ManifestError("manifest.build.source_tree must be a full Git tree hash")
    build_flavor = build.get("flavor", "release")
    if build_flavor not in ("release", "diagnostic"):
        raise ManifestError(
            "manifest.build.flavor must be either release or diagnostic"
        )
    require_provenance_receipt = build.get("provenance_receipt", False)
    if not isinstance(require_provenance_receipt, bool):
        raise ManifestError("manifest.build.provenance_receipt must be true or false")

    raw_builds = data.get("builds", [])
    if not isinstance(raw_builds, list):
        raise ManifestError("manifest.builds must be an array")
    builds: list[ArtifactRecord] = []
    for index, raw_build in enumerate(raw_builds):
        context = f"builds[{index}]"
        if not isinstance(raw_build, dict):
            raise ManifestError(f"{context} must be an object")
        raw_tests = raw_build.get("tests", [])
        if not isinstance(raw_tests, list) or not all(
            isinstance(test, str) and test for test in raw_tests
        ):
            raise ManifestError(f"{context}.tests must be an array of strings")
        sha256 = _required_string(raw_build, "sha256", context)
        if len(sha256) != 64 or any(
            character not in "0123456789abcdef" for character in sha256
        ):
            raise ManifestError(f"{context}.sha256 must be a lowercase SHA-256 hash")
        builds.append(
            ArtifactRecord(
                platform=_required_string(raw_build, "platform", context),
                builder=_required_string(raw_build, "builder", context),
                product_commit=_required_string(raw_build, "product_commit", context),
                artifact=_required_string(raw_build, "artifact", context),
                sha256=sha256,
                tests=tuple(raw_tests),
            )
        )

    return ReleaseManifest(
        path=path.resolve(),
        release=_required_string(data, "release", "manifest"),
        base_repo=_required_string(base, "repo", "base"),
        base_commit=_required_string(base, "commit", "base"),
        base_branch=_required_string(base, "branch", "base"),
        patches=tuple(patches),
        source_tree=source_tree,
        build_flavor=build_flavor,
        require_provenance_receipt=require_provenance_receipt,
        builds=tuple(builds),
    )
