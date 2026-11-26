"""Alternativas erradas plausíveis.

Escolher entre `pâine` e `televizor` não ensina nada: a resposta sai por
eliminação, sem que a palavra seja de fato recuperada da memória. Um distrator
bom é aquele que o aluno *poderia* ter escolhido — mesma classe, mesmo campo
semântico, forma parecida.

O ranqueamento é intencionalmente grosseiro e depois sorteado entre os melhores:
sempre o mesmo trio de alternativas faria o aluno decorar o layout da pergunta
em vez da palavra.
"""

from __future__ import annotations

import random

from dor.core.models import VocabItem
from dor.core.normalize import fold, levenshtein, normalize
from dor.core.synonyms import equivalent as pt_equivalent

#: De quantos candidatos bem pontuados sortear. Alto demais devolve lixo, baixo
#: demais deixa a pergunta previsível.
POOL_SIZE = 12


def _similarity(a: str, b: str) -> float:
    """0.0 a 1.0, por distância de edição sobre a forma sem diacríticos."""
    a, b = fold(normalize(a)), fold(normalize(b))
    if not a or not b:
        return 0.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def score(target: VocabItem, candidate: VocabItem, lang: str) -> float:
    """Quão plausível `candidate` é como alternativa errada para `target`."""
    points = 0.0

    if candidate.pos == target.pos:
        points += 3.0
    if target.pos == "noun" and candidate.gender == target.gender:
        points += 2.0
    if candidate.level == target.level:
        points += 1.0
    if candidate.register == target.register:
        points += 0.5

    shared = set(candidate.tags) & set(target.tags)
    points += min(len(shared), 2) * 2.0

    # Semelhança de forma: palavras parecidas obrigam a olhar com atenção.
    surface = _similarity(
        candidate.ro if lang == "ro" else candidate.pt_main,
        target.ro if lang == "ro" else target.pt_main,
    )
    points += surface * 2.0

    return points


def pick(
    target: VocabItem,
    pool: list[VocabItem],
    *,
    n: int = 3,
    lang: str = "ro",
    rng: random.Random | None = None,
) -> list[str]:
    """Devolve até `n` alternativas erradas, em texto pronto para exibir."""
    rng = rng or random.Random()

    def surface(item: VocabItem) -> str:
        return item.ro if lang == "ro" else item.pt_main

    answers = [target.ro, *target.accepts] if lang == "ro" else target.pt_answers
    correct = {normalize(s) for s in answers}

    def is_answer(text: str) -> bool:
        """Alternativa que na prática também está certa.

        Do lado do português não basta comparar strings: 'valeu' e 'obrigado'
        são a mesma resposta para o corretor, então 'valeu' não pode aparecer
        como distrator de 'mulțumesc' — a questão ficaria sem alternativa
        errada e o aluno seria reprovado por escolher uma resposta certa.
        """
        if normalize(text) in correct:
            return True
        return lang == "pt" and any(pt_equivalent(text, answer) for answer in answers)

    seen: set[str] = set()
    candidates: list[tuple[float, VocabItem]] = []
    for item in pool:
        if item.id == target.id:
            continue
        text = surface(item)
        key = normalize(text)
        # Um "distrator" que é resposta certa (sinônimo) tornaria a questão
        # insolúvel; um repetido desperdiça alternativa.
        if key in seen or is_answer(text):
            continue
        seen.add(key)
        candidates.append((score(target, item, lang), item))

    if not candidates:
        return []

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    best = [item for _, item in candidates[:POOL_SIZE]]
    rng.shuffle(best)
    return [surface(item) for item in best[:n]]


def build_choices(
    correct: str,
    distractors: list[str],
    rng: random.Random | None = None,
) -> list[str]:
    """Embaralha a correta entre as erradas."""
    rng = rng or random.Random()
    options = [correct, *distractors]
    rng.shuffle(options)
    return options
