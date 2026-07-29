import json
from pathlib import Path

from sprouted_build.commands import CommandRunner
from sprouted_build.config import load_build_config
from sprouted_build.manifest import load_release_manifest
from sprouted_build.source import prepare_windows_checkout


def test_prepare_plan_uses_exact_manifest_commits(tmp_path: Path) -> None:
    checkout = tmp_path / "vscode"
    (checkout / ".git").mkdir(parents=True)
    patches = tmp_path / "patches"
    patches.mkdir()
    (patches / "byok.patch").write_text("patch", encoding="utf-8")
    (patches / "local.patch").write_text("patch", encoding="utf-8")
    (tmp_path / "sprouted-build.yaml").write_text(
        f"""
schema_version: 1
release_manifest: release.json
source:
  upstream_url: https://example.test/microsoft/vscode.git
  build_branch_prefix: sprouted-code
builders:
  windows:
    vscode_checkout: '{checkout.as_posix()}'
""".lstrip(),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "release.json"
    manifest_path.write_text(
        json.dumps(
            {
                "release": "2026.07.0",
                "base": {
                    "repo": "microsoft/vscode",
                    "commit": "base-sha",
                    "branch": "main",
                },
                "patches": [
                    {
                        "name": "Contribution",
                        "source_repo": "example/vscode",
                        "source_ref": "patches/byok.patch",
                        "source_commit": "patch-sha",
                    },
                    {
                        "name": "Local",
                        "source_repo": "example/build",
                        "source_ref": "patches/local.patch",
                        "source_commit": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    config = load_build_config(tmp_path, include_local=False)
    manifest = load_release_manifest(manifest_path)
    runner = CommandRunner(dry_run=True)

    prepare_windows_checkout(config, manifest, runner)

    assert runner.commands[0] == ("git", "status", "--porcelain")
    assert runner.commands[1] == (
        "git",
        "fetch",
        "https://example.test/microsoft/vscode.git",
        "main",
    )
    assert runner.commands[2] == (
        "git",
        "switch",
        "-C",
        "sprouted-code/2026.07.0",
        "base-sha",
    )
    assert all("merge" not in command for command in runner.commands)
    assert runner.commands[3][-2:] == (
        "--check",
        str(patches / "byok.patch"),
    )
    assert ("git", "add", "--all") in runner.commands
    assert runner.commands[-2][-2:] == (
        "-m",
        "Apply Sprouted Code local patch queue",
    )
    assert runner.commands[-1] == ("git", "status", "--short", "--branch")
