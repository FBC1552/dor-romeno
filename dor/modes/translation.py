"""Tradução direta, nas duas direções.

RO->PT é reconhecimento (mais fácil); PT->RO é produção (mais difícil, e é o
que realmente prova que a palavra foi aprendida).
"""

from __future__ import annotations

import random

from dor.core.models import VocabItem
from dor.modes.base import Exercise

MODE = "traducao"


def build(item: VocabItem, *, direction: str = "ro_pt", rng: random.Random | None = None) -> Exercise:
    if direction == "ro_pt":
        return Exercise(
            item_id=item.id,
            mode=MODE,
            prompt=item.ro,
            instruction="traduza para o português",
            answers=item.pt_answers,
            answer_lang="pt",
            direction="ro_pt",
            prompt_style="ro",
            speak_before=item.ro,
            note=item.note_pt,
        )
    return Exercise(
        item_id=item.id,
        mode=MODE,
        prompt=item.pt_main,
        instruction="traduza para o romeno",
        answers=[item.ro, *item.accepts],
        answer_lang="ro",
        direction="pt_ro",
        prompt_style="pt",
        speak_after=item.ro,
        note=item.note_pt,
    )
