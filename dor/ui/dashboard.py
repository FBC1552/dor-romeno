"""Widgets do painel de progresso.

Tudo aqui é função pura: recebe números e devolve `Text`/`Table`. Nada toca no
banco nem no relógio sem receber a data por parâmetro — é o que permite testar
o calendário sem esperar 90 dias passarem.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from rich.table import Table
from rich.text import Text

from dor.core.models import VocabItem
from dor.storage.repos import GroupStat

#: Escala do calendário. O nível é medido contra a META DIÁRIA, não contra o
#: melhor dia — senão baixar o ritmo repintaria o passado inteiro de verde.
HEAT_STYLES = ("grey30", "green4", "green3", "bright_green", "bold bright_green")
HEAT_THRESHOLDS = (0.01, 0.5, 1.0, 2.0)

WEEKDAY_LABELS = ("seg", "", "qua", "", "sex", "", "dom")
MONTHS_PT = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)

BLOCKS = " ▁▂▃▄▅▆▇█"


def heat_level(xp: int, goal: int) -> int:
    """0 = dia em branco; 4 = dobrou a meta."""
    if xp <= 0:
        return 0
    ratio = xp / goal if goal > 0 else 1.0
    return sum(1 for t in HEAT_THRESHOLDS if ratio >= t)


def accuracy_style(accuracy: float) -> str:
    if accuracy >= 0.85:
        return "ok"
    if accuracy >= 0.6:
        return "warn"
    return "err"


def bar(ratio: float, width: int = 16, style: str = "magenta") -> Text:
    filled = round(max(0.0, min(1.0, ratio)) * width)
    return Text("█" * filled, style=style) + Text("░" * (width - filled), style="grey30")


def sparkline(values: list[int]) -> str:
    peak = max(values, default=0) or 1
    return "".join(BLOCKS[min(8, round(v / peak * 8))] for v in values)


# --------------------------------------------------------------------------- #
# calendário
# --------------------------------------------------------------------------- #


def heatmap(
    history: list[tuple[str, int]],
    *,
    today: date,
    goal: int = 120,
    weeks: int = 13,
) -> list[Text]:
    """Calendário de constância: uma coluna por semana, uma linha por dia.

    Uma barra de XP diz quanto você fez hoje; só o calendário mostra o buraco
    de duas semanas em março. É a visão que a streak esconde ao zerar.
    """
    by_day = {day: xp for day, xp in history}
    # Segunda da coluna mais antiga: o grid sempre fecha em semanas inteiras.
    last_monday = today - timedelta(days=today.weekday())
    start = last_monday - timedelta(weeks=weeks - 1)

    header = [" "] * (weeks * 2)
    previous_month = None
    written_until = -1
    for col in range(weeks):
        month = (start + timedelta(weeks=col)).month
        if month != previous_month and col * 2 > written_until:
            for offset, char in enumerate(MONTHS_PT[month - 1]):
                if col * 2 + offset < len(header):
                    header[col * 2 + offset] = char
            written_until = col * 2 + 2
        previous_month = month

    lines = [Text("     " + "".join(header).rstrip(), style="dim")]

    for row in range(7):
        line = Text(f"{WEEKDAY_LABELS[row]:>4} ", style="dim")
        for col in range(weeks):
            day = start + timedelta(weeks=col, days=row)
            if day > today:
                line.append("  ")
                continue
            level = heat_level(by_day.get(day.isoformat(), 0), goal)
            line.append("■ ", style=HEAT_STYLES[level])
        lines.append(line)

    legend = Text("     menos ", style="dim")
    for style in HEAT_STYLES:
        legend.append("■", style=style)
    legend.append(" mais", style="dim")
    legend.append(f"   (verde forte = {goal} XP, a meta do dia)", style="hint")
    lines.append(legend)
    return lines


# --------------------------------------------------------------------------- #
# recortes de desempenho
# --------------------------------------------------------------------------- #


def by_tag(
    stats: list[GroupStat], vocab: dict[str, VocabItem], *, min_reviews: int = 3
) -> list[tuple[str, int, float]]:
    """(tema, revisões, crédito médio) — o desempenho lido por assunto.

    Uma palavra com três tags entra nas três: a pergunta que isso responde é
    "como vou em comida?", não "quanto da minha nota é comida?".
    """
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for stat in stats:
        item = vocab.get(stat.key)
        if item is None:
            continue
        for tag in item.tags:
            bucket = totals[tag]
            bucket[0] += stat.reviews
            bucket[1] += stat.credit
    rows = [
        (tag, int(n), credit / n) for tag, (n, credit) in totals.items() if n >= min_reviews
    ]
    rows.sort(key=lambda r: r[2])
    return rows


def domain_table(rows: list[tuple[str, int, float]], *, width: int = 16) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="pt", no_wrap=True)
    table.add_column()
    table.add_column(justify="right", style="dim")
    for label, reviews, score in rows:
        table.add_row(
            label,
            bar(score, width, style=accuracy_style(score)),
            f"{score:.0%}  ({reviews})",
        )
    return table


def weak_table(rows: list[tuple[str, str, GroupStat]]) -> Table:
    """As palavras que mais custam, com a tradução ao lado.

    Mostrar só o id não ajuda ninguém a estudar; mostrar a resposta junto
    transforma a lista de vergonha numa lista de revisão.
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="ro", no_wrap=True)
    table.add_column(style="pt")
    table.add_column(justify="right")
    table.add_column(justify="right", style="dim")
    for ro, pt, stat in rows:
        table.add_row(
            ro,
            pt,
            Text(f"{stat.score:.0%}", style=accuracy_style(stat.score)),
            f"{stat.reviews}×",
        )
    return table


def hour_strip(activity: list[tuple[int, int, float]]) -> Text:
    """Volume por hora do dia, 24 colunas. A hora mais produtiva salta à vista."""
    counts = {hour: n for hour, n, _ in activity}
    peak = max(counts.values(), default=0) or 1
    line = Text()
    for hour in range(24):
        n = counts.get(hour, 0)
        line.append(BLOCKS[min(8, round(n / peak * 8))], style="magenta" if n else "grey30")
    return line


def best_hour(
    activity: list[tuple[int, int, float]], *, min_reviews: int = 10
) -> tuple[int, int, float] | None:
    """A hora com melhor acurácia entre as que têm amostra suficiente.

    Sem o piso de amostra, uma única resposta certa às 4h viraria conselho.
    """
    candidates = [row for row in activity if row[1] >= min_reviews]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row[2], row[1]))
