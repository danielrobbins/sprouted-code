from pathlib import Path

from sprouted_build.cli import main


def test_checksums_command_uses_configured_artifact_directory(
    tmp_path: Path,
    capsys,
) -> None:
    artifacts = tmp_path / "release-artifacts"
    artifacts.mkdir()
    (artifacts / "sprouted.zip").write_bytes(b"artifact")
    (tmp_path / "sprouted-build.yaml").write_text(
        """
schema_version: 1
paths:
  artifacts: release-artifacts
builders: {}
""".lstrip(),
        encoding="utf-8",
    )

    result = main(
        [
            "--repo-root",
            str(tmp_path),
            "--no-local-config",
            "checksums",
        ]
    )

    assert result == 0
    assert (artifacts / "checksums.txt").is_file()
    assert "Wrote" in capsys.readouterr().out
