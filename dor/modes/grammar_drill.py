"""Exercícios gerados a partir das regras declarativas.

Nenhuma questão de gramática é escrita à mão. A regra guarda um filtro sobre o
vocabulário e o par de campos origem/alvo; este módulo cruza os dois. Uma regra
de artigo definido feminino mais oitenta substantivos femininos são oitenta
exercícios — e cada palavra nova adicionada ao acervo gera mais, sozinha.
"""

from __future__ import annotations

import random

from dor.core.loader import Library, filter_vocab
from dor.core.models import GrammarRule, VocabItem
from dor.modes.base import Exercise

MODE = "gramatica"

#: Ordem das pessoas nas listas de conjugação do campo `forms`.
PERSONS = ("eu", "tu", "el / ea", "noi", "voi", "ei / ele")

#: Gênero: código no JSON -> respostas aceitas. A primeira é a que aparece na
#: correção, então precisa ser a legível — mostrar "→ f" não ensina nada.
GENDER_ANSWERS = {
    "m": ["masculino", "masculin", "m"],
    "f": ["feminino", "feminin", "f"],
    "n": ["neutro", "neutru", "n"],
}
GENDER_CHOICES = ["masculino", "feminino", "neutro"]


def matching_items(rule: GrammarRule, lib: Library) -> list[VocabItem]:
    """Itens do vocabulário que servem para esta regra."""
    if not rule.drill:
        return []
    query = dict(rule.drill["query"])
    target = rule.drill["to"]
    return [item for item in filter_vocab(lib, **query) if item.form(target)]


def build(
    rule: GrammarRule,
    lib: Library,
    *,
    item: VocabItem | None = None,
    rng: random.Random | None = None,
) -> Exercise | None:
    rng = rng or random.Random()
    if not rule.drill:
        return None

    if item is None:
        pool = matching_items(rule, lib)
        if not pool:
            return None
        item = rng.choice(pool)

    drill = rule.drill
    source = item.form(drill["from"])
    target = item.form(drill["to"])
    if not source or not target:
        return None

    note = rule.pitfall_pt or rule.contrast_pt

    # Gênero: alternativas fixas, resposta em português.
    if drill["to"] == "gender":
        return Exercise(
            item_id=item.id,
            mode=MODE,
            prompt=str(source),
            instruction=drill["prompt_pt"],
            answers=GENDER_ANSWERS[str(target)],
            answer_lang="pt",
            direction=rule.id,
            choices=list(GENDER_CHOICES),
            prompt_style="ro",
            speak_before=item.ro,
            note=note,
        )

    # Conjugação: o alvo é uma lista de seis formas; sorteia uma pessoa.
    if isinstance(target, list):
        index = rng.randrange(len(target))
        person = PERSONS[index] if index < len(PERSONS) else f"forma {index + 1}"
        return Exercise(
            item_id=item.id,
            mode=MODE,
            prompt=f"{source}   ·   {person}",
            instruction=drill["prompt_pt"],
            answers=[str(target[index])],
            answer_lang="ro",
            direction=rule.id,
            prompt_style="ro",
            speak_after=str(target[index]),
            note=note,
        )

    # Transformação simples: artigo definido, plural, genitivo.
    return Exercise(
        item_id=item.id,
        mode=MODE,
        prompt=str(source),
        instruction=drill["prompt_pt"],
        answers=[str(target)],
        answer_lang="ro",
        direction=rule.id,
        prompt_style="ro",
        speak_after=str(target),
        note=note,
    )
