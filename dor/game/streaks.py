"""Sequência de dias estudados, com proteção contra o dia perdido.

Uma streak que quebra por um único dia de viagem é uma streak que desmotiva —
o usuário desiste de recomeçar do zero. Daí os *freezes*: a cada 7 dias
consecutivos o app guarda um escudo (máximo 3), consumido automaticamente para
cobrir uma falta. É perdão limitado, não impunidade: três dias seguidos sem
estudar quebram mesmo.

O dia é o LOCAL, não o UTC. Estudar às 23h e à 1h conta como dois dias.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

#: Dias consecutivos para ganhar um escudo.
FREEZE_EVERY = 7
MAX_FREEZES = 3


@dataclass
class Streak:
    current: int = 0
    longest: int = 0
    freezes: int = 0
    last_active: date | None = None


@dataclass
class StreakUpdate:
    streak: Streak
    started: bool = False
    """Primeira atividade de todos os tempos, ou recomeço após quebra."""
    continued: bool = False
    frozen_days: int = 0
    """Quantos dias foram cobertos por escudo."""
    broke: bool = False
    freeze_earned: bool = False
    already_today: bool = False


def touch(streak: Streak, today: date) -> StreakUpdate:
    """Registra atividade em `today` e devolve o novo estado com o que mudou."""
    last = streak.last_active

    if last == today:
        return StreakUpdate(streak=streak, already_today=True)

    if last is None:
        new = Streak(current=1, longest=max(1, streak.longest), freezes=streak.freezes,
                     last_active=today)
        return StreakUpdate(streak=new, started=True)

    gap = (today - last).days

    if gap < 0:
        # Relógio andou para trás (fuso, correção manual). Não punir por isso.
        return StreakUpdate(streak=streak, already_today=True)

    missed = gap - 1
    frozen = 0
    freezes = streak.freezes

    if missed > 0:
        if missed <= freezes:
            freezes -= missed
            frozen = missed
        else:
            new = Streak(current=1, longest=streak.longest, freezes=freezes, last_active=today)
            return StreakUpdate(streak=new, broke=True, started=True)

    current = streak.current + 1
    earned = current % FREEZE_EVERY == 0 and freezes < MAX_FREEZES
    if earned:
        freezes += 1

    new = Streak(
        current=current,
        longest=max(current, streak.longest),
        freezes=freezes,
        last_active=today,
    )
    return StreakUpdate(
        streak=new,
        continued=True,
        frozen_days=frozen,
        freeze_earned=earned,
    )


def days_until_freeze(streak: Streak) -> int:
    """Quantos dias faltam para o próximo escudo (0 se já está no teto)."""
    if streak.freezes >= MAX_FREEZES:
        return 0
    return FREEZE_EVERY - (streak.current % FREEZE_EVERY)


def at_risk(streak: Streak, today: date) -> bool:
    """True quando a streak morre se hoje não houver estudo."""
    if streak.last_active is None or streak.current == 0:
        return False
    return streak.last_active < today and streak.freezes == 0


def next_deadline(streak: Streak) -> date | None:
    """Último dia possível para estudar sem quebrar, contando os escudos."""
    if streak.last_active is None:
        return None
    return streak.last_active + timedelta(days=1 + streak.freezes)
