"""Estudo a partir do acervo pessoal: música parte por parte e jornal da semana.

A mecânica é a do Lyrics Lab e a da biblioteca — glossário vira tradução, verso
vira lacuna. O que muda é a fonte e, principalmente, a trava: aqui não tem.
`data/` é publicado e por isso só cita domínio público; o acervo pessoal fica na
máquina do usuário, com o que ele mesmo colou lá.

Por isso o exercício de lacuna existe aqui e é raro no `reading`: com a letra
inteira disponível dá para apagar exatamente a palavra que a explicação acabou
de ensinar, que é o exercício que faz a gíria grudar.
"""

from __future__ import annotations

import random

from dor.core.local import KIND_LABEL_PT, Part, Piece
from dor.core.quoting import accepted_pt
from dor.modes.base import Exercise
from dor.modes.cloze import BLANK, blank_out

#: Este módulo não tem um MODE só: o rótulo de sessão é o tipo da peça, para
#: que a tela inicial consiga dizer "você nunca abriu o jornal" sem confundir
#: com "você nunca abriu a música".
MODES = tuple(KIND_LABEL_PT)


def mode_for(piece: Piece) -> str:
    """O rótulo de sessão é o próprio tipo — é ele que a tela inicial procura."""
    return piece.kind


def _source_note(piece: Piece) -> str:
    autor = piece.author or piece.source or ""
    return f"{autor} — {piece.title}" if autor else piece.title


def build_glossary(piece: Piece, entry: dict[str, str], *, direction: str = "ro_pt") -> Exercise:
    item_id = f"{piece.id}#{entry['ro']}"
    falado = entry["ro"].split("/")[0].strip()
    if direction == "pt_ro":
        return Exercise(
            item_id=item_id,
            mode=mode_for(piece),
            prompt=accepted_pt(entry["pt"])[0],
            instruction=f"como se diz em romeno?  ·  {piece.title}",
            answers=[p.strip() for p in entry["ro"].split("/")],
            answer_lang="ro",
            direction="pt_ro",
            prompt_style="pt",
            speak_after=falado,
            note=entry.get("note") or _source_note(piece),
        )
    return Exercise(
        item_id=item_id,
        mode=mode_for(piece),
        prompt=entry["ro"],
        instruction=f"o que significa?  ·  {piece.title}",
        answers=accepted_pt(entry["pt"]),
        answer_lang="pt",
        direction="ro_pt",
        prompt_style="ro",
        speak_before=falado,
        note=entry.get("note") or _source_note(piece),
    )


def build_cloze(piece: Piece, part: Part) -> Exercise | None:
    """A lacuna do trecho. Aceita a linha já furada ou o alvo a furar."""
    if part.cloze and BLANK in part.cloze:
        prompt, answer = part.cloze, part.cloze_answer
        if not answer:
            return None
    elif part.cloze_answer:
        prompt = next(
            (
                furada
                for line in part.ro
                if (furada := blank_out(line, part.cloze_answer)) and BLANK in furada
            ),
            None,
        )
        answer = part.cloze_answer
        if prompt is None:
            return None
    else:
        return None

    traducao = part.pt[0] if part.pt else ""
    return Exercise(
        item_id=f"{piece.id}#{answer}",
        mode=mode_for(piece),
        prompt=prompt,
        instruction=f"complete o verso  ·  {traducao}" if traducao else "complete o verso",
        answers=[answer],
        answer_lang="ro",
        direction="trecho",
        prompt_style="ro",
        speak_after=part.ro[0],
        note=part.explica_pt or _source_note(piece),
    )


def exercises_for(piece: Piece, *, rng: random.Random | None = None, limit: int = 0) -> list[Exercise]:
    """Todos os exercícios da peça: glossário primeiro, lacuna depois.

    A ordem não é estética. O glossário é o que a pessoa acabou de ler na ficha;
    cobrar a lacuna antes dele seria pedir para produzir o que ainda não foi
    reconhecido uma vez sequer.
    """
    rng = rng or random.Random()
    out = [build_glossary(piece, entry) for part in piece.parts for entry in part.glossary]
    rng.shuffle(out)

    lacunas = [ex for part in piece.parts if (ex := build_cloze(piece, part))]
    out.extend(lacunas)
    return out[:limit] if limit else out
