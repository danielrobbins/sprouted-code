# Patch Queue

Every change carried by a Sprouted Code build lives here as an immutable patch
file. Builds clone Microsoft's repository at the exact manifest base commit and
apply this local queue in manifest order. They do not fetch patch branches or
contributor forks.

The release manifest records the local file for each patch along with upstream
issues, pull requests, and source commits where available. Those links preserve
provenance and review history without becoming build dependencies.

Microsoft's open-source Visual Studio Code repository is MIT-licensed. Patch
material in this directory is distributed under the MIT License so it remains
compatible with the upstream project and can be submitted without a license
mismatch. Microsoft and existing
contributors retain copyright in upstream material. Original contributions in
the initial BreezyOps patchset may be copyright BreezyOps, Inc. See
[`patches/LICENSE`](LICENSE) and [`LICENSING.md`](../LICENSING.md).

## Current patches

- `0000-allow-byok-without-copilot-entitlement.patch`
  separates BYOK availability from Copilot entitlement state. A GitHub user
  without a Copilot seat can continue using independently configured custom
  endpoints, while managed-account policy remains enforceable and testable
  across the supported account and policy states. This patch is under review in
  [microsoft/vscode#324311](https://github.com/microsoft/vscode/pull/324311).
- `0001-keep-builtin-chat-extension-enabled-for-byok-builds.patch`
  keeps the bundled `GitHub.copilot-chat` extension enabled on first run. Upstream
  Visual Studio Code source disables the built-in chat extension for fresh profiles until Copilot
  setup completes, which hides the BYOK endpoint-management UI. Sprouted builds
  intentionally ship the chat extension active so BYOK models can be configured
  without requiring a Copilot sign-in first.
- `0002-preserve-copilot-sdk-entrypoint-for-source-builds.patch`
  preserves `@github/copilot/sdk/index.js` in local source builds. Current Copilot
  code imports `@github/copilot/sdk`, and pruning that entrypoint leaves the
  packaged extension with a `package.json` export that points at a missing file.
- `0003-keep-byok-model-management-reachable-during-setup.patch`
  keeps `Manage Models...` visible in the model picker when Chat is still in the
  Copilot setup-required state but BYOK model management is allowed. This fixes
  the first-run BYOK case where no custom models exist yet, so `hasByokModels`
  is false, but the user still needs a reachable UI to add one.
- `0004-identify-build-as-sprouted-code.patch`
  changes minimal product identity fields so the packaged build launches as
  Sprouted Code, produces a `Sprouted Code.exe` executable, and uses a distinct
  `sprouted-code` CLI/application identity.
- `0005-use-product-name-in-welcome-onboarding.patch`
  updates the first-launch onboarding welcome title and dialog label to use the
  product name from `product.json`, so Sprouted builds say "Welcome to Sprouted
  Code" instead of hard-coding VS Code.
- `0006-only-patch-windows-pe-dependencies.patch`
  checks native dependencies for a valid Windows Portable Executable header
  before passing them to `signtool.exe` and `rcedit.exe`. This allows Windows
  source builds to package extensions that also contain Linux or macOS native
  modules, while preserving resource updates for actual Windows binaries.
- `0007-use-cross-platform-build-test-glob.patch`
  uses portable command quoting for the build package's Node test glob. The
  previous single quotes were passed literally by `cmd.exe`, causing `npm test`
  to report success after discovering zero tests on Windows.
- `0008-enable-microsoft-extension-marketplace.patch`
  configures the Microsoft extension gallery endpoints used by the current
  Visual Studio Code distribution. Application of this patch is controlled by
  `product.extension_gallery.enabled` in `sprouted-build.yaml` and is enabled
  by default for the initial public test builds.
- `0009-configure-extension-signature-verification.patch`
  lets a downstream product declare whether its extension gallery supports
  signature verification. Microsoft supplies its proprietary verifier through
  a separate product-build overlay that Sprouted Code cannot redistribute, so
  Sprouted explicitly defaults verification off while upstream and other
  products retain the existing default of verification on.
