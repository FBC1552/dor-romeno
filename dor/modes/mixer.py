"""Escolha do modo conforme a maturidade do item.

A dificuldade sobe junto com o quanto o item já foi visto, em vez de ser
sorteada. A progressão é a mesma que um professor usaria:

    nunca visto   ->  reconhecer      (RO->PT, com áudio)
    visto pouco   ->  distinguir      (múltipla escolha)
    consolidando  ->  usar            (lacuna na frase, se houver)
    maduro        ->  produzir        (PT->RO, do zero)

Item marcado como leech volta para o reconhecimento: insistir na produção com
uma palavra que não gruda só acumula frustração.
"""

from __future__ import annotations

import random

from dor.core.loader import Library
from dor.core.models import VocabItem
from dor.core.srs import Card
from dor.modes import cloze, multiple_choice, translation
from dor.modes.base import Exercise

#: Fronteiras de reps entre os estágios.
CHOICE_UNTIL = 2
PRODUCE_FROM = 4


def pick(
    item: VocabItem,
    card: Card,
    lib: Library,
    pool: list[VocabItem],
    *,
    rng: random.Random | None = None,
    allow: set[str] | None = None,
) -> Exercise:
    """Devolve o exercício adequado, com queda para tradução se o modo não puder
    ser montado (acervo pequeno, item sem frase de exemplo)."""
    rng = rng or random.Random()

    def enabled(mode: str) -> bool:
        return allow is None or mode in allow

    if card.is_new or card.leech:
        if enabled(translation.MODE):
            return translation.build(item, direction="ro_pt", rng=rng)

    if card.reps <= CHOICE_UNTIL and enabled(multiple_choice.MODE):
        exercise = multiple_choice.build(item, pool, direction="ro_pt", rng=rng)
        if exercise:
            return exercise

    if card.reps < PRODUCE_FROM and enabled(cloze.MODE):
        exercise = cloze.build(item, lib, rng=rng)
        if exercise:
            return exercise

    if card.reps >= PRODUCE_FROM and enabled(multiple_choice.MODE) and rng.random() < 0.25:
        # Uma múltipla escolha ocasional no estágio maduro quebra a monotonia
        # sem baratear a sessão.
        exercise = multiple_choice.build(item, pool, direction="pt_ro", rng=rng)
        if exercise:
            return exercise

    direction = "pt_ro" if card.reps >= PRODUCE_FROM else "ro_pt"
    return translation.build(item, direction=direction, rng=rng)
