"""Preenchimento de lacuna, gerado do corpus de frases.

O modo mais próximo de uso real: a palavra tem que ser recuperada dentro de um
contexto sintático, não isolada. Só funciona para itens que aparecem em alguma
frase — daí o `build` devolver None quando não há material.
"""

from __future__ import annotations

import random
import re

from dor.core.loader import Library
from dor.core.models import Sentence, VocabItem
from dor.modes.base import Exercise

MODE = "lacuna"

BLANK = "____"


def blank_out(sentence: str, target: str) -> str | None:
    """Troca a primeira ocorrência do alvo por uma lacuna, respeitando limites
    de palavra — senão 'vin' apagaria o miolo de 'vinul'."""
    pattern = re.compile(rf"(?<!\w){re.escape(target)}(?!\w)", re.IGNORECASE)
    replaced, n = pattern.subn(BLANK, sentence, count=1)
    return replaced if n else None


def candidates(lib: Library, item: VocabItem) -> list[Sentence]:
    """Frases utilizáveis para este item, com lacuna resolvível."""
    out = []
    for sid in item.examples:
        sentence = lib.sentences.get(sid)
        if sentence and sentence.cloze_target and blank_out(sentence.ro, sentence.cloze_target):
            out.append(sentence)
    return out


def build(
    item: VocabItem,
    lib: Library,
    *,
    rng: random.Random | None = None,
) -> Exercise | None:
    rng = rng or random.Random()
    options = candidates(lib, item)
    if not options:
        return None

    sentence = rng.choice(options)
    target = sentence.cloze_target
    prompt = blank_out(sentence.ro, target)
    assert prompt is not None  # garantido por candidates()

    return Exercise(
        item_id=item.id,
        mode=MODE,
        prompt=prompt,
        instruction=f"complete a lacuna  ·  {sentence.pt}",
        answers=[target],
        answer_lang="ro",
        direction="cloze",
        prompt_style="ro",
        speak_after=sentence.ro,
        note=sentence.note_pt,
    )
