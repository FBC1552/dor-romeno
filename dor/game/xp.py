"""Pontuação e curva de nível.

A fórmula premia o que é pedagogicamente mais caro, não o que é mais rápido de
clicar: produzir vale mais que reconhecer, escolher entre alternativas vale
menos que escrever, e recuperar uma palavra que estava travada vale bônus.

    XP = base(modo) × direção × crédito × velocidade × srs × combo

O crédito vem direto do veredito da F2, então "quase" rende metade — errar o
diacrítico custa pontos, mas não zera o esforço.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dor.core.srs import Card

#: Custo cognitivo de cada modo.
BASE_XP = {
    "traducao": 10,
    "escolha": 5,
    "lacuna": 8,
    "gramatica": 10,
    "ditado": 12,
}
DEFAULT_BASE = 8

#: Produzir em romeno é mais difícil que reconhecer.
DIRECTION_MULT = {"pt_ro": 1.3, "cloze": 1.2}

FAST_MS = 3000
FAST_MULT = 1.2

NEW_MULT = 1.0
REVIEW_MULT = 1.2
LEECH_RECOVERY_MULT = 1.5

COMBO_STEP = 0.1
COMBO_MAX = 2.0

#: Custo em XP para subir do nível n para o n+1. Curva triangular: o nível 10
#: custa dez vezes o nível 1, o que mantém a progressão visível sem virar grind.
LEVEL_STEP = 100


@dataclass
class XPBreakdown:
    total: int
    base: int
    combo_mult: float
    fast: bool
    leech_recovery: bool


def compute(
    *,
    mode: str,
    direction: str | None,
    credit: float,
    latency_ms: int | None,
    card_before: Card,
    combo: int,
) -> XPBreakdown:
    """`combo` é quantos acertos consecutivos vinham ANTES desta resposta."""
    base = BASE_XP.get(mode, DEFAULT_BASE)
    value = float(base)

    value *= DIRECTION_MULT.get(direction or "", 1.0)
    value *= credit

    fast = bool(latency_ms is not None and latency_ms < FAST_MS and credit > 0)
    if fast:
        value *= FAST_MULT

    recovery = bool(card_before.leech and credit >= 1.0)
    if recovery:
        value *= LEECH_RECOVERY_MULT
    elif card_before.is_new:
        value *= NEW_MULT
    else:
        value *= REVIEW_MULT

    combo_mult = combo_multiplier(combo) if credit > 0 else 1.0
    value *= combo_mult

    return XPBreakdown(
        total=int(round(value)),
        base=base,
        combo_mult=combo_mult,
        fast=fast,
        leech_recovery=recovery,
    )


def combo_multiplier(combo: int) -> float:
    """1.0 no primeiro acerto, subindo 10% a cada, travado em 2.0x."""
    return min(COMBO_MAX, 1.0 + COMBO_STEP * max(0, combo))


def xp_to_reach(level: int) -> int:
    """XP acumulado necessário para estar no nível dado. Nível 1 começa em zero."""
    if level <= 1:
        return 0
    return LEVEL_STEP * (level - 1) * level // 2


def level_from_xp(xp: int) -> int:
    """Inverte a curva triangular."""
    if xp < LEVEL_STEP:
        return 1
    # xp >= 50*(n-1)*n  =>  n = floor((1 + sqrt(1 + 8*xp/100)) / 2)
    n = int((1 + math.isqrt(1 + 8 * xp // LEVEL_STEP)) // 2)
    while xp_to_reach(n + 1) <= xp:
        n += 1
    while xp_to_reach(n) > xp:
        n -= 1
    return max(1, n)


@dataclass
class LevelProgress:
    level: int
    xp_total: int
    xp_into_level: int
    xp_for_next: int

    @property
    def ratio(self) -> float:
        return self.xp_into_level / self.xp_for_next if self.xp_for_next else 1.0


def progress(xp_total: int) -> LevelProgress:
    level = level_from_xp(xp_total)
    floor_xp = xp_to_reach(level)
    next_xp = xp_to_reach(level + 1)
    return LevelProgress(
        level=level,
        xp_total=xp_total,
        xp_into_level=xp_total - floor_xp,
        xp_for_next=next_xp - floor_xp,
    )
