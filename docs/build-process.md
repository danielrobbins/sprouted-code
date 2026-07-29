# Build Process

This document describes how to prepare and run the supported Sprouted Code
build lanes.

## Recommended Control Workstation

Start the build from Windows 11. A complete desktop release normally includes
Windows, and the Windows toolchain is the awkward platform to operate remotely:
it depends on Visual Studio, the Windows SDK, PowerShell, and native packaging
tools. Keeping that lane local makes failures much easier to inspect.

The same Windows workstation can orchestrate the remaining builds:

- **Windows** builds run directly on the control workstation.
- **WSL** builds run inside a native Linux distribution through `wsl.exe`.
- **Proxmox** builds travel over SSH to a Proxmox host and run inside an
  existing Linux container through `pct`.
- **macOS** builds travel over SSH to a real Apple Silicon Mac.

Linux and macOS are straightforward remote build targets because their complete
workflows can run through SSH and ordinary shell commands. Sprouted Code does
not currently provide a remote Windows backend. Starting on Windows keeps the
one platform that benefits most from direct desktop access close at hand while
the Python tooling coordinates everything else.

## Prime the Build Environment

Sprouted Code uses the `sprouted-build` Python package in this repository. It
manages source preparation, builder provisioning, focused tests, packaging,
artifact transfer, installation, and checksums for every supported lane.

On the Windows control workstation:

1. Install Git, `uv`, Visual Studio with the C++ desktop workload, and the
   Windows SDK.
2. Create a dedicated upstream Visual Studio Code build checkout. Do not point
   the tooling at a checkout used for unrelated development.
3. Copy the local configuration example:

```powershell
Copy-Item sprouted-build.local.yaml.example sprouted-build.local.yaml
```

4. Edit `sprouted-build.local.yaml` for the builders you plan to use. The
   checked-in [example](../sprouted-build.local.yaml.example) documents every
   currently supported lane.
5. Set up key-based SSH access for Proxmox and macOS builders. Passwords and
   private keys belong in the operating system's SSH configuration and agent.
6. Create the Python environment and inspect the merged configuration:

```powershell
uv sync --dev
uv run sprouted-build config validate
uv run sprouted-build config show
```

Configuration validation checks the merged YAML structure. Each backend's
preflight then verifies its required paths, accounts, architecture, and
toolchain on the actual builder.

The local file needs only machine-specific overrides:

| Builder | Values to configure | Environment that must already exist |
| --- | --- | --- |
| Windows | Dedicated source checkout; optional Node and Visual Studio paths | Visual Studio C++ workload and Windows SDK |
| WSL | Distribution name, native Linux checkout, user, and compilers | A WSL distribution with the requested native architecture |
| Proxmox | SSH target, container ID, remote owner, and container paths | An existing Linux container and passwordless `sudo pct` access on the host |
| macOS | SSH target, checkout, Node root, and artifact directory | Apple Silicon Mac with Xcode command-line tools |

Provisioning can install the pinned Node release, required Linux packages, and
dedicated source checkouts after these foundations are available:

```powershell
uv run sprouted-build provision wsl --arch arm64 --all
uv run sprouted-build provision proxmox --arch x64 --all
uv run sprouted-build provision macos --arch arm64 --all
```

Run each preflight before preparing source or spending time on a full build:

```powershell
uv run sprouted-build preflight windows
uv run sprouted-build preflight wsl --arch arm64
uv run sprouted-build preflight proxmox --arch x64
uv run sprouted-build preflight macos --arch arm64
```

## Configuration Model

Builder configuration has two layers:

- `sprouted-build.yaml` contains committed, portable defaults.
- `sprouted-build.local.yaml` contains machine-specific overrides and remains
  outside Git and public exports.

Linux builders are organized consistently by backend and architecture:

```yaml
builders:
  wsl:
    default_architecture: arm64
    arm64: {}
    x64: {}
  proxmox:
    default_architecture: x64
    arm64: {}
    x64: {}
  macos:
    default_architecture: arm64
    arm64: {}
```

Each architecture entry describes an independent native builder. For Proxmox,
ARM64 and x64 may use different hosts, containers, checkouts, and artifact
directories. Preflight, provisioning, and source preparation use the backend's
`default_architecture` when `--arch` is omitted. Build commands require
`--arch`, making the architecture of every release artifact explicit.

Release identity, upstream commits, patch provenance, and artifact records stay
in the release manifest. The YAML configuration describes only where and how a
particular machine performs builds. Credentials do not belong in either file.

Run `uv run sprouted-build --help` for the complete command reference. The
release workflow for each backend appears below.

Source preparation starts from the exact Microsoft commit recorded in the
release manifest, then applies the ordered patch files shipped in this
repository. Pull requests and source commits remain in the manifest as
provenance, but the build never fetches patch content from a contributor's
repository. It refuses to modify a dirty checkout; configure a dedicated clean
build checkout rather than pointing it at a working development tree.

Every build command independently checks the checkout again before packaging.
The checkout must be clean and its Git tree must exactly match
`build.source_tree` in the release manifest. A normal build removes the old
platform output before invoking Gulp, then writes a deterministic provenance
receipt into the new output. The receipt records the release, source tree,
platform, architecture, build flavor, and Gulp target.

Using `--skip-gulp` does not bypass this protection. An existing output can be
archived only when its embedded receipt exactly matches the requested build.
This prevents stale output from an older source tree or architecture from being
published under the current release name.

The Windows build command installs the exact dependency graph recorded in
upstream's `package-lock.json` with `npm ci`, runs both focused BYOK test suites,
invokes the upstream package target, validates the branded executable, creates
the release ZIP, and refreshes `artifacts/checksums.txt`. Use
`--skip-install`, `--skip-tests`, or `--skip-gulp` only when deliberately
reusing output from an earlier stage.

The Sprouted patch queue checks native dependencies for a Windows Portable
Executable header before passing them to `signtool.exe` and `rcedit.exe`.
Without this check, Windows source builds can fail after package assembly when
an extension bundles Linux or macOS `*.node` files. Packaging errors are not
tolerated: a nonzero gulp result fails the build.

## Inputs

Each build should declare:

- upstream repository: `microsoft/vscode`
- upstream commit SHA
- ordered local patch files, with upstream issues, pull requests, and source
  commits recorded as provenance where available
- build platform
- build date
- builder notes

## Dedicated Source Checkouts

Keep the Sprouted Code control repository separate from every upstream build
checkout. A typical Windows layout is:

```text
C:\src\sprouted-code
C:\src\sprouted-code-build\vscode
```

Create the Windows build checkout directly from Microsoft's repository:

```powershell
git clone https://github.com/microsoft/vscode.git C:\src\sprouted-code-build\vscode
```

WSL, Proxmox, and macOS each need their own checkout on the builder's native
filesystem. Sharing `node_modules` or packaged output across operating systems
or architectures produces invalid native dependencies.

Every build checkout should use Microsoft's repository as its configured source
remote:

```text
origin  https://github.com/microsoft/vscode.git
```

The Windows checkout must exist before its first preflight. The WSL, Proxmox,
and macOS `provision ... --all` commands can create their configured checkouts.

## Source Preparation

The `prepare` command fetches the Microsoft base branch, resets the release
branch to the manifest's exact base commit, applies every local patch in manifest
order, and creates one synthetic patch-queue commit. Preview the operation
before modifying a checkout:

```powershell
uv run sprouted-build prepare windows --dry-run
uv run sprouted-build prepare windows
```

Preparation refuses a dirty checkout. Resolve upstream conflicts in the patch
source or patch files, then run preparation again from a clean build checkout.

## Test Before Packaging

Every build lane runs the focused BYOK tests automatically. To diagnose those
tests directly on Windows, run them from the Copilot extension directory:

```powershell
Set-Location C:\src\vscode\extensions\copilot

.\node_modules\.bin\vitest.cmd --run --pool=forks src/extension/byok/common/test/byokProvider.spec.ts
.\node_modules\.bin\vitest.cmd --run --pool=forks src/extension/byok/vscode-node/test/byokPolicy.spec.ts
```

Additional smoke tests should be documented in the release manifest.

## Scripted Build Flow

Use the Python CLI for release builds so every lane follows the same source,
test, provenance, packaging, and checksum rules. Prepare the exact manifest
revision before building either Windows architecture:

```powershell
uv run sprouted-build prepare windows
uv run sprouted-build build windows --arch arm64 --flavor release
```

The Windows x64 lane follows the same flow:

```powershell
uv run sprouted-build build windows --arch x64 --flavor release
```

The native WSL Linux lane is also configuration-driven:

```powershell
uv run sprouted-build preflight wsl --arch arm64
uv run sprouted-build prepare wsl --arch arm64
uv run sprouted-build build wsl --arch arm64 --flavor release
```

The native Proxmox Linux x64 lane follows the same configuration-driven flow:

```powershell
uv run sprouted-build preflight proxmox --arch x64
uv run sprouted-build prepare proxmox --arch x64
uv run sprouted-build build proxmox --arch x64 --flavor release
```

The native macOS ARM64 lane runs over SSH against a real Apple Silicon Mac:

```powershell
uv run sprouted-build provision macos --arch arm64 --all
uv run sprouted-build prepare macos --arch arm64
uv run sprouted-build build macos --arch arm64 --flavor release
```

Set `builders.macos.arm64.ssh_target` and any machine-specific paths in
`sprouted-build.local.yaml`. Provisioning installs the pinned official Node
ARM64 distribution under the configured user-owned directory and clones the
dedicated upstream Visual Studio Code build checkout. Preparation applies the
exact manifest commits and patch queue, then verifies the resulting Git tree.

The macOS build runs `npm ci`, both focused BYOK suites, and the upstream
`vscode-darwin-arm64-min` target with `CI=1`. It validates the generated
`Sprouted Code.app`, including its Sprouted-specific bundle identifier,
executable, and `sprouted-code` command-line launcher. The completed bundle is
ad-hoc signed and checked with macOS's strict, deep signature verification
before it is archived. The ZIP embeds the provenance receipt at its root,
preserves framework symlinks, and receives a remote SHA-256 digest. The local
copy is accepted only when its independently calculated digest matches.

The initial public test build uses an ad-hoc signature and is not notarized, so
macOS may require the user to approve it through Gatekeeper. Developer ID
signing, hardened-runtime validation, and Apple notarization remain future
distribution work.

Linux builds should use a WSL-native checkout such as `~/repos/vscode`, not the
Windows checkout under `/mnt/c`, because native dependencies and `node_modules`
are platform-specific. The Python preflight enforces the configured native
architecture and verifies the Linux toolchain before a build starts.

Provision a fresh Ubuntu WSL builder before its first build:

```powershell
uv run sprouted-build provision wsl --arch arm64 --all
```

This installs the base Linux build toolchain, installs Node 24 under
`~/.local/node-v24.18.0-linux-arm64`, clones or updates the WSL-native VS Code
checkout, and applies the Sprouted patch queue.

Provision the Proxmox x64 builder before its first build:

```powershell
uv run sprouted-build provision proxmox --arch x64 --all
```

Each Proxmox architecture has its own SSH target, container ID, owner, checkout,
and artifact directory under `builders.proxmox.<arch>`. Those private values
belong in `sprouted-build.local.yaml`, not committed configuration. This permits
independent native ARM64 and x64 builders without treating either architecture
as a special case. Provisioning installs the matching Node 24 distribution and
clones the upstream Visual Studio Code checkout. Source preparation then applies the exact
revisions and local Sprouted patch queue recorded by the release.

The Python WSL and Proxmox release lanes set `CI=1` and use the standalone
`vscode-linux-<arch>-min` gulp target. Diagnostic builds omit `CI=1` and use the
unminified `vscode-linux-<arch>` target. The upstream
`vscode-linux-<arch>-min-ci` target belongs to a staged CI pipeline with a prior
compile and minify phase, so the standalone Sprouted lanes do not invoke it
directly. The `-min` target runs that packaging stage internally after completing
its prerequisites.

The Proxmox lane archives the native package and pulls it into `artifacts/`.
The transfer uses a unique host-side staging path and compares the remote and
local SHA-256 digests before accepting the artifact.

WSL builds must match the Windows host's native architecture. An ARM64 Windows
workstation normally provides an `aarch64` Linux environment, while an x64
workstation normally provides `x86_64`. The preflight stops on an architecture
mismatch before native dependencies are installed or packaged.

WSL does not provide a general architecture selector for installing a
second, foreign-architecture distribution. Use the Proxmox backend or another
native Linux host for the other architecture. The configuration supports x64
and ARM64 entries for both WSL and Proxmox, allowing the same release workflow
to follow the available infrastructure. Other options include:

- build on a native Linux host or VM of the required architecture
- use a cloud runner with the required architecture
- add a deliberate QEMU/container emulation lane and accept the speed and
  native-module complexity costs

The Python workflow performs:

1. preflight checks
2. build branch preparation
3. local Sprouted patch application from `patches/*.patch`
4. dependency install
5. focused BYOK tests
6. platform package build

The first preflight requirement is the Node version from the VS Code checkout's `.nvmrc`. Current upstream VS Code requires Node 24.x. Newer Node majors are intentionally rejected by upstream preinstall logic.

## Build Artifacts

Before public release, every artifact should have:

- release manifest
- checksums
- embedded build provenance receipt
- upstream commit SHA
- patch list
- build notes

Run the complete artifact verification after all architecture builds:

```console
uv run sprouted-build release verify
```

This command verifies every manifest artifact's SHA-256 digest, archive
integrity, expected executable and license files, and embedded provenance
receipt. Set `build.provenance_receipt` to `true` in the release manifest only
after every artifact has been rebuilt with receipt-aware tooling. Older
artifacts can still be inspected, but verification reports their missing
receipts explicitly.

## Local Reinstall And Launch

Use the Python CLI to replace the portable installation with the artifact for a
specific architecture:

```powershell
uv run sprouted-build install windows --arch arm64
```

To reinstall and immediately launch:

```powershell
uv run sprouted-build install windows --arch arm64 --launch
```

To launch an already-extracted build:

```powershell
uv run sprouted-build launch windows
```

By default, the install lives at `C:\Tools\Sprouted Code`, user data lives under
`C:\Tools\Sprouted Code\data\user-data`, and extensions live under
`C:\Tools\Sprouted Code\data\extensions`. Reinstalling wipes that install
directory, including user data and extensions, unless `--preserve-user-data`
is passed. Installation validates and stages the complete archive before
replacing the existing installation, and restores the prior directory if the
replacement cannot be completed.

## App Icon Notes

The current Sprouted identity patch changes product names, executable names, and
application IDs, but it intentionally does not replace upstream icon assets yet.

Icon assets are platform-specific. A Windows icon patch will not automatically
carry over to macOS or Linux builds.

For Windows builds, the primary icon inputs live in the VS Code source tree under
`resources/win32/`:

- `resources/win32/code.ico`
- `resources/win32/code_150x150.png`
- `resources/win32/code_70x70.png`
- `resources/win32/VisualElementsManifest.xml`
- `resources/win32/appx/AppxManifest.xml`

For macOS builds, expect icon work to involve Darwin/macOS app bundle resources,
typically an `.icns` asset under the upstream macOS resource tree, plus bundle
metadata such as the app bundle name and identifier.

For Linux builds, expect icon work to involve Linux desktop icon assets and
desktop/appdata metadata, with `product.json` fields such as `linuxIconName`
connecting the product identity to the installed icon names.

A future Sprouted icon patch should replace the relevant platform assets and
update manifest or desktop metadata only if file names change. Keep icon changes
as a separate build-identity patch so they remain easy to audit apart from BYOK
behavior fixes.
