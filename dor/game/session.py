"""Camada de jogo por cima de uma sessão de estudo.

Junta XP, combo, quests, streak e conquistas num objeto só, para que o loop do
CLI não precise saber de nada disso. Tudo é gravado a cada resposta — sessão
interrompida mantém o XP e o progresso das quests já conquistados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from dor import config
from dor.game import achievements, streaks, xp
from dor.game.achievements import Achievement
from dor.game.quests import Quest, ReviewEvent, apply_event
from dor.modes.base import Answered
from dor.storage.repos import Store


@dataclass
class Reward:
    """O que uma única resposta rendeu."""

    xp: int
    combo: int
    breakdown: xp.XPBreakdown
    quests_done: list[Quest] = field(default_factory=list)
    achievements: list[Achievement] = field(default_factory=list)
    leveled_up: int | None = None


@dataclass
class SessionOutcome:
    xp_total: int
    """XP ganho NESTA sessão."""
    xp_lifetime: int
    """XP acumulado de todos os tempos — é dele que sai o nível."""
    combo_max: int
    quests_done: list[Quest]
    achievements: list[Achievement]
    streak: streaks.StreakUpdate | None
    level_before: int
    level_after: int
    daily_xp: int
    goal_xp: int

    @property
    def goal_met(self) -> bool:
        return self.daily_xp >= self.goal_xp


class GameSession:
    """Estado de jogo de uma sessão em andamento."""

    def __init__(self, store: Store, *, settings: config.Settings | None = None) -> None:
        self.store = store
        self.settings = settings or config.Settings.load()
        self.combo = 0
        self.combo_max = 0
        self.xp_total = 0
        self.items = 0
        self.correct = 0
        self.leech_recovered = 0
        self.quests_done: list[Quest] = []
        self.achievements: list[Achievement] = []
        self.level_before = xp.level_from_xp(store.total_xp())
        self._quest_day: object | None = None
        self.quests: list[Quest] = []

    def _load_quests(self, today) -> list[Quest]:
        if self._quest_day != today:
            self.quests = self.store.load_quests(today)
            self._quest_day = today
        return self.quests

    def record(self, answered: Answered, now: datetime) -> Reward:
        """Pontua uma resposta já corrigida, agendada e gravada."""
        today = now.astimezone().date()
        grade = answered.grade
        card_before = answered.card_before

        breakdown = xp.compute(
            mode=answered.exercise.mode,
            direction=answered.exercise.direction,
            credit=grade.credit,
            latency_ms=answered.latency_ms,
            card_before=card_before,
            combo=self.combo,
        )

        combo_before = self.combo
        if grade.ok:
            self.combo += 1
            self.combo_max = max(self.combo_max, self.combo)
            self.correct += 1
        else:
            self.combo = 0

        self.items += 1
        self.xp_total += breakdown.total
        if breakdown.leech_recovery:
            self.leech_recovered += 1

        event = ReviewEvent(
            mode=answered.exercise.mode,
            direction=answered.exercise.direction,
            verdict=grade.verdict,
            diacritics_only=grade.diacritics_only,
            was_new=card_before.is_new,
            was_leech=card_before.leech,
            latency_ms=answered.latency_ms,
            combo=combo_before,
        )

        quests = self._load_quests(today)
        completed = apply_event(quests, event)
        bonus = sum(q.reward_xp for q in completed)
        for quest in quests:
            self.store.save_quest(today, quest)
        self.quests_done.extend(completed)

        gained = breakdown.total + bonus
        self.xp_total += bonus
        self.store.set_review_xp(answered.review_id, gained)

        level_before = xp.level_from_xp(self.store.total_xp())
        self.store.add_daily(
            today,
            xp=gained,
            reviews=1,
            correct=1 if grade.ok else 0,
            goal_xp=self.settings.daily_goal_xp,
        )
        level_after = xp.level_from_xp(self.store.total_xp())

        unlocked = self._check_achievements(now)

        return Reward(
            xp=gained,
            combo=self.combo,
            breakdown=breakdown,
            quests_done=completed,
            achievements=unlocked,
            leveled_up=level_after if level_after > level_before else None,
        )

    def _check_achievements(self, now: datetime) -> list[Achievement]:
        counts = self.store.achievement_context_counts()
        streak = self.store.get_streak()
        context = achievements.Context(
            streak_current=streak.current,
            combo_max_session=self.combo_max,
            session_items=self.items,
            session_correct=self.correct,
            leech_recovered=self.leech_recovered,
            now=now,
            **counts,
        )
        new = achievements.check(context, set(self.store.unlocked_achievements()))
        for item in new:
            self.store.unlock_achievement(item.code, now)
        self.achievements.extend(new)
        return new

    def finish(self, now: datetime) -> SessionOutcome:
        """Fecha a sessão: registra o dia na streak e reavalia as conquistas."""
        today = now.astimezone().date()

        streak_update = None
        if self.items:
            update = streaks.touch(self.store.get_streak(), today)
            self.store.save_streak(update.streak)
            streak_update = update
            self._check_achievements(now)

        return SessionOutcome(
            xp_total=self.xp_total,
            xp_lifetime=self.store.total_xp(),
            combo_max=self.combo_max,
            quests_done=self.quests_done,
            achievements=self.achievements,
            streak=streak_update,
            level_before=self.level_before,
            level_after=xp.level_from_xp(self.store.total_xp()),
            daily_xp=self.store.daily_row(today)["xp"],
            goal_xp=self.settings.daily_goal_xp,
        )
