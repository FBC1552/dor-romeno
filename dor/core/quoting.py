"""Citação de terceiros: o que pode virar exercício e o que não pode.

Música e literatura têm o mesmo problema — o material bom quase sempre é de
alguém. A regra do projeto é curta: o app guarda ficha, glossário e link para
qualquer obra, mas só reproduz TEXTO quando ele está em domínio público.

Esta trava mora aqui, no núcleo, e não na curadoria de cada arquivo: um erro
de digitação num JSON não deve conseguir transformar obra protegida em
exercício.
"""

from __future__ import annotations

import re
from typing import Any

#: Comentário explicativo dentro de uma tradução de glossário. Vira nota,
#: nunca resposta esperada — ninguém deve digitar "a palavra que dá nome ao app".
_ASIDE = re.compile(r"\s*[—–]\s*.*$")
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")


def public_lines(excerpt: dict[str, Any] | None, *, require_cloze: bool = True) -> list[dict[str, str]]:
    """Versos/linhas citáveis de um trecho. Vazio se não for domínio público.

    A comparação é `is True` de propósito: "true" em texto, 1 ou "sim" são
    quase-verdades que não valem como autorização.
    """
    if not excerpt or excerpt.get("public_domain") is not True:
        return []
    lines = excerpt.get("lines", [])
    return [line for line in lines if line.get("cloze")] if require_cloze else list(lines)


def accepted_pt(text: str) -> list[str]:
    """Traduções aceitáveis de uma entrada de glossário.

    'estrela / a estrela' vira duas respostas certas; o comentário depois do
    travessão e o parêntese saem fora.
    """
    core = _PARENTHETICAL.sub("", _ASIDE.sub("", text))
    parts = [p.strip(" .") for p in re.split(r"[,/]", core)]
    return [p for p in parts if p] or [text.strip()]
