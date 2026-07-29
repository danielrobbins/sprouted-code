import subprocess
from pathlib import Path

import pytest

from sprouted_build.commands import CommandRunner
from sprouted_build.config import ConfigError
from sprouted_build.manifest import ReleaseManifest
from sprouted_build.provenance import (
    expected_provenance,
    verify_checkout_provenance,
    verify_output_provenance,
    write_output_provenance,
)


def _manifest(path: Path, source_tree: str) -> ReleaseManifest:
    return ReleaseManifest(
        path=path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="base",
        base_branch="main",
        patches=(),
        source_tree=source_tree,
    )


def _git(checkout: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=checkout,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def test_checkout_gate_accepts_exact_clean_tree(tmp_path: Path) -> None:
    checkout = tmp_path / "vscode"
    checkout.mkdir()
    _git(checkout, "init")
    (checkout / "source.txt").write_text("source", encoding="utf-8")
    _git(checkout, "add", "source.txt")
    _git(
        checkout,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "source",
    )
    tree = _git(checkout, "rev-parse", "HEAD^{tree}")

    verify_checkout_provenance(
        checkout,
        _manifest(tmp_path, tree),
        CommandRunner(),
    )


def test_checkout_gate_rejects_dirty_tree(tmp_path: Path) -> None:
    checkout = tmp_path / "vscode"
    checkout.mkdir()
    _git(checkout, "init")
    (checkout / "source.txt").write_text("source", encoding="utf-8")
    _git(checkout, "add", "source.txt")
    _git(
        checkout,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "source",
    )
    tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    (checkout / "source.txt").write_text("changed", encoding="utf-8")

    with pytest.raises(ConfigError, match="dirty VS Code checkout"):
        verify_checkout_provenance(
            checkout,
            _manifest(tmp_path, tree),
            CommandRunner(),
        )


def test_checkout_gate_rejects_wrong_clean_tree(tmp_path: Path) -> None:
    checkout = tmp_path / "vscode"
    checkout.mkdir()
    _git(checkout, "init")
    (checkout / "source.txt").write_text("source", encoding="utf-8")
    _git(checkout, "add", "source.txt")
    _git(
        checkout,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "source",
    )

    with pytest.raises(ConfigError, match="does not match the release manifest"):
        verify_checkout_provenance(
            checkout,
            _manifest(tmp_path, "a" * 40),
            CommandRunner(),
        )


def test_output_receipt_must_match_build(tmp_path: Path) -> None:
    output = tmp_path / "VSCode-win32-arm64"
    output.mkdir()
    manifest = _manifest(tmp_path, "a" * 40)
    expected = expected_provenance(
        manifest,
        platform="win32",
        architecture="arm64",
        flavor="release",
        gulp_target="vscode-win32-arm64-min",
    )
    write_output_provenance(output, expected)

    verify_output_provenance(output, expected)

    wrong = expected_provenance(
        manifest,
        platform="win32",
        architecture="x64",
        flavor="release",
        gulp_target="vscode-win32-x64-min",
    )
    with pytest.raises(ConfigError, match="does not match"):
        verify_output_provenance(output, wrong)
