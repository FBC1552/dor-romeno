"""Cognate Bridge e export para Anki."""

from __future__ import annotations

import random

import pytest

from dor.core.loader import load_library
from dor.core.models import Bridge, VocabItem
from dor.modes import bridge as bridge_mode
from dor.storage import anki


@pytest.fixture(scope="module")
def lib():
    return load_library()


def ponte(**kwargs) -> Bridge:
    base = {
        "id": "br.teste",
        "title": "Teste",
        "kind": "sufix",
        "pt": "-ão",
        "ro": "-une",
        "rule_pt": "regra",
        "examples": [{"pt": "razão", "ro": "rațiune"}],
    }
    return Bridge(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# acervo
# --------------------------------------------------------------------------- #


def test_ha_pontes(lib):
    assert len(lib.bridges) >= 12


def test_ha_pontes_de_som_e_de_sufixo(lib):
    tipos = {b.kind for b in lib.bridges.values()}
    assert tipos == {"sunet", "sufix"}


def test_toda_ponte_tem_regra_e_pelo_menos_dois_exemplos(lib):
    for b in lib.bridges.values():
        assert b.rule_pt.strip(), b.id
        assert len(b.examples) >= 2, b.id


def test_exemplos_sao_pares_completos(lib):
    for b in lib.bridges.values():
        for example in b.examples:
            assert example["pt"].strip() and example["ro"].strip(), b.id


def test_as_pontes_de_sufixo_mais_rentaveis_estao_presentes(lib):
    """-ção e -dade sozinhas destravam milhares de palavras."""
    ids = set(lib.bridges)
    assert {"br.cao_tie", "br.dade_tate", "br.avel_abil"} <= ids


def test_a_ponte_que_nao_existe_esta_documentada(lib):
    """'-mente' é a regra mais importante da lista justamente por não existir:
    inventar um '-ment' romeno é o erro que denuncia falante de língua latina."""
    mente = lib.bridges["br.mente"]
    assert mente.traps
    assert any(t.get("right_ro") == "rapid" for t in mente.traps)


def test_pontes_produtivas_tem_confianca_declarada(lib):
    for b in lib.bridges.values():
        assert b.confidence in ("alto", "medio"), b.id


def test_armadilhas_apontam_a_forma_certa(lib):
    for b in lib.bridges.values():
        for trap in b.traps:
            assert trap["note"].strip(), b.id
            if trap.get("wrong_ro"):
                assert trap.get("right_ro"), f"{b.id}: mostra o erro sem mostrar o certo"
                assert trap["wrong_ro"] != trap["right_ro"], b.id


# --------------------------------------------------------------------------- #
# exercícios
# --------------------------------------------------------------------------- #


def test_o_exercicio_pede_a_aplicacao_da_regra():
    exercicio = bridge_mode.build_all(ponte())[0]
    assert exercicio.prompt == "razão"
    assert exercicio.answers == ["rațiune"]
    assert exercicio.answer_lang == "ro"


def test_o_enunciado_mostra_a_ponte():
    exercicio = bridge_mode.build_all(ponte())[0]
    assert "-ão" in exercicio.instruction and "-une" in exercicio.instruction


def test_o_latim_do_exemplo_vira_nota():
    b = ponte(examples=[{"pt": "noite", "ro": "noapte", "latin": "noctem"}])
    assert "noctem" in bridge_mode.build_all(b)[0].note


def test_armadilha_vira_exercicio_com_a_nota_sempre_visivel():
    """Errar aqui é o objetivo: é mais barato descobrir a exceção num
    exercício do que no meio de uma conversa."""
    b = ponte(traps=[{"pt": "cidade", "wrong_ro": "citate", "right_ro": "oraș", "note": "húngaro"}])
    trap = bridge_mode.build_all(b)[-1]
    assert trap.answers == ["oraș"]
    assert trap.always_note is True
    assert "cuidado" in trap.instruction


def test_armadilha_sem_forma_certa_nao_vira_exercicio():
    b = ponte(traps=[{"pt": "algo", "note": "só um aviso"}])
    assert len(bridge_mode.build_all(b)) == 1


def test_a_regra_vem_antes_da_excecao():
    b = ponte(traps=[{"pt": "cidade", "right_ro": "oraș", "note": "n"}])
    direcoes = [e.instruction for e in bridge_mode.build_all(b)]
    assert "cuidado" not in direcoes[0]
    assert "cuidado" in direcoes[-1]


def test_sessao_misturada_cruza_pontes(lib):
    """Uma ponte por vez ensina o padrão; misturar ensina a ESCOLHER o padrão."""
    exercicios = bridge_mode.build_mixed(list(lib.bridges.values()), limit=20, rng=random.Random(3))
    assert len(exercicios) == 20
    assert len({e.direction for e in exercicios}) > 3


def test_sessao_misturada_respeita_o_limite(lib):
    assert len(bridge_mode.build_mixed(list(lib.bridges.values()), limit=3)) == 3


def test_todo_exercicio_do_acervo_tem_resposta_util(lib):
    for b in lib.bridges.values():
        for exercicio in bridge_mode.build_all(b, rng=random.Random(1)):
            assert exercicio.answers[0].strip(), b.id


# --------------------------------------------------------------------------- #
# Anki
# --------------------------------------------------------------------------- #


def item(**kwargs) -> VocabItem:
    base = {"id": "ro.casa", "ro": "casă", "pt": ["casa"], "pos": "noun", "level": "A1"}
    return VocabItem(**{**base, **kwargs})


def test_nota_tem_seis_campos():
    assert len(anki.note_for(item())) == 6


def test_tabulacao_no_conteudo_nao_quebra_a_coluna():
    """TSV não tem escape: uma tabulação perdida desloca tudo e o Anki importa
    o arquivo corrompido em silêncio."""
    campos = anki.note_for(item(note_pt="linha um\tlinha dois\nlinha três"))
    assert all("\t" not in c and "\n" not in c for c in campos)


def test_ponte_e_falso_amigo_entram_na_nota():
    campos = anki.note_for(
        item(
            cognate_pt={"word": "casa", "confidence": "alto"},
            false_friend={"looks_like": "carta", "actually_means": "livro"},
        )
    )
    assert "≈ casa" in campos[3]
    assert "carta" in campos[3]


def test_tags_nao_tem_espaco():
    """Espaço separa tags no Anki: 'era comunista' viraria duas."""
    campos = anki.note_for(item(tags=["era comunista"], gender="f"))
    assert " " not in campos[5].split()[0]
    assert "era_comunista" in campos[5]
    assert campos[5].startswith("dor ")


def test_exporta_cabecalho_que_o_anki_entende(tmp_path):
    result = anki.export([item()], tmp_path / "x.tsv")
    linhas = result.path.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "#separator:tab"
    assert linhas[2].startswith("#columns:")
    assert result.notes == 1


def test_sem_audio_nao_cria_pasta_de_midia(tmp_path):
    result = anki.export([item()], tmp_path / "x.tsv")
    assert result.media_dir is None
    assert not (tmp_path / "x_media").exists()


def test_com_audio_copia_o_mp3_e_referencia_no_campo(tmp_path):
    origem = tmp_path / "som.mp3"
    origem.write_bytes(b"fake")
    result = anki.export([item()], tmp_path / "x.tsv", audio_for=lambda i: origem)
    assert result.media == 1
    assert (result.media_dir / "dor_ro_casa.mp3").exists()
    assert "[sound:dor_ro_casa.mp3]" in result.path.read_text(encoding="utf-8")


def test_audio_inexistente_e_ignorado_sem_quebrar(tmp_path):
    result = anki.export([item()], tmp_path / "x.tsv", audio_for=lambda i: tmp_path / "nada.mp3")
    assert result.media == 0
    assert result.notes == 1


def test_export_do_acervo_real_nao_tem_linha_torta(lib, tmp_path):
    itens = list(lib.vocab.values())
    result = anki.export(itens, tmp_path / "tudo.tsv")
    linhas = result.path.read_text(encoding="utf-8").strip().splitlines()
    corpo = [linha for linha in linhas if not linha.startswith("#")]
    assert len(corpo) == len(itens)
    assert all(linha.count("\t") == 5 for linha in corpo)
