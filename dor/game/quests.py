"""Metas diárias.

Sorteadas de forma determinística pela data: as quests de hoje são as mesmas se
o app for aberto de manhã ou à noite, e não mudam quando a sessão é reiniciada.
Isso importa mais do que parece — meta que troca sozinha não é meta.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from dor.core.grading import Verdict


@dataclass
class ReviewEvent:
    """O que aconteceu numa resposta, para as quests avaliarem."""

    mode: str
    direction: str | None
    verdict: Verdict
    diacritics_only: bool
    was_new: bool
    was_leech: bool
    latency_ms: int | None
    combo: int


@dataclass(frozen=True)
class QuestTemplate:
    code: str
    title: str
    target: int
    reward_xp: int
    matches: Callable[[ReviewEvent], bool]


@dataclass
class Quest:
    code: str
    title: str
    target: int
    reward_xp: int
    progress: int = 0
    done: bool = False
    template: QuestTemplate | None = field(default=None, repr=False)

    @property
    def ratio(self) -> float:
        return min(1.0, self.progress / self.target) if self.target else 1.0


def _is_romanian_answer(event: ReviewEvent) -> bool:
    """Respostas escritas em romeno: produção, lacuna e drills de gramática."""
    return event.direction in ("pt_ro", "cloze") or event.mode == "gramatica"


CATALOG: tuple[QuestTemplate, ...] = (
    QuestTemplate(
        "revisoes_20", "Responda 20 revisões", 20, 40,
        lambda e: True,
    ),
    QuestTemplate(
        "acertos_15", "Acerte 15 respostas", 15, 45,
        lambda e: e.verdict is Verdict.CORRECT,
    ),
    QuestTemplate(
        "diacritice_10", "10 acertos em romeno sem escorregar no acento", 10, 60,
        lambda e: e.verdict is Verdict.CORRECT and _is_romanian_answer(e),
    ),
    QuestTemplate(
        "gramatica_10", "10 acertos no treino de gramática", 10, 50,
        lambda e: e.verdict is Verdict.CORRECT and e.mode == "gramatica",
    ),
    QuestTemplate(
        "cuvinte_noi_5", "Conheça 5 palavras novas", 5, 35,
        lambda e: e.was_new,
    ),
    QuestTemplate(
        "productie_8", "Traduza 8 palavras PARA o romeno", 8, 55,
        lambda e: e.verdict is Verdict.CORRECT and e.direction == "pt_ro",
    ),
    QuestTemplate(
        "rapid_10", "10 acertos em menos de 3 segundos", 10, 45,
        lambda e: e.verdict is Verdict.CORRECT
        and e.latency_ms is not None
        and e.latency_ms < 3000,
    ),
    QuestTemplate(
        "combo_8", "Emende 8 acertos seguidos", 8, 50,
        lambda e: e.verdict is Verdict.CORRECT,
    ),
    QuestTemplate(
        "recuperare_2", "Recupere 2 palavras travadas", 2, 70,
        lambda e: e.verdict is Verdict.CORRECT and e.was_leech,
    ),
    QuestTemplate(
        "context_6", "Complete 6 lacunas em frases", 6, 50,
        lambda e: e.verdict is Verdict.CORRECT and e.mode == "lacuna",
    ),
)

BY_CODE = {t.code: t for t in CATALOG}

QUESTS_PER_DAY = 3

#: Metas que qualquer sessão de estudo avança, independentemente do modo.
#: Uma delas sempre entra no dia — senão o sorteio pode dar três missões
#: especializadas (gramática + lacuna + recuperar travada) e o usuário fecha a
#: sessão sem ter movido nenhuma barra, que é o pior resultado possível.
BASELINE_CODES = frozenset({"revisoes_20", "acertos_15"})


def for_day(day: date, count: int = QUESTS_PER_DAY) -> list[QuestTemplate]:
    """Sorteio estável: a mesma data devolve sempre as mesmas quests."""
    rng = random.Random(day.toordinal())
    baseline = rng.choice([t for t in CATALOG if t.code in BASELINE_CODES])
    rest = [t for t in CATALOG if t.code != baseline.code]
    picked = rng.sample(rest, max(0, min(count - 1, len(rest))))
    return [baseline, *picked]


def apply_event(quests: list[Quest], event: ReviewEvent) -> list[Quest]:
    """Avança o progresso e devolve as que acabaram de ser concluídas."""
    completed: list[Quest] = []
    for quest in quests:
        if quest.done:
            continue
        template = quest.template or BY_CODE.get(quest.code)
        if template is None or not template.matches(event):
            continue

        if quest.code == "combo_8":
            # Quest de sequência: mede o melhor combo do dia, não a soma.
            quest.progress = max(quest.progress, event.combo + 1)
        else:
            quest.progress += 1

        if quest.progress >= quest.target:
            quest.progress = quest.target
            quest.done = True
            completed.append(quest)
    return completed
