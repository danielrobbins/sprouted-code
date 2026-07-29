import hashlib
from pathlib import Path

from sprouted_build.artifacts import write_checksums


def test_checksums_are_sorted_and_exclude_output_file(tmp_path: Path) -> None:
    (tmp_path / "zeta.zip").write_bytes(b"zeta")
    (tmp_path / "alpha.tar.gz").write_bytes(b"alpha")
    (tmp_path / "checksums.txt").write_text("stale\n", encoding="utf-8")

    output = write_checksums(tmp_path)

    alpha_hash = hashlib.sha256(b"alpha").hexdigest()
    zeta_hash = hashlib.sha256(b"zeta").hexdigest()
    assert output.read_text(encoding="utf-8").splitlines() == [
        f"{alpha_hash}  alpha.tar.gz",
        f"{zeta_hash}  zeta.zip",
    ]
