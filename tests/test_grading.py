"""O motor de correção é o que decide se o app é agradável ou irritante.

Cada caso aqui é um jeito real de o aluno acertar a palavra e o app achar que
errou. Se algum destes quebrar, alguém desinstala no terceiro dia.
"""

from __future__ import annotations

import pytest

from dor.core.grading import Verdict, grade
from dor.core.normalize import fix_cedilla, fold, levenshtein, normalize

# --------------------------------------------------------------------------- #
# normalização
# --------------------------------------------------------------------------- #


def test_cedilha_legada_vira_virgula():
    """ş/ţ (cedilha) é a grafia errada mas onipresente. Nunca é erro do aluno."""
    assert fix_cedilla("piaţă") == "piață"
    assert fix_cedilla("uşă") == "ușă"
    assert fix_cedilla("ŞTIU") == "ȘTIU"


def test_fold_remove_todos_os_diacriticos_romenos():
    assert fold("piață") == "piata"
    assert fold("ușă") == "usa"
    assert fold("pâine") == "paine"
    assert fold("înțeleg") == "inteleg"
    assert fold("Bună ziua") == "Buna ziua"


def test_fold_preserva_o_comprimento():
    """A dica de diacrítico compara caractere a caractere e depende disso."""
    for word in ("piață", "ușă", "pâine", "înțeleg", "mămăligă"):
        assert len(fold(word)) == len(word)


def test_fold_funciona_para_portugues_tambem():
    assert fold("não") == "nao"
    assert fold("você") == "voce"
    assert fold("coração") == "coracao"


def test_normalize_ignora_caixa_pontuacao_e_espacos():
    assert normalize("  Bună  ziua!  ") == "bună ziua"
    assert normalize("Poftim?") == "poftim"


def test_levenshtein_com_limite_sai_cedo():
    assert levenshtein("casa", "casa") == 0
    assert levenshtein("casa", "masa") == 1
    assert levenshtein("casa", "elefante", max_dist=2) == 3


# --------------------------------------------------------------------------- #
# certo
# --------------------------------------------------------------------------- #


def test_resposta_exata():
    assert grade("piață", ["piață"]).verdict is Verdict.CORRECT


def test_cedilha_legada_conta_como_certo():
    """O caso que mais geraria falso negativo — metade da web romena escreve assim."""
    g = grade("piaţă", ["piață"])
    assert g.verdict is Verdict.CORRECT
    assert g.credit == 1.0


def test_maiuscula_e_espaco_extra_contam_como_certo():
    assert grade("  BUNĂ ZIUA  ", ["bună ziua"]).verdict is Verdict.CORRECT


def test_pontuacao_final_nao_atrapalha():
    assert grade("poftim?", ["poftim"]).verdict is Verdict.CORRECT


def test_infinitivo_sem_a_conta_como_certo():
    """'a fi' e 'fi' são a mesma resposta — o 'a' é partícula, não palavra."""
    assert grade("fi", ["a fi"], lang="ro").verdict is Verdict.CORRECT
    assert grade("a fi", ["a fi"], lang="ro").verdict is Verdict.CORRECT


def test_artigo_em_portugues_e_opcional():
    assert grade("o livro", ["livro"], lang="pt").verdict is Verdict.CORRECT
    assert grade("livro", ["o livro"], lang="pt").verdict is Verdict.CORRECT


def test_sinonimo_aceito_conta_como_certo():
    g = grade("estar", ["ser", "estar"], lang="pt")
    assert g.verdict is Verdict.CORRECT
    assert g.target == "estar"


def test_acento_faltando_em_portugues_nao_e_erro():
    """Não estamos ensinando ortografia do português."""
    assert grade("nao", ["não"], lang="pt").verdict is Verdict.CORRECT
    assert grade("voce", ["você"], lang="pt").verdict is Verdict.CORRECT
    assert grade("coracao", ["coração"], lang="pt").verdict is Verdict.CORRECT


# --------------------------------------------------------------------------- #
# quase
# --------------------------------------------------------------------------- #


def test_diacritico_faltando_em_romeno_e_quase():
    g = grade("piata", ["piață"], lang="ro")
    assert g.verdict is Verdict.ALMOST
    assert g.diacritics_only
    assert g.credit == 0.5


def test_dica_nomeia_o_diacritico_esquecido():
    g = grade("piata", ["piață"], lang="ro")
    assert "ț" in g.hint
    assert "vírgula" in g.hint


def test_dica_nomeia_multiplos_diacriticos():
    g = grade("inteleg", ["înțeleg"], lang="ro")
    assert g.verdict is Verdict.ALMOST
    assert "î" in g.hint and "ț" in g.hint


def test_deslize_de_digitacao_em_palavra_longa_e_quase():
    g = grade("inteleger", ["înțelegere"], lang="ro")
    assert g.verdict is Verdict.ALMOST


def test_palavra_curta_nao_ganha_tolerancia_a_typo():
    """'casă' e 'masă' distam 1 caractere e são palavras diferentes."""
    assert grade("masa", ["casă"], lang="ro").verdict is Verdict.WRONG


# --------------------------------------------------------------------------- #
# errado
# --------------------------------------------------------------------------- #


def test_palavra_diferente_e_errado():
    g = grade("televizor", ["pâine"], lang="ro")
    assert g.verdict is Verdict.WRONG
    assert g.credit == 0.0


def test_resposta_vazia_e_errado():
    for empty in ("", "   ", "..."):
        assert grade(empty, ["casă"]).verdict is Verdict.WRONG


def test_par_minimo_por_padrao_vira_quase():
    """fată (menina) e față (rosto) diferem por um ț — e são palavras distintas.

    Fora de um exercício de par mínimo não dá para saber se o aluno quis dizer
    a outra palavra ou só comeu o acento, então o veredito generoso vale: ele
    recebe crédito parcial e a correção explícita.
    """
    g = grade("fata", ["față"], lang="ro")
    assert g.verdict is Verdict.ALMOST
    assert g.diacritics_only


def test_modo_estrito_recusa_a_troca_de_diacritico():
    """Dentro de um par mínimo, o contexto diz que a escolha foi deliberada."""
    g = grade("fata", ["față"], lang="ro", strict_diacritics=True)
    assert g.verdict is Verdict.WRONG
    assert g.credit == 0.0
    assert "palavras diferentes" in g.hint


def test_modo_estrito_nao_afeta_a_resposta_certa():
    assert grade("față", ["față"], lang="ro", strict_diacritics=True).verdict is Verdict.CORRECT


def test_modo_estrito_nao_afeta_a_cedilha_legada():
    """ş/ţ continua sendo problema de codificação, não escolha do aluno."""
    g = grade("piaţă", ["piață"], lang="ro", strict_diacritics=True)
    assert g.verdict is Verdict.CORRECT


# --------------------------------------------------------------------------- #
# escolha entre múltiplas respostas aceitas
# --------------------------------------------------------------------------- #


def test_escolhe_a_melhor_entre_varias_aceitas():
    g = grade("mesa", ["mesa", "refeição"], lang="pt")
    assert g.verdict is Verdict.CORRECT
    assert g.target == "mesa"


def test_quase_aponta_para_a_aceita_mais_proxima():
    g = grade("refeicao", ["mesa", "refeição"], lang="pt")
    assert g.target == "refeição"


def test_errado_aponta_para_a_traducao_canonica():
    """A 'mais próxima' entre respostas erradas é ruído: quem digitou 'porta'
    para 'om' precisa ver '→ homem', não '→ cara'."""
    g = grade("porta", ["homem", "pessoa", "cara"], lang="pt")
    assert g.verdict is Verdict.WRONG
    assert g.target == "homem"


def test_grade_sem_respostas_aceitas_falha_alto():
    with pytest.raises(ValueError):
        grade("qualquer", [])


# --------------------------------------------------------------------------- #
# integração com o conteúdo real
# --------------------------------------------------------------------------- #


def test_todas_as_palavras_do_acervo_se_autoavaliam_como_certas():
    """Sanidade: cada item deve validar contra si mesmo, com e sem diacríticos."""
    from dor.core.loader import load_library

    lib = load_library()
    for item in lib.vocab.values():
        assert grade(item.ro, [item.ro], lang="ro").verdict is Verdict.CORRECT
        assert grade(item.pt_main, item.all_answers, lang="pt").verdict is Verdict.CORRECT


def test_sem_diacritico_o_acervo_nunca_vira_errado():
    """Digitar sem acento deve render 'certo' ou 'quase', jamais 'errado'."""
    from dor.core.loader import load_library

    lib = load_library()
    for item in lib.vocab.values():
        g = grade(fold(item.ro), [item.ro], lang="ro")
        assert g.verdict is not Verdict.WRONG, f"{item.id}: '{fold(item.ro)}' virou errado"
