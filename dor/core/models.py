"""Modelos de domínio.

Dataclasses puras, construídas a partir dos JSON já validados por schema.
Sem dependência externa de propósito: o loader é o único ponto que conhece o
formato em disco, e daqui pra frente o resto do app fala só nestes tipos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _get_path(obj: Any, dotted: str) -> Any:
    """Resolve 'forms.def_sg' contra um objeto/dict aninhado."""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


@dataclass(slots=True)
class VocabItem:
    id: str
    ro: str
    pt: list[str]
    pos: str
    level: str
    register: str = "neutru"
    gender: str | None = None
    forms: dict[str, Any] = field(default_factory=dict)
    conjugation: str | None = None
    ipa: str | None = None
    tags: list[str] = field(default_factory=list)
    accepts: list[str] = field(default_factory=list)
    """Variantes aceitas do lado ROMENO (produção): "ce faci?", "ce mai faci"."""
    accepts_pt: list[str] = field(default_factory=list)
    """Traduções aceitas que não valem como resposta canônica exibida.

    Existe porque `pt` é lista de exibição — a primeira entra na ficha, no Anki
    e nas alternativas de múltipla escolha. Uma tradução que só serve para não
    reprovar o aluno ("como está" para 'ce faci') suja essa lista se entrar
    nela, e faz falta se não entrar em lugar nenhum."""
    cognate_pt: dict[str, Any] | None = None
    false_friend: dict[str, Any] | None = None
    etymology: str | None = None
    examples: list[str] = field(default_factory=list)
    audio_hint: dict[str, str] | None = None
    note_pt: str | None = None
    deck: str = ""

    @property
    def pt_main(self) -> str:
        return self.pt[0]

    @property
    def all_answers(self) -> list[str]:
        return [*self.pt, *self.accepts, *self.accepts_pt]

    @property
    def pt_answers(self) -> list[str]:
        """Tudo que conta como tradução certa. A primeira segue sendo a canônica."""
        return [*self.pt, *self.accepts_pt]

    def form(self, dotted: str) -> Any:
        return _get_path(self, dotted)

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> VocabItem:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


@dataclass(slots=True)
class Sentence:
    id: str
    ro: str
    pt: str
    level: str
    register: str = "neutru"
    vocab: list[str] = field(default_factory=list)
    cloze_target: str | None = None
    grammar: list[str] = field(default_factory=list)
    note_pt: str | None = None
    deck: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> Sentence:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


@dataclass(slots=True)
class GrammarRule:
    id: str
    title: str
    level: str
    explanation_pt: str
    tags: list[str] = field(default_factory=list)
    contrast_pt: str | None = None
    examples: list[dict[str, str]] = field(default_factory=list)
    table: dict[str, Any] | None = None
    drill: dict[str, Any] | None = None
    pitfall_pt: str | None = None
    deck: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> GrammarRule:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


@dataclass(slots=True)
class SlangItem:
    id: str
    ro: str
    pt: list[str]
    kind: str
    register: str
    literal_pt: str | None = None
    pt_mirror: str | None = None
    etymology: str | None = None
    safe_with: list[str] = field(default_factory=list)
    example: dict[str, str] | None = None
    note_pt: str | None = None
    tags: list[str] = field(default_factory=list)
    deck: str = ""

    @property
    def pt_main(self) -> str:
        return self.pt[0]

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> SlangItem:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


#: Ordem de exibição das eras. Não é alfabética nem cronológica por acidente:
#: é a narrativa que o app conta, do substrato ao presente.
ERAS = (
    "dacia",
    "roma",
    "migratii",
    "medieval",
    "fanariot",
    "modern",
    "razboaie",
    "comunism",
    "contemporan",
)

ERA_LABEL_PT = {
    "dacia": "antes de Roma",
    "roma": "Roma",
    "migratii": "migrações",
    "medieval": "Idade Média",
    "fanariot": "época fanariota",
    "modern": "século XIX",
    "razboaie": "guerras e união",
    "comunism": "comunismo",
    "contemporan": "hoje",
}


@dataclass(slots=True)
class HistoryEvent:
    """Um evento histórico e, obrigatoriamente, o que ele fez com a língua."""

    id: str
    title: str
    era: str
    what_pt: str
    language_pt: str
    title_ro: str | None = None
    year: int | None = None
    period: str | None = None
    words: list[dict[str, str]] = field(default_factory=list)
    grammar_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    note_pt: str | None = None
    deck: str = ""

    @property
    def when(self) -> str:
        """Como a data aparece: o período manda, o ano é o desempate."""
        if self.period:
            return self.period
        if self.year is None:
            return ""
        return f"{abs(self.year)} a.C." if self.year < 0 else str(self.year)

    @property
    def sort_key(self) -> int:
        return self.year if self.year is not None else 0

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> HistoryEvent:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


@dataclass(slots=True)
class Bridge:
    """Uma correspondência regular entre português e romeno."""

    id: str
    title: str
    kind: str
    pt: str
    ro: str
    rule_pt: str
    examples: list[dict[str, str]] = field(default_factory=list)
    latin: str | None = None
    confidence: str = "alto"
    productive: bool = False
    traps: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    deck: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> Bridge:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


PLACE_LABEL_PT = {
    "cafenea": "café",
    "restaurant": "restaurante",
    "piata": "feira",
    "magazin": "loja",
    "farmacie": "farmácia",
    "transport": "transporte",
    "strada": "rua",
    "acasa": "casa de alguém",
    "birou": "trabalho",
    "telefon": "telefone",
    "petrecere": "festa",
}


@dataclass(slots=True)
class Scene:
    """Uma cena do dia a dia: diálogo, fórmulas, rua e etiqueta."""

    id: str
    title: str
    place: str
    level: str
    goal_pt: str
    turns: list[dict[str, str]] = field(default_factory=list)
    title_ro: str | None = None
    register: str = "neutru"
    phrases: list[dict[str, str]] = field(default_factory=list)
    street: list[dict[str, str]] = field(default_factory=list)
    etiquette_pt: list[str] = field(default_factory=list)
    vocab_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    deck: str = ""

    @property
    def place_pt(self) -> str:
        return PLACE_LABEL_PT.get(self.place, self.place)

    @property
    def my_turns(self) -> list[dict[str, str]]:
        """As falas que são SUAS — o que você precisa saber produzir."""
        return [t for t in self.turns if t["who"] == "tu"]

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> Scene:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


#: Ordem dos níveis, para ordenar listas sem depender do alfabeto.
LEVEL_ORDER = {level: i for i, level in enumerate(("A1", "A2", "B1", "B2", "C1", "C2"))}

KIND_LABEL_PT = {
    "basm": "conto popular",
    "povestire": "contos",
    "roman": "romance",
    "poezie": "poesia",
    "teatru": "teatro",
    "eseu": "ensaio",
    "jurnal": "memórias",
    "copii": "infantil",
}


@dataclass(slots=True)
class Book:
    """Uma leitura recomendada, graduada pela dificuldade real para o brasileiro."""

    id: str
    title: str
    author: str
    level: str
    kind: str
    why_pt: str
    title_pt: str | None = None
    year: int | None = None
    difficulty_pt: str | None = None
    public_domain: bool = False
    where_pt: str | None = None
    excerpt: dict[str, Any] | None = None
    glossary: list[dict[str, str]] = field(default_factory=list)
    history_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    note_pt: str | None = None
    deck: str = ""

    @property
    def kind_pt(self) -> str:
        return KIND_LABEL_PT.get(self.kind, self.kind)

    @classmethod
    def from_dict(cls, d: dict[str, Any], deck: str = "") -> Book:
        known = {f for f in cls.__dataclass_fields__ if f != "deck"}
        return cls(deck=deck, **{k: v for k, v in d.items() if k in known})


@dataclass(slots=True)
class PairSide:
    ro: str
    pt: str
    ipa: str | None = None
    pos: str | None = None


@dataclass(slots=True)
class MinimalPair:
    id: str
    contrast: str
    level: str
    a: PairSide
    b: PairSide
    note_pt: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def sides(self) -> tuple[PairSide, PairSide]:
        return (self.a, self.b)

    def other(self, side: PairSide) -> PairSide:
        return self.b if side is self.a else self.a

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MinimalPair:
        known = {f for f in cls.__dataclass_fields__} - {"a", "b"}
        return cls(
            a=PairSide(**d["a"]),
            b=PairSide(**d["b"]),
            **{k: v for k, v in d.items() if k in known},
        )


@dataclass(slots=True)
class Track:
    id: str
    title: str
    why_pt: str
    artist_id: str = ""
    artist_name: str = ""
    year: int | None = None
    theme: list[str] = field(default_factory=list)
    links: dict[str, str] = field(default_factory=dict)
    excerpt: dict[str, Any] | None = None
    glossary: list[dict[str, str]] = field(default_factory=list)
    folk_elements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Artist:
    id: str
    name: str
    genre: list[str]
    why_pt: str
    era: str | None = None
    region: str | None = None
    difficulty: str | None = None
    dominant_register: str | None = None
    links: dict[str, str] = field(default_factory=dict)
    tracks: list[Track] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Artist:
        raw_tracks = d.get("tracks", []) or []
        known = {f for f in cls.__dataclass_fields__ if f != "tracks"}
        artist = cls(tracks=[], **{k: v for k, v in d.items() if k in known})
        artist.tracks = [
            Track(
                artist_id=artist.id,
                artist_name=artist.name,
                **{k: v for k, v in t.items() if k in Track.__dataclass_fields__},
            )
            for t in raw_tracks
        ]
        return artist
