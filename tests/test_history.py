"""Linha do tempo — e a regra que a mantém sendo conteúdo de idioma."""

from __future__ import annotations

import pytest

from dor.core.loader import load_library
from dor.core.models import ERA_LABEL_PT, ERAS, HistoryEvent
from dor.ui import cards


@pytest.fixture(scope="module")
def lib():
    return load_library()


def test_ha_linha_do_tempo(lib):
    assert len(lib.history) >= 15


def test_todo_evento_diz_o_que_fez_com_a_lingua(lib):
    """O critério de entrada da linha do tempo. Um evento que não muda a
    língua pertence a um livro de história, não a um app de idioma."""
    for event in lib.history.values():
        assert event.language_pt.strip(), event.id
        assert event.what_pt.strip(), event.id


def test_eras_sao_conhecidas(lib):
    for event in lib.history.values():
        assert event.era in ERAS, f"{event.id}: era '{event.era}'"


def test_toda_era_tem_rotulo_em_portugues():
    assert set(ERAS) == set(ERA_LABEL_PT)


def test_linha_do_tempo_sai_em_ordem_cronologica(lib):
    anos = [e.sort_key for e in lib.timeline]
    assert anos == sorted(anos)


def test_ano_negativo_vira_antes_de_cristo():
    event = HistoryEvent(id="hi.x", title="t", era="dacia", what_pt="a", language_pt="b", year=-500)
    assert event.when == "500 a.C."


def test_periodo_tem_prioridade_sobre_o_ano():
    """O ano existe para ordenar; o período é o que se lê."""
    event = HistoryEvent(
        id="hi.x", title="t", era="roma", what_pt="a", language_pt="b", year=1711, period="1711–1821"
    )
    assert event.when == "1711–1821"
    assert event.sort_key == 1711


def test_evento_sem_data_nao_quebra_a_ordenacao():
    event = HistoryEvent(id="hi.x", title="t", era="roma", what_pt="a", language_pt="b")
    assert event.when == ""
    assert event.sort_key == 0


def test_palavras_das_camadas_estao_bem_formadas(lib):
    for event in lib.history.values():
        for word in event.words:
            assert word["ro"].strip() and word["pt"].strip(), event.id


def test_as_camadas_do_vocabulario_estao_todas_representadas(lib):
    """Latim, substrato dácio, eslavo, turco/grego e francês: as cinco camadas
    que explicam por que uma palavra romena se parece ou não com o português."""
    ids = set(lib.history)
    assert {"hi.dacia", "hi.cucerirea_romana", "hi.slavii", "hi.fanariotii", "hi.relatinizarea"} <= ids


def test_referencias_a_gramatica_apontam_para_regras_reais(lib):
    for event in lib.history.values():
        for gid in event.grammar_refs:
            assert gid in lib.grammar, f"{event.id} → {gid}"


def test_a_liga_balcanica_explica_o_artigo_e_o_conjuntivo(lib):
    """As duas esquisitices estruturais do romeno têm a mesma causa, e o app
    precisa dizer isso em algum lugar — senão viram decoreba."""
    event = lib.history["hi.uniunea_balcanica"]
    assert "g.verb.conjunctiv" in event.grammar_refs


def test_ficha_poe_a_lingua_em_destaque(lib):
    from rich.console import Console

    from dor.ui.theme import DOR_THEME

    console = Console(width=100, record=True, theme=DOR_THEME)
    console.print(cards.event_card(lib.history["hi.fanariotii"]))
    texto = console.export_text()
    assert "na língua" in texto
    assert "cafea" in texto


def test_ficha_mostra_o_caminho_para_a_regra(lib):
    from rich.console import Console

    from dor.ui.theme import DOR_THEME

    console = Console(width=120, record=True, theme=DOR_THEME)
    rules = {r.id: r.title for r in lib.grammar.values()}
    console.print(cards.event_card(lib.history["hi.uniunea_balcanica"], rules=rules))
    texto = console.export_text()
    assert "dor drill g.verb.conjunctiv" in texto
