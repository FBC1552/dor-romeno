"""Painel de progresso: widgets puros e as consultas que os alimentam."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from dor.core.grading import Grade, Verdict
from dor.core.srs import Rating
from dor.storage.repos import GroupStat, Store
from dor.ui import dashboard as dash


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "p.db") as s:
        yield s


def log(store, item_id, verdict, *, mode="traducao", direction=None, when=None, n=1):
    credit = {Verdict.CORRECT: 1.0, Verdict.ALMOST: 0.5, Verdict.WRONG: 0.0}[verdict]
    rating = {
        Verdict.CORRECT: Rating.GOOD,
        Verdict.ALMOST: Rating.HARD,
        Verdict.WRONG: Rating.AGAIN,
    }[verdict]
    for _ in range(n):
        store.log_review(
            item_id,
            mode=mode,
            rating=rating,
            grade=Grade(verdict=verdict, credit=credit, given="x", target="y"),
            direction=direction,
            now=when or datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
        )


# --------------------------------------------------------------------------- #
# calendário
# --------------------------------------------------------------------------- #


def test_nivel_do_calendario_e_medido_contra_a_meta():
    """Contra a meta, não contra o melhor dia: senão baixar o ritmo repintaria
    o passado inteiro."""
    assert dash.heat_level(0, 120) == 0
    assert dash.heat_level(30, 120) == 1
    assert dash.heat_level(60, 120) == 2
    assert dash.heat_level(120, 120) == 3
    assert dash.heat_level(400, 120) == 4


def test_dia_em_branco_nunca_e_verde():
    assert dash.heat_level(0, 1) == 0
    assert dash.HEAT_STYLES[0] == "grey30"


def test_meta_zero_nao_divide_por_zero():
    """Sem meta definida, qualquer estudo conta como meta batida."""
    assert dash.heat_level(10, 0) == 3


def test_calendario_tem_sete_linhas_mais_cabecalho_e_legenda():
    linhas = dash.heatmap([], today=date(2026, 8, 16), weeks=4)
    assert len(linhas) == 9


def test_calendario_nao_pinta_o_futuro():
    """Quarta-feira: as três últimas casas da coluna atual ainda não existem."""
    hoje = date(2026, 8, 12)  # uma quarta
    linhas = dash.heatmap([], today=hoje, weeks=2)
    quinta, sexta, sabado = linhas[4], linhas[5], linhas[6]
    for linha in (quinta, sexta, sabado):
        assert linha.plain.rstrip().endswith("■") is False or linha.plain.count("■") == 1


def test_calendario_marca_o_dia_com_xp():
    hoje = date(2026, 8, 16)
    vazio = dash.heatmap([], today=hoje, weeks=2)
    cheio = dash.heatmap([(hoje.isoformat(), 500)], today=hoje, weeks=2)
    assert vazio != cheio
    estilos = {span.style for line in cheio for span in line.spans}
    assert dash.HEAT_STYLES[4] in estilos


def test_calendario_respeita_a_quantidade_de_semanas():
    curto = dash.heatmap([], today=date(2026, 8, 16), weeks=4)
    longo = dash.heatmap([], today=date(2026, 8, 16), weeks=20)
    assert len(longo[1].plain) > len(curto[1].plain)


def test_calendario_mostra_os_meses_do_periodo():
    linhas = dash.heatmap([], today=date(2026, 8, 16), weeks=13)
    cabecalho = linhas[0].plain
    assert "ago" in cabecalho
    assert "mai" in cabecalho


# --------------------------------------------------------------------------- #
# barras e cores
# --------------------------------------------------------------------------- #


def test_barra_respeita_a_largura_e_satura():
    assert len(dash.bar(0.5, 10).plain) == 10
    assert dash.bar(9.0, 10).plain == "█" * 10
    assert dash.bar(-1.0, 10).plain == "░" * 10


def test_cor_da_acuracia_muda_de_faixa():
    assert dash.accuracy_style(0.95) == "ok"
    assert dash.accuracy_style(0.7) == "warn"
    assert dash.accuracy_style(0.3) == "err"


def test_sparkline_tem_um_caractere_por_valor():
    assert len(dash.sparkline([1, 5, 3, 0])) == 4
    assert dash.sparkline([]) == ""


# --------------------------------------------------------------------------- #
# recortes
# --------------------------------------------------------------------------- #


def test_agrupa_por_item_modo_e_regra(store):
    log(store, "ro.casa", Verdict.CORRECT, n=3)
    log(store, "ro.casa", Verdict.WRONG, mode="ditado")
    log(store, "ro.masa", Verdict.ALMOST, mode="gramatica", direction="g.plural")

    por_item = {s.key: s for s in store.group_stats("item_id")}
    assert por_item["ro.casa"].reviews == 4
    assert por_item["ro.casa"].correct == 3

    por_modo = {s.key: s for s in store.group_stats("mode")}
    assert set(por_modo) == {"traducao", "ditado", "gramatica"}

    por_regra = {s.key: s for s in store.group_stats("direction")}
    assert set(por_regra) == {"g.plural"}, "direction nulo não vira grupo"


def test_coluna_fora_da_lista_e_recusada(store):
    """O nome entra direto no SQL — a lista fechada é a defesa."""
    with pytest.raises(ValueError):
        store.group_stats("item_id; DROP TABLE reviews")


def test_score_conta_quase_como_meio_acerto():
    stat = GroupStat(key="x", reviews=2, correct=1, almost=1, credit=1.5)
    assert stat.accuracy == 0.5
    assert stat.score == 0.75


def test_palavras_fracas_vem_ordenadas_pela_pior(store):
    log(store, "ro.facil", Verdict.CORRECT, n=5)
    log(store, "ro.media", Verdict.ALMOST, n=5)
    log(store, "ro.dificil", Verdict.WRONG, n=5)

    fracas = store.weak_items(min_reviews=3)
    assert [s.key for s in fracas] == ["ro.dificil", "ro.media"]


def test_palavra_perfeita_fica_fora_da_lista_de_fracas(store):
    log(store, "ro.perfeita", Verdict.CORRECT, n=9)
    assert store.weak_items(min_reviews=3) == []


def test_palavra_com_poucas_respostas_nao_conta_como_fraca(store):
    """Uma única resposta errada não faz de uma palavra o seu ponto fraco."""
    log(store, "ro.nova", Verdict.WRONG)
    assert store.weak_items(min_reviews=3) == []


def test_desempate_favorece_a_amostra_menor(store):
    """Errar 3 de 3 é sinal pior que errar 6 de 12, com o mesmo percentual."""
    log(store, "ro.pouco", Verdict.WRONG, n=3)
    log(store, "ro.muito", Verdict.WRONG, n=12)
    fracas = store.weak_items(min_reviews=3)
    assert [s.key for s in fracas] == ["ro.muito", "ro.pouco"]


def test_agrega_por_tema(store):
    from dor.core.models import VocabItem

    vocab = {
        "ro.a": VocabItem(id="ro.a", ro="a", pt=["a"], pos="noun", level="A1", tags=["casa"]),
        "ro.b": VocabItem(
            id="ro.b", ro="b", pt=["b"], pos="noun", level="A1", tags=["casa", "comida"]
        ),
    }
    log(store, "ro.a", Verdict.CORRECT, n=4)
    log(store, "ro.b", Verdict.WRONG, n=4)

    linhas = dict((tag, (n, score)) for tag, n, score in dash.by_tag(store.group_stats("item_id"), vocab))
    assert linhas["casa"] == (8, 0.5)
    assert linhas["comida"] == (4, 0.0), "uma palavra com duas tags entra nas duas"


def test_tema_sem_amostra_suficiente_fica_de_fora(store):
    from dor.core.models import VocabItem

    vocab = {"ro.a": VocabItem(id="ro.a", ro="a", pt=["a"], pos="noun", level="A1", tags=["raro"])}
    log(store, "ro.a", Verdict.CORRECT)
    assert dash.by_tag(store.group_stats("item_id"), vocab, min_reviews=3) == []


def test_temas_saem_do_pior_para_o_melhor(store):
    from dor.core.models import VocabItem

    vocab = {
        "ro.a": VocabItem(id="ro.a", ro="a", pt=["a"], pos="noun", level="A1", tags=["bom"]),
        "ro.b": VocabItem(id="ro.b", ro="b", pt=["b"], pos="noun", level="A1", tags=["ruim"]),
    }
    log(store, "ro.a", Verdict.CORRECT, n=4)
    log(store, "ro.b", Verdict.WRONG, n=4)
    assert [t for t, _, _ in dash.by_tag(store.group_stats("item_id"), vocab)] == ["ruim", "bom"]


# --------------------------------------------------------------------------- #
# horários
# --------------------------------------------------------------------------- #


def test_atividade_por_hora_usa_o_relogio_local(store):
    meia_noite_utc = datetime(2026, 8, 16, 0, 30, tzinfo=UTC)
    log(store, "ro.casa", Verdict.CORRECT, when=meia_noite_utc, n=2)
    horas = store.hour_activity()
    esperada = meia_noite_utc.astimezone().hour
    assert [(h, n) for h, n, _ in horas] == [(esperada, 2)]


def test_faixa_de_horas_tem_24_colunas():
    assert len(dash.hour_strip([(9, 5, 1.0)]).plain) == 24


def test_melhor_horario_ignora_amostra_pequena():
    """Uma única resposta certa às 4h não é conselho de estudo."""
    atividade = [(4, 1, 1.0), (21, 40, 0.8)]
    assert dash.best_hour(atividade, min_reviews=10) == (21, 40, 0.8)


def test_sem_amostra_nenhuma_nao_ha_melhor_horario():
    assert dash.best_hour([(4, 1, 1.0)], min_reviews=10) is None


def test_dias_com_estudo_conta_so_os_dias_com_revisao(store):
    hoje = date(2026, 8, 16)
    store.add_daily(hoje, xp=50, reviews=10, correct=8)
    store.add_daily(hoje - timedelta(days=1), xp=0, reviews=0, correct=0)
    assert store.review_days() == 1
