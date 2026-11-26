"""Normalização de texto para comparação de respostas.

O romeno tem duas armadilhas de codificação que fariam o app rejeitar respostas
corretas se fossem ignoradas:

1. **Vírgula vs. cedilha.** As letras corretas são ș/ț (U+0219/U+021B, vírgula
   embaixo), mas metade do texto romeno em circulação usa ş/ţ (U+015F/U+0163,
   cedilha), herança de fontes antigas e do Windows pré-Vista. São caracteres
   diferentes para o computador e a mesma letra para um romeno. Digitar a
   variante com cedilha nunca é erro do aluno.

2. **Formas decompostas.** "ă" pode chegar como um caractere só (U+0103) ou como
   "a" + breve combinante. Sem normalizar Unicode, os dois não são iguais.

A dobra de diacríticos (`fold`) é o que permite distinguir "errou a palavra" de
"acertou a palavra e esqueceu o acento" — que são coisas pedagogicamente
distintas e merecem respostas distintas.
"""

from __future__ import annotations

import re
import unicodedata

#: Letras que o aluno pode produzir no lugar das corretas, sem que isso seja
#: erro de romeno. Aplicado silenciosamente na normalização.
#:
#: - ş/ţ: cedilha em vez de vírgula, herança de fontes pré-Vista.
#: - ŧ/Ŧ: t cortado (U+0167), letra do sami do norte. Não existe em romeno, mas
#:   sai de layouts de teclado tortos e é visualmente confundível com ț.
#:   Ao contrário da cedilha, não tem decomposição canônica — sem esta tabela o
#:   `fold` a deixaria passar e a resposta viraria "errado".
LEGACY_LETTER_FIX = str.maketrans(
    {
        "ş": "ș",
        "Ş": "Ș",
        "ţ": "ț",
        "Ţ": "Ț",
        "ŧ": "ț",
        "Ŧ": "Ț",
    }
)

#: Nomes dos diacríticos romenos, para a dica quando o aluno esquece um.
DIACRITIC_NAMES = {
    "ă": "ă (a com breve)",
    "â": "â (a com circunflexo, no meio da palavra)",
    "î": "î (i com circunflexo, no começo ou fim)",
    "ș": "ș (s com vírgula embaixo — som de 'ch')",
    "ț": "ț (t com vírgula embaixo — som de 'ts')",
}

#: Prefixos que podem ser omitidos sem que a resposta esteja errada.
#: Em romeno, o "a" do infinitivo (a fi) e os artigos indefinidos.
#: Em português, os artigos.
OPTIONAL_PREFIXES = {
    "ro": ("a ", "un ", "o ", "se ", "a se "),
    "pt": ("o ", "a ", "os ", "as ", "um ", "uma ", "ao ", "à "),
}

_PUNCT_EDGE = re.compile(r"^[\s\"'“”‘’.,!?;:…\-–—()\[\]]+|[\s\"'“”‘’.,!?;:…\-–—()\[\]]+$")
_WS = re.compile(r"\s+")


def fix_legacy_letters(text: str) -> str:
    """ş/ţ (cedilha) e ŧ (t cortado) -> ș/ț. A grafia correta do romeno usa vírgula."""
    return text.translate(LEGACY_LETTER_FIX)


#: Nome anterior, mantido porque descreve bem o caso mais comum.
fix_cedilla = fix_legacy_letters


def normalize(text: str) -> str:
    """Forma canônica para comparação exata: NFC, cedilha corrigida, minúsculas,
    espaços colapsados e pontuação das bordas removida.

    Preserva os diacríticos — quem os remove é `fold`.
    """
    text = unicodedata.normalize("NFC", text)
    text = fix_legacy_letters(text)
    text = text.casefold()
    text = _WS.sub(" ", text).strip()
    return _PUNCT_EDGE.sub("", text)


def fold(text: str) -> str:
    """Remove todos os diacríticos, preservando o comprimento.

    Funciona igual para romeno e português porque ă, â, î, ș e ț têm
    decomposição canônica (letra base + marca combinante), assim como á, ã, ç.
    """
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", stripped)


def strip_optional_prefix(text: str, lang: str) -> str:
    """Remove um artigo ou partícula inicial que o aluno pode legitimamente omitir."""
    for prefix in sorted(OPTIONAL_PREFIXES.get(lang, ()), key=len, reverse=True):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def compare_key(text: str, lang: str) -> str:
    """Chave de comparação tolerante: normalizada, sem prefixo opcional."""
    return strip_optional_prefix(normalize(text), lang)


def levenshtein(a: str, b: str, max_dist: int | None = None) -> int:
    """Distância de edição, com saída antecipada quando passa de `max_dist`.

    Devolve `max_dist + 1` quando estoura o limite — o valor exato não interessa
    depois que já se sabe que está longe demais.
    """
    if a == b:
        return 0
    if max_dist is not None and abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if max_dist is not None and min(cur) > max_dist:
            return max_dist + 1
        prev = cur
    return prev[-1]


def diacritic_diff(given: str, target: str) -> list[tuple[int, str, str]]:
    """Posições onde só o diacrítico difere.

    Só faz sentido quando `fold(given) == fold(target)`, o que garante mesmo
    comprimento e permite comparar caractere a caractere.
    """
    return [
        (i, g, t) for i, (g, t) in enumerate(zip(given, target, strict=False)) if g != t
    ]


def describe_diacritics(chars: list[str]) -> str:
    """Nomeia os diacríticos esquecidos, sem repetir."""
    seen: list[str] = []
    for c in chars:
        name = DIACRITIC_NAMES.get(c)
        if name and name not in seen:
            seen.append(name)
    return ", ".join(seen)
