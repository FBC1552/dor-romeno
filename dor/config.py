"""Caminhos, constantes e ajustes do usuário.

Dados de conteúdo (JSON) vivem no repositório; dados do usuário (progresso,
cache de áudio, exports) vivem no diretório de aplicação do sistema, para que
atualizar o repo nunca apague o progresso.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "dor"

# --- conteúdo (versionado no repo) ------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent
DATA_DIR = Path(os.environ.get("DOR_DATA_DIR", REPO_DIR / "data"))

SCHEMA_DIR = DATA_DIR / "schema"
VOCAB_DIR = DATA_DIR / "vocabulary"
SENTENCE_DIR = DATA_DIR / "sentences"
GRAMMAR_DIR = DATA_DIR / "grammar"
CULTURE_DIR = DATA_DIR / "culture"
BRIDGE_DIR = DATA_DIR / "bridges"
SLANG_DIR = CULTURE_DIR / "slang"
MUSIC_DIR = CULTURE_DIR / "music"
HISTORY_DIR = CULTURE_DIR / "history"
DAILY_DIR = CULTURE_DIR / "daily"
ART_DIR = DATA_DIR / "art"

# --- dados do usuário (fora do repo) ----------------------------------------
USER_DIR = Path(os.environ.get("DOR_USER_DIR", user_data_dir(APP_NAME, appauthor=False)))
DB_PATH = USER_DIR / "progress.db"
AUDIO_CACHE_DIR = USER_DIR / "audio_cache"
EXPORT_DIR = USER_DIR / "exports"
SETTINGS_PATH = USER_DIR / "settings.json"

#: Acervo pessoal: letra de música e trecho de jornal que o app usa mas NÃO
#: distribui. Mora junto com o progresso, fora do repositório, e por isso pode
#: guardar texto de terceiros inteiro — o que sai daqui não vai para lugar
#: nenhum. A trava de `core/quoting.py` continua valendo para `data/`, que é o
#: que o projeto publica.
LOCAL_DIR = USER_DIR / "conteudo"
INBOX_DIR = LOCAL_DIR / "inbox"

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

REGISTERS = ("formal", "neutru", "colocvial", "argou", "vulgar")

#: Cor por registro — o aviso visual que evita falar argou com o chefe.
REGISTER_STYLE = {
    "formal": "bright_blue",
    "neutru": "green",
    "colocvial": "yellow",
    "argou": "dark_orange",
    "vulgar": "red",
}

# "padrão" e não "neutro": o gênero gramatical neutro já ocupa essa palavra na
# UI, e as duas coisas aparecem lado a lado na ficha da palavra.
REGISTER_LABEL_PT = {
    "formal": "formal",
    "neutru": "padrão",
    "colocvial": "coloquial",
    "argou": "gíria",
    "vulgar": "vulgar",
}

#: Vozes neurais romenas do edge-tts.
VOICE_FEMALE = "ro-RO-AlinaNeural"
VOICE_MALE = "ro-RO-EmilNeural"
DEFAULT_VOICE = VOICE_FEMALE

#: Vozes em português, para a narração bilíngue dos episódios. Alternar timbre
#: entre os idiomas é o que impede o ouvido de tratar tudo como um bloco só.
VOICE_PT_FEMALE = "pt-BR-FranciscaNeural"
VOICE_PT_MALE = "pt-BR-AntonioNeural"


@dataclass
class Settings:
    """Preferências do usuário, persistidas em settings.json."""

    daily_goal_xp: int = 120
    voice: str = DEFAULT_VOICE
    rate: str = "-5%"
    autoplay: bool = True
    tts_provider: str = "auto"  # auto | edge | gtts | piper | off
    show_ipa: bool = True
    max_register: str = "vulgar"  # filtra conteúdo acima deste registro

    @classmethod
    def load(cls) -> Settings:
        if SETTINGS_PATH.exists():
            try:
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return cls()
            known = {f for f in cls.__dataclass_fields__}
            return cls(**{k: v for k, v in raw.items() if k in known})
        return cls()

    def save(self) -> None:
        ensure_user_dirs()
        SETTINGS_PATH.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )


def ensure_user_dirs() -> None:
    for d in (USER_DIR, AUDIO_CACHE_DIR, EXPORT_DIR, LOCAL_DIR, INBOX_DIR):
        d.mkdir(parents=True, exist_ok=True)


def force_utf8_console() -> None:
    """O console do Windows come ș/ț se não for empurrado para UTF-8."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
