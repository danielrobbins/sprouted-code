from sprouted_build.macos import MacOSBuilder
from sprouted_build.macos_build import (
    MACOS_BUNDLE_IDENTIFIER,
    MACOS_CLI_NAME,
    build_macos_build_script,
    macos_artifact_name,
)
from sprouted_build.provenance import BuildProvenance, PROVENANCE_FILE


def _builder() -> MacOSBuilder:
    return MacOSBuilder(
        "builder@mac",
        "arm64",
        "/Users/builder/repos/vscode",
        "/Users/builder/.local",
        "/Users/builder/artifacts",
        "24.18.0",
    )


def _provenance() -> BuildProvenance:
    return BuildProvenance(
        schema_version=1,
        release="2026.07.0",
        source_tree="a" * 40,
        platform="darwin",
        architecture="arm64",
        flavor="release",
        gulp_target="vscode-darwin-arm64-min",
    )


def test_macos_artifact_name_contains_release_and_architecture() -> None:
    assert (
        macos_artifact_name("2026.07.0", "arm64")
        == "sprouted-code-2026.07.0-darwin-arm64.zip"
    )


def test_macos_build_runs_tests_gulp_and_provenance_archive() -> None:
    script = build_macos_build_script(
        _builder(),
        release_name="sprouted-code-2026.07.0-darwin-arm64",
        provenance=_provenance(),
        flavor="release",
        skip_install=False,
        skip_tests=False,
        skip_gulp=False,
        no_archive=False,
    )

    assert "npm ci" in script
    assert "export CI=1" in script
    assert "byokProvider.spec.ts" in script
    assert "npm run gulp -- vscode-darwin-arm64-min" in script
    assert 'rm -rf "$output_dir"' in script
    assert "Sprouted Code.app" in script
    assert MACOS_BUNDLE_IDENTIFIER in script
    assert f"Contents/Resources/app/bin/{MACOS_CLI_NAME}" in script
    assert "codesign --force --deep --sign - --timestamp=none" in script
    assert "codesign --verify --deep --strict --verbose=2" in script
    assert "Signature=adhoc" in script
    assert PROVENANCE_FILE in script
    assert "zip -Xqry" in script
    assert "shasum -a 256" in script
