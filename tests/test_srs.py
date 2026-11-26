"""Agendamento e persistência.

Os testes rodam contra um banco temporário de verdade (não um mock), porque o
que precisa ser garantido é justamente que o SQLite grava e relê o estado — não
que uma abstração devolve o que colocaram nela.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dor.core.grading import Verdict, grade
from dor.core.srs import (
    FAST_ANSWER_MS,
    LEECH_THRESHOLD,
    Card,
    FSRSScheduler,
    Rating,
    SM2Scheduler,
    available_schedulers,
    get_scheduler,
    rating_from_grade,
)
from dor.storage.db import MigrationError, connect, migrate
from dor.storage.repos import Store

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "progress.db") as s:
        yield s


@pytest.fixture(params=["fsrs", "sm2"])
def scheduler(request):
    if request.param == "fsrs" and not FSRSScheduler.available():
        pytest.skip("fsrs não instalado")
    return get_scheduler(request.param)


# --------------------------------------------------------------------------- #
# tradução do veredito para nota
# --------------------------------------------------------------------------- #


def test_errado_vira_again():
    g = grade("televizor", ["pâine"], lang="ro")
    assert g.verdict is Verdict.WRONG
    assert rating_from_grade(g, 5000) is Rating.AGAIN


def test_quase_vira_hard():
    """Sabia a palavra e tropeçou no diacrítico não é o mesmo que não saber."""
    g = grade("piata", ["piață"], lang="ro")
    assert g.verdict is Verdict.ALMOST
    assert rating_from_grade(g, 5000) is Rating.HARD


def test_certo_e_lento_vira_good():
    g = grade("piață", ["piață"], lang="ro")
    assert rating_from_grade(g, 9000) is Rating.GOOD


def test_certo_e_rapido_vira_easy():
    g = grade("piață", ["piață"], lang="ro")
    assert rating_from_grade(g, FAST_ANSWER_MS - 1) is Rating.EASY


def test_sem_latencia_nao_promove_para_easy():
    g = grade("piață", ["piață"], lang="ro")
    assert rating_from_grade(g, None) is Rating.GOOD


def test_quase_rapido_continua_hard():
    """Velocidade não compensa acento errado."""
    g = grade("piata", ["piață"], lang="ro")
    assert rating_from_grade(g, 100) is Rating.HARD


# --------------------------------------------------------------------------- #
# agendadores
# --------------------------------------------------------------------------- #


def test_sm2_sempre_disponivel():
    assert "sm2" in available_schedulers()
    assert isinstance(get_scheduler("sm2"), SM2Scheduler)


def test_review_agenda_no_futuro(scheduler):
    card = scheduler.review(Card(item_id="ro.casa"), Rating.GOOD, NOW)
    assert card.due_at > NOW
    assert card.reps == 1
    assert card.last_review == NOW


def test_acerto_repetido_espaca_cada_vez_mais(scheduler):
    card = Card(item_id="ro.casa")
    intervals = []
    now = NOW
    for _ in range(5):
        card = scheduler.review(card, Rating.GOOD, now)
        intervals.append(card.due_at - now)
        now = card.due_at
    assert intervals[-1] > intervals[0], f"intervalos não cresceram: {intervals}"


def test_errar_conta_recaida_e_encurta_o_intervalo(scheduler):
    card = Card(item_id="ro.casa")
    now = NOW
    longo = timedelta(0)
    for _ in range(3):
        anterior = now
        card = scheduler.review(card, Rating.GOOD, now)
        longo = card.due_at - anterior
        now = card.due_at

    card = scheduler.review(card, Rating.AGAIN, now)
    assert card.lapses == 1
    assert (card.due_at - now) < longo


def test_easy_espaca_mais_que_good(scheduler):
    base = Card(item_id="ro.casa")
    warm = scheduler.review(scheduler.review(base, Rating.GOOD, NOW), Rating.GOOD, NOW)
    good = scheduler.review(warm, Rating.GOOD, NOW)
    easy = scheduler.review(warm, Rating.EASY, NOW)
    assert easy.due_at >= good.due_at


def test_item_vira_leech_apos_recaidas_seguidas(scheduler):
    card = Card(item_id="ro.casa")
    now = NOW
    for _ in range(LEECH_THRESHOLD):
        card = scheduler.review(card, Rating.AGAIN, now)
        now += timedelta(minutes=10)
    assert card.leech


def test_card_novo_esta_vencido():
    assert Card(item_id="ro.casa").is_due(NOW)
    assert Card(item_id="ro.casa").is_new


# --------------------------------------------------------------------------- #
# persistência
# --------------------------------------------------------------------------- #


def test_migration_cria_esquema_e_e_idempotente(tmp_path):
    from dor.storage.db import _migration_files

    esperada = max(n for n, _ in _migration_files())
    path = tmp_path / "p.db"
    conn = connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == esperada
    assert migrate(conn) == esperada  # rodar de novo não quebra nem duplica
    conn.close()


def test_migrations_sao_numeradas_em_sequencia():
    from dor.storage.db import _migration_files

    numeros = [n for n, _ in _migration_files()]
    assert numeros == list(range(1, len(numeros) + 1))


def test_migration_com_arquivo_invalido_falha_alto(tmp_path, monkeypatch):
    from dor.storage import db

    bad = tmp_path / "migrations"
    bad.mkdir()
    (bad / "002_broken.sql").write_text("ISTO NAO E SQL;", encoding="utf-8")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", bad)
    # connect() migra na abertura, então a falha aparece já aqui — e o
    # user_version não avança, porque a migration roda dentro de transação.
    with pytest.raises(MigrationError):
        connect(tmp_path / "p.db")


def test_card_sobrevive_ao_fechamento_do_banco(tmp_path, scheduler):
    path = tmp_path / "p.db"
    with Store(path) as s:
        s.save_card(scheduler.review(Card(item_id="ro.dor"), Rating.GOOD, NOW))

    with Store(path) as s:  # processo novo, mesmo arquivo
        card = s.get_card("ro.dor")
    assert card.reps == 1
    assert card.due_at > NOW


def test_item_desconhecido_volta_como_card_novo(store):
    card = store.get_card("ro.inexistente")
    assert card.is_new and card.due_at is None


def test_due_item_ids_respeita_o_relogio(store, scheduler):
    store.save_card(scheduler.review(Card(item_id="ro.casa"), Rating.GOOD, NOW))
    assert store.due_item_ids(NOW) == []
    assert "ro.casa" in store.due_item_ids(NOW + timedelta(days=400))


def test_log_review_grava_o_veredito(store):
    g = grade("piata", ["piață"], lang="ro")
    store.log_review("ro.piata", mode="traducao", rating=Rating.HARD, grade=g, now=NOW)
    row = store.conn.execute("SELECT * FROM reviews").fetchone()
    assert row["verdict"] == "quase"
    assert row["credit"] == 0.5
    assert row["answer_given"] == "piata"


def test_sessao_interrompida_mantem_o_que_ja_foi_feito(tmp_path):
    """O contador sobe a cada resposta, não no fim — Ctrl+C não zera a sessão."""
    path = tmp_path / "p.db"
    with Store(path) as s:
        sid = s.start_session("traducao")
        s.bump_session(sid, correct=True, credit=1.0)
        s.bump_session(sid, correct=False, credit=0.0)
        # sem end_session: simula o terminal fechado no meio

    with Store(path) as s:
        summary = s.end_session(sid)
    assert summary.items_seen == 2
    assert summary.correct == 1
    assert summary.accuracy == 0.5


def test_overview_conta_certas_e_quase(store):
    store.log_review(
        "ro.a", mode="traducao", rating=Rating.GOOD, grade=grade("casă", ["casă"]), now=NOW
    )
    store.log_review(
        "ro.b", mode="traducao", rating=Rating.HARD, grade=grade("piata", ["piață"]), now=NOW
    )
    data = store.overview()
    assert data["revisões"] == 2
    assert data["certas"] == 1
    assert data["quase"] == 1
    assert data["acurácia"] == 0.5


def test_forecast_devolve_um_dia_por_linha(store, scheduler):
    store.save_card(scheduler.review(Card(item_id="ro.casa"), Rating.GOOD, NOW))
    forecast = store.forecast(7, NOW)
    assert len(forecast) == 7
    assert sum(n for _, n in forecast) >= 0


# --------------------------------------------------------------------------- #
# ciclo completo
# --------------------------------------------------------------------------- #


def test_ciclo_completo_responder_agenda_e_persiste(tmp_path):
    """Corrigir -> agendar -> gravar, e reler tudo num processo novo."""
    import random

    from dor.core.loader import load_library
    from dor.core.selection import build_queue
    from dor.modes import base, translation

    lib = load_library()
    path = tmp_path / "p.db"
    scheduler = get_scheduler()

    with Store(path) as store:
        queue = build_queue(lib, store, limit=3, rng=random.Random(0), now=NOW)
        assert len(queue) == 3
        sid = store.start_session(translation.MODE)
        for item in queue:
            base.answer(
                translation.build(item, direction="ro_pt"),
                item.pt_main,
                latency_ms=5000,
                store=store,
                scheduler=scheduler,
                session_id=sid,
                now=NOW,
            )
        summary = store.end_session(sid)

    assert summary.items_seen == 3
    assert summary.correct == 3

    with Store(path) as store:
        assert len(store.seen_item_ids()) == 3
        assert store.due_item_ids(NOW) == []  # tudo agendado para o futuro
        assert store.overview()["acurácia"] == 1.0


def test_fila_prioriza_o_vencido_sobre_o_novo(tmp_path, scheduler):
    from dor.core.loader import load_library
    from dor.core.selection import build_queue

    lib = load_library()
    with Store(tmp_path / "p.db") as store:
        card = scheduler.review(Card(item_id="ro.dor"), Rating.AGAIN, NOW)
        store.save_card(card)
        queue = build_queue(lib, store, limit=5, now=card.due_at + timedelta(days=1))
    assert queue[0].id == "ro.dor"
