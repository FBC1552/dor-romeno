"""Backup e restauração do progresso.

Copiar `progress.db` na mão não basta: com WAL ligado, parte das escritas
recentes vive no arquivo `-wal` ao lado, e uma cópia simples pode perder os
últimos dias de estudo — silenciosamente, que é o pior jeito de perder.

Por isso usamos `sqlite3.Connection.backup()`, a API oficial: ela lê um banco
consistente mesmo com o app aberto e escreve um arquivo único, sem WAL pendurado.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dor import config
from dor.storage import db


class BackupError(Exception):
    pass


@contextmanager
def _open(path: Path):
    """Conexão que realmente FECHA no fim.

    `with sqlite3.connect(...)` cuida da transação, não do arquivo — e no
    Windows a conexão aberta mantém o `-wal` travado, fazendo a restauração
    falhar com PermissionError.
    """
    with closing(sqlite3.connect(path)) as conn:
        yield conn


@dataclass
class BackupInfo:
    path: Path
    bytes: int
    reviews: int
    items: int
    created: datetime


def default_name(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"dor_backup_{now:%Y%m%d_%H%M}.db"


def create(out_path: Path | None = None, *, source: Path | None = None) -> BackupInfo:
    """Copia o banco para um arquivo único e consistente."""
    source = source or config.DB_PATH
    if not source.exists():
        raise BackupError("ainda não há progresso para salvar")

    config.ensure_user_dirs()
    out_path = out_path or (config.EXPORT_DIR / default_name())
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with _open(source) as src, _open(out_path) as dst:
        src.backup(dst)

    return _describe(out_path)


def _describe(path: Path) -> BackupInfo:
    with _open(path) as conn:
        try:
            reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            items = conn.execute("SELECT COUNT(*) FROM items_state").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"{path.name} não parece um backup do dor: {exc}") from exc
    return BackupInfo(
        path=path,
        bytes=path.stat().st_size,
        reviews=reviews,
        items=items,
        created=datetime.fromtimestamp(path.stat().st_mtime),
    )


def inspect(path: Path) -> BackupInfo:
    """Lê o backup sem restaurar — é o que permite avisar o que será perdido."""
    if not path.exists():
        raise BackupError(f"arquivo não encontrado: {path}")
    return _describe(path)


def restore(path: Path, *, target: Path | None = None) -> BackupInfo:
    """Substitui o progresso atual pelo backup, guardando o atual antes.

    Restaurar é destrutivo por natureza, então o banco que está sendo
    substituído vira ele mesmo um backup automático. Ninguém deve conseguir
    apagar meses de estudo com um comando e nenhuma rede de segurança.
    """
    info = inspect(path)
    target = target or config.DB_PATH

    if target.exists():
        # Vai junto dos outros backups, não ao lado do banco: uma rede de
        # segurança que o `--list` não enxerga não serve de rede.
        config.ensure_user_dirs()
        create(
            config.EXPORT_DIR / f"dor_antes_de_restaurar_{datetime.now():%Y%m%d_%H%M%S}.db",
            source=target,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    with _open(path) as src, _open(target) as dst:
        src.backup(dst)

    # O WAL do banco antigo não vale mais nada e confundiria a próxima abertura.
    for suffix in ("-wal", "-shm"):
        leftover = target.with_name(target.name + suffix)
        leftover.unlink(missing_ok=True)

    # Migrar na hora: um backup antigo pode estar num esquema anterior, e é
    # melhor descobrir isso aqui do que no meio de uma sessão.
    db.connect(target).close()
    return info


def list_backups(directory: Path | None = None) -> list[BackupInfo]:
    directory = directory or config.EXPORT_DIR
    if not directory.exists():
        return []
    found = []
    for path in sorted(directory.glob("dor_*backup*.db")) + sorted(
        directory.glob("dor_antes_de_restaurar_*.db")
    ):
        try:
            found.append(_describe(path))
        except BackupError:
            continue
    return sorted(found, key=lambda b: b.created, reverse=True)
