"""A ilustração de contexto e a ficha de estreia.

A queixa que originou as duas: a palavra aparecia sozinha na tela, sem nada em
volta, e só depois de errar é que o aluno descobria o que ela queria dizer.

O que estes testes protegem é sobretudo a integridade do acervo — uma chave com
erro de digitação não quebra nada, só faz o símbolo sumir em silêncio, que é o
pior tipo de defeito para um conteúdo opcional.
"""

from __future__ import annotations

import pytest
from rich.cells import cell_len
from rich.text import Text

from dor.core.loader import load_library
from dor.ui import art


@pytest.fixture(scope="module")
def lib():
    return load_library()


def test_todo_simbolo_aponta_para_uma_palavra_existente(lib):
    items, _ = art._art_data()
    orfaos = [key for key in items if key not in lib.vocab]
    assert not orfaos, f"símbolos sem palavra correspondente: {orfaos}"


def test_toda_tag_com_simbolo_e_usada_por_alguma_palavra(lib):
    _, tags = art._art_data()
    usadas = {tag for item in lib.vocab.values() for tag in item.tags}
    assert not set(tags) - usadas


def test_simbolo_cabe_na_coluna_reservada():
    """Símbolo largo desalinha a coluna de texto em toda a sessão."""
    items, tags = art._art_data()
    for key, symbol in [*items.items(), *tags.items()]:
        assert symbol, f"{key} tem símbolo vazio"
        assert cell_len(symbol) <= art.ART_WIDTH, f"{key}: {symbol!r}"
        assert "\n" not in symbol, key


def test_cobertura_alcanca_a_maioria_do_acervo(lib):
    """Um pictograma por palavra concreta não basta: verbo e adjetivo eram
    justamente o que o desenho ASCII não alcançava."""
    com_arte = [i for i in lib.vocab.values() if art.has_art(i)]
    assert len(com_arte) > len(lib.vocab) * 0.9


def test_palavra_sem_simbolo_proprio_cai_na_tag(lib):
    """'poftim' não tem ícone honesto — herda o da cortesia."""
    _, tags = art._art_data()
    items, _ = art._art_data()
    herdeiros = [
        i
        for i in lib.vocab.values()
        if i.id not in items and art.has_art(i)
    ]
    assert herdeiros, "se ninguém herda da tag, a rede de segurança morreu"
    assert art.symbol_for(herdeiros[0]) in tags.values()


def test_palavra_sem_simbolo_nenhum_nao_quebra(lib):
    """Cobertura parcial é o projeto, não uma falha: quem chama não checa."""

    class Orfa:
        id = "ro.inexistente"
        tags = ()

    bloco = Text("qualquer coisa")
    assert art.beside(Orfa(), bloco) is bloco
    assert not art.has_art(Orfa())


def test_beside_alinha_o_texto_numa_coluna_so(lib):
    casa = lib.vocab["ro.casa"]
    saida = art.beside(casa, Text("casă\ncasa")).plain.split("\n")
    assert saida[0].startswith(art.symbol_for(casa))
    assert saida[0].endswith("casă")
    # a segunda linha começa na mesma coluna visual que a primeira
    assert cell_len(saida[0].removesuffix("casă")) == cell_len(saida[1].removesuffix("casa"))


def test_ficha_de_estreia_traz_traducao_simbolo_e_exemplo(lib):
    from rich.console import Console

    from dor.ui import cards

    item = lib.vocab["ro.paine"]
    example = lib.sentences[item.examples[0]] if item.examples else None

    saida = Console(width=90, record=True)
    saida.print(cards.intro_card(item, example=example))
    texto = saida.export_text()

    assert "pâine" in texto
    assert "pão" in texto
    assert art.symbol_for(item) in texto


# --------------------------------------------------------------------------- #
# o preço da dica
# --------------------------------------------------------------------------- #


def test_dica_derruba_o_acerto_para_meio_credito(lib):
    """O símbolo de uma palavra concreta É a resposta — 🥔 para 'cartof'."""
    from dor.core.grading import CREDIT_ALMOST, Verdict, after_hint, grade

    result = after_hint(grade("batata", lib.vocab["ro.cartof"].pt_answers, lang="pt"))
    assert result.verdict is Verdict.CORRECT, "dizer 'errado' a quem acertou seria mentira"
    assert result.credit == CREDIT_ALMOST
    assert result.hinted


def test_dica_nao_piora_quem_ja_tinha_errado(lib):
    from dor.core.grading import Verdict, after_hint, grade

    errado = grade("praça", lib.vocab["ro.cartof"].pt_answers, lang="pt")
    assert after_hint(errado) == errado
    assert errado.verdict is Verdict.WRONG


def test_acerto_com_dica_volta_mais_cedo(lib):
    """Agendar como recall limpo faria a palavra sumir sem nunca ter sido lembrada."""
    from dor.core.grading import after_hint, grade
    from dor.core.srs import Rating, rating_from_grade

    limpo = grade("batata", lib.vocab["ro.cartof"].pt_answers, lang="pt")
    assert rating_from_grade(limpo, latency_ms=9999) is Rating.GOOD
    assert rating_from_grade(after_hint(limpo), latency_ms=9999) is Rating.HARD
