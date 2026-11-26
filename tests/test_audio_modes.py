"""Modos de áudio: ditado, escuta, pares mínimos e shadowing.

Nada aqui toca a rede: o que se testa é a construção do exercício e a seleção
de conteúdo. A síntese em si é responsabilidade do provedor de TTS.
"""

from __future__ import annotations

import random

import pytest

from dor.core.grading import Verdict, grade
from dor.core.loader import load_library
from dor.core.normalize import fold
from dor.modes import dictation, listening, minimal_pairs, shadowing


@pytest.fixture(scope="module")
def lib():
    return load_library()


@pytest.fixture
def rng():
    return random.Random(20260816)


# --------------------------------------------------------------------------- #
# conteúdo dos pares mínimos
# --------------------------------------------------------------------------- #


def test_acervo_tem_pares_minimos(lib):
    assert len(lib.pairs) >= 10


def test_os_dois_lados_do_par_sao_realmente_diferentes(lib):
    for pair in lib.pairs.values():
        assert pair.a.ro != pair.b.ro, f"{pair.id}: os dois lados são a mesma palavra"


def test_par_minimo_difere_por_pouco(lib):
    """Se as palavras não são quase idênticas, não é par mínimo — é só um par."""
    from dor.core.normalize import levenshtein, normalize

    for pair in lib.pairs.values():
        a, b = normalize(pair.a.ro), normalize(pair.b.ro)
        assert levenshtein(a, b) <= 2, f"{pair.id}: '{a}' e '{b}' estão longe demais"


def test_contraste_some_ao_tirar_diacriticos(lib):
    """O ponto do acervo: são contrastes que o brasileiro não enxerga nem ouve.

    Todo par ou fica idêntico sem diacríticos (ș/s, ț/t, ă/a), ou envolve â/î,
    que é a vogal que o português não tem.
    """
    for pair in lib.pairs.values():
        iguais_sem_acento = fold(pair.a.ro).lower() == fold(pair.b.ro).lower()
        vogal_inexistente = any(c in pair.a.ro + pair.b.ro for c in "âî")
        assert iguais_sem_acento or vogal_inexistente, f"{pair.id}: contraste trivial"


def test_lados_tem_traducao(lib):
    for pair in lib.pairs.values():
        assert pair.a.pt.strip() and pair.b.pt.strip()


def test_other_devolve_o_lado_oposto(lib):
    pair = lib.pairs["mp.peste"]
    assert pair.other(pair.a) is pair.b
    assert pair.other(pair.b) is pair.a


# --------------------------------------------------------------------------- #
# exercício de par mínimo
# --------------------------------------------------------------------------- #


def test_par_minimo_oferece_as_duas_palavras(lib, rng):
    pair = lib.pairs["mp.peste"]
    ex = minimal_pairs.build(pair, rng=rng)
    assert set(ex.choices) == {"pește", "peste"}
    assert len(ex.choices) == 2


def test_a_palavra_tocada_e_a_resposta_certa(lib, rng):
    for pair in lib.pairs.values():
        ex = minimal_pairs.build(pair, rng=rng)
        assert ex.speak_before == ex.answers[0]
        assert ex.answers[0] in ex.choices


def test_par_minimo_agenda_o_proprio_par(lib, rng):
    """O contraste é a unidade de aprendizado, não a palavra solta."""
    pair = lib.pairs["mp.fata"]
    ex = minimal_pairs.build(pair, rng=rng)
    assert ex.item_id == "mp.fata"


def test_par_minimo_sorteia_os_dois_lados(lib):
    pair = lib.pairs["mp.peste"]
    tocadas = {minimal_pairs.build(pair, rng=random.Random(s)).speak_before for s in range(30)}
    assert tocadas == {"pește", "peste"}


def test_nota_mostra_o_significado_dos_dois(lib, rng):
    pair = lib.pairs["mp.desert"]
    ex = minimal_pairs.build(pair, rng=rng)
    assert ex.always_note
    assert "deserto" in ex.note and "sobremesa" in ex.note


def test_escolher_o_par_errado_e_erro_seco_nao_quase(lib, rng):
    """O perdão de diacrítico da F2 tem que ser DESLIGADO aqui.

    Em `pește` / `peste` a diferença é só um diacrítico, então a regra geral
    daria 'quase' e meio ponto por escolher a palavra errada — o que desmonta
    o exercício, já que distinguir as duas É a atividade.
    """
    for pair in lib.pairs.values():
        ex = minimal_pairs.build(pair, rng=rng)
        assert ex.strict_diacritics
        errada = next(c for c in ex.choices if c != ex.answers[0])
        resultado = grade(errada, ex.answers, lang="ro", strict_diacritics=True)
        assert resultado.verdict is Verdict.WRONG, f"{pair.id}: escolher errado deu crédito"
        assert resultado.credit == 0.0


def test_sem_o_modo_estrito_o_mesmo_erro_seria_perdoado(lib, rng):
    """Confirma que o rigor é local, e não uma mudança de comportamento geral."""
    ex = minimal_pairs.build(lib.pairs["mp.cos"], rng=rng)
    errada = next(c for c in ex.choices if c != ex.answers[0])
    assert grade(errada, ex.answers, lang="ro").verdict is Verdict.ALMOST


def test_audio_texts_cobre_os_dois_lados(lib):
    textos = minimal_pairs.audio_texts(list(lib.pairs.values()))
    assert len(textos) == 2 * len(lib.pairs)
    assert "pește" in textos and "peste" in textos


# --------------------------------------------------------------------------- #
# ditado
# --------------------------------------------------------------------------- #


def test_ditado_nao_revela_a_palavra_no_enunciado(lib):
    item = lib.vocab["ro.paine"]
    ex = dictation.build(item, lib)
    assert item.ro not in ex.prompt
    assert ex.speak_before == item.ro
    assert ex.answers == [item.ro]
    assert ex.answer_lang == "ro"


def test_ditado_de_frase_usa_o_exemplo(lib, rng):
    item = lib.vocab["ro.vin"]
    ex = dictation.build(item, lib, use_sentence=True, rng=rng)
    frases = {lib.sentences[s].ro for s in item.examples}
    assert ex.answers[0] in frases


def test_ditado_sem_exemplo_cai_na_palavra(lib, rng):
    sem = next(i for i in lib.vocab.values() if not i.examples)
    ex = dictation.build(sem, lib, use_sentence=True, rng=rng)
    assert ex.answers == [sem.ro]


def test_ditado_sem_acento_vira_quase_nao_errado(lib):
    """É o modo em que o diacrítico mais importa — e onde punir seria fatal."""
    item = lib.vocab["ro.paine"]
    ex = dictation.build(item, lib)
    resultado = grade(fold(item.ro), ex.answers, lang="ro")
    assert resultado.verdict is Verdict.ALMOST


# --------------------------------------------------------------------------- #
# escuta
# --------------------------------------------------------------------------- #


def test_escuta_pede_portugues(lib):
    item = lib.vocab["ro.casa"]
    ex = listening.build(item, lib)
    assert ex.answer_lang == "pt"
    assert ex.answers == item.pt
    assert ex.speak_before == item.ro


def test_escuta_nao_mostra_a_palavra_antes(lib):
    for item in list(lib.vocab.values())[:20]:
        ex = listening.build(item, lib)
        assert item.ro not in ex.prompt


# --------------------------------------------------------------------------- #
# shadowing
# --------------------------------------------------------------------------- #


def test_shadowing_devolve_frases(lib, rng):
    steps = shadowing.build(lib, limit=5, rng=rng)
    assert len(steps) == 5
    assert all(s.ro and s.pt for s in steps)


def test_shadowing_respeita_o_limite(lib, rng):
    assert len(shadowing.build(lib, limit=3, rng=rng)) == 3
    assert len(shadowing.build(lib, limit=999, rng=rng)) == len(lib.sentences)


def test_pausa_cresce_com_a_frase():
    curta = shadowing.pause_for("Da.")
    longa = shadowing.pause_for("Nu-ți face griji, mă descurc foarte bine aici.")
    assert longa > curta
    assert curta >= shadowing.MIN_PAUSE_MS


def test_shadowing_filtra_por_nivel(lib, rng):
    steps = shadowing.build(lib, limit=99, level="A1", rng=rng)
    assert steps and all(s.sentence.level == "A1" for s in steps)


def test_ritmo_lento_e_realmente_mais_lento():
    assert shadowing.SLOW_RATE.startswith("-")
