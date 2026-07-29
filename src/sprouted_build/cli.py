from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Sequence

import yaml

from .artifacts import write_checksums
from .commands import CommandRunner
from .config import ConfigError, load_build_config
from .focused_tests import run_focused_windows_tests
from .flavors import BUILD_FLAVORS
from .manifest import ManifestError, load_release_manifest
from .macos import MACOS_ARCHITECTURES, preflight_macos
from .macos_build import build_macos
from .macos_provision import provision_macos
from .macos_source import prepare_macos_checkout
from .proxmox_build import build_proxmox, preflight_proxmox
from .proxmox_provision import provision_proxmox
from .proxmox_source import prepare_proxmox_checkout
from .release import verify_release_artifacts
from .source import prepare_windows_checkout
from .windows import preflight_windows
from .windows_build import WINDOWS_ARCHITECTURES, build_windows
from .windows_install import (
    install_windows_artifact,
    launch_windows,
    resolve_windows_artifact,
)
from .wsl import LINUX_ARCHITECTURES, preflight_wsl
from .wsl_build import build_wsl
from .wsl_provision import provision_wsl
from .wsl_source import prepare_wsl_checkout


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sprouted-build")
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--local-config", type=Path)
    parser.add_argument("--no-local-config", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Inspect build configuration")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_subparsers.add_parser(
        "validate", help="Validate defaults and local overrides"
    )
    show_parser = config_subparsers.add_parser(
        "show", help="Print effective configuration"
    )
    show_parser.add_argument("--json", action="store_true", dest="as_json")

    checksum_parser = subparsers.add_parser("checksums", help="Write SHA-256 checksums")
    checksum_parser.add_argument("--artifact-directory", type=Path)
    checksum_parser.add_argument("--output-file", default="checksums.txt")

    release_parser = subparsers.add_parser(
        "release", help="Validate release artifacts and evidence"
    )
    release_subparsers = release_parser.add_subparsers(
        dest="release_command", required=True
    )
    release_verify_parser = release_subparsers.add_parser(
        "verify", help="Verify artifacts against the release manifest"
    )
    release_verify_parser.add_argument("--artifact-directory", type=Path)

    preflight_parser = subparsers.add_parser(
        "preflight", help="Validate a build environment"
    )
    preflight_subparsers = preflight_parser.add_subparsers(
        dest="platform",
        required=True,
    )
    preflight_subparsers.add_parser("windows", help="Validate the Windows toolchain")
    preflight_wsl_parser = preflight_subparsers.add_parser(
        "wsl", help="Validate a native WSL Linux builder"
    )
    preflight_wsl_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES)
    preflight_proxmox_parser = preflight_subparsers.add_parser(
        "proxmox", help="Validate a Proxmox Linux builder container"
    )
    preflight_proxmox_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES)
    preflight_macos_parser = preflight_subparsers.add_parser(
        "macos", help="Validate a native remote macOS builder"
    )
    preflight_macos_parser.add_argument("--arch", choices=MACOS_ARCHITECTURES)

    provision_parser = subparsers.add_parser(
        "provision", help="Provision a build environment"
    )
    provision_subparsers = provision_parser.add_subparsers(
        dest="platform", required=True
    )
    provision_wsl_parser = provision_subparsers.add_parser(
        "wsl", help="Provision a native WSL Linux builder"
    )
    provision_wsl_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES)
    provision_wsl_parser.add_argument("--install-packages", action="store_true")
    provision_wsl_parser.add_argument("--install-node", action="store_true")
    provision_wsl_parser.add_argument("--clone", action="store_true")
    provision_wsl_parser.add_argument("--all", action="store_true")
    provision_wsl_parser.add_argument("--dry-run", action="store_true")
    provision_proxmox_parser = provision_subparsers.add_parser(
        "proxmox", help="Provision a Proxmox Linux builder container"
    )
    provision_proxmox_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES)
    provision_proxmox_parser.add_argument("--install-packages", action="store_true")
    provision_proxmox_parser.add_argument("--install-node", action="store_true")
    provision_proxmox_parser.add_argument("--clone", action="store_true")
    provision_proxmox_parser.add_argument("--all", action="store_true")
    provision_proxmox_parser.add_argument("--dry-run", action="store_true")
    provision_macos_parser = provision_subparsers.add_parser(
        "macos", help="Provision a native remote macOS builder"
    )
    provision_macos_parser.add_argument("--arch", choices=MACOS_ARCHITECTURES)
    provision_macos_parser.add_argument("--install-node", action="store_true")
    provision_macos_parser.add_argument("--clone", action="store_true")
    provision_macos_parser.add_argument("--all", action="store_true")
    provision_macos_parser.add_argument("--dry-run", action="store_true")

    prepare_parser = subparsers.add_parser("prepare", help="Prepare a source checkout")
    prepare_subparsers = prepare_parser.add_subparsers(dest="platform", required=True)
    prepare_windows_parser = prepare_subparsers.add_parser(
        "windows",
        help="Prepare the Windows VS Code checkout",
    )
    prepare_windows_parser.add_argument("--skip-fetch", action="store_true")
    prepare_windows_parser.add_argument("--dry-run", action="store_true")
    prepare_wsl_parser = prepare_subparsers.add_parser(
        "wsl", help="Prepare a WSL-native VS Code checkout"
    )
    prepare_wsl_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES)
    prepare_wsl_parser.add_argument("--skip-fetch", action="store_true")
    prepare_wsl_parser.add_argument("--dry-run", action="store_true")
    prepare_proxmox_parser = prepare_subparsers.add_parser(
        "proxmox", help="Prepare a Proxmox Linux VS Code checkout"
    )
    prepare_proxmox_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES)
    prepare_proxmox_parser.add_argument("--skip-fetch", action="store_true")
    prepare_proxmox_parser.add_argument("--dry-run", action="store_true")
    prepare_macos_parser = prepare_subparsers.add_parser(
        "macos", help="Prepare source on a native remote macOS builder"
    )
    prepare_macos_parser.add_argument("--arch", choices=MACOS_ARCHITECTURES)
    prepare_macos_parser.add_argument("--skip-fetch", action="store_true")
    prepare_macos_parser.add_argument("--dry-run", action="store_true")

    test_parser = subparsers.add_parser("test", help="Run build-related tests")
    test_subparsers = test_parser.add_subparsers(dest="test_command", required=True)
    test_subparsers.add_parser("focused", help="Run the focused BYOK tests on Windows")

    build_parser = subparsers.add_parser("build", help="Build a Sprouted Code package")
    build_subparsers = build_parser.add_subparsers(dest="platform", required=True)
    build_windows_parser = build_subparsers.add_parser(
        "windows",
        help="Build a Windows package",
    )
    build_windows_parser.add_argument(
        "--arch", choices=WINDOWS_ARCHITECTURES, required=True
    )
    build_windows_parser.add_argument(
        "--flavor", choices=BUILD_FLAVORS, default="release"
    )
    build_windows_parser.add_argument("--skip-install", action="store_true")
    build_windows_parser.add_argument("--skip-tests", action="store_true")
    build_windows_parser.add_argument("--skip-gulp", action="store_true")
    build_windows_parser.add_argument("--no-archive", action="store_true")
    build_windows_parser.add_argument("--dry-run", action="store_true")
    build_wsl_parser = build_subparsers.add_parser(
        "wsl", help="Build a native WSL Linux package"
    )
    build_wsl_parser.add_argument("--arch", choices=LINUX_ARCHITECTURES, required=True)
    build_wsl_parser.add_argument("--flavor", choices=BUILD_FLAVORS, default="release")
    build_wsl_parser.add_argument("--skip-install", action="store_true")
    build_wsl_parser.add_argument("--skip-tests", action="store_true")
    build_wsl_parser.add_argument("--skip-gulp", action="store_true")
    build_wsl_parser.add_argument("--no-archive", action="store_true")
    build_wsl_parser.add_argument("--dry-run", action="store_true")
    build_proxmox_parser = build_subparsers.add_parser(
        "proxmox", help="Build a Linux package in Proxmox"
    )
    build_proxmox_parser.add_argument(
        "--arch", choices=LINUX_ARCHITECTURES, required=True
    )
    build_proxmox_parser.add_argument(
        "--flavor", choices=BUILD_FLAVORS, default="release"
    )
    build_proxmox_parser.add_argument("--skip-install", action="store_true")
    build_proxmox_parser.add_argument("--skip-tests", action="store_true")
    build_proxmox_parser.add_argument("--skip-gulp", action="store_true")
    build_proxmox_parser.add_argument("--no-archive", action="store_true")
    build_proxmox_parser.add_argument("--no-pull", action="store_true")
    build_proxmox_parser.add_argument("--dry-run", action="store_true")
    build_macos_parser = build_subparsers.add_parser(
        "macos", help="Build on a native remote macOS builder"
    )
    build_macos_parser.add_argument(
        "--arch", choices=MACOS_ARCHITECTURES, required=True
    )
    build_macos_parser.add_argument(
        "--flavor", choices=BUILD_FLAVORS, default="release"
    )
    build_macos_parser.add_argument("--skip-install", action="store_true")
    build_macos_parser.add_argument("--skip-tests", action="store_true")
    build_macos_parser.add_argument("--skip-gulp", action="store_true")
    build_macos_parser.add_argument("--no-archive", action="store_true")
    build_macos_parser.add_argument("--no-pull", action="store_true")
    build_macos_parser.add_argument("--dry-run", action="store_true")

    install_parser = subparsers.add_parser("install", help="Install a build artifact")
    install_subparsers = install_parser.add_subparsers(dest="platform", required=True)
    install_windows_parser = install_subparsers.add_parser(
        "windows",
        help="Install a portable Windows build",
    )
    install_windows_parser.add_argument(
        "--arch", choices=WINDOWS_ARCHITECTURES, required=True
    )
    install_windows_parser.add_argument(
        "--flavor", choices=BUILD_FLAVORS, default="release"
    )
    install_windows_parser.add_argument("--artifact", type=Path)
    install_windows_parser.add_argument("--preserve-user-data", action="store_true")
    install_windows_parser.add_argument("--launch", action="store_true")

    launch_parser = subparsers.add_parser("launch", help="Launch an installed build")
    launch_subparsers = launch_parser.add_subparsers(dest="platform", required=True)
    launch_windows_parser = launch_subparsers.add_parser(
        "windows",
        help="Launch the portable Windows build",
    )
    launch_windows_parser.add_argument("--user-data-dir", type=Path)
    launch_windows_parser.add_argument("--extensions-dir", type=Path)
    launch_windows_parser.add_argument("--disable-workspace-trust", action="store_true")
    launch_windows_parser.add_argument("arguments", nargs=argparse.REMAINDER)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_build_config(
            args.repo_root,
            local_config=args.local_config,
            include_local=not args.no_local_config,
        )

        if args.command == "config":
            if args.config_command == "validate":
                print("Build configuration is valid.")
                for source in config.sources:
                    print(f"  {source}")
                return 0
            if args.config_command == "show":
                if args.as_json:
                    print(json.dumps(config.data, indent=2))
                else:
                    print(yaml.safe_dump(config.data, sort_keys=False).rstrip())
                return 0

        if args.command == "checksums":
            artifact_directory = (
                args.artifact_directory.resolve()
                if args.artifact_directory
                else config.resolve_path("paths.artifacts")
            )
            output_path = write_checksums(
                artifact_directory,
                output_file=args.output_file,
            )
            print(f"Wrote {output_path}")
            return 0

        if args.command == "release" and args.release_command == "verify":
            artifact_directory = (
                args.artifact_directory.resolve()
                if args.artifact_directory
                else config.resolve_path("paths.artifacts")
            )
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            verification = verify_release_artifacts(artifact_directory, manifest)
            for artifact in verification.artifacts:
                print(f"Verified {artifact.name}")
            for warning in verification.warnings:
                print(f"Warning: {warning}")
            print(
                f"Verified {len(verification.artifacts)} release artifact(s) "
                "against the manifest."
            )
            return 0

        if args.command == "preflight" and args.platform == "windows":
            preflight_windows(config, CommandRunner())
            return 0

        if args.command == "preflight" and args.platform == "wsl":
            preflight_wsl(config, CommandRunner(), architecture=args.arch)
            return 0
        if args.command == "preflight" and args.platform == "proxmox":
            preflight_proxmox(config, CommandRunner(), architecture=args.arch)
            return 0
        if args.command == "preflight" and args.platform == "macos":
            preflight_macos(config, CommandRunner(), architecture=args.arch)
            return 0

        if args.command == "provision" and args.platform == "wsl":
            provision_wsl(
                config,
                CommandRunner(dry_run=args.dry_run),
                architecture=args.arch,
                install_packages=args.install_packages or args.all,
                install_node=args.install_node or args.all,
                clone=args.clone or args.all,
            )
            return 0
        if args.command == "provision" and args.platform == "proxmox":
            provision_proxmox(
                config,
                CommandRunner(dry_run=args.dry_run),
                install_packages=args.install_packages or args.all,
                install_node=args.install_node or args.all,
                clone=args.clone or args.all,
                architecture=args.arch,
            )
            return 0
        if args.command == "provision" and args.platform == "macos":
            provision_macos(
                config,
                CommandRunner(dry_run=args.dry_run),
                install_node=args.install_node or args.all,
                clone=args.clone or args.all,
                architecture=args.arch,
            )
            return 0

        if args.command == "prepare" and args.platform == "windows":
            manifest_path = config.resolve_path("release_manifest")
            manifest = load_release_manifest(manifest_path)
            prepare_windows_checkout(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                skip_fetch=args.skip_fetch,
            )
            return 0

        if args.command == "prepare" and args.platform == "wsl":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            prepare_wsl_checkout(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                architecture=args.arch,
                skip_fetch=args.skip_fetch,
            )
            return 0
        if args.command == "prepare" and args.platform == "proxmox":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            prepare_proxmox_checkout(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                skip_fetch=args.skip_fetch,
                architecture=args.arch,
            )
            return 0
        if args.command == "prepare" and args.platform == "macos":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            prepare_macos_checkout(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                skip_fetch=args.skip_fetch,
                architecture=args.arch,
            )
            return 0

        if args.command == "test" and args.test_command == "focused":
            run_focused_windows_tests(config, CommandRunner())
            return 0

        if args.command == "build" and args.platform == "windows":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            toolchain = preflight_windows(config, CommandRunner())
            build_windows(
                config,
                manifest,
                toolchain,
                CommandRunner(dry_run=args.dry_run),
                architecture=args.arch,
                flavor=args.flavor,
                skip_install=args.skip_install,
                skip_tests=args.skip_tests,
                skip_gulp=args.skip_gulp,
                no_archive=args.no_archive,
            )
            return 0

        if args.command == "build" and args.platform == "wsl":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            build_wsl(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                architecture=args.arch,
                flavor=args.flavor,
                skip_install=args.skip_install,
                skip_tests=args.skip_tests,
                skip_gulp=args.skip_gulp,
                no_archive=args.no_archive,
            )
            return 0
        if args.command == "build" and args.platform == "proxmox":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            build_proxmox(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                architecture=args.arch,
                flavor=args.flavor,
                skip_install=args.skip_install,
                skip_tests=args.skip_tests,
                skip_gulp=args.skip_gulp,
                no_archive=args.no_archive,
                no_pull=args.no_pull,
            )
            return 0
        if args.command == "build" and args.platform == "macos":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            build_macos(
                config,
                manifest,
                CommandRunner(dry_run=args.dry_run),
                architecture=args.arch,
                flavor=args.flavor,
                skip_install=args.skip_install,
                skip_tests=args.skip_tests,
                skip_gulp=args.skip_gulp,
                no_archive=args.no_archive,
                no_pull=args.no_pull,
            )
            return 0

        if args.command == "install" and args.platform == "windows":
            manifest = load_release_manifest(config.resolve_path("release_manifest"))
            artifact_path = resolve_windows_artifact(
                config,
                manifest,
                architecture=args.arch,
                flavor=args.flavor,
                artifact_path=args.artifact,
            )
            install_windows_artifact(
                config,
                artifact_path,
                preserve_user_data=args.preserve_user_data,
            )
            if args.launch:
                launch_windows(config)
            return 0

        if args.command == "launch" and args.platform == "windows":
            extra_arguments = args.arguments
            if extra_arguments[:1] == ["--"]:
                extra_arguments = extra_arguments[1:]
            launch_windows(
                config,
                user_data_directory=args.user_data_dir,
                extensions_directory=args.extensions_dir,
                disable_workspace_trust=args.disable_workspace_trust,
                extra_arguments=extra_arguments,
            )
            return 0
    except (
        ConfigError,
        ManifestError,
        FileNotFoundError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        parser.error(str(error))

    return 2
