"""Ditado: ouvir e escrever.

O melhor exercício que existe para os diacríticos. Escrever `ș` e `ț` a partir
de uma imagem visual da palavra é decoreba; escrever a partir do som obriga o
ouvido a separar de verdade `pește` de `peste`.

É também onde o veredito "quase" da F2 mais importa — errar o acento num ditado
é informação valiosa, não fracasso.
"""

from __future__ import annotations

import random

from dor.core.loader import Library
from dor.core.models import VocabItem
from dor.modes.base import Exercise

MODE = "ditado"

AUDIO_PROMPT = "🔊  ·  ·  ·"


def build(
    item: VocabItem,
    lib: Library | None = None,
    *,
    use_sentence: bool = False,
    rng: random.Random | None = None,
) -> Exercise:
    """Com `use_sentence`, dita uma frase de exemplo em vez da palavra solta."""
    rng = rng or random.Random()

    target = item.ro
    note = item.note_pt
    if use_sentence and lib:
        options = [lib.sentences[s] for s in item.examples if s in lib.sentences]
        if options:
            sentence = rng.choice(options)
            target = sentence.ro
            note = sentence.pt

    return Exercise(
        item_id=item.id,
        mode=MODE,
        prompt=AUDIO_PROMPT,
        instruction="escreva o que ouviu   ·   [r] repetir",
        answers=[target],
        answer_lang="ro",
        direction="ditado",
        prompt_style="dim",
        speak_before=target,
        note=note,
    )
