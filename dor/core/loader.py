"""Carga e validação do conteúdo em disco.

Único módulo que conhece o layout de `data/`. Valida cada arquivo contra o
schema correspondente, checa invariantes que o JSON Schema não expressa (IDs
duplicados, referências quebradas entre frases e vocabulário) e devolve
modelos prontos, com cache em memória por processo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from dor import config
from dor.core.models import (
    Artist,
    Book,
    Bridge,
    GrammarRule,
    HistoryEvent,
    MinimalPair,
    Scene,
    Sentence,
    SlangItem,
    Track,
    VocabItem,
)


class ContentError(Exception):
    """Erro de conteúdo com caminho de arquivo para diagnóstico."""


@dataclass
class Issue:
    file: Path
    message: str
    where: str = ""

    def __str__(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.file.name}{loc}: {self.message}"


@dataclass
class Library:
    """Todo o conteúdo carregado, indexado."""

    vocab: dict[str, VocabItem] = field(default_factory=dict)
    sentences: dict[str, Sentence] = field(default_factory=dict)
    grammar: dict[str, GrammarRule] = field(default_factory=dict)
    slang: dict[str, SlangItem] = field(default_factory=dict)
    artists: dict[str, Artist] = field(default_factory=dict)
    pairs: dict[str, MinimalPair] = field(default_factory=dict)
    history: dict[str, HistoryEvent] = field(default_factory=dict)
    books: dict[str, Book] = field(default_factory=dict)
    scenes: dict[str, Scene] = field(default_factory=dict)
    bridges: dict[str, Bridge] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def tracks(self) -> list[Track]:
        return [t for a in self.artists.values() for t in a.tracks]

    def counts(self) -> dict[str, int]:
        return {
            "vocabulário": len(self.vocab),
            "frases": len(self.sentences),
            "regras": len(self.grammar),
            "gíria": len(self.slang),
            "artistas": len(self.artists),
            "faixas": len(self.tracks),
            "pares mínimos": len(self.pairs),
            "eventos históricos": len(self.history),
            "livros": len(self.books),
            "cenas": len(self.scenes),
            "pontes": len(self.bridges),
        }

    @property
    def timeline(self) -> list[HistoryEvent]:
        return sorted(self.history.values(), key=lambda e: e.sort_key)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContentError(f"{path}: JSON inválido — {exc}") from exc
    except OSError as exc:
        raise ContentError(f"{path}: não foi possível ler — {exc}") from exc


@cache
def _validator(schema_name: str) -> Draft202012Validator:
    path = config.SCHEMA_DIR / schema_name
    if not path.exists():
        raise ContentError(f"schema ausente: {path}")
    return Draft202012Validator(_read_json(path))


def _validate(path: Path, schema_name: str, payload: Any) -> list[Issue]:
    issues: list[Issue] = []
    for err in sorted(_validator(schema_name).iter_errors(payload), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in err.path) or "raiz"
        issues.append(Issue(path, err.message, where))
    return issues


#: Nome público do validador de schema, para quem carrega conteúdo que não é do
#: repositório — o acervo pessoal em `core/local.py`.
check_schema = _validate


def _json_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.json"))


def load_library(strict: bool = False) -> Library:
    """Carrega tudo. Com `strict`, levanta ContentError no primeiro problema."""
    lib = Library()

    def record(issues: list[Issue]) -> bool:
        if not issues:
            return True
        if strict:
            raise ContentError("\n".join(str(i) for i in issues))
        lib.issues.extend(issues)
        return False

    def add_all(items, target: dict, path: Path, label: str) -> None:
        for obj in items:
            if obj.id in target:
                record([Issue(path, f"ID duplicado de {label}: {obj.id}")])
                continue
            target[obj.id] = obj

    # vocabulário
    for path in _json_files(config.VOCAB_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "vocabulary.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all(
            [VocabItem.from_dict(d, deck) for d in payload["items"]], lib.vocab, path, "vocabulário"
        )

    # frases
    for path in _json_files(config.SENTENCE_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "sentences.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all(
            [Sentence.from_dict(d, deck) for d in payload["items"]], lib.sentences, path, "frase"
        )

    # gramática
    for path in _json_files(config.GRAMMAR_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "grammar.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all(
            [GrammarRule.from_dict(d, deck) for d in payload["items"]], lib.grammar, path, "regra"
        )

    # gíria / expressões
    for path in _json_files(config.SLANG_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "slang.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all([SlangItem.from_dict(d, deck) for d in payload["items"]], lib.slang, path, "gíria")

    # pares mínimos (arquivo único na raiz de culture/)
    pairs_path = config.CULTURE_DIR / "minimal_pairs.json"
    if pairs_path.exists():
        payload = _read_json(pairs_path)
        if record(_validate(pairs_path, "minimal_pairs.schema.json", payload)):
            add_all(
                [MinimalPair.from_dict(d) for d in payload["items"]],
                lib.pairs,
                pairs_path,
                "par mínimo",
            )

    # história
    for path in _json_files(config.HISTORY_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "history.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all(
            [HistoryEvent.from_dict(d, deck) for d in payload["items"]],
            lib.history,
            path,
            "evento",
        )

    # biblioteca (arquivo único na raiz de culture/)
    books_path = config.CULTURE_DIR / "books.json"
    if books_path.exists():
        payload = _read_json(books_path)
        if record(_validate(books_path, "library.schema.json", payload)):
            deck = payload["meta"]["id"]
            add_all(
                [Book.from_dict(d, deck) for d in payload["items"]], lib.books, books_path, "livro"
            )

    # cenas do dia a dia
    for path in _json_files(config.DAILY_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "situations.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all([Scene.from_dict(d, deck) for d in payload["items"]], lib.scenes, path, "cena")

    # pontes de cognato
    for path in _json_files(config.BRIDGE_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "bridges.schema.json", payload)):
            continue
        deck = payload["meta"]["id"]
        add_all([Bridge.from_dict(d, deck) for d in payload["items"]], lib.bridges, path, "ponte")

    # música
    for path in _json_files(config.MUSIC_DIR):
        payload = _read_json(path)
        if not record(_validate(path, "music.schema.json", payload)):
            continue
        add_all([Artist.from_dict(d) for d in payload["artists"]], lib.artists, path, "artista")

    _check_references(lib, strict)
    _link_examples(lib)
    return lib


def _link_examples(lib: Library) -> None:
    """Fecha o elo frase → palavra no sentido inverso.

    A frase já declara o vocabulário que usa. Exigir que a palavra também
    liste a frase seria a mesma informação escrita duas vezes — e o que se
    escreve duas vezes acaba divergindo: uma frase nova ficaria invisível para
    o modo lacuna até alguém lembrar de editar o outro arquivo.
    """
    for sent in lib.sentences.values():
        for vid in sent.vocab:
            item = lib.vocab.get(vid)
            if item is not None and sent.id not in item.examples:
                item.examples.append(sent.id)


def _check_references(lib: Library, strict: bool) -> None:
    """Invariantes que o JSON Schema não alcança: referências cruzadas."""
    issues: list[Issue] = []
    unknown = Path("<referências>")

    for item in lib.vocab.values():
        for sid in item.examples:
            if sid not in lib.sentences:
                issues.append(Issue(unknown, f"{item.id} aponta para frase inexistente '{sid}'"))

    for sent in lib.sentences.values():
        for vid in sent.vocab:
            if vid not in lib.vocab:
                issues.append(Issue(unknown, f"{sent.id} aponta para vocábulo inexistente '{vid}'"))
        for gid in sent.grammar:
            if gid not in lib.grammar:
                issues.append(Issue(unknown, f"{sent.id} aponta para regra inexistente '{gid}'"))
        if sent.cloze_target and sent.cloze_target not in sent.ro:
            issues.append(
                Issue(unknown, f"{sent.id}: cloze_target '{sent.cloze_target}' não está na frase")
            )

    for event in lib.history.values():
        for gid in event.grammar_refs:
            if gid not in lib.grammar:
                issues.append(Issue(unknown, f"{event.id} aponta para regra inexistente '{gid}'"))

    for book in lib.books.values():
        for hid in book.history_refs:
            if hid not in lib.history:
                issues.append(Issue(unknown, f"{book.id} aponta para evento inexistente '{hid}'"))

    for scene in lib.scenes.values():
        for vid in scene.vocab_refs:
            if vid not in lib.vocab:
                issues.append(Issue(unknown, f"{scene.id} aponta para vocábulo inexistente '{vid}'"))

    for artist in lib.artists.values():
        for track in artist.tracks:
            for entry in track.glossary:
                sid = entry.get("slang_id")
                if sid and sid not in lib.slang:
                    issues.append(Issue(unknown, f"{track.id} aponta para gíria inexistente '{sid}'"))

    if issues:
        if strict:
            raise ContentError("\n".join(str(i) for i in issues))
        lib.issues.extend(issues)


def _matches(value: str | None, wanted: str | list[str]) -> bool:
    """Aceita valor único ou lista.

    A lista existe por causa do neutro: a regra do artigo masculino vale
    igualmente para o neutro, e sem isso ela teria de ser escrita duas vezes.
    """
    return value in wanted if isinstance(wanted, list) else value == wanted


def filter_vocab(
    lib: Library,
    *,
    level: str | list[str] | None = None,
    pos: str | list[str] | None = None,
    gender: str | list[str] | None = None,
    conjugation: str | list[str] | None = None,
    register: str | list[str] | None = None,
    tag: str | None = None,
    deck: str | None = None,
    ends_with: str | None = None,
    has_form: str | None = None,
) -> list[VocabItem]:
    """Filtro declarativo — é isto que os drills de gramática consomem."""
    out = list(lib.vocab.values())
    if level:
        out = [i for i in out if _matches(i.level, level)]
    if pos:
        out = [i for i in out if _matches(i.pos, pos)]
    if gender:
        out = [i for i in out if _matches(i.gender, gender)]
    if conjugation:
        out = [i for i in out if _matches(i.conjugation, conjugation)]
    if register:
        out = [i for i in out if _matches(i.register, register)]
    if tag:
        out = [i for i in out if tag in i.tags]
    if deck:
        out = [i for i in out if i.deck == deck]
    if ends_with:
        out = [i for i in out if i.ro.endswith(ends_with)]
    if has_form:
        out = [i for i in out if i.form(has_form)]
    return out
