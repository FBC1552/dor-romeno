"""Console compartilhado e helpers de estilo."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

from dor import config

DOR_THEME = Theme(
    {
        "ro": "bold bright_yellow",
        "pt": "bright_white",
        "hint": "dim italic",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "xp": "bold magenta",
        "reg.formal": config.REGISTER_STYLE["formal"],
        "reg.neutru": config.REGISTER_STYLE["neutru"],
        "reg.colocvial": config.REGISTER_STYLE["colocvial"],
        "reg.argou": config.REGISTER_STYLE["argou"],
        "reg.vulgar": config.REGISTER_STYLE["vulgar"],
    }
)

console = Console(theme=DOR_THEME)


def register_badge(register: str) -> Text:
    """Etiqueta colorida de registro — o aviso de 'não fale isso com o chefe'."""
    label = config.REGISTER_LABEL_PT.get(register, register)
    return Text(f" {label} ", style=f"reverse reg.{register}")


def etymology_note(etymology: str | None) -> str:
    if not etymology:
        return ""
    labels = {
        "latin": "latim — tem cognato em português",
        "slav": "eslavo — sem atalho, decore",
        "romani": "romani (cigano) — camada da gíria",
        "turc": "turco",
        "maghiar": "húngaro",
        "francez": "francês",
        "german": "alemão",
        "grec": "grego",
        "englez": "inglês",
        "necunoscut": "origem incerta",
    }
    return labels.get(etymology, etymology)
