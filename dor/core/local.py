"""O acervo pessoal: música e jornal que o app usa mas não distribui.

O projeto tem uma trava dura em `core/quoting.py` — só reproduz texto em
domínio público. Ela existe porque `data/` é publicado, e publicar letra de
artista vivo é problema de outra ordem.

Só que estudar rap contemporâneo pelo glossário e nunca pelo verso é estudar
pela metade. A saída não é afrouxar a trava do repositório: é ter um segundo
acervo, em `%LOCALAPPDATA%/dor/conteudo`, do lado do progresso e fora do git.
O que entra ali é do usuário e fica com o usuário — a letra que ele colou, o
parágrafo de jornal que ele recortou. Nada disso viaja.

Daí a assimetria proposital deste módulo: ele valida formato (schema), mas não
tem opinião nenhuma sobre direito autoral. Quem decide o que pode ser guardado
aqui é a pessoa dona da máquina.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from dor import config
from dor.core.loader import ContentError, Issue, check_schema

SCHEMA = "lote.schema.json"

KIND_LABEL_PT = {
    "versuri": "música",
    "jurnal": "jornal",
}


def current_week(day: date | None = None) -> str:
    """A semana ISO de hoje, no formato que os lotes usam."""
    iso = (day or date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@dataclass(slots=True)
class Part:
    """O pedaço explicado — a unidade que o aluno de fato estuda."""

    ro: list[str]
    pt: list[str] = field(default_factory=list)
    at: str | None = None
    explica_pt: str | None = None
    glossary: list[dict[str, str]] = field(default_factory=list)
    cloze: str | None = None
    cloze_answer: str | None = None

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """Linha em romeno com a sua tradução, ou string vazia quando falta."""
        return [(ro, self.pt[i] if i < len(self.pt) else "") for i, ro in enumerate(self.ro)]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Part:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass(slots=True)
class Piece:
    """Uma faixa ou uma notícia."""

    id: str
    title: str
    parts: list[Part]
    kind: str = "versuri"
    week: str = ""
    title_pt: str | None = None
    author: str | None = None
    source: str | None = None
    link: str | None = None
    date: str | None = None
    level: str = "B1"
    why_pt: str | None = None
    note_pt: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def kind_pt(self) -> str:
        return KIND_LABEL_PT.get(self.kind, self.kind)

    @property
    def glossary(self) -> list[dict[str, str]]:
        """Todo o glossário da peça, na ordem em que aparece."""
        return [entry for part in self.parts for entry in part.glossary]

    @classmethod
    def from_dict(cls, d: dict[str, Any], *, kind: str, week: str) -> Piece:
        known = set(cls.__dataclass_fields__) - {"parts", "kind", "week"}
        return cls(
            kind=kind,
            week=week,
            parts=[Part.from_dict(p) for p in d["parts"]],
            **{k: v for k, v in d.items() if k in known},
        )


@dataclass
class LocalContent:
    pieces: dict[str, Piece] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def of_kind(self, kind: str) -> list[Piece]:
        """As peças de um tipo, da semana mais recente para a mais antiga."""
        chosen = [p for p in self.pieces.values() if p.kind == kind]
        return sorted(chosen, key=lambda p: (p.week, p.id), reverse=True)

    def weeks(self) -> list[str]:
        return sorted({p.week for p in self.pieces.values()}, reverse=True)

    def since(self, week: str) -> list[Piece]:
        return [p for p in self.pieces.values() if p.week >= week]


def load_local(directory: Path | None = None, *, strict: bool = False) -> LocalContent:
    """Lê o acervo pessoal. Diretório ausente não é erro — é o caso comum."""
    root = Path(directory or config.LOCAL_DIR)
    content = LocalContent()
    if not root.exists():
        return content

    for path in sorted(root.rglob("*.json")):
        # A caixa de entrada é rascunho por definição: o que está lá ainda não
        # passou pelo `dor atualizar` e não deve aparecer no estudo.
        if config.INBOX_DIR.name in path.relative_to(root).parts:
            continue
        content.issues.extend(_absorb(content, path, strict=strict))
    return content


def _absorb(content: LocalContent, path: Path, *, strict: bool) -> list[Issue]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise ContentError(f"{path}: {exc}") from exc
        return [Issue(path, f"não foi possível ler — {exc}", "raiz")]

    issues = check_schema(path, SCHEMA, payload)
    if issues:
        if strict:
            raise ContentError("\n".join(str(i) for i in issues))
        return issues

    meta = payload["meta"]
    for raw in payload["pieces"]:
        piece = Piece.from_dict(raw, kind=meta["kind"], week=meta["week"])
        if piece.id in content.pieces:
            issues.append(Issue(path, f"peça repetida: {piece.id}", "pieces"))
            continue
        content.pieces[piece.id] = piece
    return issues


def find(content: LocalContent, needle: str, *, kind: str | None = None) -> Piece | None:
    """Acha por id ou por pedaço do título — ninguém digita o id inteiro."""
    pool = content.of_kind(kind) if kind else list(content.pieces.values())
    lowered = needle.lower()
    for piece in pool:
        if piece.id == needle:
            return piece
    for piece in pool:
        if lowered in piece.title.lower() or lowered in piece.id:
            return piece
    return None
