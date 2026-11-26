"""Export para Anki, sem dependência nova.

Não geramos `.apkg`: isso exigiria `genanki` e um formato de banco que muda
entre versões do Anki. Escrevemos o que o Anki importa nativamente desde
sempre — um TSV com cabeçalho de campos — mais uma pasta de áudio para copiar
em `collection.media`.

O ponto do export não é migrar de app. É garantir que o progresso e o material
não fiquem presos aqui: conteúdo que só existe dentro de uma ferramenta é
conteúdo que se perde quando a ferramenta cansa.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from dor.core.models import VocabItem

#: O Anki lê estas linhas de metadado no topo do arquivo e dispensa o usuário
#: de configurar separador e HTML na tela de importação.
HEADER = (
    "#separator:tab",
    "#html:true",
    "#columns:Frente\tVerso\tPronúncia\tNota\tÁudio\tTags",
)


@dataclass
class ExportResult:
    path: Path
    notes: int
    media_dir: Path | None = None
    media: int = 0


def _clean(text: str) -> str:
    """TSV não tem escape: tabulação e quebra de linha viram espaço.

    Uma tabulação perdida dentro de um campo desloca a coluna e corrompe o
    arquivo inteiro de forma silenciosa — o Anki importa e só depois se percebe.
    """
    return " ".join(str(text).split())


def note_for(item: VocabItem, *, audio: str = "") -> list[str]:
    """Uma nota do Anki a partir de uma palavra do acervo."""
    extra = []
    if item.cognate_pt:
        extra.append(f"≈ {item.cognate_pt['word']}")
    if item.false_friend:
        extra.append(f"⚠ falso amigo: parece '{item.false_friend['looks_like']}'")
    if item.note_pt:
        extra.append(item.note_pt)

    tags = ["dor", item.level, item.pos, *item.tags]
    if item.gender:
        tags.append(item.gender)

    return [
        _clean(item.ro),
        _clean(", ".join(item.pt)),
        _clean(f"/{item.ipa}/" if item.ipa else ""),
        _clean(" · ".join(extra)),
        audio,
        " ".join(_clean(t).replace(" ", "_") for t in tags),
    ]


def export(
    items: list[VocabItem],
    out_path: Path,
    *,
    audio_for=None,
) -> ExportResult:
    """Escreve o TSV e, se houver áudio, copia os MP3 para uma pasta ao lado.

    `audio_for` recebe o item e devolve o caminho do MP3 (ou None). Fica como
    parâmetro para o export não depender de rede: quem chama decide se
    sintetiza, se usa só o cache ou se ignora o áudio.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    media_dir = out_path.parent / f"{out_path.stem}_media"
    copied = 0

    rows = []
    for item in items:
        audio_field = ""
        if audio_for is not None:
            source = audio_for(item)
            if source and Path(source).exists():
                media_dir.mkdir(parents=True, exist_ok=True)
                # Nome estável e sem acento: o Anki guarda tudo num diretório
                # plano, e o id já é único.
                name = f"dor_{item.id.replace('.', '_')}.mp3"
                shutil.copyfile(source, media_dir / name)
                audio_field = f"[sound:{name}]"
                copied += 1
        rows.append(note_for(item, audio=audio_field))

    lines = [*HEADER, *["\t".join(row) for row in rows]]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return ExportResult(
        path=out_path,
        notes=len(rows),
        media_dir=media_dir if copied else None,
        media=copied,
    )
