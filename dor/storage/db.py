"""Conexão SQLite e aplicação de migrations.

O progresso do usuário mora fora do repositório (`%LOCALAPPDATA%\\dor`), então
atualizar o código nunca apaga o que foi estudado. A versão do esquema fica no
`PRAGMA user_version` do próprio arquivo — não precisa de tabela de controle.

Cada migration roda dentro de uma transação: ou o arquivo inteiro aplica, ou
nada aplica e a versão não avança.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dor import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_MIGRATION_NAME = re.compile(r"^(\d+)_")


class MigrationError(Exception):
    pass


def _migration_files() -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = _MIGRATION_NAME.match(path.name)
        if not m:
            raise MigrationError(f"migration sem prefixo numérico: {path.name}")
        out.append((int(m.group(1)), path))
    if [n for n, _ in out] != sorted({n for n, _ in out}):
        raise MigrationError("migrations com número duplicado ou fora de ordem")
    return out


def migrate(conn: sqlite3.Connection) -> int:
    """Aplica o que faltar e devolve a versão final do esquema."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, path in _migration_files():
        if version <= current:
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            with conn:  # transação: commit no sucesso, rollback na exceção
                conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {version}")
        except sqlite3.Error as exc:
            raise MigrationError(f"falha na migration {path.name}: {exc}") from exc
        current = version
    return current


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Abre (criando se preciso) o banco de progresso, já migrado."""
    path = path or config.DB_PATH
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # WAL: sessão interrompida no meio (Ctrl+C, terminal fechado) não corrompe
    # nem perde o que já foi gravado.
    if path != Path(":memory:"):
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    migrate(conn)
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def db_info(path: Path | None = None) -> dict[str, object]:
    """Resumo para o `dor doctor`."""
    path = path or config.DB_PATH
    if not path.exists():
        return {"existe": False, "caminho": str(path)}
    with session(path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        items = conn.execute("SELECT COUNT(*) FROM items_state").fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return {
        "existe": True,
        "caminho": str(path),
        "esquema": version,
        "itens": items,
        "revisões": reviews,
        "sessões": sessions,
        "bytes": path.stat().st_size,
    }
