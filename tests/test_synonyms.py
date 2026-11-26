"""Equivalência em português — aceitar o que o aluno de fato digita.

O relato que originou este módulo: 'ce faci' está fichado como "como vai", o
aluno respondeu "como está" e levou um vermelho. Nenhum dos casos aqui é
hipotético; são maneiras normais de dizer a mesma coisa em português.

A segunda metade do arquivo é a guarda do lado oposto: afrouxar demais aceita
"oi" como resposta de uma pergunta, e aí a correção deixa de significar
qualquer coisa.
"""

from __future__ import annotations

import pytest

from dor.core.grading import Verdict, grade
from dor.core.loader import load_library
from dor.core.synonyms import EQUIVALENT_PT, equivalent, groups_of, pt_key


@pytest.fixture(scope="module")
def lib():
    return load_library()


def _grade(given: str, item):
    return grade(given, item.pt_answers, lang="pt")


# --------------------------------------------------------------------------- #
# o que tem de ser aceito
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "given",
    ["como vai", "como está", "como esta", "como você está", "tudo bem", "tudo bom", "beleza"],
)
def test_ce_faci_aceita_as_variantes_de_como_vai(lib, given):
    assert _grade(given, lib.vocab["ro.ce_faci"]).verdict is Verdict.CORRECT


def test_pronome_solto_nao_muda_a_resposta():
    assert pt_key("como está você") == pt_key("como está")
    assert equivalent("como vai você", "como vai")


def test_pronome_sozinho_continua_sendo_resposta():
    """A limpeza não pode zerar uma resposta que é só o pronome."""
    assert pt_key("você") == "voce"


@pytest.mark.parametrize(
    ("given", "item_id"),
    [
        ("valeu", "ro.multumesc"),
        ("obrigado", "ro.mersi"),
        ("por gentileza", "ro.te_rog"),
        ("desculpe", "ro.scuze"),
        ("adeus", "ro.pa"),
        ("ok", "ro.bine"),
        ("angu", "ro.mamaliga"),
        ("nostalgia", "ro.dor"),
    ],
)
def test_formulas_de_cortesia_aceitam_o_sinonimo(lib, given, item_id):
    assert _grade(given, lib.vocab[item_id]).verdict is Verdict.CORRECT


def test_equivalente_avisa_qual_e_a_forma_da_ficha(lib):
    """Aceitar sem mostrar a forma canônica esconde o que vai voltar depois."""
    result = _grade("como está", lib.vocab["ro.ce_faci"])
    assert result.loose
    assert "como vai" in result.hint


def test_acento_errado_em_portugues_nao_e_equivalencia_e_sim_igualdade(lib):
    """ "ate logo" é a mesma resposta mal acentuada — anunciar 'também vale'
    sugeriria uma diferença que não existe."""
    result = _grade("ate logo", lib.vocab["ro.la_revedere"])
    assert result.verdict is Verdict.CORRECT
    assert not result.loose


# --------------------------------------------------------------------------- #
# o que NÃO pode ser aceito
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("given", "item_id"),
    [
        ("oi", "ro.ce_faci"),  # cumprimento não responde a uma pergunta
        ("bem", "ro.ce_faci"),  # 'bine' é a resposta, não a pergunta
        ("como vai", "ro.buna"),  # o caminho inverso do mesmo erro
        ("bom dia", "ro.ce_faci"),
        ("tchau", "ro.buna"),
    ],
)
def test_equivalencia_nao_vira_vale_tudo(lib, given, item_id):
    assert _grade(given, lib.vocab[item_id]).verdict is not Verdict.CORRECT


def test_equivalencia_nao_e_transitiva():
    """ "e aí" serve para chegar e para perguntar como vai. Se estivesse em um
    dos grupos, viraria ponte entre os dois — por isso não está em nenhum."""
    assert groups_of("e aí") == frozenset()
    assert not equivalent("oi", "como vai")


def test_so_vale_para_o_portugues(lib):
    """Do lado romeno o aluno tem que produzir a palavra, não uma parecida."""
    item = lib.vocab["ro.buna_ziua"]
    assert grade("salut", [item.ro], lang="ro").verdict is Verdict.WRONG


# --------------------------------------------------------------------------- #
# invariante do acervo
# --------------------------------------------------------------------------- #


def test_traducao_fichada_pertence_a_no_maximo_um_grupo(lib):
    """A regra que impede a ponte indevida, verificada contra o acervo inteiro.

    Uma tradução que está na ficha de uma palavra E em dois grupos liga os dois
    grupos por dentro daquela palavra: 'ce faci' lista "e aí"; se "e aí" também
    morasse no grupo de chegada, "oi" viraria resposta certa para 'ce faci'.
    """
    culpados = []
    for item in lib.vocab.values():
        for answer in item.pt_answers:
            if len(groups_of(answer)) > 1:
                culpados.append(f"{item.id}: {answer!r}")
    assert not culpados, "traduções em mais de um grupo: " + ", ".join(culpados)


def test_grupos_nao_repetem_o_mesmo_dito_por_engano():
    """Duplicata dentro de um grupo é inofensiva; entre grupos é a ponte acima.

    Este teste não proíbe a segunda: só garante que ela seja rara o bastante
    para ser lida uma a uma quando alguém mexer na tabela.
    """
    compartilhados = {phrase for group in EQUIVALENT_PT for phrase in group if len(groups_of(phrase)) > 1}
    assert compartilhados <= {"beleza"}
