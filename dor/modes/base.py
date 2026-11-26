"""Contrato comum a todos os modos de estudo.

Cada modo constrói um `Exercise` e não sabe mais nada: quem corrige, agenda,
grava e desenha é o mesmo código para todos. Adicionar um modo é escrever uma
função `build(...) -> Exercise`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from dor.core.grading import Grade, after_hint, grade
from dor.core.srs import Card, Rating, Scheduler, rating_from_grade
from dor.storage.repos import Store


@dataclass
class Exercise:
    item_id: str
    """Item do vocabulário a agendar no SRS — mesmo quando a pergunta vem de
    uma frase ou de uma regra de gramática, o que se aprende é a palavra."""

    mode: str
    prompt: str
    instruction: str
    answers: list[str]
    answer_lang: str = "ro"
    direction: str | None = None
    choices: list[str] = field(default_factory=list)
    prompt_style: str = "ro"
    speak_before: str | None = None
    speak_after: str | None = None
    note: str | None = None
    """Contexto mostrado depois de responder (tradução da frase, dica da regra)."""
    always_note: bool = False
    """Se True, a nota aparece mesmo quando a resposta está certa — usado pelos
    pares mínimos, onde saber o que era a outra palavra é metade do exercício."""
    strict_diacritics: bool = False
    """Desliga o perdão do acento. Só faz sentido quando distinguir o diacrítico
    É o exercício, isto é, nos pares mínimos."""

    @property
    def is_choice(self) -> bool:
        return bool(self.choices)


@dataclass
class Answered:
    exercise: Exercise
    grade: Grade
    rating: Rating
    latency_ms: int
    card_before: Card
    """Estado do item ANTES desta resposta — é o que a pontuação consulta para
    saber se era novo, se estava travado ou se era revisão em dia."""
    review_id: int


def answer(
    exercise: Exercise,
    given: str,
    *,
    latency_ms: int,
    store: Store,
    scheduler: Scheduler,
    session_id: int | None = None,
    now: datetime | None = None,
    hinted: bool = False,
) -> Answered:
    """Corrige, agenda e persiste — nesta ordem, tudo confirmado na hora.

    `hinted` diz que o aluno pediu a dica antes de responder. O preço mora aqui
    e não na tela porque ele muda o agendamento, não só o texto do veredito.
    """
    now = now or datetime.now(UTC)
    result = grade(
        given,
        exercise.answers,
        lang=exercise.answer_lang,
        strict_diacritics=exercise.strict_diacritics,
    )
    if hinted:
        result = after_hint(result)
    rating = rating_from_grade(result, latency_ms)

    card_before = store.get_card(exercise.item_id)
    store.save_card(scheduler.review(card_before, rating, now))
    review_id = store.log_review(
        exercise.item_id,
        mode=exercise.mode,
        rating=rating,
        grade=result,
        direction=exercise.direction,
        latency_ms=latency_ms,
        session_id=session_id,
        now=now,
    )
    if session_id is not None:
        store.bump_session(session_id, correct=result.ok, credit=result.credit)

    return Answered(exercise, result, rating, latency_ms, card_before, review_id)


def resolve_choice(exercise: Exercise, given: str) -> str:
    """Numa múltipla escolha, aceita o número da alternativa ou o texto dela."""
    raw = given.strip()
    if exercise.is_choice and raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(exercise.choices):
            return exercise.choices[index]
    return given


class Timer:
    """Cronômetro por pergunta — a latência decide entre nota Good e Easy."""

    elapsed_ms: int = 0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)
