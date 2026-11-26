"""Acesso ao banco de progresso.

Um `Store` por processo. Toda escrita é confirmada na hora — não existe estado
de sessão só em memória esperando um "salvar". Fechar o terminal no meio de uma
sessão perde no máximo a resposta que estava sendo digitada.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from dor.core.grading import Grade
from dor.core.srs import Card, Rating
from dor.game import quests as quests_mod
from dor.game.quests import Quest
from dor.game.streaks import Streak
from dor.storage import db


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _row_to_card(row: sqlite3.Row) -> Card:
    return Card(
        item_id=row["item_id"],
        stability=row["stability"],
        difficulty=row["difficulty"],
        step=row["step"],
        state=row["state"],
        due_at=_parse(row["due_at"]),
        last_review=_parse(row["last_review"]),
        reps=row["reps"],
        lapses=row["lapses"],
        leech=bool(row["leech"]),
    )


@dataclass
class GroupStat:
    """Desempenho de um recorte qualquer — um item, um modo, uma regra."""

    key: str
    reviews: int
    correct: int
    almost: int
    credit: float
    last_ts: str | None = None

    @property
    def accuracy(self) -> float:
        return self.correct / self.reviews if self.reviews else 0.0

    @property
    def score(self) -> float:
        """Crédito médio. Conta o `quase` como meio acerto, igual à correção —
        senão errar o acento ficaria indistinguível de não saber a palavra."""
        return self.credit / self.reviews if self.reviews else 0.0


@dataclass
class SessionSummary:
    session_id: int
    mode: str
    items_seen: int
    correct: int
    credit_sum: float
    started_at: datetime

    @property
    def accuracy(self) -> float:
        return self.correct / self.items_seen if self.items_seen else 0.0


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.conn = db.connect(path)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- estado dos itens ---------------------------------------------------

    def get_card(self, item_id: str) -> Card:
        row = self.conn.execute(
            "SELECT * FROM items_state WHERE item_id = ?", (item_id,)
        ).fetchone()
        return _row_to_card(row) if row else Card(item_id=item_id)

    def save_card(self, card: Card) -> None:
        self.conn.execute(
            """
            INSERT INTO items_state
                (item_id, stability, difficulty, step, state, due_at,
                 last_review, reps, lapses, leech)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                stability   = excluded.stability,
                difficulty  = excluded.difficulty,
                step        = excluded.step,
                state       = excluded.state,
                due_at      = excluded.due_at,
                last_review = excluded.last_review,
                reps        = excluded.reps,
                lapses      = excluded.lapses,
                leech       = excluded.leech
            """,
            (
                card.item_id,
                card.stability,
                card.difficulty,
                card.step,
                int(card.state),
                _iso(card.due_at),
                _iso(card.last_review),
                card.reps,
                card.lapses,
                int(card.leech),
            ),
        )

    def due_item_ids(self, now: datetime | None = None, limit: int = 500) -> list[str]:
        now = now or datetime.now(UTC)
        rows = self.conn.execute(
            """
            SELECT item_id FROM items_state
            WHERE due_at IS NOT NULL AND due_at <= ?
            ORDER BY due_at ASC
            LIMIT ?
            """,
            (_iso(now), limit),
        ).fetchall()
        return [r["item_id"] for r in rows]

    def seen_item_ids(self) -> set[str]:
        rows = self.conn.execute("SELECT item_id FROM items_state").fetchall()
        return {r["item_id"] for r in rows}

    def session_modes(self) -> set[str]:
        """Que atividades já foram abertas alguma vez.

        A tela inicial usa isto para marcar o que o aluno ainda não
        experimentou — um app com doze modos que só sugere `dor review` é, na
        prática, um app de um modo só.
        """
        rows = self.conn.execute("SELECT DISTINCT mode FROM sessions").fetchall()
        return {r["mode"] for r in rows}

    def leech_item_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT item_id FROM items_state WHERE leech = 1 ORDER BY lapses DESC"
        ).fetchall()
        return [r["item_id"] for r in rows]

    def unleech(self, item_id: str | None = None) -> int:
        """Tira a marca de travado, de um item ou de todos.

        A marca é um diagnóstico do passado, não uma sentença: depois de
        estudar a palavra por fora, insistir em tratá-la como problemática
        mantém o item preso no modo mais fácil para sempre.
        """
        if item_id:
            cur = self.conn.execute(
                "UPDATE items_state SET leech = 0 WHERE item_id = ? AND leech = 1", (item_id,)
            )
        else:
            cur = self.conn.execute("UPDATE items_state SET leech = 0 WHERE leech = 1")
        return cur.rowcount

    def last_review(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM reviews ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def undo_last_review(self) -> dict[str, Any] | None:
        """Apaga a última resposta e recalcula o agendamento do item.

        Só a resposta some. O estado do cartão é REFEITO a partir do histórico
        que sobrou — reaplicar o agendador é a única forma de o intervalo voltar
        a ser coerente, já que ele depende de toda a sequência anterior.
        """
        review = self.last_review()
        if review is None:
            return None

        self.conn.execute("DELETE FROM reviews WHERE id = ?", (review["id"],))
        self._undo_bookkeeping(review)
        self._rebuild_card(review["item_id"])
        return review

    def _undo_bookkeeping(self, review: dict[str, Any]) -> None:
        """Desfaz o que a resposta somou fora da tabela de revisões."""
        day = _parse(review["ts"]).astimezone().date().isoformat()
        self.conn.execute(
            """
            UPDATE daily
               SET xp = MAX(0, xp - ?), reviews = MAX(0, reviews - 1),
                   correct = MAX(0, correct - ?)
             WHERE day = ?
            """,
            (review["xp"] or 0, int(review["verdict"] == "certo"), day),
        )
        if review["session_id"]:
            self.conn.execute(
                """
                UPDATE sessions
                   SET items_seen = MAX(0, items_seen - 1),
                       correct = MAX(0, correct - ?),
                       credit_sum = MAX(0, credit_sum - ?)
                 WHERE id = ?
                """,
                (int(review["verdict"] == "certo"), review["credit"], review["session_id"]),
            )

    def _rebuild_card(self, item_id: str) -> None:
        """Reaplica o agendador sobre o histórico restante do item."""
        from dor.core.srs import Card, get_scheduler

        rows = self.conn.execute(
            "SELECT rating, ts FROM reviews WHERE item_id = ? ORDER BY id", (item_id,)
        ).fetchall()

        if not rows:
            self.conn.execute("DELETE FROM items_state WHERE item_id = ?", (item_id,))
            return

        scheduler = get_scheduler()
        card = Card(item_id=item_id)
        for row in rows:
            card = scheduler.review(card, Rating(row["rating"]), _parse(row["ts"]))
        self.save_card(card)

    def forecast(self, days: int = 7, now: datetime | None = None) -> list[tuple[str, int]]:
        """Quantas revisões vencem por dia — mata a surpresa de acordar com 300."""
        now = now or datetime.now(UTC)
        out: list[tuple[str, int]] = []
        for offset in range(days):
            start = (now + timedelta(days=offset)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(days=1)
            n = self.conn.execute(
                "SELECT COUNT(*) FROM items_state WHERE due_at >= ? AND due_at < ?",
                (_iso(start), _iso(end)),
            ).fetchone()[0]
            out.append((start.date().isoformat(), n))
        return out

    # --- histórico ----------------------------------------------------------

    def log_review(
        self,
        item_id: str,
        *,
        mode: str,
        rating: Rating,
        grade: Grade,
        direction: str | None = None,
        latency_ms: int | None = None,
        session_id: int | None = None,
        xp: int = 0,
        now: datetime | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO reviews
                (item_id, mode, direction, rating, verdict, credit,
                 latency_ms, answer_given, session_id, xp, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                mode,
                direction,
                int(rating),
                str(grade.verdict),
                grade.credit,
                latency_ms,
                grade.given,
                session_id,
                xp,
                _iso(now or datetime.now(UTC)),
            ),
        )
        return int(cur.lastrowid)

    def set_review_xp(self, review_id: int, xp: int) -> None:
        """O XP só é conhecido depois da correção, então entra num segundo passo."""
        self.conn.execute("UPDATE reviews SET xp = ? WHERE id = ?", (xp, review_id))

    # --- sessões ------------------------------------------------------------

    def start_session(self, mode: str, now: datetime | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (mode, started_at) VALUES (?, ?)",
            (mode, _iso(now or datetime.now(UTC))),
        )
        return int(cur.lastrowid)

    def bump_session(self, session_id: int, *, correct: bool, credit: float) -> None:
        """Atualiza o contador a cada resposta, não no fim.

        É o que faz uma sessão interrompida continuar contando o que já foi feito.
        """
        self.conn.execute(
            """
            UPDATE sessions
               SET items_seen = items_seen + 1,
                   correct    = correct + ?,
                   credit_sum = credit_sum + ?
             WHERE id = ?
            """,
            (1 if correct else 0, credit, session_id),
        )

    def end_session(self, session_id: int, now: datetime | None = None) -> SessionSummary:
        self.conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (_iso(now or datetime.now(UTC)), session_id),
        )
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return SessionSummary(
            session_id=row["id"],
            mode=row["mode"],
            items_seen=row["items_seen"],
            correct=row["correct"],
            credit_sum=row["credit_sum"],
            started_at=_parse(row["started_at"]),
        )

    # --- gamificação --------------------------------------------------------

    def add_daily(
        self,
        day: date,
        *,
        xp: int = 0,
        reviews: int = 0,
        correct: int = 0,
        seconds: int = 0,
        goal_xp: int | None = None,
    ) -> int:
        """Acumula o dia e devolve o XP total dele."""
        self.conn.execute(
            """
            INSERT INTO daily (day, xp, reviews, correct, seconds)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
                xp      = xp + excluded.xp,
                reviews = reviews + excluded.reviews,
                correct = correct + excluded.correct,
                seconds = seconds + excluded.seconds
            """,
            (day.isoformat(), xp, reviews, correct, seconds),
        )
        total = self.conn.execute(
            "SELECT xp FROM daily WHERE day = ?", (day.isoformat(),)
        ).fetchone()[0]
        if goal_xp is not None:
            self.conn.execute(
                "UPDATE daily SET goal_met = ? WHERE day = ?",
                (1 if total >= goal_xp else 0, day.isoformat()),
            )
        return int(total)

    def daily_row(self, day: date) -> dict[str, int]:
        row = self.conn.execute("SELECT * FROM daily WHERE day = ?", (day.isoformat(),)).fetchone()
        if row is None:
            return {"xp": 0, "reviews": 0, "correct": 0, "seconds": 0, "goal_met": 0}
        return {k: row[k] for k in ("xp", "reviews", "correct", "seconds", "goal_met")}

    def daily_history(self, days: int = 365) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            "SELECT day, xp FROM daily ORDER BY day DESC LIMIT ?", (days,)
        ).fetchall()
        return [(r["day"], r["xp"]) for r in reversed(rows)]

    def total_xp(self) -> int:
        return int(self.conn.execute("SELECT COALESCE(SUM(xp), 0) FROM daily").fetchone()[0])

    def get_streak(self) -> Streak:
        row = self.conn.execute("SELECT * FROM streak WHERE id = 1").fetchone()
        return Streak(
            current=row["current"],
            longest=row["longest"],
            freezes=row["freezes"],
            last_active=date.fromisoformat(row["last_active"]) if row["last_active"] else None,
        )

    def save_streak(self, streak: Streak) -> None:
        self.conn.execute(
            """
            UPDATE streak
               SET current = ?, longest = ?, freezes = ?, last_active = ?
             WHERE id = 1
            """,
            (
                streak.current,
                streak.longest,
                streak.freezes,
                streak.last_active.isoformat() if streak.last_active else None,
            ),
        )

    def load_quests(self, day: date) -> list[Quest]:
        """Carrega as quests do dia, criando-as na primeira vez."""
        rows = self.conn.execute(
            "SELECT * FROM quests WHERE day = ? ORDER BY code", (day.isoformat(),)
        ).fetchall()

        if not rows:
            for template in quests_mod.for_day(day):
                self.conn.execute(
                    "INSERT INTO quests (day, code, target, reward_xp) VALUES (?, ?, ?, ?)",
                    (day.isoformat(), template.code, template.target, template.reward_xp),
                )
            rows = self.conn.execute(
                "SELECT * FROM quests WHERE day = ? ORDER BY code", (day.isoformat(),)
            ).fetchall()

        out = []
        for row in rows:
            template = quests_mod.BY_CODE.get(row["code"])
            out.append(
                Quest(
                    code=row["code"],
                    title=template.title if template else row["code"],
                    target=row["target"],
                    reward_xp=row["reward_xp"],
                    progress=row["progress"],
                    done=bool(row["done"]),
                    template=template,
                )
            )
        return out

    def save_quest(self, day: date, quest: Quest) -> None:
        self.conn.execute(
            "UPDATE quests SET progress = ?, done = ? WHERE day = ? AND code = ?",
            (quest.progress, int(quest.done), day.isoformat(), quest.code),
        )

    def unlocked_achievements(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT code, unlocked_at FROM achievements").fetchall()
        return {r["code"]: r["unlocked_at"] for r in rows}

    def unlock_achievement(self, code: str, now: datetime | None = None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO achievements (code, unlocked_at) VALUES (?, ?)",
            (code, _iso(now or datetime.now(UTC))),
        )

    def achievement_context_counts(self) -> dict[str, int]:
        """Contagens acumuladas que as conquistas consultam."""
        c = self.conn
        romanian = c.execute(
            """
            SELECT COUNT(*) FROM reviews
             WHERE verdict = 'certo'
               AND (direction IN ('pt_ro', 'cloze') OR mode = 'gramatica')
            """
        ).fetchone()[0]
        gender = c.execute(
            "SELECT COUNT(*) FROM reviews WHERE verdict = 'certo' AND direction LIKE 'g.gen%'"
        ).fetchone()[0]
        return {
            "total_reviews": c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
            "total_correct": c.execute(
                "SELECT COUNT(*) FROM reviews WHERE verdict = 'certo'"
            ).fetchone()[0],
            "words_seen": c.execute("SELECT COUNT(*) FROM items_state").fetchone()[0],
            "romanian_correct": romanian,
            "gender_correct": gender,
        }

    # --- estatísticas -------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        c = self.conn
        total_reviews = c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        correct = c.execute("SELECT COUNT(*) FROM reviews WHERE verdict = 'certo'").fetchone()[0]
        almost = c.execute("SELECT COUNT(*) FROM reviews WHERE verdict = 'quase'").fetchone()[0]
        by_state = {
            row["state"]: row["n"]
            for row in c.execute(
                "SELECT state, COUNT(*) AS n FROM items_state GROUP BY state"
            ).fetchall()
        }
        return {
            "itens_em_estudo": c.execute("SELECT COUNT(*) FROM items_state").fetchone()[0],
            "revisões": total_reviews,
            "certas": correct,
            "quase": almost,
            "acurácia": correct / total_reviews if total_reviews else 0.0,
            "vencendo_agora": len(self.due_item_ids()),
            "leeches": len(self.leech_item_ids()),
            "aprendendo": by_state.get(1, 0),
            "revisão": by_state.get(2, 0),
            "reaprendendo": by_state.get(3, 0),
            "sessões": c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
        }

    #: Colunas de `reviews` pelas quais o painel pode agrupar. Lista fechada
    #: porque o nome entra direto no SQL — não há como parametrizar identificador.
    GROUPABLE = frozenset({"item_id", "mode", "direction"})

    def group_stats(self, column: str, *, min_reviews: int = 1) -> list[GroupStat]:
        """Desempenho agrupado por item, modo ou regra de gramática.

        É daqui que sai tudo que o painel mostra como "onde você tropeça":
        item_id vira palavra fraca, direction vira regra fraca.
        """
        if column not in self.GROUPABLE:
            raise ValueError(f"coluna não agrupável: {column}")
        rows = self.conn.execute(
            f"""
            SELECT {column} AS key,
                   COUNT(*) AS n,
                   SUM(verdict = 'certo') AS certo,
                   SUM(verdict = 'quase') AS quase,
                   SUM(credit) AS credit,
                   MAX(ts) AS last_ts
              FROM reviews
             WHERE {column} IS NOT NULL
             GROUP BY {column}
            HAVING n >= ?
            """,
            (min_reviews,),
        ).fetchall()
        return [
            GroupStat(
                key=row["key"],
                reviews=row["n"],
                correct=row["certo"] or 0,
                almost=row["quase"] or 0,
                credit=row["credit"] or 0.0,
                last_ts=row["last_ts"],
            )
            for row in rows
        ]

    def weak_items(self, *, min_reviews: int = 3, limit: int = 5) -> list[GroupStat]:
        """As palavras que mais custam. Ordena pelo crédito médio e desempata
        pelo volume — errar 3 de 3 é pior sinal que errar 3 de 12."""
        stats = [s for s in self.group_stats("item_id", min_reviews=min_reviews) if s.score < 1.0]
        stats.sort(key=lambda s: (s.score, -s.reviews))
        return stats[:limit]

    def hour_activity(self) -> list[tuple[int, int, float]]:
        """(hora local, revisões, acurácia) — para descobrir seu melhor horário.

        A conversão para hora local é feita em Python de propósito: o `ts` é UTC
        e o modificador 'localtime' do SQLite depende do fuso do processo, o que
        deixaria o resultado impossível de testar.
        """
        buckets: dict[int, list[int]] = {}
        for ts, verdict in self.conn.execute("SELECT ts, verdict FROM reviews").fetchall():
            when = _parse(ts)
            if when is None:
                continue
            hour = when.astimezone().hour
            slot = buckets.setdefault(hour, [0, 0])
            slot[0] += 1
            slot[1] += verdict == "certo"
        return [(h, n, c / n) for h, (n, c) in sorted(buckets.items())]

    def review_days(self) -> int:
        """Dias distintos com alguma revisão — o denominador honesto da média."""
        return int(self.conn.execute("SELECT COUNT(*) FROM daily WHERE reviews > 0").fetchone()[0])
