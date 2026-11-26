"""Escuta ativa: ouvir e entender.

Diferente do ditado — aqui não interessa a ortografia, interessa se a palavra
foi compreendida. A resposta vem em português, e a palavra romena só aparece na
correção. É o exercício mais próximo de conversa real, onde ninguém mostra a
grafia antes de falar.
"""

from __future__ import annotations

import random

from dor.core.loader import Library
from dor.core.models import VocabItem
from dor.modes.base import Exercise

MODE = "escuta"

AUDIO_PROMPT = "🔊  ·  ·  ·"


def build(
    item: VocabItem,
    lib: Library | None = None,
    *,
    rng: random.Random | None = None,
) -> Exercise:
    return Exercise(
        item_id=item.id,
        mode=MODE,
        prompt=AUDIO_PROMPT,
        instruction="o que você ouviu, em português?   ·   [r] repetir",
        answers=item.pt_answers,
        answer_lang="pt",
        direction="escuta",
        prompt_style="dim",
        speak_before=item.ro,
        speak_after=item.ro,
        note=item.note_pt,
    )
