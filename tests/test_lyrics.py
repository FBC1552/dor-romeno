"""Lyrics Lab — e a trava de direito autoral que ele carrega."""

from __future__ import annotations

import random

import pytest

from dor.core.loader import load_library
from dor.core.models import Track
from dor.modes import lyrics


@pytest.fixture(scope="module")
def lib():
    return load_library()


@pytest.fixture(scope="module")
def tracks(lib):
    return {t.id: t for t in lib.tracks}


def faixa(**kwargs) -> Track:
    base = {"id": "tr.teste", "title": "Teste", "why_pt": "por quê", "artist_name": "Alguém"}
    return Track(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# direito autoral
# --------------------------------------------------------------------------- #


def test_trecho_protegido_nao_vira_exercicio():
    """A trava mora no código, não só na curadoria: um JSON com letra alheia e
    sem a marca de domínio público não gera exercício nenhum."""
    protegida = faixa(
        excerpt={"lines": [{"ro": "un vers", "pt": "um verso", "cloze": "vers"}]},
    )
    assert lyrics.usable_excerpt(protegida) == []
    assert lyrics.build_all(protegida) == []


def test_public_domain_precisa_ser_exatamente_true():
    """'true' em texto, 1, ou qualquer coisa 'quase verdadeira' não passa."""
    for valor in ("true", 1, "sim", None):
        t = faixa(excerpt={"public_domain": valor, "lines": [{"ro": "a", "pt": "b", "cloze": "a"}]})
        assert lyrics.usable_excerpt(t) == [], valor


def test_trecho_de_dominio_publico_vira_exercicio():
    linha = {"ro": "un vers", "pt": "um verso", "cloze": "vers"}
    t = faixa(excerpt={"public_domain": True, "lines": [linha]})
    assert len(lyrics.usable_excerpt(t)) == 1


def test_faixa_protegida_ainda_estuda_pelo_glossario():
    """Ficar sem trecho não é ficar sem aula — o glossário é livre."""
    t = faixa(
        excerpt={"lines": [{"ro": "un vers", "pt": "um verso", "cloze": "vers"}]},
        glossary=[{"ro": "cartier", "pt": "bairro"}],
    )
    exercicios = lyrics.build_all(t)
    assert len(exercicios) == 1
    assert exercicios[0].direction in ("ro_pt", "pt_ro")


def test_acervo_real_nao_tem_trecho_protegido_marcado_como_livre(lib):
    for track in lib.tracks:
        if not track.excerpt:
            continue
        if track.excerpt.get("public_domain") is True:
            assert len(track.excerpt["lines"]) <= 4, track.id


# --------------------------------------------------------------------------- #
# construção
# --------------------------------------------------------------------------- #


def test_verso_perde_exatamente_a_palavra_alvo(tracks):
    exercicio = lyrics.build_line(
        tracks["tr.miorita"], {"ro": "Pe-un picior de plai,", "pt": "...", "cloze": "plai"}
    )
    assert exercicio is not None
    assert "____" in exercicio.prompt
    assert "plai" not in exercicio.prompt
    assert exercicio.answers == ["plai"]


def test_verso_com_alvo_ausente_nao_vira_exercicio():
    assert lyrics.build_line(faixa(), {"ro": "abc", "pt": "x", "cloze": "zzz"}) is None


def test_a_traducao_do_verso_fica_no_enunciado(tracks):
    """Sem ela a lacuna vira adivinhação: nada indica qual palavra falta."""
    exercicio = lyrics.build_line(
        tracks["tr.miorita"], {"ro": "Pe-o gură de rai,", "pt": "numa boca de paraíso", "cloze": "rai"}
    )
    assert "numa boca de paraíso" in exercicio.instruction


def test_versos_vem_antes_do_glossario(tracks):
    """O verso dá o contexto; o glossário cobra a palavra sozinha depois."""
    exercicios = lyrics.build_all(tracks["tr.miorita"], rng=random.Random(1))
    direcoes = [e.direction for e in exercicios]
    assert direcoes.index("verso") < min(
        i for i, d in enumerate(direcoes) if d in ("ro_pt", "pt_ro")
    )


def test_glossario_gera_as_duas_direcoes(tracks):
    entrada = {"ro": "dor", "pt": "saudade"}
    ro_pt = lyrics.build_glossary(tracks["tr.doina"], entrada, direction="ro_pt")
    pt_ro = lyrics.build_glossary(tracks["tr.doina"], entrada, direction="pt_ro")
    assert ro_pt.prompt == "dor" and ro_pt.answer_lang == "pt"
    assert pt_ro.prompt == "saudade" and pt_ro.answer_lang == "ro"


def test_comentario_do_glossario_nao_vira_resposta():
    """Ninguém deve ter de digitar 'a palavra que dá nome a este app'."""
    assert lyrics.accepted_pt("saudade — a palavra que dá nome a este app") == ["saudade"]


def test_parenteses_saem_da_resposta():
    assert lyrics.accepted_pt("vamos... (convite, com conjuntivo)") == ["vamos"]


def test_barra_e_virgula_viram_respostas_alternativas():
    assert lyrics.accepted_pt("estrela / a estrela") == ["estrela", "a estrela"]
    assert lyrics.accepted_pt("terra, chão") == ["terra", "chão"]


def test_traducao_sem_nucleo_sobrevive():
    """Se a limpeza comer tudo, é melhor devolver o texto original que nada."""
    assert lyrics.accepted_pt("(só um comentário)") == ["(só um comentário)"]


def test_id_do_glossario_e_estavel(tracks):
    entrada = {"ro": "dor", "pt": "saudade"}
    a = lyrics.glossary_id(tracks["tr.doina"], entrada)
    b = lyrics.glossary_id(tracks["tr.doina"], entrada)
    assert a == b == "tr.doina#dor"


def test_id_do_glossario_prefere_a_giria_do_acervo(tracks):
    """Quando a palavra já existe em data/culture/slang, o SRS deve agendar o
    mesmo item — senão o progresso se divide em dois."""
    entrada = {"ro": "mișto", "pt": "legal", "slang_id": "sl.misto"}
    assert lyrics.glossary_id(tracks["tr.doina"], entrada) == "sl.misto"


# --------------------------------------------------------------------------- #
# acervo
# --------------------------------------------------------------------------- #


def test_ha_folclore_de_dominio_publico(lib):
    livres = [t for t in lib.tracks if lyrics.usable_excerpt(t)]
    assert len(livres) >= 5


def test_toda_faixa_com_trecho_livre_gera_exercicio(lib):
    for track in lib.tracks:
        for line in lyrics.usable_excerpt(track):
            assert lyrics.build_line(track, line) is not None, f"{track.id}: {line['cloze']}"


def test_toda_faixa_diz_por_que_existe(lib):
    for track in lib.tracks:
        assert track.why_pt.strip(), track.id


def test_glossario_traz_registro_ou_neutro_implicito(lib):
    from dor import config

    for track in lib.tracks:
        for entry in track.glossary:
            assert entry.get("register", "neutru") in config.REGISTERS, track.id


def test_a_mioria_esta_no_acervo(tracks):
    """A balada fundadora — se ela sumir, o acervo folclórico perdeu o centro."""
    assert "tr.miorita" in tracks
    assert lyrics.usable_excerpt(tracks["tr.miorita"])
