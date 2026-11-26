"""Cognate Bridge — derivar a palavra romena a partir da portuguesa.

O exercício não pergunta "o que significa": pergunta "aplique a regra". Quem
sabe que -ção vira -ție não precisa ter visto 'informație' antes para acertar,
e é exatamente essa capacidade que o modo treina.

As armadilhas entram como exercício também, e valem tanto quanto os acertos:
uma regra sem exceção conhecida vira excesso de confiança.
"""

from __future__ import annotations

import random

from dor.core.models import Bridge
from dor.modes.base import Exercise

MODE = "punte"


def build_example(bridge: Bridge, example: dict[str, str]) -> Exercise:
    """Do português para o romeno, aplicando a regra."""
    note = example.get("note")
    if example.get("latin"):
        latin = f"latim: {example['latin']}"
        note = f"{latin} — {note}" if note else latin
    return Exercise(
        item_id=f"{bridge.id}#{example['ro']}",
        mode=MODE,
        prompt=example["pt"],
        instruction=f"aplique a ponte {bridge.pt} → {bridge.ro}",
        answers=[example["ro"]],
        answer_lang="ro",
        direction=bridge.id,
        prompt_style="pt",
        speak_after=example["ro"],
        note=note,
    )


def build_trap(bridge: Bridge, trap: dict[str, str]) -> Exercise | None:
    """A exceção, cobrada como exceção — com a nota sempre visível.

    Errar aqui é o objetivo pedagógico: é mais barato descobrir que 'cidade'
    não vira 'citate' num exercício do que no meio de uma conversa.
    """
    if not trap.get("right_ro"):
        return None
    return Exercise(
        item_id=f"{bridge.id}#trap#{trap['right_ro']}",
        mode=MODE,
        prompt=trap["pt"],
        instruction=f"cuidado — a ponte {bridge.pt} → {bridge.ro} falha aqui",
        answers=[trap["right_ro"]],
        answer_lang="ro",
        direction=bridge.id,
        prompt_style="pt",
        speak_after=trap["right_ro"],
        note=trap["note"],
        always_note=True,
    )


def build_all(bridge: Bridge, *, rng: random.Random | None = None) -> list[Exercise]:
    """Exemplos primeiro, armadilhas depois — a regra antes da exceção."""
    rng = rng or random.Random()
    examples = list(bridge.examples)
    rng.shuffle(examples)
    exercises = [build_example(bridge, e) for e in examples]
    exercises += [x for t in bridge.traps if (x := build_trap(bridge, t))]
    return exercises


def build_mixed(
    bridges: list[Bridge], *, limit: int = 15, rng: random.Random | None = None
) -> list[Exercise]:
    """Sessão embaralhada entre pontes.

    Treinar uma ponte de cada vez ensina o padrão; misturar ensina a ESCOLHER
    o padrão, que é o que a vida real cobra.
    """
    rng = rng or random.Random()
    pool = [e for bridge in bridges for e in build_all(bridge, rng=rng)]
    rng.shuffle(pool)
    return pool[:limit]
