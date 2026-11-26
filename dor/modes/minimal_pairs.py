"""Discriminação auditiva por pares mínimos.

Toca uma das duas palavras e pergunta qual foi. Não há dica de contexto, não há
grafia — só o som. É o único exercício que treina a percepção antes da
produção, e sem ele o aluno passa anos ouvindo `ș` e `s` como a mesma coisa.

Os pares recebem estado próprio no SRS (`item_id = mp.<id>`), então um contraste
que você erra volta mais vezes, exatamente como uma palavra.
"""

from __future__ import annotations

import random

from dor.core.models import MinimalPair, PairSide
from dor.modes.base import Exercise

MODE = "perechi"

AUDIO_PROMPT = "🔊  ·  ·  ·"


def build(pair: MinimalPair, *, rng: random.Random | None = None) -> Exercise:
    rng = rng or random.Random()
    played: PairSide = rng.choice(pair.sides)

    choices = [pair.a.ro, pair.b.ro]
    rng.shuffle(choices)

    note = f"{pair.a.ro} = {pair.a.pt}   ·   {pair.b.ro} = {pair.b.pt}"
    if pair.note_pt:
        note += f"\n  {pair.note_pt}"

    return Exercise(
        item_id=pair.id,
        mode=MODE,
        prompt=AUDIO_PROMPT,
        instruction=f"qual palavra você ouviu?   ·   contraste {pair.contrast}   ·   [r] repetir",
        answers=[played.ro],
        answer_lang="ro",
        direction=f"mp:{pair.contrast}",
        choices=choices,
        prompt_style="dim",
        speak_before=played.ro,
        note=note,
        always_note=True,
        strict_diacritics=True,
    )


def audio_texts(pairs: list[MinimalPair]) -> list[str]:
    """Todo o áudio que uma sessão pode precisar — os dois lados de cada par."""
    return [side.ro for pair in pairs for side in pair.sides]
