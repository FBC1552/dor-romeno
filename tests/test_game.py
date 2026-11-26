"""Gamificação: XP, níveis, streak, quests e conquistas."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from dor.core.grading import Verdict
from dor.core.srs import Card
from dor.game import achievements, quests, streaks, xp
from dor.game.quests import Quest, ReviewEvent
from dor.game.session import GameSession
from dor.storage.repos import Store

TODAY = date(2026, 8, 16)
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

NEW = Card(item_id="ro.x")
MATURE = Card(item_id="ro.x", reps=5)
LEECH = Card(item_id="ro.x", reps=9, lapses=5, leech=True)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "p.db") as s:
        yield s


def event(**kwargs) -> ReviewEvent:
    base = dict(
        mode="traducao",
        direction="ro_pt",
        verdict=Verdict.CORRECT,
        diacritics_only=False,
        was_new=False,
        was_leech=False,
        latency_ms=5000,
        combo=0,
    )
    return ReviewEvent(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# XP
# --------------------------------------------------------------------------- #


def test_errar_nao_da_xp():
    result = xp.compute(
        mode="traducao", direction="ro_pt", credit=0.0, latency_ms=5000, card_before=NEW, combo=0
    )
    assert result.total == 0


def test_quase_da_credito_parcial():
    certo = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=5000, card_before=NEW, combo=0
    )
    quase = xp.compute(
        mode="traducao", direction="ro_pt", credit=0.5, latency_ms=5000, card_before=NEW, combo=0
    )
    assert 0 < quase.total < certo.total


def test_producao_vale_mais_que_reconhecimento():
    reconhecer = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=5000, card_before=MATURE, combo=0
    )
    produzir = xp.compute(
        mode="traducao", direction="pt_ro", credit=1.0, latency_ms=5000, card_before=MATURE, combo=0
    )
    assert produzir.total > reconhecer.total


def test_escolha_vale_menos_que_escrever():
    escolha = xp.compute(
        mode="escolha", direction="ro_pt", credit=1.0, latency_ms=5000, card_before=MATURE, combo=0
    )
    escrever = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=5000, card_before=MATURE, combo=0
    )
    assert escolha.total < escrever.total


def test_resposta_rapida_ganha_bonus():
    lenta = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=9000, card_before=MATURE, combo=0
    )
    rapida = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=500, card_before=MATURE, combo=0
    )
    assert rapida.fast and rapida.total > lenta.total


def test_recuperar_leech_vale_bonus():
    normal = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=9000, card_before=MATURE, combo=0
    )
    recuperada = xp.compute(
        mode="traducao", direction="ro_pt", credit=1.0, latency_ms=9000, card_before=LEECH, combo=0
    )
    assert recuperada.leech_recovery and recuperada.total > normal.total


def test_combo_multiplica_ate_o_teto():
    assert xp.combo_multiplier(0) == 1.0
    assert xp.combo_multiplier(5) > xp.combo_multiplier(2)
    assert xp.combo_multiplier(50) == xp.COMBO_MAX


def test_errar_ignora_o_combo():
    """Multiplicar zero por dois continua zero — mas o campo não deve mentir."""
    result = xp.compute(
        mode="traducao", direction="ro_pt", credit=0.0, latency_ms=100, card_before=MATURE, combo=9
    )
    assert result.combo_mult == 1.0


# --------------------------------------------------------------------------- #
# níveis
# --------------------------------------------------------------------------- #


def test_nivel_um_comeca_em_zero():
    assert xp.level_from_xp(0) == 1
    assert xp.xp_to_reach(1) == 0


def test_curva_de_nivel_e_crescente():
    custos = [xp.xp_to_reach(n + 1) - xp.xp_to_reach(n) for n in range(1, 15)]
    assert custos == sorted(custos)
    assert len(set(custos)) > 1, "a curva precisa encarecer, senão vira contagem linear"


def test_level_from_xp_inverte_xp_to_reach():
    for level in range(1, 40):
        limiar = xp.xp_to_reach(level)
        assert xp.level_from_xp(limiar) == level
        assert xp.level_from_xp(limiar - 1) == max(1, level - 1)


def test_progresso_dentro_do_nivel():
    p = xp.progress(xp.xp_to_reach(5) + 10)
    assert p.level == 5
    assert p.xp_into_level == 10
    assert 0 < p.ratio < 1


# --------------------------------------------------------------------------- #
# streak
# --------------------------------------------------------------------------- #


def test_primeira_atividade_comeca_a_streak():
    update = streaks.touch(streaks.Streak(), TODAY)
    assert update.started and update.streak.current == 1


def test_dia_seguinte_continua():
    s = streaks.Streak(current=3, longest=3, last_active=TODAY)
    update = streaks.touch(s, TODAY + timedelta(days=1))
    assert update.continued and update.streak.current == 4


def test_estudar_duas_vezes_no_mesmo_dia_nao_conta_dobrado():
    s = streaks.Streak(current=3, last_active=TODAY)
    update = streaks.touch(s, TODAY)
    assert update.already_today and update.streak.current == 3


def test_escudo_cobre_dia_perdido():
    s = streaks.Streak(current=10, longest=10, freezes=2, last_active=TODAY)
    update = streaks.touch(s, TODAY + timedelta(days=2))  # faltou 1 dia
    assert update.frozen_days == 1
    assert update.streak.current == 11
    assert update.streak.freezes == 1


def test_sem_escudo_a_streak_quebra():
    s = streaks.Streak(current=10, longest=10, freezes=0, last_active=TODAY)
    update = streaks.touch(s, TODAY + timedelta(days=3))
    assert update.broke and update.streak.current == 1
    assert update.streak.longest == 10, "o recorde não pode ser perdido"


def test_escudos_nao_cobrem_falta_longa():
    s = streaks.Streak(current=10, freezes=2, last_active=TODAY)
    update = streaks.touch(s, TODAY + timedelta(days=5))  # faltaram 4 dias
    assert update.broke


def test_escudo_ganho_a_cada_sete_dias():
    s = streaks.Streak(current=6, longest=6, freezes=0, last_active=TODAY)
    update = streaks.touch(s, TODAY + timedelta(days=1))
    assert update.streak.current == 7
    assert update.freeze_earned and update.streak.freezes == 1


def test_escudos_tem_teto():
    s = streaks.Streak(current=13, freezes=streaks.MAX_FREEZES, last_active=TODAY)
    update = streaks.touch(s, TODAY + timedelta(days=1))
    assert update.streak.freezes == streaks.MAX_FREEZES


def test_relogio_para_tras_nao_quebra_a_streak():
    s = streaks.Streak(current=5, last_active=TODAY)
    update = streaks.touch(s, TODAY - timedelta(days=1))
    assert update.streak.current == 5


def test_at_risk_so_quando_nao_ha_escudo():
    amanha = TODAY + timedelta(days=1)
    assert streaks.at_risk(streaks.Streak(current=3, freezes=0, last_active=TODAY), amanha)
    assert not streaks.at_risk(streaks.Streak(current=3, freezes=1, last_active=TODAY), amanha)
    assert not streaks.at_risk(streaks.Streak(), amanha)


# --------------------------------------------------------------------------- #
# quests
# --------------------------------------------------------------------------- #


def test_quests_do_dia_sao_estaveis():
    assert quests.for_day(TODAY) == quests.for_day(TODAY)


def test_dias_diferentes_tendem_a_quests_diferentes():
    semana = {tuple(q.code for q in quests.for_day(TODAY + timedelta(days=d))) for d in range(7)}
    assert len(semana) > 1


def test_progresso_avanca_e_conclui():
    q = Quest(code="acertos_15", title="", target=2, reward_xp=10,
              template=quests.BY_CODE["acertos_15"])
    assert quests.apply_event([q], event()) == []
    assert quests.apply_event([q], event()) == [q]
    assert q.done and q.progress == 2


def test_quest_concluida_nao_avanca_mais():
    q = Quest(code="acertos_15", title="", target=1, reward_xp=10, done=True, progress=1,
              template=quests.BY_CODE["acertos_15"])
    quests.apply_event([q], event())
    assert q.progress == 1


def test_quest_de_acerto_ignora_erro():
    q = Quest(code="acertos_15", title="", target=3, reward_xp=10,
              template=quests.BY_CODE["acertos_15"])
    quests.apply_event([q], event(verdict=Verdict.WRONG))
    assert q.progress == 0


def test_quest_de_combo_guarda_o_melhor_nao_a_soma():
    q = Quest(code="combo_8", title="", target=8, reward_xp=10,
              template=quests.BY_CODE["combo_8"])
    quests.apply_event([q], event(combo=4))
    quests.apply_event([q], event(combo=0))  # combo quebrou e recomeçou
    assert q.progress == 5, "o melhor combo do dia não pode regredir"


def test_quest_de_romeno_aceita_lacuna_e_gramatica():
    template = quests.BY_CODE["diacritice_10"]
    assert template.matches(event(direction="cloze"))
    assert template.matches(event(mode="gramatica", direction="g.gen.neutru"))
    assert not template.matches(event(direction="ro_pt"))


def test_todo_template_tem_meta_e_recompensa_positivas():
    for template in quests.CATALOG:
        assert template.target > 0 and template.reward_xp > 0


def test_todo_dia_tem_ao_menos_uma_missao_que_qualquer_sessao_avanca():
    """Sem isso, o sorteio pode dar três missões especializadas e o usuário
    fecha a sessão sem mover nenhuma barra."""
    generica = event()
    for offset in range(400):
        dia = TODAY + timedelta(days=offset)
        templates = quests.for_day(dia)
        assert any(t.matches(generica) for t in templates), f"{dia}: nenhuma missão avança"
        assert len(templates) == quests.QUESTS_PER_DAY
        assert len({t.code for t in templates}) == quests.QUESTS_PER_DAY


# --------------------------------------------------------------------------- #
# conquistas
# --------------------------------------------------------------------------- #


def context(**kwargs) -> achievements.Context:
    base = dict(
        total_reviews=0, total_correct=0, words_seen=0, romanian_correct=0,
        gender_correct=0, streak_current=0, combo_max_session=0,
        session_items=0, session_correct=0, leech_recovered=0, now=NOW,
    )
    return achievements.Context(**{**base, **kwargs})


def test_primeira_revisao_desbloqueia():
    novas = achievements.check(context(total_reviews=1), set())
    assert "primul_pas" in {a.code for a in novas}


def test_conquista_ja_obtida_nao_repete():
    novas = achievements.check(context(total_reviews=1), {"primul_pas"})
    assert "primul_pas" not in {a.code for a in novas}


def test_sessao_perfeita_exige_tamanho_minimo():
    curta = achievements.check(context(session_items=4, session_correct=4), set())
    longa = achievements.check(context(session_items=10, session_correct=10), set())
    assert "fara_gres" not in {a.code for a in curta}
    assert "fara_gres" in {a.code for a in longa}


def test_noctambul_depende_da_hora():
    madrugada = datetime(2026, 8, 16, 2, tzinfo=UTC)
    novas = achievements.check(context(now=madrugada), set())
    assert "noctambul" in {a.code for a in novas}
    assert "noctambul" not in {a.code for a in achievements.check(context(), set())}


def test_catalogo_sem_codigos_duplicados():
    codes = [a.code for a in achievements.CATALOG]
    assert len(codes) == len(set(codes))


# --------------------------------------------------------------------------- #
# integração com a sessão
# --------------------------------------------------------------------------- #


def _answer(store, item_id="ro.casa", correct=True, latency=5000, now=NOW):
    from dor.core.loader import load_library
    from dor.core.srs import get_scheduler
    from dor.modes import base, translation

    lib = load_library()
    item = lib.vocab[item_id]
    exercise = translation.build(item, direction="ro_pt")
    given = item.pt_main if correct else "zzzzzz"
    return base.answer(
        exercise, given, latency_ms=latency, store=store, scheduler=get_scheduler(), now=now
    )


def test_sessao_acumula_xp_e_persiste(store):
    game = GameSession(store)
    reward = game.record(_answer(store), NOW)
    assert reward.xp > 0
    assert store.total_xp() == reward.xp
    assert store.daily_row(NOW.astimezone().date())["xp"] == reward.xp


def test_xp_fica_gravado_na_revisao(store):
    game = GameSession(store)
    reward = game.record(_answer(store), NOW)
    row = store.conn.execute("SELECT xp FROM reviews").fetchone()
    assert row["xp"] == reward.xp


def test_combo_sobe_e_zera_ao_errar(store):
    from dor.core.loader import load_library

    lib = load_library()
    ids = [i.id for i in list(lib.vocab.values())[:4]]
    game = GameSession(store)

    for item_id in ids[:3]:
        game.record(_answer(store, item_id), NOW)
    assert game.combo == 3
    assert game.combo_max == 3

    game.record(_answer(store, ids[3], correct=False), NOW)
    assert game.combo == 0
    assert game.combo_max == 3


def test_finish_registra_a_streak(store):
    game = GameSession(store)
    game.record(_answer(store), NOW)
    outcome = game.finish(NOW)
    assert outcome.streak is not None
    assert store.get_streak().current == 1


def test_sessao_sem_resposta_nao_marca_o_dia(store):
    """Abrir o app e sair não pode valer streak."""
    outcome = GameSession(store).finish(NOW)
    assert outcome.streak is None
    assert store.get_streak().current == 0


def test_conquista_e_gravada_uma_vez_so(store):
    game = GameSession(store)
    game.record(_answer(store), NOW)
    game.record(_answer(store, "ro.masa"), NOW)
    unlocked = store.unlocked_achievements()
    assert "primul_pas" in unlocked
    total = store.conn.execute(
        "SELECT COUNT(*) FROM achievements WHERE code = 'primul_pas'"
    ).fetchone()[0]
    assert total == 1


def test_quest_concluida_paga_bonus(store):
    """A recompensa da missão entra no XP do dia, não só num contador solto."""
    day = NOW.astimezone().date()
    store.load_quests(day)
    store.conn.execute(
        "UPDATE quests SET code = 'acertos_15', target = 1, reward_xp = 999 "
        "WHERE day = ? AND code = (SELECT code FROM quests WHERE day = ? LIMIT 1)",
        (day.isoformat(), day.isoformat()),
    )
    game = GameSession(store)
    reward = game.record(_answer(store), NOW)
    assert any(q.reward_xp == 999 for q in reward.quests_done)
    assert store.daily_row(day)["xp"] >= 999


def test_progresso_de_quest_sobrevive_a_nova_sessao(store):
    day = NOW.astimezone().date()
    GameSession(store).record(_answer(store), NOW)
    antes = sum(q.progress for q in store.load_quests(day))

    # Segunda sessão, processo de jogo novo, mesmo dia.
    GameSession(store).record(_answer(store, "ro.masa"), NOW)
    depois = sum(q.progress for q in store.load_quests(day))
    assert depois > antes


def test_meta_diaria_e_marcada_ao_ser_batida(store, monkeypatch):
    from dor import config as cfg

    settings = cfg.Settings(daily_goal_xp=1)
    game = GameSession(store, settings=settings)
    game.record(_answer(store), NOW)
    assert store.daily_row(NOW.astimezone().date())["goal_met"] == 1
