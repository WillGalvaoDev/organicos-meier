"""E01-03: regras estáticas do ruff (acceptance A-10)."""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _ruff(codigo: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    arquivo = tmp_path / "trecho.py"
    arquivo.write_text(codigo, encoding="utf-8")
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(RAIZ / "pyproject.toml"),
            "--no-cache",
            "--output-format",
            "concise",
            str(arquivo),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_dtz_ruff_acusa_datetime_now_sem_fuso(tmp_path: Path) -> None:  # A-10
    resultado = _ruff("from datetime import datetime\n\nx = datetime.now()\n", tmp_path)
    assert resultado.returncode != 0
    assert "DTZ005" in resultado.stdout


def test_dtz_ruff_acusa_utcnow(tmp_path: Path) -> None:
    resultado = _ruff("from datetime import datetime\n\nx = datetime.utcnow()\n", tmp_path)
    assert resultado.returncode != 0
    assert "DTZ003" in resultado.stdout


def test_dtz_ruff_aceita_now_com_fuso(tmp_path: Path) -> None:
    resultado = _ruff(
        "from datetime import UTC, datetime\n\nx = datetime.now(UTC)\n",
        tmp_path,
    )
    assert "DTZ" not in resultado.stdout
