import json
from pathlib import Path

import pytest

from sprouted_build.manifest import ManifestError, load_release_manifest


def test_manifest_loads_exact_build_inputs(tmp_path: Path) -> None:
    path = tmp_path / "release.json"
    path.write_text(
        json.dumps(
            {
                "release": "2026.07.0",
                "base": {
                    "repo": "microsoft/vscode",
                    "commit": "abc123",
                    "branch": "main",
                },
                "build": {
                    "flavor": "release",
                    "source_tree": "1" * 40,
                    "provenance_receipt": True,
                },
                "patches": [
                    {
                        "name": "Committed patch",
                        "source_repo": "example/vscode",
                        "source_ref": "patches/contribution.patch",
                        "source_commit": "def456",
                    },
                    {
                        "name": "File patch",
                        "source_repo": "example/build",
                        "source_ref": "patches/fix.patch",
                        "source_commit": "",
                    },
                ],
                "builds": [
                    {
                        "platform": "win32-arm64",
                        "builder": "local",
                        "product_commit": "abc123",
                        "artifact": "sprouted.zip",
                        "sha256": "2" * 64,
                        "tests": ["unit tests: pass"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_release_manifest(path)

    assert manifest.release == "2026.07.0"
    assert manifest.base_commit == "abc123"
    assert manifest.source_tree == "1" * 40
    assert manifest.require_provenance_receipt is True
    assert manifest.patches[0].source_commit == "def456"
    assert manifest.patches[1].is_file
    assert manifest.builds[0].artifact == "sprouted.zip"


def test_manifest_rejects_non_file_patch_sources(tmp_path: Path) -> None:
    path = tmp_path / "release.json"
    path.write_text(
        json.dumps(
            {
                "release": "test",
                "base": {"repo": "microsoft/vscode", "commit": "abc", "branch": "main"},
                "patches": [
                    {
                        "name": "Floating branch",
                        "source_repo": "example/vscode",
                        "source_ref": "feature",
                        "source_commit": "def456",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match=r"local \.patch file"):
        load_release_manifest(path)
