"""Múltipla escolha com alternativas plausíveis.

Passo intermediário entre reconhecer e produzir: o aluno ainda não consegue
escrever a palavra do zero, mas já precisa distingui-la de vizinhas próximas.
"""

from __future__ import annotations

import random

from dor.core import distractors
from dor.core.models import VocabItem
from dor.modes.base import Exercise

MODE = "escolha"

MIN_CHOICES = 3


def build(
    item: VocabItem,
    pool: list[VocabItem],
    *,
    direction: str = "ro_pt",
    n_choices: int = 4,
    rng: random.Random | None = None,
) -> Exercise | None:
    """Devolve None quando o acervo é pequeno demais para alternativas decentes."""
    rng = rng or random.Random()
    lang = "pt" if direction == "ro_pt" else "ro"
    correct = item.pt_main if direction == "ro_pt" else item.ro

    wrong = distractors.pick(item, pool, n=n_choices - 1, lang=lang, rng=rng)
    if len(wrong) < MIN_CHOICES - 1:
        return None

    choices = distractors.build_choices(correct, wrong, rng)

    if direction == "ro_pt":
        return Exercise(
            item_id=item.id,
            mode=MODE,
            prompt=item.ro,
            instruction="qual a tradução?",
            answers=[correct],
            answer_lang="pt",
            direction="ro_pt",
            choices=choices,
            prompt_style="ro",
            speak_before=item.ro,
            note=item.note_pt,
        )
    return Exercise(
        item_id=item.id,
        mode=MODE,
        prompt=item.pt_main,
        instruction="qual a palavra em romeno?",
        answers=[correct],
        answer_lang="ro",
        direction="pt_ro",
        choices=choices,
        prompt_style="pt",
        speak_after=item.ro,
        note=item.note_pt,
    )
