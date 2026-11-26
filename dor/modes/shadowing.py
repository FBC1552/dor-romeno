"""Shadowing: ouvir devagar, repetir, ouvir na velocidade normal.

Único modo sem correção — não há o que digitar. O objetivo é a boca, não a
memória: reproduzir a melodia da frase enquanto ela ainda está no ouvido.

Por isso não entra no SRS nem pontua. Fingir que dá para avaliar pronúncia sem
ouvir o aluno seria desonesto; a avaliação de fala fica para quando houver
reconhecimento de voz.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from dor.core.loader import Library
from dor.core.models import Sentence

MODE = "shadowing"

#: Ritmo da primeira passada. O edge-tts aceita o formato de porcentagem.
SLOW_RATE = "-35%"
NORMAL_RATE = "+0%"

#: Pausa para repetir, proporcional ao tamanho da frase.
PAUSE_PER_CHAR_MS = 55
MIN_PAUSE_MS = 1200


@dataclass
class ShadowStep:
    sentence: Sentence
    pause_ms: int

    @property
    def ro(self) -> str:
        return self.sentence.ro

    @property
    def pt(self) -> str:
        return self.sentence.pt


def pause_for(text: str) -> int:
    """Tempo de repetição: quem fala devagar precisa de mais espaço."""
    return max(MIN_PAUSE_MS, int(len(text) * PAUSE_PER_CHAR_MS))


def build(
    lib: Library,
    *,
    limit: int = 8,
    level: str | None = None,
    rng: random.Random | None = None,
) -> list[ShadowStep]:
    rng = rng or random.Random()
    pool = [s for s in lib.sentences.values() if level is None or s.level == level]
    if not pool:
        return []
    rng.shuffle(pool)
    return [ShadowStep(sentence=s, pause_ms=pause_for(s.ro)) for s in pool[:limit]]


def audio_texts(steps: list[ShadowStep]) -> list[str]:
    return [step.ro for step in steps]
