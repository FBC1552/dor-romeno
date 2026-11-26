"""Estudo a partir de um livro: trecho citável e glossário.

Mesma mecânica do Lyrics Lab, mesma trava de citação — o que muda é a fonte.
Um livro protegido continua rendendo glossário; é o texto literal que exige
domínio público.
"""

from __future__ import annotations

import random

from dor.core.models import Book
from dor.core.quoting import accepted_pt, public_lines
from dor.modes.base import Exercise
from dor.modes.cloze import BLANK, blank_out

MODE = "leitura"


def usable_excerpt(book: Book) -> list[dict[str, str]]:
    """Linhas citáveis. O campo `public_domain` do livro não basta: o trecho
    precisa carregar a própria marca, porque é ele que vai para a tela."""
    return public_lines(book.excerpt)


def build_line(book: Book, line: dict[str, str]) -> Exercise | None:
    prompt = blank_out(line["ro"], line["cloze"])
    if prompt is None or BLANK not in prompt:
        return None
    return Exercise(
        item_id=f"{book.id}#{line['cloze']}",
        mode=MODE,
        prompt=prompt,
        instruction=f"complete a frase  ·  {line['pt']}",
        answers=[line["cloze"]],
        answer_lang="ro",
        direction="trecho",
        prompt_style="ro",
        speak_after=line["ro"],
        note=f"{book.author} — {book.title}",
    )


def build_glossary(book: Book, entry: dict[str, str], *, direction: str = "ro_pt") -> Exercise:
    item_id = entry.get("slang_id") or f"{book.id}#{entry['ro']}"
    if direction == "pt_ro":
        return Exercise(
            item_id=item_id,
            mode=MODE,
            prompt=accepted_pt(entry["pt"])[0],
            instruction=f"como se diz em romeno?  ·  {book.title}",
            answers=[p.strip() for p in entry["ro"].split("/")],
            answer_lang="ro",
            direction="pt_ro",
            prompt_style="pt",
            speak_after=entry["ro"].split("/")[0].strip(),
            note=f"{book.author} — {book.title}",
        )
    return Exercise(
        item_id=item_id,
        mode=MODE,
        prompt=entry["ro"],
        instruction=f"o que significa?  ·  {book.title}",
        answers=accepted_pt(entry["pt"]),
        answer_lang="pt",
        direction="ro_pt",
        prompt_style="ro",
        speak_before=entry["ro"].split("/")[0].strip(),
        note=f"{book.author} — {book.title}",
    )


def build_all(book: Book, *, rng: random.Random | None = None) -> list[Exercise]:
    rng = rng or random.Random()
    exercises: list[Exercise] = []

    for line in usable_excerpt(book):
        exercise = build_line(book, line)
        if exercise:
            exercises.append(exercise)

    glossary = list(book.glossary)
    rng.shuffle(glossary)
    for entry in glossary:
        exercises.append(build_glossary(book, entry, direction=rng.choice(("ro_pt", "pt_ro"))))

    return exercises
