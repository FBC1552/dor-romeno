"""Treino a partir de uma cena do dia a dia.

O exercício é sempre de PRODUÇÃO, do português para o romeno. Reconhecer
'Cât costă?' não adianta nada no balcão da padaria — na hora, quem tem de
produzir a frase é você. Por isso este modo não tem direção inversa.
"""

from __future__ import annotations

import random

from dor.core.models import Scene
from dor.modes.base import Exercise

MODE = "cena"


def build_phrase(scene: Scene, phrase: dict[str, str]) -> Exercise:
    """Fórmula do português para o romeno, com o 'quando usar' como dica."""
    hint = phrase.get("when_pt")
    return Exercise(
        item_id=f"{scene.id}#{phrase['ro']}",
        mode=MODE,
        prompt=phrase["pt"],
        instruction=f"como se diz?  ·  {scene.title}",
        answers=[phrase["ro"]],
        answer_lang="ro",
        direction="pt_ro",
        prompt_style="pt",
        speak_after=phrase["ro"],
        note=hint,
    )


def build_turn(scene: Scene, turn: dict[str, str]) -> Exercise:
    """Sua fala do diálogo, pedida pela tradução. É a mesma cena, com contexto."""
    return Exercise(
        item_id=f"{scene.id}#{turn['ro']}",
        mode=MODE,
        prompt=turn["pt"],
        instruction=f"sua vez  ·  {scene.title}",
        answers=[turn["ro"]],
        answer_lang="ro",
        direction="pt_ro",
        prompt_style="pt",
        speak_after=turn["ro"],
        note=turn.get("note_pt"),
    )


def build_all(scene: Scene, *, rng: random.Random | None = None, with_turns: bool = True) -> list[Exercise]:
    """As fórmulas primeiro, as falas do diálogo depois.

    A fórmula é a peça isolada; a fala é ela dentro da conversa. Treinar na
    ordem inversa faria o aluno decorar o diálogo em vez da estrutura.
    """
    rng = rng or random.Random()

    phrases = list(scene.phrases)
    rng.shuffle(phrases)
    exercises = [build_phrase(scene, p) for p in phrases]

    if with_turns:
        seen = {e.item_id for e in exercises}
        for turn in scene.my_turns:
            exercise = build_turn(scene, turn)
            if exercise.item_id not in seen:
                exercises.append(exercise)
                seen.add(exercise.item_id)

    return exercises
