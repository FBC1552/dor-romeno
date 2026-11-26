"""Síntese de fala em romeno, com cascata de provedores e cache permanente.

Cada áudio é sintetizado uma única vez na vida e guardado em disco indexado por
sha1(texto|voz|rate). Depois das primeiras sessões o app roda offline na
prática, o que é a defesa contra o provedor online sair do ar.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from dor import config


class TTSError(Exception):
    pass


class TTSProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def synth(self, text: str, out: Path, voice: str, rate: str) -> None: ...


def cache_path(text: str, voice: str, rate: str) -> Path:
    key = f"{text}|{voice}|{rate}".encode()
    digest = hashlib.sha1(key).hexdigest()
    return config.AUDIO_CACHE_DIR / f"{digest[:2]}" / f"{digest}.mp3"


class EdgeProvider:
    """Vozes neurais da Microsoft (ro-RO-AlinaNeural / ro-RO-EmilNeural)."""

    name = "edge"

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

    def synth(self, text: str, out: Path, voice: str, rate: str) -> None:
        import asyncio

        import edge_tts

        async def run() -> None:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(out))

        try:
            asyncio.run(run())
        except Exception as exc:  # rede fora, endpoint mudou, voz inválida
            raise TTSError(f"edge-tts falhou: {exc}") from exc


class GTTSProvider:
    """Fallback via Google Translate TTS. Uma voz só, sem controle de ritmo."""

    name = "gtts"

    def available(self) -> bool:
        try:
            import gtts  # noqa: F401
        except ImportError:
            return False
        return True

    def synth(self, text: str, out: Path, voice: str, rate: str) -> None:
        from gtts import gTTS

        try:
            gTTS(text=text, lang="ro", slow=rate.startswith("-")).save(str(out))
        except Exception as exc:
            raise TTSError(f"gTTS falhou: {exc}") from exc


PROVIDERS: list[TTSProvider] = [EdgeProvider(), GTTSProvider()]


def available_providers() -> list[str]:
    return [p.name for p in PROVIDERS if p.available()]


def synthesize(
    text: str,
    *,
    voice: str | None = None,
    rate: str | None = None,
    provider: str = "auto",
    force: bool = False,
) -> Path:
    """Devolve o caminho do MP3, sintetizando só se não estiver em cache."""
    settings = config.Settings.load()
    voice = voice or settings.voice
    rate = rate if rate is not None else settings.rate

    config.ensure_user_dirs()
    out = cache_path(text, voice, rate)
    if out.exists() and not force:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    candidates = [p for p in PROVIDERS if provider in ("auto", p.name)]
    if not candidates:
        raise TTSError(f"provedor desconhecido: {provider}")

    errors: list[str] = []
    for p in candidates:
        if not p.available():
            errors.append(f"{p.name}: não instalado")
            continue
        try:
            p.synth(text, out, voice, rate)
        except TTSError as exc:
            errors.append(str(exc))
            out.unlink(missing_ok=True)
            continue
        if out.exists() and out.stat().st_size > 0:
            return out
        errors.append(f"{p.name}: saída vazia")
        out.unlink(missing_ok=True)

    raise TTSError("nenhum provedor conseguiu sintetizar:\n  " + "\n  ".join(errors))


def play(path: Path, *, blocking: bool = True) -> None:
    """Toca o arquivo. Usa pygame se disponível; senão cai no player do SO."""
    try:
        import pygame
    except ImportError:
        _play_with_os(path)
        return

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        if blocking:
            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy():
                clock.tick(30)
    except Exception:
        _play_with_os(path)


def _play_with_os(path: Path) -> None:
    if sys.platform == "win32":
        import os

        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["afplay", str(path)], check=False)
    else:
        player = shutil.which("mpv") or shutil.which("ffplay") or shutil.which("aplay")
        if player:
            subprocess.run([player, str(path)], check=False)


def prewarm(
    texts: list[str],
    *,
    voice: str | None = None,
    rate: str | None = None,
    on_progress=None,
) -> tuple[int, int]:
    """Sintetiza tudo antes da sessão começar.

    Sem isso, cada pergunta de um modo de escuta paga a latência da rede na
    frente do usuário. Devolve (quantos foram sintetizados agora, quantos
    falharam) — os que já estavam em cache não contam.
    """
    # Resolve os padrões uma vez, senão o cache_path daqui e o de dentro do
    # synthesize podem divergir e o "já estava em cache" mente.
    settings = config.Settings.load()
    voice = voice or settings.voice
    rate = rate if rate is not None else settings.rate

    synthesized = failed = 0
    for i, text in enumerate(texts):
        try:
            existed = cache_path(text, voice, rate).exists()
            synthesize(text, voice=voice, rate=rate)
            if not existed:
                synthesized += 1
        except TTSError:
            failed += 1
        if on_progress:
            on_progress(i + 1, len(texts))
    return synthesized, failed


def cache_stats() -> tuple[int, int]:
    """(quantidade de arquivos, bytes totais) no cache de áudio."""
    if not config.AUDIO_CACHE_DIR.exists():
        return 0, 0
    files = list(config.AUDIO_CACHE_DIR.rglob("*.mp3"))
    return len(files), sum(f.stat().st_size for f in files)
