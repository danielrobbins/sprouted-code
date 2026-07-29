from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .config import BuildConfig, ConfigError
from .manifest import ReleaseManifest


def resolve_local_patch(config: BuildConfig, source_ref: str) -> Path:
    path = (config.repo_root / source_ref).resolve()
    try:
        path.relative_to(config.repo_root)
    except ValueError as error:
        raise ConfigError(
            f"Patch path escapes repository root: {source_ref}"
        ) from error
    if not path.is_file():
        raise ConfigError(f"Patch file not found: {path}")
    return path


def resolve_build_patches(
    config: BuildConfig,
    manifest: ReleaseManifest,
) -> tuple[Path, ...]:
    patches = [
        resolve_local_patch(config, patch.source_ref)
        for patch in manifest.patches
        if patch.is_file
    ]

    gallery = config.get("product.extension_gallery", {})
    if not isinstance(gallery, Mapping):
        raise ConfigError("product.extension_gallery must be a mapping")
    enabled = gallery.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("product.extension_gallery.enabled must be true or false")
    if enabled:
        patch_ref = gallery.get("patch")
        if not isinstance(patch_ref, str) or not patch_ref:
            raise ConfigError(
                "product.extension_gallery.patch is required when the gallery is enabled"
            )
        gallery_patch = resolve_local_patch(config, patch_ref)
        if gallery_patch not in patches:
            raise ConfigError(
                "The enabled extension gallery patch must be declared in the "
                "release manifest patch queue"
            )

        verify_signatures = gallery.get("verify_signatures", True)
        if not isinstance(verify_signatures, bool):
            raise ConfigError(
                "product.extension_gallery.verify_signatures must be true or false"
            )
        if not verify_signatures:
            policy_patch_ref = gallery.get("signature_policy_patch")
            if not isinstance(policy_patch_ref, str) or not policy_patch_ref:
                raise ConfigError(
                    "product.extension_gallery.signature_policy_patch is required "
                    "when signature verification is disabled"
                )
            policy_patch = resolve_local_patch(config, policy_patch_ref)
            if policy_patch not in patches:
                raise ConfigError(
                    "The extension signature policy patch must be declared in the "
                    "release manifest patch queue"
                )

    if len(set(patches)) != len(patches):
        raise ConfigError("The build patch queue contains a duplicate patch path")
    return tuple(patches)
