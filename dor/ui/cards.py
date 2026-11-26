"""Fichas de leitura — o lado 'estudar' do que o resto do app faz 'praticar'."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dor import config
from dor.core.models import (
    ERA_LABEL_PT,
    Artist,
    Book,
    Bridge,
    GrammarRule,
    HistoryEvent,
    Scene,
    Sentence,
    Track,
    VocabItem,
)
from dor.ui import art
from dor.ui.theme import etymology_note, register_badge


def intro_card(item: VocabItem, *, example: Sentence | None = None) -> RenderableType:
    """A ficha completa da estreia de uma palavra, mostrada logo APÓS a
    primeira tentativa.

    A posição é a coisa mais importante deste código, e custou duas rodadas de
    feedback para chegar nela. Antes da pergunta a ficha entregava a resposta e
    o exercício virava cópia; sem ficha nenhuma a palavra aparecia do nada e o
    aluno tinha que errar às cegas. O que fica antes da pergunta é só o símbolo
    — ele dá o referente sem dar a palavra —, e a explicação vem aqui, quando
    já existe uma tentativa em que grudar.

    A ordem interna é a do reconhecimento, não a da prova: símbolo e palavra,
    tradução em seguida, e a ponte com o português por último, que é o que
    transforma decoreba em dedução.
    """
    head = Text()
    head.append(item.ro, style="ro")
    if item.ipa:
        head.append(f"   /{item.ipa}/", style="dim")
    head.append("  ")
    head.append_text(register_badge(item.register))
    head.append("\n")
    head.append(", ".join(item.pt), style="pt")
    head.append(f"   ({item.pos})", style="dim")

    if item.cognate_pt:
        head.append("\n≈ ", style="bold green")
        head.append(item.cognate_pt["word"], style="pt")
        if item.cognate_pt.get("note"):
            head.append(f"  — {item.cognate_pt['note']}", style="hint")
    elif item.etymology:
        head.append(f"\n{etymology_note(item.etymology)}", style="hint")

    blocks: list[RenderableType] = [art.beside(item, head)]

    if item.false_friend:
        ff = item.false_friend
        blocks.append(
            Text("\n⚠ falso amigo: ", style="bold warn")
            + Text(f"parece '{ff['looks_like']}', mas é '{ff['actually_means']}'", style="pt")
        )
    if item.note_pt:
        blocks.append(Text(f"\n{item.note_pt}", style="hint"))
    if example is not None:
        blocks.append(
            Text(f"\n{example.ro}", style="ro") + Text(f"\n{example.pt}", style="dim")
        )

    return Panel(
        Group(*blocks),
        title="[bold]palavra nova[/]",
        subtitle=f"[dim]{item.level}[/]",
        title_align="left",
        subtitle_align="right",
        border_style="bright_magenta",
        padding=(1, 2),
    )


def rule_card(rule: GrammarRule, *, exercises: int = 0) -> RenderableType:
    """A regra inteira: explicação, contraste com o português, tabela e armadilha.

    A ordem não é decorativa. O contraste vem logo depois da explicação porque
    é ele que fixa: o brasileiro não aprende o genitivo romeno decorando o
    genitivo romeno, e sim percebendo o que o português faz no lugar dele.
    """
    blocks: list[RenderableType] = [Text(rule.explanation_pt, style="pt")]

    if rule.contrast_pt:
        blocks += [
            Text(),
            Text("em português", style="bold dim"),
            Text(rule.contrast_pt, style="pt"),
        ]

    if rule.table:
        table = Table(box=None, padding=(0, 2), header_style="bold dim")
        for header in rule.table["headers"]:
            table.add_column(header)
        for row in rule.table["rows"]:
            table.add_row(*[Text(cell, style="ro" if i else "dim") for i, cell in enumerate(row)])
        blocks += [Text(), table]

    if rule.examples:
        blocks.append(Text())
        for example in rule.examples:
            blocks.append(
                Text(f"  {example['ro']}", style="ro") + Text(f"   {example['pt']}", style="dim")
            )

    if rule.pitfall_pt:
        blocks += [
            Text(),
            Text("⚠ a armadilha", style="bold warn"),
            Text(rule.pitfall_pt, style="pt"),
        ]

    footer = (
        Text(f"{exercises} exercícios — rode: dor drill {rule.id}", style="hint")
        if exercises
        else Text("regra de teoria: não gera exercício a partir do vocabulário", style="hint")
    )
    blocks += [Text(), footer]

    return Panel(
        Group(*blocks),
        title=f"[bold]{rule.title}[/]  [dim]{rule.level}[/]",
        title_align="left",
        border_style="bright_yellow",
        padding=(1, 2),
    )


def _glossary_table(entries: list[dict[str, str]]) -> Table:
    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column(style="ro", no_wrap=True)
    table.add_column(style="pt")
    table.add_column()
    for entry in entries:
        register = entry.get("register", "neutru")
        label = config.REGISTER_LABEL_PT.get(register, register)
        table.add_row(entry["ro"], entry["pt"], Text(label, style=f"reg.{register}"))
    return table


def bridge_card(bridge: Bridge) -> RenderableType:
    """A regra, os pares e — com destaque — onde ela falha.

    Uma ponte sem exceção conhecida vira excesso de confiança, então a
    armadilha nunca fica escondida atrás de um comando extra.
    """
    blocks: list[RenderableType] = [Text(bridge.rule_pt, style="pt"), Text()]

    header = Text("  ")
    header.append(bridge.pt, style="bright_white")
    header.append("  →  ", style="dim")
    header.append(bridge.ro, style="ro")
    if bridge.latin:
        header.append(f"   (latim {bridge.latin})", style="hint")
    blocks.append(header)

    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column(style="pt", no_wrap=True)
    table.add_column(style="dim")
    table.add_column(style="ro", no_wrap=True)
    table.add_column(style="hint")
    for example in bridge.examples:
        note = example.get("note", "")
        if example.get("latin"):
            note = f"← {example['latin']}" + (f" · {note}" if note else "")
        table.add_row(example["pt"], "→", example["ro"], note)
    blocks += [Text(), table]

    if bridge.traps:
        blocks += [Text(), Text("⚠ onde a ponte quebra", style="bold warn")]
        for trap in bridge.traps:
            line = Text(f"  {trap['pt']}", style="pt")
            if trap.get("wrong_ro"):
                line.append(f"  ≠ {trap['wrong_ro']}", style="err")
            if trap.get("right_ro"):
                line.append(f"  = {trap['right_ro']}", style="ro")
            blocks.append(line)
            blocks.append(Text(f"    {trap['note']}", style="hint"))

    marks = []
    if bridge.productive:
        marks.append("produtiva — dá para inventar palavra e acertar")
    marks.append(f"confiança {bridge.confidence}")
    blocks += [Text(), Text("  " + "  ·  ".join(marks), style="hint")]

    return Panel(
        Group(*blocks),
        title=f"[bold]{bridge.title}[/]",
        subtitle=f"[dim]{'som' if bridge.kind == 'sunet' else 'sufixo'}[/]",
        title_align="left",
        subtitle_align="right",
        border_style="bright_white",
        padding=(1, 2),
    )


def scene_card(scene: Scene) -> RenderableType:
    """Diálogo, fórmulas, o que se fala na rua e a etiqueta.

    A etiqueta fica por último e em destaque porque é o que de fato entrega
    um estrangeiro: quem chega com flores em número par acertou a gramática
    toda e errou a única coisa que ia ser lembrada.
    """
    blocks: list[RenderableType] = [Text(scene.goal_pt, style="pt"), Text()]

    for turn in scene.turns:
        mine = turn["who"] == "tu"
        marker = "você" if mine else "ele"
        blocks.append(
            Text(f"  {marker:>4}  ", style="bold magenta" if mine else "dim")
            + Text(turn["ro"], style="ro" if mine else "bright_yellow")
        )
        blocks.append(Text(f"        {turn['pt']}", style="dim"))
        if turn.get("note_pt"):
            blocks.append(Text(f"        {turn['note_pt']}", style="hint"))

    if scene.phrases:
        table = Table(box=None, padding=(0, 2), show_header=False)
        table.add_column(style="ro", no_wrap=True)
        table.add_column(style="pt")
        table.add_column(style="hint")
        for phrase in scene.phrases:
            table.add_row(phrase["ro"], phrase["pt"], phrase.get("when_pt", ""))
        blocks += [Text(), Text("vale decorar", style="bold dim"), table]

    if scene.street:
        table = Table(box=None, padding=(0, 2), header_style="bold dim")
        table.add_column("o livro ensina", style="dim")
        table.add_column("na rua", style="ro")
        table.add_column("", style="hint")
        for pair in scene.street:
            table.add_row(pair["textbook"], pair["street"], pair.get("note_pt", ""))
        blocks += [Text(), table]

    if scene.etiquette_pt:
        blocks += [Text(), Text("etiqueta", style="bold warn")]
        for rule in scene.etiquette_pt:
            blocks.append(Text(f"  • {rule}", style="pt"))

    title = f"[bold]{scene.title}[/]"
    if scene.title_ro:
        title += f"  [bright_yellow]{scene.title_ro}[/]"
    return Panel(
        Group(*blocks),
        title=title,
        subtitle=f"[dim]{scene.place_pt} · {scene.level}[/]",
        title_align="left",
        subtitle_align="right",
        border_style="bright_blue",
        padding=(1, 2),
    )


def book_card(book: Book) -> RenderableType:
    """A ficha do livro, com a dificuldade REAL antes de qualquer elogio.

    'Por que ler' vende; 'o que torna difícil' é o que evita abandonar o livro
    na página 20 achando que o problema é você.
    """
    from dor.modes.reading import usable_excerpt

    blocks: list[RenderableType] = [Text(book.why_pt, style="pt")]

    if book.difficulty_pt:
        blocks += [
            Text(),
            Text("o que esperar", style="bold dim"),
            Text(book.difficulty_pt, style="pt"),
        ]

    lines = usable_excerpt(book) or (
        book.excerpt.get("lines", []) if book.excerpt and book.public_domain else []
    )
    if lines:
        blocks.append(Text())
        for line in lines:
            blocks.append(
                Text(f"  {line['ro']}", style="ro") + Text(f"\n    {line['pt']}", style="dim")
            )

    if book.glossary:
        blocks += [Text(), Text("glossário", style="bold dim"), _glossary_table(book.glossary)]

    if book.where_pt:
        blocks += [Text(), Text(f"onde achar: {book.where_pt}", style="hint")]
    if book.note_pt:
        blocks.append(Text(book.note_pt, style="hint"))

    title = f"[bold]{book.title}[/]"
    if book.title_pt:
        title += f"  [dim]({book.title_pt})[/]"
    year = f" · {book.year}" if book.year else ""
    return Panel(
        Group(*blocks),
        title=title,
        subtitle=f"[dim]{book.author}{year} · {book.kind_pt} · {book.level}[/]",
        title_align="left",
        subtitle_align="right",
        border_style="bright_green",
        padding=(1, 2),
    )


def event_card(event: HistoryEvent, *, rules: dict[str, str] | None = None) -> RenderableType:
    """Um evento histórico, com o efeito sobre a língua em destaque.

    'O que aconteceu' vem em cinza e 'o que isso fez com a língua' em branco,
    invertendo o peso que um livro de história daria. Aqui o evento é o
    pretexto; a língua é o assunto.
    """
    blocks: list[RenderableType] = [
        Text(event.what_pt, style="dim"),
        Text(),
        Text("na língua", style="bold dim"),
        Text(event.language_pt, style="pt"),
    ]

    if event.words:
        table = Table(box=None, padding=(0, 2), show_header=False)
        table.add_column(style="ro", no_wrap=True)
        table.add_column(style="pt")
        table.add_column(style="hint")
        for word in event.words:
            table.add_row(word["ro"], word["pt"], word.get("note", ""))
        blocks += [Text(), Text("o que entrou na língua", style="bold dim"), table]

    for gid in event.grammar_refs:
        label = (rules or {}).get(gid, gid)
        blocks.append(Text(f"  → explica a regra: {label}  (dor drill {gid} -t)", style="hint"))

    if event.note_pt:
        blocks += [Text(), Text(event.note_pt, style="hint")]

    era = ERA_LABEL_PT.get(event.era, event.era)
    title = f"[bold]{event.title}[/]"
    if event.title_ro:
        title += f"  [bright_yellow]{event.title_ro}[/]"
    return Panel(
        Group(*blocks),
        title=title,
        subtitle=f"[dim]{event.when} · {era}[/]",
        title_align="left",
        subtitle_align="right",
        border_style="bright_cyan",
        padding=(1, 2),
    )


def track_card(track: Track, artist: Artist | None = None) -> RenderableType:
    """A ficha da faixa: por que ela importa, o trecho citável e o glossário.

    O trecho só aparece quando é domínio público. Para obra protegida a ficha
    fica no glossário e no link — o app não guarda letra alheia.
    """
    from dor.modes.lyrics import usable_excerpt

    blocks: list[RenderableType] = [Text(track.why_pt, style="pt")]

    if track.theme:
        blocks.append(Text(f"temas: {' · '.join(track.theme)}", style="hint"))
    if track.folk_elements:
        blocks.append(Text(f"elementos: {' · '.join(track.folk_elements)}", style="hint"))

    excerpt = track.excerpt or {}
    lines = excerpt.get("lines", [])
    if lines and excerpt.get("public_domain") is True:
        blocks.append(Text())
        for line in lines:
            blocks.append(
                Text(f"  {line['ro']}", style="ro") + Text(f"\n    {line['pt']}", style="dim")
            )
        blocks.append(Text("  (domínio público)", style="hint"))
    elif lines:
        blocks += [Text(), Text("  trecho não exibido: obra protegida", style="hint")]

    if track.glossary:
        blocks += [Text(), Text("glossário", style="bold dim"), _glossary_table(track.glossary)]

    links = {**(artist.links if artist else {}), **track.links}
    if links:
        blocks += [Text(), Text("  " + "   ".join(links.values()), style="dim")]

    if not usable_excerpt(track) and not track.glossary:
        blocks += [Text(), Text("sem material de treino — esta ficha é para ouvir", style="hint")]

    subtitle = artist.name if artist else track.artist_name
    year = f"  ({track.year})" if track.year else ""
    return Panel(
        Group(*blocks),
        title=f"[bold]{track.title}[/]{year}  [dim]{subtitle}[/]",
        title_align="left",
        border_style="bright_magenta",
        padding=(1, 2),
    )


def piece_card(piece) -> RenderableType:
    """Uma faixa ou notícia, parte por parte.

    O formato responde a uma queixa concreta: glossário solto no fim não ensina
    música. Cada pedaço aparece com o verso, a tradução embaixo, o que está
    acontecendo ali e só então as palavras daquele pedaço — para que a
    explicação esteja ao lado do que ela explica, e não trinta linhas abaixo.
    """
    blocks: list[RenderableType] = []
    if piece.why_pt:
        blocks += [Text(piece.why_pt, style="pt"), Text()]

    for n, part in enumerate(piece.parts, 1):
        rotulo = part.at or f"parte {n}"
        blocks.append(Text(f"[{rotulo}]", style="bold cyan"))
        for ro, pt in part.pairs:
            blocks.append(Text(f"  {ro}", style="ro"))
            if pt:
                blocks.append(Text(f"  {pt}", style="dim"))
        if part.explica_pt:
            blocks.append(Text(f"\n  {part.explica_pt}", style="pt"))
        if part.glossary:
            blocks.append(_glossary_table(part.glossary))
        blocks.append(Text())

    if piece.note_pt:
        blocks.append(Text(piece.note_pt, style="hint"))
    if piece.link:
        blocks.append(Text(f"fonte: {piece.link}", style="hint"))

    autor = piece.author or piece.source or ""
    title = f"[bold]{piece.title}[/]"
    if piece.title_pt:
        title += f"  [dim]({piece.title_pt})[/]"
    if autor:
        title += f"  [dim]{autor}[/]"
    subtitle = " · ".join(x for x in (piece.date, piece.level, piece.week) if x)
    return Panel(
        Group(*blocks),
        title=title,
        subtitle=f"[dim]{subtitle}[/]",
        title_align="left",
        subtitle_align="right",
        border_style="bright_magenta",
        padding=(1, 2),
    )
