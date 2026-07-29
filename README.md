# Sprouted Code

**Sprouted Code gives useful Visual Studio Code patches somewhere to live, be used, tested, and improved.**

Sprouted Code is a [Kernel Seeds](https://kernel-seeds.org) project maintained by Daniel Robbins and built from [Microsoft's open-source Visual Studio Code codebase](https://github.com/microsoft/vscode). It follows upstream closely and turns a small, public patch queue into working builds that developers can actually run.

Independent AI workflows are the first focus, but the broader goal is simple: put useful community fixes into developers’ hands while they make their way upstream.

## The Story Behind Sprouted Code

**Sprouted Code grew out of a practical problem I ran into while working with open-weight, self-hosted, and other BYOK AI models.** I kept hitting Visual Studio Code bugs that made these models unnecessarily difficult to configure and use. Some only appeared when GitHub Copilot was unavailable. Others left model-management controls hidden behind Copilot setup state or broke ordinary source builds.

**I fixed the problems and started to submit the fixes upstream.** That's the right thing to do, and upstream pull requests are essential to lasting improvement. But here's the thing: review takes time. One patch was accepted immediately. Another important fix has sat untouched for three weeks (and is still sitting there.) That's the reality of it. During that time, a useful fix exists as source code while remaining unavailable to most developers.

**Sprouted Code closes that gap.** A pull request gives maintainers something to review. A working build gives developers something to use, test, and improve. That's the larger mission: **empower developers with timely fixes for issues that are impacting their critical AI workflows.**

## Get Sprouted Code

**Sprouted Code is distributed as a portable application.** Download the [latest release](https://github.com/danielrobbins/sprouted-code/releases/latest) and its `checksums.txt` file, then choose the archive matching your system:

| System | Archive |
| --- | --- |
| Windows on Intel or AMD 64-bit | `sprouted-code-2026.07.0-win32-x64.zip` |
| Windows on ARM64 | `sprouted-code-2026.07.0-win32-arm64.zip` |
| Linux on Intel or AMD 64-bit | `sprouted-code-2026.07.0-linux-x64.tar.gz` |
| Linux on ARM64 | `sprouted-code-2026.07.0-linux-arm64.tar.gz` |
| macOS on Apple Silicon | `sprouted-code-2026.07.0-darwin-arm64.zip` |

### Windows

Download the matching Windows ZIP and
[`install-win11.ps1`](scripts/install-win11.ps1) into your Downloads folder.
Then open PowerShell and run:

```powershell
install-win11.ps1
```

The installer detects x64 or ARM64, asks before replacing an existing installation, and adds Sprouted Code to the Start Menu. Initial builds are unsigned, so Windows may display a publisher warning on first launch.

### Linux

Check your system architecture with `uname -m`: `x86_64` uses the `linux-x64` archive, while `aarch64` or `arm64` uses the `linux-arm64` archive.

For an x86-64 system, verify, extract, and launch the archive with:

```console
sha256sum sprouted-code-2026.07.0-linux-x64.tar.gz
tar -xzf sprouted-code-2026.07.0-linux-x64.tar.gz
./VSCode-linux-x64/sprouted-code
```

Use `linux-arm64` and `VSCode-linux-arm64` in the corresponding commands on an ARM64 system. Compare the reported digest with `checksums.txt`. The extracted directory can be moved anywhere writable. The [detailed installation guide](docs/install.md) also covers Linux desktop dependencies.

### macOS

The current macOS build supports Apple Silicon (`arm64`). Download `sprouted-code-2026.07.0-darwin-arm64.zip`, then verify and extract it:

```console
shasum -a 256 sprouted-code-2026.07.0-darwin-arm64.zip
ditto -x -k sprouted-code-2026.07.0-darwin-arm64.zip .
mv "Sprouted Code.app" /Applications/
open "/Applications/Sprouted Code.app"
```

Compare the digest with `checksums.txt` before opening the application. The current build is ad hoc signed but not notarized. On first launch, macOS may require you to Control-click the application and choose **Open**, or approve it under **System Settings > Privacy & Security**.

## From Patch to Working Build

**Every Sprouted Code release starts with a recorded upstream Visual Studio Code revision and applies a small, ordered patch queue through a Python build system:**

```text
recorded upstream commit
+ documented patch queue
+ defined build environment
= working Sprouted Code build
```

**Each release is fully documented:** the upstream commit, patch provenance, build environment, test results, artifact checksums, and release manifest. Anyone can inspect what changed and follow a generally useful fix back to its upstream issue or pull request.

**The patch queue is focused.** A good Sprouted Code patch solves a demonstrated problem, stays small enough to understand, includes a credible test story, and fits the architecture of the upstream project. Once an accepted fix reaches the upstream revision used by Sprouted Code, its downstream patch can disappear.

**The build system itself is Python-based and included in the repository.** This makes it easy to inspect, modify, and extend the build process that transforms upstream source plus patches into a working Sprouted Code build.

## Independent AI Workflows

**VS Code's native Chat window is a powerful agentic environment built right into the editor.** It works with your current workspace, reads and modifies files, runs terminal commands, and uses built-in, extension, and MCP tools. Until recently, this integrated experience was tied to GitHub Copilot.

**Microsoft has now opened native Chat to BYOK ("bring your own key") models.** You can connect commercial APIs, hosted open-weight models, and models running on local or private infrastructure while keeping the editor's Chat, agent, and tooling experience.

**This independence is valuable, but the transition isn't complete.** Copilot-first assumptions still create practical bugs: model-management controls can disappear during setup, and signing in to GitHub without a Copilot entitlement can disable an otherwise compatible endpoint. Sprouted Code carries a tested fix for the latter—submitted upstream as [microsoft/vscode#324311](https://github.com/microsoft/vscode/pull/324311) and still awaiting substantive review after three weeks.

**Sprouted Code makes independent AI workflows practical today.** Choose the model and infrastructure that fit your work without giving up the native editor experience around it.

## The Initial BreezyOps Patchset

**The first patchset came from work I was doing through BreezyOps, Inc.** It's a focused group of compatibility, source-build, and identity fixes. It basically fixes all setup and configuration bugs related to adding your own model to the model providers list. There were several issues, particularly if you did not have an existing GitHub Copilot subscription.

Here's the full set of fixes in the first BreezyOps patchset:

### Group 1: Model Choice and Setup Patches

- **Allow BYOK endpoints without a Copilot entitlement.** This fix was submitted upstream as [microsoft/vscode#324311](https://github.com/microsoft/vscode/pull/324311). Having an enterprise GitHub account with no Copilot entitlement would disable BYOK endpoints for no good reason. This patch fixes this.

- **Keep the built-in Chat extension available for BYOK setup.** Fresh source builds can disable Chat while waiting for Copilot setup, which also removes the interface needed to configure independent endpoints. The patch keeps that interface available.

- **Keep model management reachable during initial setup.** `Manage Models...` should be visible before the first custom model has been added. Fixed with this patch.

### Group 2: Source-Build Correctness

- **Preserve the Copilot SDK entrypoint used by the built-in Chat extension.** Source-build packaging can remove an entrypoint that the extension still imports. Preserving it allows Chat to activate correctly.

- **Apply Windows resource changes only to Windows binaries.** The build now identifies actual Windows Portable Executable files before invoking Windows resource tools, allowing extension trees containing Linux and macOS native modules to package correctly.

- **Run the real build test suite on Windows.** Cross-platform command quoting ensures that Windows discovers and runs the same build tests as POSIX systems instead of quietly reporting success with zero tests.

### Sprouted Identity Patches

- The product and executable names identify the build as Sprouted Code.
- First-run onboarding welcomes developers to Sprouted Code.

**The compatibility fixes are intended for upstream submission** whenever they solve a generally useful problem. The two identity changes belong specifically to Sprouted Code builds.

## Working With Upstream

**VS Code Insiders follows Microsoft's active development stream, and Sprouted Code tracks it closely.** Think of it as staying in step with upstream while carrying a small, focused patch queue that developers can actually use in working builds.

**The order of work is deliberate:** make Sprouted Code work properly first, get the fixes into developers' hands, and then pursue upstream inclusion for changes with broader value. Upstream review still matters—it always will—but it's no longer a prerequisite for the community to benefit from the work.

**This creates a practical incubation path.** Patches can prove their value in public, gather real-world feedback, improve through actual use, and move upstream with better evidence behind them. Maintainers remain free to review them on their own schedule, while developers no longer have to wait for that process before testing and benefiting from the work.

**Keeping the queue small is essential.** It makes it possible to update the upstream base frequently and understand every difference the project carries. You should always be able to see what changed and why.

**GitHub Copilot remains fully available.** Developers who want Copilot can sign in and use it normally. Sprouted Code expands the practical choices around it, not replaces them.

## Help Cultivate It

**Sprouted Code is a place for focused improvements with real users behind them.** You can help by:

- Using the public builds on real projects
- Reporting editor, patch, build, and packaging problems
- Testing a patch across different platforms and model providers
- Improving reproduction steps and focused tests
- Contributing small patches with a demonstrated use case and an upstream path

**Bring problems to this project first.** That gives us a place to determine whether an issue comes from upstream, an included patch, or the build and packaging process. When a fix belongs upstream, the Sprouted Code issue can preserve that path and link the broader work.

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [patch policy](docs/patch-policy.md) for the contribution model.

## Documentation

- [Installation](docs/install.md)
- [Build process](docs/build-process.md)
- [Build strategy](docs/build-strategy.md)
- [Developer FAQ](docs/developer-faq.md)
- [Patch policy](docs/patch-policy.md)
- [Security policy](SECURITY.md)

## License

Original Sprouted Code build tooling and documentation are copyright 2026 Daniel Robbins and licensed under GPL-3.0-only. Patches to Microsoft's open-source Visual Studio Code codebase use MIT-compatible terms appropriate for upstream contribution. Built artifacts retain the upstream MIT and bundled third-party licenses.

See [LICENSING.md](LICENSING.md) for the complete licensing and attribution details.

Sprouted Code is independently maintained and is not affiliated with, endorsed by, or sponsored by Microsoft or GitHub. Visual Studio Code is a Microsoft product and trademark.
