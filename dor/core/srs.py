"""Agendamento por repetição espaçada.

FSRS é o estado da arte e é o agendador padrão. Mas ele é uma dependência
externa, e um app de estudo que quebra porque um pacote mudou de API é um app
que se perde. Por isso existe o `SM2Scheduler`: implementação em stdlib puro do
algoritmo clássico do SuperMemo-2, que assume automaticamente se o `fsrs` não
estiver instalado. Os dois gravam nas mesmas colunas.

A tradução do veredito da correção para a nota do agendador é a cola entre a
F2 e esta fase:

    errado                -> Again   (o item volta logo)
    quase                 -> Hard    (sabia, tropeçou no acento)
    certo                 -> Good
    certo e rápido (<3 s) -> Easy    (resposta automática, pode espaçar mais)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Protocol

from dor.core.grading import Grade, Verdict

#: Abaixo disso a resposta é considerada automática, não calculada.
FAST_ANSWER_MS = 3000

#: Quantas recaídas até o item ser marcado como "leech" e merecer intervenção.
LEECH_THRESHOLD = 4


class Rating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


class CardState(IntEnum):
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


@dataclass(slots=True)
class Card:
    """Estado de agendamento de um item, espelhando as colunas de `items_state`."""

    item_id: str
    stability: float | None = None
    difficulty: float | None = None
    step: int | None = 0
    state: int = CardState.LEARNING
    due_at: datetime | None = None
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0
    leech: bool = False

    @property
    def is_new(self) -> bool:
        return self.reps == 0

    def is_due(self, now: datetime | None = None) -> bool:
        if self.due_at is None:
            return True
        return self.due_at <= (now or datetime.now(UTC))


def rating_from_grade(grade: Grade, latency_ms: int | None = None) -> Rating:
    """Converte o veredito da correção na nota que o agendador entende."""
    if grade.verdict is Verdict.WRONG:
        return Rating.AGAIN
    if grade.verdict is Verdict.ALMOST:
        return Rating.HARD
    # Acertou, mas com a dica na tela: agendar como recall limpo faria a
    # palavra sumir do radar sem nunca ter sido lembrada sozinha.
    if grade.hinted:
        return Rating.HARD
    if latency_ms is not None and latency_ms < FAST_ANSWER_MS:
        return Rating.EASY
    return Rating.GOOD


class Scheduler(Protocol):
    name: str

    def review(self, card: Card, rating: Rating, now: datetime) -> Card: ...


class FSRSScheduler:
    """Adaptador sobre py-fsrs (API 5.x/6.x: `Scheduler.review_card`)."""

    name = "fsrs"

    def __init__(self) -> None:
        from fsrs import Scheduler as _FSRS

        self._impl = _FSRS()

    @staticmethod
    def available() -> bool:
        try:
            import fsrs  # noqa: F401
        except ImportError:
            return False
        return True

    def review(self, card: Card, rating: Rating, now: datetime) -> Card:
        from fsrs import Card as FCard
        from fsrs import Rating as FRating
        from fsrs import State as FState

        fcard = FCard(
            state=FState(card.state),
            step=card.step,
            stability=card.stability,
            difficulty=card.difficulty,
            due=card.due_at or now,
            last_review=card.last_review,
        )
        updated, _log = self._impl.review_card(fcard, FRating(int(rating)), now)

        lapses = card.lapses + (1 if rating is Rating.AGAIN else 0)
        return replace(
            card,
            stability=updated.stability,
            difficulty=updated.difficulty,
            step=updated.step,
            state=int(updated.state),
            due_at=updated.due,
            last_review=now,
            reps=card.reps + 1,
            lapses=lapses,
            leech=lapses >= LEECH_THRESHOLD,
        )


class SM2Scheduler:
    """SuperMemo-2 em stdlib puro, para quando o `fsrs` não estiver disponível.

    Reaproveita as colunas do FSRS: `stability` guarda o intervalo em dias e
    `difficulty` guarda o fator de facilidade.
    """

    name = "sm2"

    MIN_EASE = 1.3
    DEFAULT_EASE = 2.5

    #: Nota do agendador -> qualidade do SM-2 (escala 0–5 do algoritmo original).
    QUALITY = {Rating.AGAIN: 2, Rating.HARD: 3, Rating.GOOD: 4, Rating.EASY: 5}

    @staticmethod
    def available() -> bool:
        return True

    def review(self, card: Card, rating: Rating, now: datetime) -> Card:
        ease = card.difficulty or self.DEFAULT_EASE
        interval = card.stability or 0.0
        reps = card.reps + 1
        lapses = card.lapses
        quality = self.QUALITY[rating]

        if rating is Rating.AGAIN:
            lapses += 1
            interval = 1.0
            state = CardState.RELEARNING
            reps_effective = 0
        else:
            reps_effective = reps
            if card.reps == 0:
                interval = 1.0
            elif card.reps == 1:
                interval = 6.0
            else:
                interval = max(1.0, round(interval * ease, 2))
            state = CardState.REVIEW

        # Ajuste de facilidade do SM-2 original.
        ease = max(self.MIN_EASE, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

        return replace(
            card,
            stability=interval,
            difficulty=round(ease, 4),
            step=reps_effective,
            state=int(state),
            due_at=now + timedelta(days=interval),
            last_review=now,
            reps=reps,
            lapses=lapses,
            leech=lapses >= LEECH_THRESHOLD,
        )


def get_scheduler(prefer: str = "auto") -> Scheduler:
    """`auto` usa FSRS se estiver instalado; senão cai no SM-2."""
    if prefer in ("auto", "fsrs") and FSRSScheduler.available():
        return FSRSScheduler()
    if prefer == "fsrs":
        raise RuntimeError("fsrs não está instalado — rode: pip install fsrs")
    return SM2Scheduler()


def available_schedulers() -> list[str]:
    names = []
    if FSRSScheduler.available():
        names.append("fsrs")
    names.append("sm2")
    return names
