"""Modos de estudo e geração de exercícios."""

from __future__ import annotations

import random

import pytest

from dor.core import distractors
from dor.core.grading import Verdict, grade
from dor.core.loader import load_library
from dor.core.normalize import normalize
from dor.core.srs import Card, get_scheduler
from dor.modes import base, cloze, grammar_drill, mixer, multiple_choice, translation
from dor.storage.repos import Store


@pytest.fixture(scope="module")
def lib():
    return load_library()


@pytest.fixture(scope="module")
def pool(lib):
    return list(lib.vocab.values())


@pytest.fixture
def rng():
    return random.Random(20260816)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "p.db") as s:
        yield s


# --------------------------------------------------------------------------- #
# tradução
# --------------------------------------------------------------------------- #


def test_traducao_ro_pt_pergunta_em_romeno(lib):
    item = lib.vocab["ro.casa"]
    ex = translation.build(item, direction="ro_pt")
    assert ex.prompt == "casă"
    assert ex.answer_lang == "pt"
    assert "casa" in ex.answers
    assert ex.speak_before == "casă"


def test_traducao_pt_ro_pede_producao(lib):
    item = lib.vocab["ro.casa"]
    ex = translation.build(item, direction="pt_ro")
    assert ex.prompt == "casa"
    assert ex.answer_lang == "ro"
    assert "casă" in ex.answers
    assert ex.speak_after == "casă"


# --------------------------------------------------------------------------- #
# distratores
# --------------------------------------------------------------------------- #


def test_distratores_nao_incluem_a_resposta_certa(lib, pool, rng):
    item = lib.vocab["ro.casa"]
    wrong = distractors.pick(item, pool, n=3, lang="pt", rng=rng)
    assert all(normalize(w) not in {normalize(p) for p in item.pt} for w in wrong)


def test_distratores_nao_se_repetem(lib, pool, rng):
    for item in list(lib.vocab.values())[:20]:
        wrong = distractors.pick(item, pool, n=3, lang="ro", rng=rng)
        assert len(wrong) == len({normalize(w) for w in wrong})


def test_distrator_prefere_mesma_classe_e_campo_semantico(lib, pool):
    """`pâine` (comida) deve pontuar mais que `a merge` (verbo) como alternativa
    para `vin` (bebida) — é o que separa escolha que ensina de chute."""
    alvo = lib.vocab["ro.vin"]
    comida = lib.vocab["ro.paine"]
    verbo = lib.vocab["ro.a_merge"]
    assert distractors.score(alvo, comida, "ro") > distractors.score(alvo, verbo, "ro")


def test_distrator_de_substantivo_prefere_mesmo_genero(lib):
    alvo = lib.vocab["ro.casa"]  # feminino
    mesmo = lib.vocab["ro.masa"]  # feminino
    outro = lib.vocab["ro.scaun"]  # neutro
    assert distractors.score(alvo, mesmo, "ro") > distractors.score(alvo, outro, "ro")


def test_build_choices_inclui_a_correta(rng):
    options = distractors.build_choices("casa", ["mesa", "porta", "livro"], rng)
    assert "casa" in options
    assert len(options) == 4


# --------------------------------------------------------------------------- #
# múltipla escolha
# --------------------------------------------------------------------------- #


def test_multipla_escolha_tem_exatamente_uma_certa(lib, pool, rng):
    for item in list(lib.vocab.values())[:25]:
        ex = multiple_choice.build(item, pool, direction="ro_pt", rng=rng)
        if ex is None:
            continue
        certas = [
            c for c in ex.choices if grade(c, ex.answers, lang=ex.answer_lang).verdict is Verdict.CORRECT
        ]
        assert len(certas) == 1, f"{item.id}: {len(certas)} alternativas certas em {ex.choices}"


def test_multipla_escolha_devolve_none_com_acervo_minusculo(lib, rng):
    item = lib.vocab["ro.casa"]
    assert multiple_choice.build(item, [item], rng=rng) is None


def test_numero_da_alternativa_e_aceito_como_resposta(lib, pool, rng):
    item = lib.vocab["ro.casa"]
    ex = multiple_choice.build(item, pool, direction="ro_pt", rng=rng)
    index = ex.choices.index("casa") + 1
    assert base.resolve_choice(ex, str(index)) == "casa"
    assert base.resolve_choice(ex, "casa") == "casa"


def test_numero_fora_da_faixa_passa_direto_e_vira_erro(lib, pool, rng):
    ex = multiple_choice.build(lib.vocab["ro.casa"], pool, rng=rng)
    assert base.resolve_choice(ex, "99") == "99"


# --------------------------------------------------------------------------- #
# lacuna
# --------------------------------------------------------------------------- #


def test_lacuna_respeita_limite_de_palavra():
    """'vin' não pode abrir buraco no meio de 'vinul'."""
    assert cloze.blank_out("Vinul este bun.", "vin") is None
    assert cloze.blank_out("Beau vin roșu.", "vin") == "Beau ____ roșu."


def test_lacuna_alvo_ausente_devolve_none():
    assert cloze.blank_out("Casa este mare.", "pâine") is None


def test_lacuna_gerada_esconde_a_resposta(lib, rng):
    item = lib.vocab["ro.vin"]
    ex = cloze.build(item, lib, rng=rng)
    assert ex is not None
    assert cloze.BLANK in ex.prompt
    assert ex.answers[0].lower() not in ex.prompt.lower()


def test_lacuna_devolve_none_sem_frase_de_exemplo(lib, rng):
    sem_exemplo = [i for i in lib.vocab.values() if not i.examples]
    assert sem_exemplo, "o acervo precisa de ao menos um item sem exemplo para este teste"
    assert cloze.build(sem_exemplo[0], lib, rng=rng) is None


# --------------------------------------------------------------------------- #
# gramática gerada
# --------------------------------------------------------------------------- #


def test_toda_regra_com_drill_gera_exercicio(lib, rng):
    for rule in lib.grammar.values():
        if not rule.drill:
            continue
        ex = grammar_drill.build(rule, lib, rng=rng)
        assert ex is not None, f"{rule.id} não gerou exercício"
        assert ex.answers and all(a for a in ex.answers)


def test_drill_de_artigo_pede_a_forma_definida(lib, rng):
    rule = lib.grammar["g.articol.hotarat.fem.sg"]
    ex = grammar_drill.build(rule, lib, item=lib.vocab["ro.casa"], rng=rng)
    assert ex.prompt == "casă"
    assert ex.answers == ["casa"]


def test_drill_de_genero_oferece_as_tres_opcoes(lib, rng):
    rule = lib.grammar["g.gen.neutru"]
    ex = grammar_drill.build(rule, lib, item=lib.vocab["ro.scaun"], rng=rng)
    assert set(ex.choices) == {"masculino", "feminino", "neutro"}
    assert grade("neutro", ex.answers, lang="pt").verdict is Verdict.CORRECT
    assert grade("feminino", ex.answers, lang="pt").verdict is Verdict.WRONG


def test_drill_de_conjugacao_sorteia_uma_pessoa(lib, rng):
    rule = lib.grammar["g.verb.prezent"]
    ex = grammar_drill.build(rule, lib, item=lib.vocab["ro.a_fi"], rng=rng)
    formas = lib.vocab["ro.a_fi"].forms["prezent"]
    assert ex.answers[0] in formas
    assert any(p in ex.prompt for p in grammar_drill.PERSONS)


def test_drill_cobre_todo_o_acervo_elegivel(lib):
    """Cada regra deve alcançar mais itens que o número de exercícios de uma
    sessão — é a promessa de 'exercício infinito'."""
    for rule in lib.grammar.values():
        if not rule.drill:
            continue
        assert len(grammar_drill.matching_items(rule, lib)) >= 5, rule.id


# --------------------------------------------------------------------------- #
# mixer
# --------------------------------------------------------------------------- #


def test_item_novo_comeca_por_reconhecimento(lib, pool, rng):
    item = lib.vocab["ro.casa"]
    ex = mixer.pick(item, Card(item_id=item.id), lib, pool, rng=rng)
    assert ex.mode == translation.MODE
    assert ex.direction == "ro_pt"


def test_item_maduro_cobra_producao(lib, pool):
    item = lib.vocab["ro.dor"]
    card = Card(item_id=item.id, reps=10)
    # o mixer tem um sorteio de 25% para escolha; fixar a semente evita flake
    modos = {
        mixer.pick(item, card, lib, pool, rng=random.Random(seed)).direction for seed in range(20)
    }
    assert "pt_ro" in modos
    assert modos <= {"pt_ro"}


def test_leech_volta_para_o_reconhecimento(lib, pool, rng):
    item = lib.vocab["ro.dor"]
    card = Card(item_id=item.id, reps=20, lapses=6, leech=True)
    ex = mixer.pick(item, card, lib, pool, rng=rng)
    assert ex.direction == "ro_pt"


def test_filtro_de_modo_e_respeitado(lib, pool, rng):
    item = lib.vocab["ro.casa"]
    card = Card(item_id=item.id, reps=1)
    ex = mixer.pick(item, card, lib, pool, rng=rng, allow={translation.MODE})
    assert ex.mode == translation.MODE


def test_mixer_sempre_devolve_exercicio(lib, pool, rng):
    """Nenhuma combinação de item e maturidade pode deixar a sessão sem pergunta."""
    for item in lib.vocab.values():
        for reps in (0, 1, 3, 5, 12):
            ex = mixer.pick(item, Card(item_id=item.id, reps=reps), lib, pool, rng=rng)
            assert ex.prompt and ex.answers


# --------------------------------------------------------------------------- #
# integração
# --------------------------------------------------------------------------- #


def test_todo_modo_persiste_e_agenda(lib, pool, store, rng):
    scheduler = get_scheduler()
    item = lib.vocab["ro.vin"]
    exercicios = [
        translation.build(item, direction="ro_pt"),
        multiple_choice.build(item, pool, rng=rng),
        cloze.build(item, lib, rng=rng),
        grammar_drill.build(lib.grammar["g.gen.neutru"], lib, item=item, rng=rng),
    ]
    sid = store.start_session("teste")
    for ex in exercicios:
        assert ex is not None
        base.answer(
            ex, ex.answers[0], latency_ms=4000, store=store, scheduler=scheduler, session_id=sid
        )

    summary = store.end_session(sid)
    assert summary.items_seen == len(exercicios)
    assert summary.correct == len(exercicios)
    # Os quatro exercícios são do mesmo vocábulo — inclusive o drill de gênero,
    # que é gerado a partir dele. Logo, quatro revisões no mesmo card.
    assert store.get_card(item.id).reps == len(exercicios)


def test_modos_gravam_o_proprio_nome(lib, pool, store, rng):
    scheduler = get_scheduler()
    item = lib.vocab["ro.casa"]
    ex = multiple_choice.build(item, pool, rng=rng)
    base.answer(ex, ex.answers[0], latency_ms=1000, store=store, scheduler=scheduler)
    row = store.conn.execute("SELECT mode FROM reviews").fetchone()
    assert row["mode"] == multiple_choice.MODE
