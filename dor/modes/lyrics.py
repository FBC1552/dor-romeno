"""Lyrics Lab — estudar pelo que você já ouviria de qualquer jeito.

Duas fontes de exercício por faixa: o GLOSSÁRIO (palavra ↔ tradução, funciona
para qualquer música) e o TRECHO citado (lacuna no verso, com a tradução como
apoio).

A trava de direito autoral vive aqui, não só no conteúdo: `usable_excerpt`
recusa qualquer trecho que não esteja marcado como domínio público, então nem
um erro de curadoria transforma letra protegida em exercício.
"""

from __future__ import annotations

import random

from dor.core.models import Track
from dor.core.quoting import accepted_pt, public_lines
from dor.modes.base import Exercise
from dor.modes.cloze import BLANK, blank_out

MODE = "lyrics"


def usable_excerpt(track: Track) -> list[dict[str, str]]:
    """Versos citáveis desta faixa.

    Uma faixa protegida continua estudável pelo glossário; é o trecho literal
    que exige a marca de domínio público.
    """
    return public_lines(track.excerpt)


def glossary_id(track: Track, entry: dict[str, str]) -> str:
    """ID sintético e estável para o SRS agendar a palavra do glossário."""
    return entry.get("slang_id") or f"{track.id}#{entry['ro']}"


def build_glossary(track: Track, entry: dict[str, str], *, direction: str = "ro_pt") -> Exercise:
    """Palavra do glossário ↔ tradução."""
    if direction == "pt_ro":
        return Exercise(
            item_id=glossary_id(track, entry),
            mode=MODE,
            prompt=accepted_pt(entry["pt"])[0],
            instruction=f"como se diz em romeno?  ·  {track.title}",
            answers=[p.strip() for p in entry["ro"].split("/")],
            answer_lang="ro",
            direction="pt_ro",
            prompt_style="pt",
            speak_after=entry["ro"].split("/")[0].strip(),
            note=f"{track.artist_name} — {track.title}",
        )
    return Exercise(
        item_id=glossary_id(track, entry),
        mode=MODE,
        prompt=entry["ro"],
        instruction=f"o que significa?  ·  {track.title}",
        answers=accepted_pt(entry["pt"]),
        answer_lang="pt",
        direction="ro_pt",
        prompt_style="ro",
        speak_before=entry["ro"].split("/")[0].strip(),
        note=f"{track.artist_name} — {track.title}",
    )


def build_line(track: Track, line: dict[str, str]) -> Exercise | None:
    """Lacuna no verso, com a tradução do verso como apoio."""
    prompt = blank_out(line["ro"], line["cloze"])
    if prompt is None or BLANK not in prompt:
        return None
    return Exercise(
        item_id=f"{track.id}#{line['cloze']}",
        mode=MODE,
        prompt=prompt,
        instruction=f"complete o verso  ·  {line['pt']}",
        answers=[line["cloze"]],
        answer_lang="ro",
        direction="verso",
        prompt_style="ro",
        speak_after=line["ro"],
        note=f"{track.artist_name} — {track.title}",
    )


def build_all(track: Track, *, rng: random.Random | None = None) -> list[Exercise]:
    """Tudo que a faixa consegue gerar, com os versos antes do glossário.

    A ordem é deliberada: o verso dá o contexto em que a palavra vive, e depois
    o glossário cobra a palavra sozinha. Ao contrário, o exercício vira lista.
    """
    rng = rng or random.Random()
    exercises: list[Exercise] = []

    for line in usable_excerpt(track):
        exercise = build_line(track, line)
        if exercise:
            exercises.append(exercise)

    glossary = list(track.glossary)
    rng.shuffle(glossary)
    for entry in glossary:
        exercises.append(build_glossary(track, entry, direction=rng.choice(("ro_pt", "pt_ro"))))

    return exercises
