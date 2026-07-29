import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_UPSTREAM_LABEL = re.compile(r"\bCode\s*-\s*OSS\b|\bCode OSS\b", re.I)


def test_public_documentation_avoids_confusing_upstream_label() -> None:
    documents = [
        *ROOT.glob("*.md"),
        *ROOT.joinpath("docs").rglob("*.md"),
        *ROOT.joinpath("patches").glob("*.md"),
    ]
    violations = [
        str(path.relative_to(ROOT))
        for path in documents
        if path.name not in {"AGENTS.md", "TODO.md", "publication-snapshot.md"}
        and FORBIDDEN_UPSTREAM_LABEL.search(path.read_text(encoding="utf-8"))
    ]

    assert violations == []
