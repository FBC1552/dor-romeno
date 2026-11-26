"""Conquistas.

Marcos raros e permanentes, ao contrário das quests, que são diárias. Metade
delas premia constância (streak, volume) e metade premia superar as armadilhas
específicas do romeno para um falante de português — gênero neutro, diacríticos,
produção do zero.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Context:
    """Tudo o que uma conquista pode querer olhar."""

    total_reviews: int
    total_correct: int
    words_seen: int
    romanian_correct: int
    """Acertos escrevendo em romeno (produção, lacuna, gramática)."""
    gender_correct: int
    streak_current: int
    combo_max_session: int
    session_items: int
    session_correct: int
    leech_recovered: int
    now: datetime


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    description: str
    check: Callable[[Context], bool]


CATALOG: tuple[Achievement, ...] = (
    Achievement(
        "primul_pas", "Primul pas", "Sua primeira revisão.",
        lambda c: c.total_reviews >= 1,
    ),
    Achievement(
        "o_suta", "O sută", "100 revisões respondidas.",
        lambda c: c.total_reviews >= 100,
    ),
    Achievement(
        "o_mie", "O mie", "1000 revisões respondidas.",
        lambda c: c.total_reviews >= 1000,
    ),
    Achievement(
        "poliglot", "Poliglot", "100 palavras diferentes estudadas.",
        lambda c: c.words_seen >= 100,
    ),
    Achievement(
        "neutru_nativ", "Neutru nativ",
        "50 acertos no gênero — o obstáculo nº 1 do brasileiro.",
        lambda c: c.gender_correct >= 50,
    ),
    Achievement(
        "diacritic_perfect", "Diacritic perfect",
        "100 acertos escrevendo em romeno, com todos os acentos no lugar.",
        lambda c: c.romanian_correct >= 100,
    ),
    Achievement(
        "saptamana", "O săptămână", "7 dias seguidos de estudo.",
        lambda c: c.streak_current >= 7,
    ),
    Achievement(
        "maratonist", "Maratonist", "30 dias seguidos de estudo.",
        lambda c: c.streak_current >= 30,
    ),
    Achievement(
        "combo_zece", "Zece la rând", "10 acertos consecutivos numa sessão.",
        lambda c: c.combo_max_session >= 10,
    ),
    Achievement(
        "fara_gres", "Fără greș", "Uma sessão de 10 ou mais com 100% de acerto.",
        lambda c: c.session_items >= 10 and c.session_correct == c.session_items,
    ),
    Achievement(
        "revenire", "Revenire", "Recuperou uma palavra que estava travada.",
        lambda c: c.leech_recovered >= 1,
    ),
    Achievement(
        "noctambul", "Noctambul", "Estudou entre meia-noite e 5 da manhã.",
        lambda c: 0 <= c.now.hour < 5,
    ),
    Achievement(
        "matinal", "Matinal", "Estudou antes das 7 da manhã.",
        lambda c: 5 <= c.now.hour < 7,
    ),
)

BY_CODE = {a.code: a for a in CATALOG}


def check(context: Context, already_unlocked: set[str]) -> list[Achievement]:
    """Conquistas satisfeitas agora e ainda não desbloqueadas."""
    return [a for a in CATALOG if a.code not in already_unlocked and a.check(context)]
