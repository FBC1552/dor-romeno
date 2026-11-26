"""Cenas do dia a dia: o diálogo, a rua e a etiqueta."""

from __future__ import annotations

import random

import pytest

from dor.core.loader import load_library
from dor.core.models import PLACE_LABEL_PT, Scene
from dor.modes import scene as scene_mode
from dor.ui import cards


@pytest.fixture(scope="module")
def lib():
    return load_library()


def cena(**kwargs) -> Scene:
    base = {
        "id": "si.teste",
        "title": "Teste",
        "place": "cafenea",
        "level": "A1",
        "goal_pt": "fazer algo",
        "turns": [
            {"who": "ei", "ro": "Bună!", "pt": "Oi!"},
            {"who": "tu", "ro": "Salut!", "pt": "Oi!"},
        ],
    }
    return Scene(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# acervo
# --------------------------------------------------------------------------- #


def test_ha_cenas(lib):
    assert len(lib.scenes) >= 6


def test_toda_cena_diz_o_que_voce_sai_sabendo(lib):
    for item in lib.scenes.values():
        assert item.goal_pt.strip(), item.id


def test_toda_cena_tem_dialogo_com_os_dois_lados(lib):
    """Diálogo em que só um fala é texto, não conversa."""
    for item in lib.scenes.values():
        lados = {t["who"] for t in item.turns}
        assert lados == {"tu", "ei"}, item.id


def test_toda_cena_tem_formulas_para_treinar(lib):
    for item in lib.scenes.values():
        assert item.phrases, item.id


def test_toda_cena_traz_etiqueta(lib):
    """A etiqueta é metade do ponto: quem acerta a gramática e chega com
    buquê par errou a única coisa que vai ser lembrada."""
    for item in lib.scenes.values():
        assert item.etiquette_pt, item.id


def test_maioria_das_cenas_contrasta_livro_e_rua(lib):
    com_rua = [s for s in lib.scenes.values() if s.street]
    assert len(com_rua) >= len(lib.scenes) * 0.7


def test_lugares_sao_conhecidos(lib):
    for item in lib.scenes.values():
        assert item.place in PLACE_LABEL_PT, item.id


def test_registros_sao_validos(lib):
    from dor import config

    for item in lib.scenes.values():
        assert item.register in config.REGISTERS, item.id


def test_ha_cena_de_socorro_no_nivel_mais_baixo(lib):
    """'Não entendi' e 'mais devagar' precisam estar acessíveis desde o A1 —
    são as frases que impedem a conversa de morrer."""
    a1 = [s for s in lib.scenes.values() if s.level == "A1"]
    frases = {p["ro"] for s in a1 for p in s.phrases}
    assert "Nu înțeleg." in frases
    assert "Mai rar, vă rog." in frases


def test_referencias_de_vocabulario_apontam_para_itens_reais(lib):
    for item in lib.scenes.values():
        for vid in item.vocab_refs:
            assert vid in lib.vocab, f"{item.id} → {vid}"


# --------------------------------------------------------------------------- #
# exercícios
# --------------------------------------------------------------------------- #


def test_o_treino_e_sempre_de_producao(lib):
    """Reconhecer 'Cât costă?' não ajuda no balcão: quem produz é você."""
    for item in lib.scenes.values():
        for exercise in scene_mode.build_all(item, rng=random.Random(1)):
            assert exercise.direction == "pt_ro"
            assert exercise.answer_lang == "ro"


def test_formulas_vem_antes_das_falas_do_dialogo():
    """A fórmula é a peça isolada; a fala é ela dentro da conversa."""
    item = cena(phrases=[{"ro": "Mersi!", "pt": "Obrigado!"}])
    exercicios = scene_mode.build_all(item, rng=random.Random(1))
    assert exercicios[0].answers == ["Mersi!"]
    assert exercicios[-1].answers == ["Salut!"]


def test_fala_repetida_na_lista_de_formulas_nao_vira_exercicio_duplo():
    item = cena(phrases=[{"ro": "Salut!", "pt": "Oi!"}])
    exercicios = scene_mode.build_all(item, rng=random.Random(1))
    assert len(exercicios) == 1


def test_so_as_minhas_falas_viram_exercicio():
    """Você não precisa saber produzir a fala do garçom."""
    item = cena()
    respostas = {e.answers[0] for e in scene_mode.build_all(item, rng=random.Random(1))}
    assert "Salut!" in respostas
    assert "Bună!" not in respostas


def test_quando_usar_vira_a_dica_do_exercicio():
    item = cena(phrases=[{"ro": "Cât costă?", "pt": "Quanto custa?", "when_pt": "no balcão"}])
    exercicio = scene_mode.build_all(item, rng=random.Random(1))[0]
    assert exercicio.note == "no balcão"


def test_a_frase_romena_e_falada_depois_da_resposta():
    item = cena(phrases=[{"ro": "Cât costă?", "pt": "Quanto custa?"}])
    exercicio = scene_mode.build_all(item, rng=random.Random(1))[0]
    assert exercicio.speak_after == "Cât costă?"
    assert exercicio.speak_before is None, "ouvir antes entregaria a resposta"


def test_pode_treinar_so_as_formulas():
    item = cena(phrases=[{"ro": "Mersi!", "pt": "Obrigado!"}])
    assert len(scene_mode.build_all(item, with_turns=False)) == 1


# --------------------------------------------------------------------------- #
# ficha
# --------------------------------------------------------------------------- #


def test_ficha_mostra_dialogo_rua_e_etiqueta(lib):
    from rich.console import Console

    from dor.ui.theme import DOR_THEME

    console = Console(width=100, record=True, theme=DOR_THEME)
    console.print(cards.scene_card(lib.scenes["si.acasa"]))
    texto = console.export_text()
    assert "etiqueta" in texto
    assert "ÍMPAR" in texto
    assert "vale decorar" in texto


def test_ficha_marca_quem_fala(lib):
    from rich.console import Console

    from dor.ui.theme import DOR_THEME

    console = Console(width=100, record=True, theme=DOR_THEME)
    console.print(cards.scene_card(lib.scenes["si.cafenea"]))
    texto = console.export_text()
    assert "você" in texto and "ele" in texto
