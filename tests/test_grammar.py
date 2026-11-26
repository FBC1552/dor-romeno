"""Camada de gramática A2: filtros, quadro de formas e fichas de leitura."""

from __future__ import annotations

import random

import pytest

from dor.core.loader import filter_vocab, load_library
from dor.modes import grammar_drill
from dor.ui import cards


@pytest.fixture(scope="module")
def lib():
    return load_library()


# --------------------------------------------------------------------------- #
# filtro
# --------------------------------------------------------------------------- #


def test_filtro_por_conjugacao(lib):
    quarta = filter_vocab(lib, pos="verb", conjugation="IV")
    assert quarta
    assert all(v.conjugation == "IV" for v in quarta)


def test_filtro_aceita_lista_de_valores(lib):
    """O neutro obriga: a regra do artigo masculino vale igual para ele, e sem
    lista teria de ser escrita duas vezes."""
    masc_neutro = filter_vocab(lib, pos="noun", gender=["m", "n"])
    assert {i.gender for i in masc_neutro} == {"m", "n"}
    assert len(masc_neutro) == len(filter_vocab(lib, pos="noun", gender="m")) + len(
        filter_vocab(lib, pos="noun", gender="n")
    )


def test_filtro_com_lista_vazia_nao_filtra_nada(lib):
    assert len(filter_vocab(lib, gender=[])) == len(lib.vocab)


def test_regra_do_artigo_masculino_nao_pega_feminino(lib):
    """A regra dizia 'masculino e neutro' e sorteava 'casă → casa'."""
    rule = lib.grammar["g.articol.hotarat.masc.sg"]
    for item in grammar_drill.matching_items(rule, lib):
        assert item.gender in ("m", "n"), item.id


# --------------------------------------------------------------------------- #
# quadro de formas
# --------------------------------------------------------------------------- #


def test_conjuntivo_comeca_com_sa(lib):
    for item in filter_vocab(lib, pos="verb", has_form="forms.conjunctiv"):
        assert item.forms["conjunctiv"].startswith("să "), item.id


def test_futuro_falado_usa_o_sa(lib):
    """'O să' não conjuga — quem escreve 'oi să' ou 'o sa' quebra a regra toda."""
    for item in filter_vocab(lib, pos="verb", has_form="forms.viitor_popular"):
        assert item.forms["viitor_popular"].startswith("o să "), item.id


def test_imperfeito_tem_seis_pessoas(lib):
    for item in filter_vocab(lib, pos="verb", has_form="forms.imperfect"):
        formas = item.forms["imperfect"]
        assert isinstance(formas, list) and len(formas) == 6, item.id


def test_imperfeito_confunde_eu_com_noi(lib):
    """Traço real do romeno, e a armadilha que a regra promete: 1ª do singular
    e 1ª do plural são idênticas."""
    verbo = lib.vocab["ro.a_manca"]
    assert verbo.forms["imperfect"][0] == verbo.forms["imperfect"][3]


def test_gerundio_termina_em_and_ou_ind(lib):
    for item in filter_vocab(lib, pos="verb", has_form="forms.gerunziu"):
        assert item.forms["gerunziu"].endswith(("ând", "ind", "ându-se", "indu-se")), item.id


def test_adjetivos_tem_as_tres_formas(lib):
    adjetivos = filter_vocab(lib, pos="adj")
    assert len(adjetivos) >= 10
    for item in adjetivos:
        for chave in ("f_sg", "m_pl", "f_pl"):
            assert item.forms.get(chave), f"{item.id} sem {chave}"


def test_adjetivo_invariavel_repete_a_forma(lib):
    """'Mare' serve aos dois gêneros — o quadro precisa dizer isso, não omitir."""
    mare = lib.vocab["ro.mare"]
    assert mare.forms["f_sg"] == mare.ro
    assert mare.forms["m_pl"] == mare.forms["f_pl"] == "mari"


def test_conjugacao_iv_tem_verbo_com_e_sem_esc(lib):
    """A regra afirma que o -esc é traço do verbo. Sem os dois casos no acervo,
    a afirmação não se sustenta no treino."""
    quarta = filter_vocab(lib, pos="verb", conjugation="IV", has_form="forms.prezent")
    com_esc = [v for v in quarta if v.forms["prezent"][0].endswith("esc")]
    sem_esc = [v for v in quarta if not v.forms["prezent"][0].endswith("esc")]
    assert com_esc and sem_esc


# --------------------------------------------------------------------------- #
# regras
# --------------------------------------------------------------------------- #


def test_ha_gramatica_de_a2(lib):
    a2 = [r for r in lib.grammar.values() if r.level == "A2"]
    assert len(a2) >= 15


def test_toda_regra_tem_contraste_com_o_portugues(lib):
    """O contraste é o que fixa: o brasileiro aprende o caso romeno percebendo
    o que o português faz no lugar dele."""
    for rule in lib.grammar.values():
        assert rule.contrast_pt, f"{rule.id} não diz como o português faz"


def test_toda_regra_tem_exemplos(lib):
    for rule in lib.grammar.values():
        assert rule.examples, f"{rule.id} não tem exemplo"
        for example in rule.examples:
            assert example["ro"].strip() and example["pt"].strip()


def test_regras_sem_drill_sao_de_teoria_e_nao_estao_quebradas(lib):
    """Uma regra sem drill é uma escolha (pronome não se gera do vocabulário),
    e por isso precisa compensar com tabela ou armadilha."""
    for rule in lib.grammar.values():
        if rule.drill:
            continue
        assert rule.table or rule.pitfall_pt, f"{rule.id}: teoria sem tabela nem armadilha"


def test_toda_regra_com_drill_gera_exercicio_resolvivel(lib):
    rng = random.Random(1)
    for rule in lib.grammar.values():
        pool = grammar_drill.matching_items(rule, lib)
        if not pool:
            continue
        exercise = grammar_drill.build(rule, lib, item=pool[0], rng=rng)
        assert exercise is not None, rule.id
        assert exercise.answers and exercise.answers[0].strip(), rule.id
        assert exercise.instruction.strip(), rule.id


def test_o_acervo_gera_centenas_de_exercicios(lib):
    total = sum(len(grammar_drill.matching_items(r, lib)) for r in lib.grammar.values())
    assert total >= 200, f"só {total} exercícios gerados"


def test_ids_de_regra_nao_colidem_entre_arquivos(lib):
    assert len(lib.grammar) == len({r.id for r in lib.grammar.values()})


# --------------------------------------------------------------------------- #
# ficha
# --------------------------------------------------------------------------- #


def render(renderable) -> str:
    from rich.console import Console

    console = Console(width=100, record=True)
    console.print(renderable)
    return console.export_text()


def test_ficha_mostra_explicacao_contraste_e_armadilha(lib):
    rule = lib.grammar["g.verb.conjunctiv"]
    texto = render(cards.rule_card(rule, exercises=14))
    assert "a armadilha" in texto
    assert "em português" in texto
    assert "dor drill g.verb.conjunctiv" in texto


def test_ficha_de_teoria_avisa_que_nao_ha_treino(lib):
    texto = render(cards.rule_card(lib.grammar["g.pron.dativ"], exercises=0))
    assert "teoria" in texto
    assert "dor drill" not in texto


def test_ficha_renderiza_a_tabela(lib):
    texto = render(cards.rule_card(lib.grammar["g.pron.acuzativ"]))
    assert "îl" in texto and "văd" in texto


def test_ficha_de_regra_sem_tabela_nao_quebra(lib):
    texto = render(cards.rule_card(lib.grammar["g.verb.imperfect"]))
    assert "Imperfeito" in texto
