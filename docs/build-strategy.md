# Build Strategy

Sprouted Code produces transparent, developer-oriented compatibility builds
from a recorded upstream Visual Studio Code revision and patch queue. The project borrows useful
release safeguards from mature distributions without trying to reproduce every
part of Microsoft's or VSCodium's release infrastructure.

Platform concerns are deliberately separated. A sound Windows build does not
prove Linux portability, and neither says anything about macOS signing or
notarization.

## Shared Build Policy

All build lanes use:

- the exact upstream revision recorded in the release manifest
- the documented Sprouted patch queue
- Node 24 at the version selected by the build configuration
- `npm ci` so installation follows the committed lockfiles
- focused tests for the included compatibility patches
- SHA-256 checksums for completed artifacts
- clean-source gates and embedded build provenance receipts

Two build flavors are available:

- `release` uses the upstream minimized `-min` target and is the default
- `diagnostic` preserves the less-transformed developer output for debugging

Release builds also set `CI=1`, matching the assumptions made by upstream's
CI-aware packaging transforms. Diagnostic builds do not force that variable.
The flavor changes compilation and artifact naming. It does not turn the
portable archives into signed installers or native distribution packages.

### Difference from Microsoft's publish pipeline

Sprouted's release flavor uses the upstream minimized application target, but
it is not yet a reproduction of Microsoft's full publish pipeline. In
particular, Microsoft's publish jobs separately build platform-specific Claude
and Codex Agent SDK tarballs, upload them to `main.vscode-cdn.net`, and stamp
their version and download URL into the packaged `product.json`. Local builds
and ordinary upstream CI runs intentionally omit this stamp.

Sprouted does not have authority to publish Agent SDKs to Microsoft's CDN and
does not synthesize that metadata. This affects the separately distributed
first-party Claude and Codex agent providers. It does not prevent the bundled
chat extension or configured BYOK language-model endpoints from operating.
Other remaining publish-pipeline differences include signing, notarization,
native installers, update metadata, symbols, and Microsoft-operated artifact
publication.

## Windows

### Current path

Windows ARM64 and x64 builds run natively on Windows with the upstream
platform build targets. The result is a complete portable ZIP containing the
editor, bundled extensions, licenses, and Sprouted identity.

The release flavor uses targets such as:

```console
npm run gulp -- vscode-win32-arm64-min
```

The diagnostic flavor omits `-min` and adds `-diagnostic` to the archive name.

### What is correct today

The Windows source-build path is suitable for Sprouted's public test builds.
It compiles and packages the full portable application and has been exercised
on both supported architectures. Sprouted patches also fix two upstream
from-source problems encountered in this lane: cross-platform build-test
quoting and overly broad Windows resource editing of non-Windows native files.

### Current limits

The ZIP is unsigned, has no installer, and has no automatic update service.
Those are distribution features, not evidence that the compiled application is
incomplete. Signing and installers can be added later without changing how the
editor itself is built.

## Linux

Linux is the most complicated initial platform because an archive can be
correctly built yet fail on another distribution for two independent reasons:

1. required desktop libraries are not installed
2. a binary imports newer ABI symbol versions than the host provides

### Runtime libraries

Electron expects NSPR, NSS, GTK, X11, ALSA, and related libraries from the host
distribution. A DEB or RPM declares those requirements; a portable tarball
cannot install them automatically.

The first observed Funtoo failure was:

```console
./sprouted-code: error while loading shared libraries: libnspr4.so: cannot open shared object file
```

Use `scripts/install-linux-dependencies.sh --check` to inspect the baseline
libraries. `--print` shows the package set for the detected package manager,
and the explicit `--install` mode installs it. Debian/Ubuntu, RPM-family, and
Gentoo/Funtoo systems are covered.

### ABI baseline experiment

Sprouted now has native Ubuntu 20.04 builders for ARM64 and x64. The current
upstream Visual Studio Code source requires a newer C++ toolchain than Focal
ships, so those builders use GCC
11 from `ppa:ubuntu-toolchain-r/test` while retaining Focal's glibc 2.31
userspace.

The x64 release build completed successfully on this baseline. Analysis of all
48 packaged ELF files found maximum imports of:

```text
GLIBC_2.34
GLIBCXX_3.4.30
CXXABI_1.3.13
```

Those maxima come from upstream prebuilt components included in the final
tree, notably Microsoft authentication and container-support binaries. They
are not reduced merely by compiling the rest of the editor on an older host.
This is why Sprouted does not currently claim that the full archive supports
glibc 2.31, even though it can be built there.

`scripts/analyze-linux-build.sh` makes this measurement repeatable against an
extracted build tree. Future compatibility work must either obtain or rebuild
the relevant prebuilts against the chosen baseline, omit optional components
deliberately, or adopt an explicit upstream-style sysroot and packaging path.

### Current distribution model

The initial Linux output remains a portable tarball for ARM64 and x64. It is a
public test artifact, not a native package. Native DEB/RPM packages could later
declare dependencies, install desktop metadata, and support clean removal, but
they are not required to evaluate the Sprouted patch queue.

## macOS

Sprouted has a native, manifest-driven macOS ARM64 build lane. Intel macOS is
not an initial target. The lane provisions a real Apple Silicon Mac over SSH,
prepares the exact source tree, runs the focused tests and minimized upstream
build, and returns a checksum-verified ZIP with an embedded provenance receipt.

The current application bundle is ad-hoc signed and suitable for development
and internal testing. A normal public distribution also requires an Apple
Developer account, a Sprouted-specific bundle identifier, Developer ID signing,
hardened-runtime validation, and notarization. Those remain explicit
public-release gates; a successful source build does not silently satisfy them.

## Relationship To VSCodium

VSCodium is a mature general-purpose distribution with native packages,
installers, signing, update metadata, an explicit Linux sysroot, and a large
multi-platform release matrix. Sprouted Code has a narrower role: publish and
exercise a small, auditable queue of upstream-oriented patches.

Useful VSCodium practices worth adopting selectively include:

- exact lockfile installation with retries where network reliability warrants
- explicit ABI checks
- clean-machine artifact smoke tests
- native package metadata when those formats are introduced
- separate platform signing and release lanes

Copying its complete pipeline would also import operational scope that is not
needed for the first Sprouted releases.

## Near-Term Release Standard

Before a public artifact is promoted, Sprouted should:

1. build it from a clean dependency installation
2. run the focused patch tests and Python tooling tests
3. record the build flavor, upstream revision, and patch provenance
4. verify the source tree and embedded artifact receipt
5. run the Linux dependency and ABI analyzer where applicable
6. smoke-test every architecture on a native system
7. disclose signing, installer, update, gallery, and compatibility limits

## Release Evidence

The release manifest and checksum file answer different questions:

- the manifest records the exact upstream revision and ordered patch queue
- a build record associates one completed artifact with its builder and tests
- `checksums.txt` lets anyone verify that downloaded artifact bytes are intact
- smoke-test records show what behavior was actually exercised after packaging

Changing the upstream revision, patch queue, product configuration, toolchain,
or build flavor invalidates the old build records. They must be removed before
new builds and recreated only after the replacement artifacts pass validation.
Checksums alone do not prove provenance or function; test prose alone does not
identify the bytes that were tested.

This standard keeps the builds useful and honest while leaving room for the
release process to mature platform by platform.
