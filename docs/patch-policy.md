# Patch Policy

Sprouted Code carries a small patch set for BYOK and open-model workflow compatibility.

## Patch Categories

### Pending Upstream

Patches with an open upstream pull request.

These are preferred because they make the upstream intent clear.

### Incubating

Patches being tested in Sprouted Code before upstream submission.

Incubating patches should have:

- a clear problem statement
- a small scope
- local tests or reproduction notes
- an intended upstream path

### Accepted Upstream

Patches accepted upstream but not yet present in the selected build base.

These should be removed from the Sprouted Code patch set once the build base includes them.

### Build Identity

Minimal changes needed to identify Sprouted Code builds.

These should stay small and avoid turning Sprouted Code into a separately branded editor fork.

## Rules

- Keep patches small and auditable.
- Prefer upstream pull requests over permanent downstream-only changes.
- Document the issue, pull request, commit SHA, and reason for every patch.
- Remove patches once upstream includes them.
- Avoid broad rebranding or behavior changes unrelated to BYOK/open-model compatibility.

