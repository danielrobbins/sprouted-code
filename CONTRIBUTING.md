# Contributing To Sprouted Code

Sprouted Code cultivates small, auditable improvements to the upstream Visual
Studio Code source with a clear problem statement, test story, and path toward
upstream inclusion when appropriate.

Before preparing a substantial change, open an issue describing the developer
problem, why it belongs in Sprouted Code, and whether it is intended for the
upstream `microsoft/vscode` repository.

## Patch Contributions

A patch should:

- address a demonstrated developer problem
- remain close to upstream architecture and conventions
- preserve unrelated upstream behavior
- include focused tests or reproducible validation
- identify its authorship, license, and intended upstream path

Patch contributions to the upstream Visual Studio Code source must be available
under MIT-compatible terms and must satisfy any contribution agreement required
by the upstream project.

## Build Tooling And Documentation

Changes to the Sprouted Code build tooling, tests, manifests, or documentation
are contributed under GPL-3.0-only.

Run the local checks before submitting:

```console
uv sync --dev
uv run ruff format --check src tests
uv run ruff check src tests
uv run pytest -q
uv run sprouted-build --no-local-config config validate
```

Do not commit credentials, private network addresses, account names, private
builder locations, or other machine-specific configuration. Put local builder
details in the ignored `sprouted-build.local.yaml` file.
