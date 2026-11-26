"""Rede de segurança do progresso: backup, restauração, desfazer e destravar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dor.core.grading import Grade, Verdict
from dor.core.srs import Rating
from dor.storage import backup
from dor.storage.repos import Store


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "progress.db"


def log(store, item_id="ro.casa", verdict=Verdict.CORRECT, *, xp=10, when=None, session_id=None):
    credit = {Verdict.CORRECT: 1.0, Verdict.ALMOST: 0.5, Verdict.WRONG: 0.0}[verdict]
    rating = {
        Verdict.CORRECT: Rating.GOOD,
        Verdict.ALMOST: Rating.HARD,
        Verdict.WRONG: Rating.AGAIN,
    }[verdict]
    now = when or datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    review_id = store.log_review(
        item_id,
        mode="traducao",
        rating=rating,
        grade=Grade(verdict=verdict, credit=credit, given="x", target="y"),
        xp=xp,
        session_id=session_id,
        now=now,
    )
    from dor.core.srs import get_scheduler

    card = store.get_card(item_id)
    store.save_card(get_scheduler().review(card, rating, now))
    store.add_daily(now.astimezone().date(), xp=xp, reviews=1, correct=int(credit == 1.0))
    return review_id


# --------------------------------------------------------------------------- #
# backup
# --------------------------------------------------------------------------- #


def test_backup_de_banco_inexistente_falha_com_mensagem(tmp_path):
    with pytest.raises(backup.BackupError):
        backup.create(tmp_path / "saida.db", source=tmp_path / "nao_existe.db")


def test_backup_preserva_as_revisoes(db_path, tmp_path):
    with Store(db_path) as store:
        for _ in range(5):
            log(store)

    info = backup.create(tmp_path / "b.db", source=db_path)
    assert info.reviews == 5
    assert info.bytes > 0

    with Store(tmp_path / "b.db") as restored:
        assert restored.overview()["revisões"] == 5


def test_backup_nao_deixa_wal_pendurado(db_path, tmp_path):
    """Cópia manual perderia as escritas que ainda vivem no -wal; a API oficial
    do sqlite escreve um arquivo único e consistente."""
    with Store(db_path) as store:
        log(store)
    out = tmp_path / "b.db"
    backup.create(out, source=db_path)
    assert not out.with_name(out.name + "-wal").exists()


def test_inspecionar_arquivo_que_nao_e_banco(tmp_path):
    lixo = tmp_path / "lixo.db"
    lixo.write_text("isto não é um banco", encoding="utf-8")
    with pytest.raises(backup.BackupError):
        backup.inspect(lixo)


def test_restaurar_traz_o_progresso_de_volta(db_path, tmp_path):
    with Store(db_path) as store:
        for _ in range(3):
            log(store)
    salvo = backup.create(tmp_path / "b.db", source=db_path)

    with Store(db_path) as store:
        for _ in range(7):
            log(store, "ro.masa")
        assert store.overview()["revisões"] == 10

    backup.restore(salvo.path, target=db_path)
    with Store(db_path) as store:
        assert store.overview()["revisões"] == 3


def test_restaurar_guarda_o_progresso_atual_antes(db_path, tmp_path, monkeypatch):
    """Restaurar é destrutivo. Ninguém deve apagar meses de estudo com um
    comando e nenhuma rede de segurança."""
    from dor import config

    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "USER_DIR", tmp_path)
    monkeypatch.setattr(config, "AUDIO_CACHE_DIR", tmp_path / "audio")

    with Store(db_path) as store:
        log(store)
    antigo = backup.create(tmp_path / "b.db", source=db_path)

    with Store(db_path) as store:
        for _ in range(9):
            log(store, "ro.masa")

    backup.restore(antigo.path, target=db_path)
    salvos = [b for b in backup.list_backups(tmp_path / "exports") if "antes" in b.path.name]
    assert salvos, "o progresso substituído não foi guardado"
    assert salvos[0].reviews == 10


def test_banco_restaurado_abre_e_migra(db_path, tmp_path):
    with Store(db_path) as store:
        log(store)
    salvo = backup.create(tmp_path / "b.db", source=db_path)
    backup.restore(salvo.path, target=db_path)
    with Store(db_path) as store:
        assert store.overview()["revisões"] == 1


def test_lista_vazia_quando_nao_ha_backups(tmp_path):
    assert backup.list_backups(tmp_path / "nao_existe") == []


def test_lista_ordena_do_mais_novo_para_o_mais_velho(db_path, tmp_path):
    import os

    with Store(db_path) as store:
        log(store)
    velho = backup.create(tmp_path / "dor_backup_velho.db", source=db_path)
    novo = backup.create(tmp_path / "dor_backup_novo.db", source=db_path)
    os.utime(velho.path, (0, 1_000_000))

    nomes = [b.path.name for b in backup.list_backups(tmp_path)]
    assert nomes[0] == novo.path.name


# --------------------------------------------------------------------------- #
# desfazer
# --------------------------------------------------------------------------- #


def test_desfazer_sem_historico_devolve_nada(db_path):
    with Store(db_path) as store:
        assert store.undo_last_review() is None


def test_desfazer_apaga_so_a_ultima_resposta(db_path):
    with Store(db_path) as store:
        log(store, verdict=Verdict.CORRECT)
        log(store, verdict=Verdict.WRONG)

        desfeita = store.undo_last_review()
        assert desfeita["verdict"] == "errado"
        assert store.overview()["revisões"] == 1


def test_desfazer_devolve_o_xp_e_o_acerto_do_dia(db_path):
    dia = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    with Store(db_path) as store:
        log(store, xp=30, when=dia)
        log(store, xp=12, when=dia)
        store.undo_last_review()

        linha = store.daily_row(dia.astimezone().date())
        assert linha["xp"] == 30
        assert linha["reviews"] == 1


def test_desfazer_nao_deixa_contador_negativo(db_path):
    with Store(db_path) as store:
        log(store, xp=5)
        store.undo_last_review()
        linha = store.daily_row(datetime(2026, 8, 17, 12, 0, tzinfo=UTC).astimezone().date())
        assert linha["xp"] >= 0
        assert linha["reviews"] >= 0


def test_desfazer_reagenda_o_item_pelo_historico_restante(db_path):
    """O intervalo depende da sequência inteira, então o cartão é refeito do
    zero a partir do que sobrou — não 'desandado' por aproximação."""
    base = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    with Store(db_path) as store:
        log(store, when=base)
        depois_de_uma = store.get_card("ro.casa")
        log(store, when=base + timedelta(days=1))
        assert store.get_card("ro.casa").reps == 2

        store.undo_last_review()
        agora = store.get_card("ro.casa")
        assert agora.reps == depois_de_uma.reps == 1


def test_desfazer_a_unica_resposta_apaga_o_cartao(db_path):
    """Item que nunca foi respondido não deve continuar 'em estudo'."""
    with Store(db_path) as store:
        log(store)
        assert "ro.casa" in store.seen_item_ids()
        store.undo_last_review()
        assert "ro.casa" not in store.seen_item_ids()


def test_desfazer_ajusta_a_sessao(db_path):
    with Store(db_path) as store:
        sid = store.start_session("teste")
        log(store, session_id=sid)
        store.bump_session(sid, correct=True, credit=1.0)
        store.undo_last_review()
        resumo = store.end_session(sid)
        assert resumo.items_seen == 0
        assert resumo.correct == 0


# --------------------------------------------------------------------------- #
# destravar
# --------------------------------------------------------------------------- #


def travar(store, item_id):
    from dataclasses import replace

    store.save_card(replace(store.get_card(item_id), leech=True))


def test_destravar_um_item(db_path):
    with Store(db_path) as store:
        log(store, "ro.casa")
        log(store, "ro.masa")
        travar(store, "ro.casa")
        travar(store, "ro.masa")

        assert store.unleech("ro.casa") == 1
        assert store.leech_item_ids() == ["ro.masa"]


def test_destravar_todos(db_path):
    with Store(db_path) as store:
        for item in ("ro.casa", "ro.masa"):
            log(store, item)
            travar(store, item)
        assert store.unleech() == 2
        assert store.leech_item_ids() == []


def test_destravar_item_que_nao_esta_travado_nao_conta(db_path):
    with Store(db_path) as store:
        log(store)
        assert store.unleech("ro.casa") == 0
