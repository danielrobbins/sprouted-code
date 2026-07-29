# Developer FAQ

## Why does Sprouted Code use `npm ci` instead of `npm install`?

`npm ci` installs the dependency graph recorded by the upstream lockfiles. It
fails when those files disagree instead of rewriting them, removes the prior
dependency tree, and gives repeatable clean-build behavior. Sprouted follows
the upstream lockfiles rather than choosing dependency upgrades of its own.

An interrupted remote `npm ci` can leave another installer process operating
on the same tree. Before retrying a failed remote build, confirm that no prior
`npm`, `node`, or gulp process is still active.

## What is the difference between release and diagnostic builds?

Release builds use the minimized upstream `-min` target and are the default.
Diagnostic builds use the ordinary developer-oriented target, preserve output
that is easier to inspect, and carry `-diagnostic` in the artifact name.

```console
uv run sprouted-build build windows --arch arm64 --flavor release
uv run sprouted-build build windows --arch arm64 --flavor diagnostic
```

Both flavors contain the same Sprouted patch queue.

## Why does the Linux builder use Ubuntu 20.04 with GCC 11?

Focal provides an older glibc baseline, but its default GCC 9 lacks the C++20
support required by current Node and Electron headers. GCC 11 from Ubuntu's
toolchain PPA supplies the compiler and standard library headers needed to
build while preserving the older base userspace.

This does not automatically make every bundled binary compatible with Focal.
Some upstream prebuilt components currently require GLIBC 2.34 and newer C++
ABI symbols. The release analyzer records that effective floor.

## How do I inspect a Linux artifact?

Extract it on a Linux system with `file`, `readelf`, and `ldd`, then run:

```console
scripts/analyze-linux-build.sh /path/to/VSCode-linux-x64
```

The report lists unresolved shared libraries, the maximum imported GLIBC,
GLIBCXX, and CXXABI versions, and the direct shared-library requirements.

## How do portable Linux users install runtime dependencies?

The helper defaults to a non-destructive check:

```console
scripts/install-linux-dependencies.sh --check
```

Use `--print` to review the package list and `--install` to invoke the detected
package manager. It supports apt, dnf/yum, and emerge. This is an unofficial
bootstrap for the portable archives and readable guidance for future distro
package maintainers; it is not a substitute for a native package transaction.

## Does a successful Windows build validate Linux or macOS?

No. Windows has its own native modules, resource tools, artifact format, and
signing story. Linux adds distro libraries and ABI floors. macOS adds Apple
signing and notarization. Sprouted validates and documents each lane
independently.

## Are macOS builds supported?

The build tooling supports native Apple Silicon builds on a remote Mac and
produces a checksum-verified ZIP with source provenance. These builds are
currently ad-hoc signed for development and internal testing. Normal public
distribution still requires a Sprouted-specific bundle identifier, an Apple
Developer account, Developer ID signing, hardened-runtime validation, and
notarization. Intel macOS is not an initial target.
