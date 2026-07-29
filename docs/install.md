# Installing Sprouted Code

Sprouted Code 2026.07.0 is distributed as portable archives. It does not yet
include an installer or automatic update service.

Before installing, verify the artifact against the published
`checksums.txt` file.

## Windows

1. Download the ZIP matching the system architecture:
   - Intel or AMD 64-bit:
     `sprouted-code-2026.07.0-win32-x64.zip`
   - Windows ARM64:
     `sprouted-code-2026.07.0-win32-arm64.zip`
2. Verify its SHA-256 digest against `checksums.txt`:

```powershell
Get-FileHash .\sprouted-code-2026.07.0-win32-x64.zip -Algorithm SHA256
```

Use the `win32-arm64` filename when verifying the ARM64 archive.

3. Extract the complete archive into a new, empty directory at a permanent,
   writable location such as `%LOCALAPPDATA%\Programs\Sprouted Code`.
4. Launch `Sprouted Code.exe` from that directory.

The initial Windows builds are not digitally signed. Windows may display a
SmartScreen or publisher warning. Verify the SHA-256 checksum before deciding
whether to run the software.

## Linux

1. Download the tarball matching the system architecture:
   - Intel or AMD 64-bit:
     `sprouted-code-2026.07.0-linux-x64.tar.gz`
   - Linux ARM64:
     `sprouted-code-2026.07.0-linux-arm64.tar.gz`
2. Verify, extract, and launch the bundled executable:

```console
sha256sum sprouted-code-2026.07.0-linux-x64.tar.gz
tar -xzf sprouted-code-2026.07.0-linux-x64.tar.gz
./VSCode-linux-x64/sprouted-code
```

Use `linux-arm64` and `VSCode-linux-arm64` in the corresponding commands on an
ARM64 system. Compare the reported digest with `checksums.txt` before launching
the application.

Portable archives rely on desktop libraries supplied by the host distribution.
After obtaining the helper scripts from the Sprouted Code repository, inspect
the system before launch:

```console
./scripts/install-linux-dependencies.sh --check
```

Use `--print` to review the packages for apt, dnf/yum, or emerge. The explicit
`--install` option invokes the detected package manager. Review the command and
package list before allowing it to modify the system.

The initial Linux archives also contain some upstream prebuilt components that
require GLIBC 2.34 even when the surrounding editor is built on an older
userspace. See the [build strategy](build-strategy.md) for the measured ABI
requirements and current compatibility boundary.

## macOS

The current macOS build supports Apple Silicon (`arm64`). Intel macOS builds are
not currently available.

1. Download `sprouted-code-2026.07.0-darwin-arm64.zip`.
2. Verify its SHA-256 digest against `checksums.txt`:

```console
shasum -a 256 sprouted-code-2026.07.0-darwin-arm64.zip
```

3. Extract the application:

```console
ditto -x -k sprouted-code-2026.07.0-darwin-arm64.zip .
```

4. Move the application into `/Applications` and open it:

```console
mv "Sprouted Code.app" /Applications/
open "/Applications/Sprouted Code.app"
```

The current macOS build is ad hoc signed but not notarized. On first launch,
macOS may require you to Control-click the application and choose **Open**, or
approve it under **System Settings > Privacy & Security**. Verify the checksum
before choosing to run the application.

## Extensions

The bundled Chat extension used for BYOK support is included in Sprouted Code.
The initial public test builds also enable access to the Microsoft extension
Marketplace so extension discovery, installation, and update behavior can be
tested as part of normal editor use. Extensions can still be installed from a
local `.vsix` file using **Extensions: Install from VSIX...** or:

```console
sprouted-code --install-extension path/to/extension.vsix
```

Marketplace enablement is an explicit, auditable product configuration in the
Sprouted build definition rather than an upstream source default.

Microsoft's extension signature verifier is not part of the open-source Visual
Studio Code repository, and its license does not permit Sprouted Code to
redistribute it.
Sprouted therefore defaults `extensions.verifySignature` off. Extensions are
still delivered over HTTPS from the configured Marketplace, but Sprouted Code
does not independently verify their Microsoft signatures.

## Updates

Sprouted Code currently uses explicit, versioned releases. A new release should
be installed alongside or over the prior portable directory only after its
checksum and release manifest have been reviewed.
