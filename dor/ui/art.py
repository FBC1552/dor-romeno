"""Ilustração de contexto — o referente antes da tradução.

Uma palavra que aparece sozinha na tela não tem contexto nenhum: o aluno lê
'pâine', lê 'pão' e memoriza um par de strings. O símbolo troca isso por uma
imagem, que é o que a memória de fato guarda.

A primeira versão disto era desenho ASCII. Não funcionou: em quatro linhas de
barra e underline, 'pão' e 'batata' viram o mesmo borrão, e um desenho que
precisa de legenda não está fazendo o trabalho de desenho. O pictograma é
legível na hora e ainda alcança verbo e adjetivo, que rabisco de linha não
alcançava — 'a se descurca' não tem desenho possível, mas tem 🤹.

Como o símbolo aparece sempre ao lado da palavra e da tradução, ele não precisa
ser inequívoco sozinho. 🍽️ para `masă` é mesa posta, não prato; ao lado da
palavra "mesa" ninguém se confunde.

A cobertura ainda é parcial de propósito: quando não há símbolo honesto, a tag
resolve (saudação, comida, cortesia) e o resto fica sem — inventar um ícone
vago para 'a trebui' seria ruído, não contexto.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from rich.cells import cell_len
from rich.text import Text

from dor import config

ART_PATH = config.ART_DIR / "ilustracoes.json"

#: Largura reservada para a coluna do símbolo. Emoji ocupa duas células na
#: maioria dos terminais, mas nem todos concordam — a coluna fixa mantém o
#: texto alinhado mesmo quando a conta de largura erra por uma célula.
ART_WIDTH = 3


@cache
def _art_data() -> tuple[dict[str, str], dict[str, str]]:
    """Carrega o acervo uma vez por processo. Sem arquivo, o app segue sem arte."""
    path = Path(ART_PATH)
    if not path.exists():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("items", {}), data.get("tags", {})


def symbol_for(item) -> str:
    """O símbolo da palavra: o próprio primeiro, o da tag como rede de segurança."""
    items, tags = _art_data()
    own = items.get(item.id)
    if own:
        return own
    for tag in getattr(item, "tags", ()):
        fallback = tags.get(tag)
        if fallback:
            return fallback
    return ""


def has_art(item) -> bool:
    return bool(symbol_for(item))


def render(item) -> Text:
    """O símbolo sozinho, com a margem que o resto da sessão usa."""
    return Text(f"  {symbol_for(item)}")


def beside(item, block: Text, *, gap: int = 2) -> Text:
    """Símbolo na primeira linha, texto à direita, resto do texto alinhado.

    Sem arte devolve o bloco intacto — quem chama não precisa checar antes.
    """
    symbol = symbol_for(item)
    if not symbol:
        return block

    width = ART_WIDTH + gap
    out = Text(symbol)
    out.append(" " * max(1, width - cell_len(symbol)))
    for i, line in enumerate(block.split("\n")):
        if i:
            out.append("\n" + " " * width)
        out.append_text(line)
    return out
