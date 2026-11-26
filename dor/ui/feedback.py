"""Renderização do veredito.

Separado de `core.grading` de propósito: o motor de correção não conhece Rich e
pode ser testado sem terminal nenhum.
"""

from __future__ import annotations

from rich.text import Text

from dor.core.grading import Grade, Verdict
from dor.core.normalize import fold, normalize

VERDICT_STYLE = {
    Verdict.CORRECT: "bold green",
    Verdict.ALMOST: "bold yellow",
    Verdict.WRONG: "bold red",
}

VERDICT_MARK = {
    Verdict.CORRECT: "✓",
    Verdict.ALMOST: "≈",
    Verdict.WRONG: "✗",
}

VERDICT_LABEL = {
    Verdict.CORRECT: "certo",
    Verdict.ALMOST: "quase",
    Verdict.WRONG: "errado",
}


def highlight_correction(given: str, target: str) -> Text:
    """Mostra o alvo com os caracteres que diferem realçados.

    Quando os dois só diferem por diacrítico, o comprimento é igual e dá para
    apontar o caractere exato — que é o feedback que faz o acento ser aprendido.
    """
    out = Text()
    g, t = normalize(given), normalize(target)

    if fold(g) != fold(t) or len(g) != len(t):
        # Palavras diferentes: realçar caractere a caractere seria ruído.
        out.append(target, style="bold green")
        return out

    for gc, tc in zip(g, t, strict=False):
        out.append(tc, style="bold reverse yellow" if gc != tc else "green")
    return out


def render(grade: Grade, *, show_target: bool = True) -> Text:
    """Linha de feedback pronta para imprimir."""
    style = VERDICT_STYLE[grade.verdict]
    out = Text()
    out.append(f"{VERDICT_MARK[grade.verdict]} ", style=style)
    out.append(VERDICT_LABEL[grade.verdict], style=style)
    if grade.is_almost or grade.hinted:
        out.append(f" ({grade.credit:.0%})", style="magenta")
    if grade.hinted:
        out.append("  com dica", style="dim")

    if grade.verdict is Verdict.CORRECT:
        if show_target:
            out.append("   ")
            out.append(grade.target, style="bold green")
        # Acerto por equivalência ainda merece a forma da ficha: é ela que vai
        # voltar na próxima revisão e no áudio.
        if grade.loose and grade.hint:
            out.append(f"\n   {grade.hint}", style="dim italic")
        return out

    out.append("   ")
    if grade.diacritics_only:
        out.append_text(highlight_correction(grade.given, grade.target))
    else:
        out.append(grade.given, style="strike dim red")
        out.append("  →  ")
        out.append(grade.target, style="bold green")

    if grade.hint:
        out.append(f"\n   {grade.hint}", style="dim italic")

    return out


# --------------------------------------------------------------------------- #
# recompensas
# --------------------------------------------------------------------------- #


def render_reward(reward) -> Text:
    """Sufixo curto na linha do veredito: XP, combo e bônus.

    Mostra só o XP DA RESPOSTA. O bônus de missão sai na linha da própria
    missão — somá-lo aqui faria uma resposta errada exibir '+35 XP'.
    """
    out = Text()
    if not reward.breakdown.total:
        return out

    out.append(f"   +{reward.breakdown.total} XP", style="xp")
    if reward.combo >= 2:
        out.append(f"  ×{reward.breakdown.combo_mult:.1f} combo {reward.combo}", style="magenta")
    if reward.breakdown.fast:
        out.append("  ⚡", style="yellow")
    if reward.breakdown.leech_recovery:
        out.append("  ♻ recuperada", style="bold green")
    return out


def render_unlocks(reward) -> list[Text]:
    """Linhas extras para quest concluída, nível novo e conquista."""
    lines: list[Text] = []
    if reward.leveled_up:
        lines.append(Text(f"  ⬆  NÍVEL {reward.leveled_up}", style="bold magenta"))
    for quest in reward.quests_done:
        lines.append(
            Text("  ✔ missão  ", style="bold cyan")
            + Text(quest.title, style="pt")
            + Text(f"  +{quest.reward_xp} XP", style="xp")
        )
    for achievement in reward.achievements:
        lines.append(
            Text("  ★ conquista  ", style="bold yellow")
            + Text(achievement.title, style="bold")
            + Text(f"  — {achievement.description}", style="hint")
        )
    return lines


def xp_bar(ratio: float, width: int = 24) -> Text:
    filled = round(max(0.0, min(1.0, ratio)) * width)
    return Text("█" * filled, style="magenta") + Text("░" * (width - filled), style="dim")


def render_outcome(summary, outcome, quests) -> Text:
    """Painel de fim de sessão."""
    from dor.game import xp as xp_mod

    out = Text()
    out.append("\nsessão encerrada  ", style="bold")
    out.append(f"{summary.correct}/{summary.items_seen} certas", style="ok")
    out.append(f"  ({summary.accuracy:.0%})", style="dim")
    out.append(f"  +{outcome.xp_total} XP", style="xp")
    if outcome.combo_max >= 3:
        out.append(f"  melhor combo {outcome.combo_max}", style="magenta")
    out.append("\n")

    progress = xp_mod.progress(outcome.xp_lifetime)
    out.append("\n  nível ", style="dim")
    out.append(str(progress.level), style="bold magenta")
    out.append("  ")
    out.append_text(xp_bar(progress.ratio))
    out.append(f"  {progress.xp_into_level}/{progress.xp_for_next}\n", style="dim")

    if outcome.streak and not outcome.streak.already_today:
        update = outcome.streak
        out.append("  streak ", style="dim")
        out.append(f"{update.streak.current} dia(s)", style="bold ok")
        if update.frozen_days:
            out.append(f"  ❄ {update.frozen_days} dia(s) coberto(s) por escudo", style="cyan")
        if update.freeze_earned:
            out.append("  ❄ +1 escudo", style="bold cyan")
        if update.broke:
            out.append("  (recomeçou)", style="warn")
        out.append(f"  · escudos: {update.streak.freezes}\n", style="dim")

    goal_ratio = outcome.daily_xp / outcome.goal_xp if outcome.goal_xp else 1.0
    out.append("  meta   ", style="dim")
    out.append_text(xp_bar(goal_ratio))
    out.append(f"  {outcome.daily_xp}/{outcome.goal_xp} XP hoje", style="dim")
    if outcome.goal_met:
        out.append("  ✓ batida!", style="bold ok")
    out.append("\n")

    pendentes = [q for q in quests if not q.done]
    if pendentes:
        out.append("\n  missões de hoje\n", style="bold")
        for quest in pendentes:
            out.append("    ")
            out.append_text(xp_bar(quest.ratio, width=12))
            out.append(f"  {quest.progress}/{quest.target}  ", style="dim")
            out.append(quest.title, style="pt")
            out.append(f"  +{quest.reward_xp}\n", style="dim xp")

    return out
