from sprouted_build.provenance import BuildProvenance, PROVENANCE_FILE
from sprouted_build.wsl import WslBuilder
from sprouted_build.wsl_build import build_wsl_build_script, linux_artifact_name


def _provenance(architecture: str, flavor: str = "release") -> BuildProvenance:
    suffix = "-min" if flavor == "release" else ""
    return BuildProvenance(
        schema_version=1,
        release="2026.07.0",
        source_tree="a" * 40,
        platform="linux",
        architecture=architecture,
        flavor=flavor,
        gulp_target=f"vscode-linux-{architecture}{suffix}",
    )


def test_linux_artifact_name_contains_release_and_architecture() -> None:
    assert (
        linux_artifact_name("2026.07.0", "arm64")
        == "sprouted-code-2026.07.0-linux-arm64.tar.gz"
    )


def test_build_script_runs_tests_gulp_and_archive() -> None:
    builder = WslBuilder(
        "Ubuntu",
        "arm64",
        "~/repos/vscode",
        "24.18.0",
        cc="gcc-11",
        cxx="g++-11",
    )

    script = build_wsl_build_script(
        builder,
        artifact_directory="/mnt/c/repo/artifacts",
        release_name="sprouted-code-2026.07.0-linux-arm64",
        provenance=_provenance("arm64"),
        flavor="release",
        skip_install=False,
        skip_tests=False,
        skip_gulp=False,
        no_archive=False,
    )

    assert "npm ci" in script
    assert "export CI=1" in script
    assert "export CC=gcc-11" in script
    assert "export VSCODE_REMOTE_CXX=g++-11" in script
    assert "byokProvider.spec.ts" in script
    assert "byokPolicy.spec.ts" in script
    assert "npm run gulp -- vscode-linux-arm64-min" in script
    assert "git status --porcelain" in script
    assert "git rev-parse 'HEAD^{tree}'" in script
    assert 'rm -rf "$output_dir"' in script
    assert PROVENANCE_FILE in script
    assert "VSCode-linux-arm64" in script
    assert "/mnt/c/repo/artifacts" in script


def test_noop_build_script_omits_optional_stages() -> None:
    builder = WslBuilder("Ubuntu", "x64", "~/repos/vscode", "24.18.0")

    script = build_wsl_build_script(
        builder,
        artifact_directory="/mnt/c/repo/artifacts",
        release_name="release",
        provenance=_provenance("x64", "diagnostic"),
        flavor="diagnostic",
        skip_install=True,
        skip_tests=True,
        skip_gulp=True,
        no_archive=True,
    )

    assert "npm ci" not in script
    assert "npm run gulp" not in script
    assert "export CI=1" not in script
    assert "git status --porcelain" in script


def test_diagnostic_build_uses_non_minified_target() -> None:
    builder = WslBuilder("Ubuntu", "x64", "~/repos/vscode", "24.18.0")

    script = build_wsl_build_script(
        builder,
        artifact_directory="/mnt/c/repo/artifacts",
        release_name="release-diagnostic",
        provenance=_provenance("x64", "diagnostic"),
        flavor="diagnostic",
        skip_install=True,
        skip_tests=True,
        skip_gulp=False,
        no_archive=True,
    )

    assert "npm run gulp -- vscode-linux-x64" in script
    assert "vscode-linux-x64-min" not in script
    assert PROVENANCE_FILE in script
