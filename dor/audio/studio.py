"""Montagem de episódios de áudio.

O planejamento (`plan`) é puro: decide o roteiro sem tocar em rede nem em disco,
o que o torna testável e permite mostrar o episódio antes de gastar minutos
sintetizando. A montagem (`render`) sintetiza cada fala, aproveita o cache
permanente e junta tudo num MP3.

Não usamos pydub: ele depende de `audioop`, removido do Python 3.13 (PEP 594).
Falamos direto com o ffmpeg — que vem por pip via `imageio-ffmpeg`, sem exigir
instalação no sistema — e lemos duração e tags com `mutagen`.
"""

from __future__ import annotations

import random
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dor import config
from dor.audio import tts
from dor.core.loader import Library, filter_vocab
from dor.core.models import VocabItem

#: Parâmetros de saída. Voz falada não ganha nada acima disso e o arquivo
#: precisa caber no celular.
SAMPLE_RATE = 24000
CHANNELS = 1
BITRATE = "64k"

#: Estimativa de fala para prever a duração antes de sintetizar. Aferido contra
#: as vozes do edge-tts em ritmo normal; a duração real é medida depois.
CHARS_PER_SECOND = 13.5

MODES = ("drill", "passive", "sleep")


class StudioError(Exception):
    pass


@dataclass
class Segment:
    text: str
    lang: str
    voice: str
    rate: str = "+0%"
    pause_ms: int = 300
    label: str = ""

    def estimated_seconds(self) -> float:
        return len(self.text) / CHARS_PER_SECOND + self.pause_ms / 1000


@dataclass
class Episode:
    title: str
    theme: str
    mode: str
    number: int
    segments: list[Segment] = field(default_factory=list)
    item_ids: list[str] = field(default_factory=list)

    @property
    def estimated_seconds(self) -> float:
        return sum(s.estimated_seconds() for s in self.segments)

    @property
    def romanian_texts(self) -> list[str]:
        return [s.text for s in self.segments if s.lang == "ro"]


@dataclass
class RenderResult:
    path: Path
    seconds: float
    segments: int
    transcript: Path | None = None


# --------------------------------------------------------------------------- #
# planejamento
# --------------------------------------------------------------------------- #


def _ro(text: str, voice: str, rate: str = "+0%", pause_ms: int = 300, label: str = "") -> Segment:
    return Segment(text, "ro", voice, rate, pause_ms, label)


def _pt(text: str, voice: str, rate: str = "+0%", pause_ms: int = 300, label: str = "") -> Segment:
    return Segment(text, "pt", voice, rate, pause_ms, label)


def _drill_block(item: VocabItem, pause_ms: int) -> list[Segment]:
    """RO → silêncio para responder → PT → RO devagar, com timbre trocado.

    A pausa vem ANTES da tradução de propósito: é a janela em que o ouvinte
    tenta lembrar sozinho. Entregar o português antes disso transforma o
    episódio em audiolivro.
    """
    return [
        _ro(item.ro, config.VOICE_FEMALE, pause_ms=pause_ms, label="alvo"),
        _pt(item.pt_main, config.VOICE_PT_FEMALE, pause_ms=400, label="tradução"),
        _ro(item.ro, config.VOICE_MALE, rate="-20%", pause_ms=700, label="confirmação"),
    ]


def _passive_block(item: VocabItem, index: int) -> list[Segment]:
    """Só romeno, alternando as vozes. Para ouvir lavando louça."""
    voice = config.VOICE_FEMALE if index % 2 == 0 else config.VOICE_MALE
    return [_ro(item.ro, voice, pause_ms=500, label="alvo")]


def _sleep_block(item: VocabItem) -> list[Segment]:
    """Devagar, repetido, com pausas longas."""
    return [
        _ro(item.ro, config.VOICE_FEMALE, rate="-30%", pause_ms=900, label="alvo"),
        _ro(item.ro, config.VOICE_MALE, rate="-30%", pause_ms=900, label="eco"),
        _pt(item.pt_main, config.VOICE_PT_FEMALE, rate="-15%", pause_ms=1200, label="tradução"),
    ]


def items_for_seconds(items: list[VocabItem], mode: str, seconds: float, pause_ms: int) -> int:
    """Quantos itens cabem no tempo pedido, pela estimativa de fala."""
    if not items:
        return 0
    sample = _block(items[0], mode, 0, pause_ms)
    per_item = sum(s.estimated_seconds() for s in sample) or 1.0
    return max(1, min(len(items), int(seconds / per_item)))


def _block(item: VocabItem, mode: str, index: int, pause_ms: int) -> list[Segment]:
    if mode == "drill":
        return _drill_block(item, pause_ms)
    if mode == "passive":
        return _passive_block(item, index)
    if mode == "sleep":
        return _sleep_block(item)
    raise StudioError(f"modo desconhecido: {mode}")


def plan(
    lib: Library,
    *,
    mode: str = "drill",
    theme: str | None = None,
    deck: str | None = None,
    level: str | None = None,
    pos: str | None = None,
    count: int | None = None,
    minutes: float | None = None,
    pause_ms: int = 1800,
    number: int = 1,
    rng: random.Random | None = None,
) -> Episode:
    """Monta o roteiro. Não sintetiza nada — só decide o que será falado."""
    if mode not in MODES:
        raise StudioError(f"modo desconhecido: {mode} (use {', '.join(MODES)})")

    rng = rng or random.Random()
    pool = filter_vocab(lib, level=level, deck=deck, tag=theme, pos=pos)
    if not pool:
        raise StudioError("nenhum item bate com esse filtro")

    rng.shuffle(pool)

    if count is None:
        count = (
            items_for_seconds(pool, mode, minutes * 60, pause_ms) if minutes else min(15, len(pool))
        )
    chosen = pool[: max(1, count)]

    label = theme or deck or level or "geral"
    title = f"Episódio {number} · {label}"

    segments: list[Segment] = []
    if mode != "passive":
        segments.append(
            _pt(
                f"Episódio {number}. Tema: {label}. "
                f"{'Ouça, tente lembrar, e confira.' if mode == 'drill' else 'Relaxe e apenas ouça.'}",
                config.VOICE_PT_FEMALE,
                pause_ms=900,
                label="intro",
            )
        )

    for index, item in enumerate(chosen):
        segments.extend(_block(item, mode, index, pause_ms))

    if mode != "passive":
        segments.append(
            _pt("Fim do episódio. La revedere!", config.VOICE_PT_FEMALE, pause_ms=0, label="outro")
        )

    return Episode(
        title=title,
        theme=label,
        mode=mode,
        number=number,
        segments=segments,
        item_ids=[i.id for i in chosen],
    )


# --------------------------------------------------------------------------- #
# montagem
# --------------------------------------------------------------------------- #


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise StudioError(
            "ffmpeg ausente — instale com: pip install imageio-ffmpeg"
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration_seconds(path: Path) -> float:
    """Duração real do MP3, lida do próprio arquivo."""
    try:
        from mutagen.mp3 import MP3
    except ImportError:
        return 0.0
    try:
        return float(MP3(path).info.length)
    except Exception:
        return 0.0


def _filter_script(segments: list[Segment]) -> str:
    """Um filtro por entrada: normaliza o formato e acrescenta o silêncio.

    O `aformat` é seguro contra vozes que venham com taxa diferente — a
    concatenação exige formato idêntico e falha feio quando não é o caso.
    """
    chains, labels = [], []
    for i, seg in enumerate(segments):
        chain = f"[{i}:a]aformat=sample_rates={SAMPLE_RATE}:channel_layouts=mono"
        if seg.pause_ms > 0:
            chain += f",apad=pad_dur={seg.pause_ms / 1000:.3f}"
        chain += f"[s{i}]"
        chains.append(chain)
        labels.append(f"[s{i}]")
    concat = "".join(labels) + f"concat=n={len(segments)}:v=0:a=1[out]"
    return ";".join([*chains, concat])


def render(
    episode: Episode,
    out_path: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    synth: Callable[..., Path] | None = None,
) -> RenderResult:
    """Sintetiza cada fala (aproveitando o cache) e junta tudo num MP3."""
    if not episode.segments:
        raise StudioError("episódio vazio")

    synth = synth or tts.synthesize
    out_path.parent.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    for i, seg in enumerate(episode.segments):
        try:
            clips.append(synth(seg.text, voice=seg.voice, rate=seg.rate))
        except tts.TTSError as exc:
            raise StudioError(f"falha ao sintetizar '{seg.text[:40]}': {exc}") from exc
        if on_progress:
            on_progress(i + 1, len(episode.segments))

    exe = ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "filter.txt"
        # Script em arquivo em vez de argumento: com 100 segmentos o filtro
        # passa do limite de linha de comando do Windows.
        script.write_text(_filter_script(episode.segments), encoding="utf-8")

        cmd = [exe, "-y", "-hide_banner", "-loglevel", "error"]
        for clip in clips:
            cmd += ["-i", str(clip)]
        cmd += [
            "-filter_complex_script", str(script),
            "-map", "[out]",
            "-c:a", "libmp3lame",
            "-b:a", BITRATE,
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0 or not out_path.exists():
        raise StudioError(f"ffmpeg falhou:\n{result.stderr.strip()[:800]}")

    tag(out_path, episode)
    return RenderResult(
        path=out_path,
        seconds=duration_seconds(out_path),
        segments=len(episode.segments),
    )


def tag(path: Path, episode: Episode) -> None:
    """Escreve ID3 para o episódio aparecer decente no player do celular."""
    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.id3 import ID3NoHeaderError
        from mutagen.mp3 import MP3
    except ImportError:
        return

    try:
        audio = MP3(path, ID3=EasyID3)
    except ID3NoHeaderError:
        audio = MP3(path)
        audio.add_tags(ID3=EasyID3)
        audio = MP3(path, ID3=EasyID3)
    except Exception:
        return

    audio["title"] = episode.title
    audio["album"] = "dor · romeno"
    audio["artist"] = "dor"
    audio["genre"] = "Speech"
    audio["tracknumber"] = str(episode.number)
    try:
        audio.save()
    except Exception:
        pass


def write_transcript(episode: Episode, path: Path, lib: Library | None = None) -> Path:
    """Transcrição em Markdown, para conferir o que passou no ouvido."""
    lines = [f"# {episode.title}", "", f"Modo: `{episode.mode}` · {len(episode.item_ids)} itens", ""]

    if lib is not None and episode.item_ids:
        # A lista de palavras vem primeiro: é o que se consulta depois de ouvir,
        # sem precisar varrer o roteiro fala por fala.
        lines += ["## Palavras", ""]
        for item_id in episode.item_ids:
            item = lib.vocab.get(item_id)
            if item:
                lines.append(f"- **{item.ro}** — {item.pt_main}")
        lines += ["", "## Roteiro", ""]

    for seg in episode.segments:
        if seg.label in ("intro", "outro"):
            lines += ["", f"_{seg.text}_", ""]
            continue
        marker = "**" if seg.lang == "ro" else ""
        lines.append(f"- `{seg.label or '·'}` {marker}{seg.text}{marker}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_playlist(entries: list[tuple[Path, str, float]], path: Path) -> Path:
    """Playlist M3U com títulos e durações."""
    lines = ["#EXTM3U"]
    for file_path, title, seconds in entries:
        lines.append(f"#EXTINF:{int(seconds)},{title}")
        lines.append(file_path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
