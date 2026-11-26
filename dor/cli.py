"""Ponto de entrada: `dor <comando>`.

F0/F1 entregam diagnóstico, validação e navegação do conteúdo. Os modos de
estudo entram a partir da F4 e se penduram aqui.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dor import __version__, config
from dor.core.loader import ContentError, filter_vocab, load_library
from dor.ui.theme import console, etymology_note, register_badge

app = typer.Typer(
    name="dor",
    help="CLI de imersão em romeno para falantes de português.",
    invoke_without_command=True,
    add_completion=False,
)

#: Teclas que pedem para ouvir o áudio de novo, nos modos de escuta.
REPLAY_KEYS = {"r", "rep"}

#: Pede o símbolo da palavra sem desistir da pergunta. O "?" saiu do replay de
#: áudio e veio para cá porque é o que a mão faz quando falta contexto, não
#: quando falta volume — e onde não há símbolo ele ainda repete o áudio.
HINT_KEYS = {"?", "d", "dica"}

#: O cardápio da tela inicial: comando, o que ele faz, e os rótulos de sessão
#: que provam que já foi usado alguma vez.
#:
#: A ordem é pedagógica, não alfabética: vocabulário, gramática, as pontes, e só
#: então áudio e cultura. E a lista é explícita em vez de gerada do `--help`
#: porque nem todo comando é atividade — `backup` e `export-audio` são
#: ferramentas, e misturá-las aqui esconderia justamente o que se veio procurar.
#:
#: `modes` vazio marca o que não abre sessão e portanto não dá para saber se já
#: foi lido: leitura de acervo nunca ganha selo de "novo".
HOME_ACTIVITIES: tuple[tuple[str, str, frozenset[str]], ...] = (
    (
        "dor review",
        "revisão espaçada — o que vence hoje",
        frozenset({"misto", "traducao", "escolha", "lacuna"}),
    ),
    ("dor drill", "gramática, com exercícios tirados do vocabulário", frozenset({"gramatica"})),
    ("dor punte", "as pontes que viram português em romeno", frozenset({"punte"})),
    ("dor zi", "cena do dia a dia: pedir, perguntar, se despedir", frozenset({"cena"})),
    ("dor listen", "ouvir e escrever — ditado e compreensão", frozenset({"escuta", "ditado"})),
    ("dor pairs", "pares mínimos: ouça e diga qual das duas foi", frozenset({"perechi"})),
    ("dor shadow", "shadowing: ouça devagar e repita em voz alta", frozenset({"shadowing"})),
    ("dor lupta", "Boss Battle: só as palavras que te derrubam", frozenset({"lupta"})),
    ("dor lyrics", "uma faixa pelo glossário e pelos versos", frozenset({"lyrics"})),
    ("dor versuri", "música parte por parte: verso, gíria e lacuna", frozenset({"versuri"})),
    ("dor jurnal", "o jornal da semana em romeno, com glossário", frozenset({"jurnal"})),
    ("dor livros", "biblioteca graduada: o que ler, e em que ordem", frozenset({"leitura"})),
    ("dor istorie", "a história pelo que ela fez com a língua", frozenset()),
    ("dor atualizar", "traz o lote da semana para o acervo pessoal", frozenset()),
    ("dor stats", "painel: nível, calendário e pontos fracos", frozenset()),
)


def _activities_table(tried: set[str], *, badges: bool = True) -> Table:
    """O cardápio, com selo no que ainda não foi experimentado.

    Na primeira execução o selo sai de cena: marcar as doze linhas como "novo"
    não informa nada, só polui a tela de quem ainda não fez nada.
    """
    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column(style="bright_yellow", no_wrap=True)
    table.add_column(style="dim")
    table.add_column(style="bold cyan", no_wrap=True)
    for command, what, modes in HOME_ACTIVITIES:
        novo = "novo" if badges and modes and not (modes & tried) else ""
        table.add_row(command, what, novo)
    return table


@app.callback()
def _root(ctx: typer.Context) -> None:
    config.force_utf8_console()
    # `dor` sozinho abre a tela inicial em vez de despejar o --help. Quem chega
    # sem lembrar o comando quer saber o que fazer AGORA, não ler 25 opções.
    if ctx.invoked_subcommand is None:
        _home()


def _home() -> None:
    """Onde você está e o que fazer em seguida."""
    from datetime import date

    from dor.game import streaks as streaks_mod
    from dor.game import xp as xp_mod
    from dor.storage.repos import Store
    from dor.ui.feedback import xp_bar

    today = date.today()
    with Store() as store:
        total_xp = store.total_xp()
        streak = store.get_streak()
        daily = store.daily_row(today)
        due = len(store.due_item_ids())
        seen = len(store.seen_item_ids())
        tried = store.session_modes()

    settings = config.Settings.load()
    progress = xp_mod.progress(total_xp)

    head = Text("dor", style="bold bright_yellow")
    head.append(f"  v{__version__}\n", style="dim")

    if seen == 0:
        head.append("\nromeno para quem fala português.\n\n", style="pt")
        head.append("comece por ", style="bold")
        head.append("dor review", style="bright_yellow")
        head.append(" — e tem mais o que fazer aqui:\n", style="bold")
        console.print(
            Panel(
                Group(head, _activities_table(tried, badges=False)),
                border_style="bright_yellow",
            )
        )
        return

    head.append("\nnível ", style="dim")
    head.append(str(progress.level), style="bold magenta")
    head.append("  ")
    head.append_text(xp_bar(progress.ratio, width=18))
    head.append(f"  {progress.xp_into_level}/{progress.xp_for_next}\n", style="dim")

    head.append("streak ", style="dim")
    head.append(f"{streak.current} dia(s)", style="bold ok")
    if streaks_mod.at_risk(streak, today):
        head.append("   ⚠ estude hoje ou quebra", style="bold warn")
    head.append("\nmeta   ", style="dim")
    head.append_text(xp_bar(daily["xp"] / (settings.daily_goal_xp or 1), width=18))
    head.append(f"  {daily['xp']}/{settings.daily_goal_xp} XP", style="dim")

    head.append("\n\n")
    if due:
        head.append(f"{due} palavra(s) vencendo agora   ", style="bold")
        head.append("dor review", style="bright_yellow")
    else:
        head.append("nada vencido — bom momento para conteúdo novo", style="dim")

    # O cardápio inteiro aparece SEMPRE, e não só quando não há nada vencido.
    # Sugerir apenas `dor review` fazia a tela inicial esconder onze doze avos do
    # app de quem estuda todo dia — que é exatamente quem já passou daqui.
    foot = Text("\ntodos os comandos: ", style="dim")
    foot.append("dor --help", style="bright_yellow")

    console.print(
        Panel(
            Group(head, Text("\no que tem aqui", style="bold"), _activities_table(tried), foot),
            border_style="bright_yellow",
        )
    )


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
@app.command()
def doctor() -> None:
    """Diagnostica o ambiente: Python, conteúdo, provedores de TTS e cache."""
    from dor.audio import tts

    console.print(
        Panel.fit(
            Text("dor", style="bold bright_yellow")
            + Text(f"  v{__version__}\n", style="dim")
            + Text("romeno para quem fala português", style="hint"),
            border_style="bright_yellow",
        )
    )

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()

    t.add_row("Python", f"{sys.version.split()[0]}  ({sys.executable})")
    t.add_row("Conteúdo", str(config.DATA_DIR))
    t.add_row("Progresso", str(config.USER_DIR))

    providers = tts.available_providers()
    if providers:
        t.add_row("TTS", Text(", ".join(providers), style="ok"))
    else:
        t.add_row("TTS", Text("nenhum provedor — instale com: pip install -e .[audio]", style="err"))

    try:
        import pygame  # noqa: F401

        t.add_row("Player", Text("pygame", style="ok"))
    except ImportError:
        t.add_row("Player", Text("pygame ausente — cai no player do sistema", style="warn"))

    count, size = tts.cache_stats()
    t.add_row("Cache de áudio", f"{count} arquivos · {size / 1024:.0f} KB")

    from dor.core.srs import available_schedulers
    from dor.storage.db import db_info

    t.add_row("Agendador", Text(" > ".join(available_schedulers()), style="ok"))

    info = db_info()
    if info["existe"]:
        t.add_row(
            "Progresso (banco)",
            f"esquema v{info['esquema']} · {info['itens']} itens · "
            f"{info['revisões']} revisões · {info['bytes'] / 1024:.0f} KB",
        )
    else:
        t.add_row("Progresso (banco)", Text("ainda não criado — rode `dor review`", style="hint"))

    console.print(t)

    # Teste de diacríticos: se o terminal comer isto, nada mais funciona direito.
    console.print()
    console.print("  Teste de diacríticos ", Text("ă â î ș ț  Ă Â Î Ș Ț", style="ro"))
    console.print("  ", Text("Dacă você vê todos os cinco pares acima, o terminal está OK.", style="hint"))

    # Conteúdo
    console.print()
    try:
        lib = load_library()
    except ContentError as exc:
        console.print(Text(f"Conteúdo inválido:\n{exc}", style="err"))
        raise typer.Exit(1) from exc

    counts = Table(show_header=False, box=None, padding=(0, 2))
    counts.add_column(style="dim")
    counts.add_column(justify="right", style="ok")
    for label, n in lib.counts().items():
        counts.add_row(label, str(n))
    console.print(counts)

    if lib.issues:
        console.print()
        console.print(Text(f"{len(lib.issues)} problema(s) de conteúdo — rode `dor validate`", style="warn"))


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #
@app.command()
def validate() -> None:
    """Valida todos os JSON contra os schemas e checa referências cruzadas."""
    try:
        lib = load_library()
    except ContentError as exc:
        console.print(Text(str(exc), style="err"))
        raise typer.Exit(1) from exc

    if not lib.issues:
        counts = " · ".join(f"{n} {label}" for label, n in lib.counts().items())
        console.print(Text("✓ conteúdo válido", style="ok"), Text(f"— {counts}", style="dim"))
        return

    console.print(Text(f"✗ {len(lib.issues)} problema(s):\n", style="err"))
    for issue in lib.issues:
        # Text() em vez de f-string: os caminhos vêm com [colchetes] e o Rich
        # os engoliria como marcação de estilo.
        console.print(Text(f"  • {issue}"))
    raise typer.Exit(1)


# --------------------------------------------------------------------------- #
# list
# --------------------------------------------------------------------------- #
@app.command("list")
def list_vocab(
    level: Annotated[str | None, typer.Option("--level", "-l", help="A1, A2, B1...")] = None,
    pos: Annotated[str | None, typer.Option("--pos", "-p", help="noun, verb, adj, expr...")] = None,
    gender: Annotated[str | None, typer.Option("--gender", "-g", help="m, f, n")] = None,
    register: Annotated[str | None, typer.Option("--register", "-r")] = None,
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    deck: Annotated[str | None, typer.Option("--deck", "-d")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 40,
) -> None:
    """Lista e filtra o vocabulário carregado."""
    lib = load_library()
    items = filter_vocab(
        lib, level=level, pos=pos, gender=gender, register=register, tag=tag, deck=deck
    )

    if not items:
        console.print(Text("nenhum item bate com esse filtro", style="warn"))
        raise typer.Exit(1)

    table = Table(box=None, padding=(0, 2))
    table.add_column("romeno", style="ro")
    table.add_column("português", style="pt")
    table.add_column("classe", style="dim")
    table.add_column("gên.", style="dim", justify="center")
    table.add_column("registro")
    table.add_column("ponte PT", style="dim italic")

    for item in items[:limit]:
        bridge = ""
        if item.false_friend:
            bridge = f"⚠ falso amigo: parece '{item.false_friend['looks_like']}'"
        elif item.cognate_pt:
            bridge = f"≈ {item.cognate_pt['word']}"
        elif item.etymology in ("slav", "romani", "turc"):
            bridge = etymology_note(item.etymology)

        table.add_row(
            item.ro,
            ", ".join(item.pt),
            item.pos,
            item.gender or "",
            register_badge(item.register),
            bridge,
        )

    console.print(table)
    shown = min(limit, len(items))
    console.print(Text(f"\n{shown} de {len(items)} item(ns)", style="dim"))


# --------------------------------------------------------------------------- #
# show
# --------------------------------------------------------------------------- #

#: Nome legível de cada campo de `forms`. A chave é técnica porque é ela que as
#: regras de gramática consomem; a ficha é para gente ler.
FORM_LABELS = {
    "def_sg": "definido sg.",
    "indef_pl": "plural",
    "def_pl": "plural definido",
    "gen_dat_sg": "genitivo/dativo",
    "prezent": "presente",
    "participiu": "particípio",
    "perfect_compus": "perfeito composto",
    "imperfect": "imperfeito",
    "viitor": "futuro (escrito)",
    "viitor_popular": "futuro (falado)",
    "conjunctiv": "conjuntivo",
    "gerunziu": "gerúndio",
    "imperativ": "imperativo",
    "f_sg": "feminino sg.",
    "m_pl": "masculino pl.",
    "f_pl": "feminino/neutro pl.",
}


@app.command()
def show(
    word: Annotated[str, typer.Argument(help="Palavra em romeno ou ID (ro.casa)")],
    silent: Annotated[bool, typer.Option("--silent", "-s", help="Não tocar o áudio")] = False,
) -> None:
    """Mostra a ficha completa de uma palavra e toca a pronúncia."""
    lib = load_library()

    item = lib.vocab.get(word)
    if item is None:
        # Sem diacrítico: quem quer consultar 'casă' digita "casa", e exigir o
        # ă no teclado brasileiro só para LER a ficha não ensina nada.
        from dor.core.normalize import fold, normalize

        needle = fold(normalize(word))
        matches = [i for i in lib.vocab.values() if fold(normalize(i.ro)) == needle]
        if not matches:
            matches = [i for i in lib.vocab.values() if needle in fold(normalize(i.ro))]
        if not matches:
            console.print(Text(f"não encontrei '{word}'", style="err"))
            raise typer.Exit(1)
        item = matches[0]

    # O cabeçalho fica separado do corpo só por causa do desenho: ele sobe ao
    # lado da palavra, e uma ficha inteira indentada pela largura do rabisco
    # seria ilegível.
    head = Text()
    head.append(item.ro, style="ro")
    if item.ipa:
        head.append(f"  /{item.ipa}/", style="dim")
    head.append("  ")
    head.append_text(register_badge(item.register))
    head.append("\n")
    head.append(", ".join(item.pt), style="pt")
    head.append(f"   ({item.pos}", style="dim")
    if item.gender:
        gender_pt = {"m": "masculino", "f": "feminino", "n": "neutro"}[item.gender]
        head.append(f", {gender_pt}", style="dim")
    head.append(")", style="dim")
    if item.accepts_pt:
        head.append(f"\ntambém aceito: {', '.join(item.accepts_pt)}", style="hint")

    body = Text()

    if item.forms:
        body.append("\nFormas\n", style="bold")
        for k, v in item.forms.items():
            val = ", ".join(v) if isinstance(v, list) else v
            body.append(f"  {FORM_LABELS.get(k, k):<22}", style="dim")
            body.append(f"{val}\n", style="ro")

    if item.cognate_pt:
        body.append("\n≈ ponte com o português: ", style="bold green")
        body.append(f"{item.cognate_pt['word']}", style="pt")
        if item.cognate_pt.get("note"):
            body.append(f"  — {item.cognate_pt['note']}", style="hint")
        body.append("\n")

    if item.false_friend:
        ff = item.false_friend
        body.append("\n⚠ falso amigo: ", style="bold dark_orange")
        body.append(f"parece '{ff['looks_like']}', mas significa '{ff['actually_means']}'\n", style="pt")

    if item.etymology:
        body.append("\norigem: ", style="dim")
        body.append(f"{etymology_note(item.etymology)}\n", style="hint")

    if item.note_pt:
        body.append(f"\n{item.note_pt}\n", style="hint")

    examples = [lib.sentences[s] for s in item.examples if s in lib.sentences]
    if examples:
        body.append("\nExemplos\n", style="bold")
        for s in examples:
            body.append(f"  {s.ro}\n", style="ro")
            body.append(f"  {s.pt}\n\n", style="hint")

    from dor.ui import art

    console.print(
        Panel(
            Group(art.beside(item, head), body),
            border_style="bright_yellow",
            title=item.id,
            title_align="left",
        )
    )

    if not silent:
        _speak(item.ro)


# --------------------------------------------------------------------------- #
# say
# --------------------------------------------------------------------------- #
@app.command()
def say(
    text: Annotated[str, typer.Argument(help="Texto em romeno")],
    voice: Annotated[str | None, typer.Option("--voice", "-v", help="alina | emil | <id edge-tts>")] = None,
    rate: Annotated[str | None, typer.Option("--rate", help='ex.: "-20%"')] = None,
) -> None:
    """Sintetiza e toca um texto em romeno (fica em cache para sempre)."""
    aliases = {"alina": config.VOICE_FEMALE, "emil": config.VOICE_MALE}
    _speak(text, voice=aliases.get(voice or "", voice), rate=rate, verbose=True)


def _speak(text: str, *, voice: str | None = None, rate: str | None = None, verbose: bool = False) -> None:
    from dor.audio import tts

    try:
        path = tts.synthesize(text, voice=voice, rate=rate)
    except tts.TTSError as exc:
        console.print(Text(f"áudio indisponível — {exc}", style="warn"))
        return
    if verbose:
        console.print(Text(f"♪ {text}", style="ro"), Text(f"  {path.name}", style="dim"))
    tts.play(path)


# --------------------------------------------------------------------------- #
# music / slang (navegação do conteúdo cultural já semeado)
# --------------------------------------------------------------------------- #
def _run_session(
    exercises_of,
    *,
    total: int,
    mode_label: str,
    silent: bool,
    lives: int | None = None,
    lib=None,
) -> tuple[int, int, int]:
    """Loop único de sessão, comum a todos os modos.

    `exercises_of` é um iterável de (Exercise, extra) — o `extra` é só texto
    decorativo para o cabeçalho (ex.: "novo").

    `lib` liga o contexto visual, em três momentos diferentes:

    - na **estreia** do item, a ficha de apresentação inteira — cobrar antes de
      mostrar não testa nada, só produz um erro sem informação;
    - **sob demanda**, com `?`, o desenho como dica;
    - **depois de responder**, o desenho ao lado da correção — que é o que faz
      a imagem voltar a cada revisão, e não só uma vez na vida.

    Sem `lib` a sessão roda igual, só sem desenho: os modos que não estudam
    palavra do vocabulário (cena, leitura, letra) não têm o que mostrar.

    Com `lives`, cada erro custa uma vida e a sessão acaba quando elas zeram:
    é o que separa a luta do estudo normal. Devolve (respondidas, certas,
    vidas restantes).
    """
    from datetime import UTC, datetime

    from dor.core.srs import get_scheduler
    from dor.game.session import GameSession
    from dor.modes import base
    from dor.storage.repos import Store
    from dor.ui import art, cards, feedback

    def vocab_item(item_id: str):
        return lib.vocab.get(item_id) if lib is not None else None

    with Store() as store:
        scheduler = get_scheduler()
        game = GameSession(store)
        session_id = store.start_session(mode_label)
        console.print(
            Text(f"\n{total} itens", style="bold"),
            Text(
                f"· agendador: {scheduler.name} · ? mostra o desenho · "
                "Enter vazio pula · Ctrl+C encerra\n",
                style="dim",
            ),
        )

        answered = correct = 0
        left = lives or 0

        try:
            for n, (exercise, badge) in enumerate(exercises_of(store), 1):
                item = vocab_item(exercise.item_id)
                estreia = item is not None and store.get_card(exercise.item_id).is_new

                head = Text(f"{n}/{total}  ", style="dim")
                # Na estreia o símbolo entra no próprio enunciado, e SÓ ele. A
                # ficha inteira aqui entregaria a resposta da pergunta logo
                # abaixo e o exercício viraria cópia; a imagem dá o referente
                # sem dar a palavra, que é exatamente o que falta quando o item
                # aparece do nada.
                if estreia and art.has_art(item):
                    head.append(f"{art.symbol_for(item)}  ")
                head.append(exercise.prompt, style=exercise.prompt_style)
                if badge:
                    head.append(f"   {badge}", style="dim cyan")
                if lives:
                    head.append("   " + "♥" * left, style="bold red")
                console.print(head)
                console.print(Text(f"  {exercise.instruction}", style="hint"))

                if exercise.is_choice:
                    for i, choice in enumerate(exercise.choices, 1):
                        console.print(Text(f"    {i}. ", style="dim") + Text(choice, style="pt"))

                if not silent and exercise.speak_before:
                    _speak(exercise.speak_before)

                # O aluno pode pedir para ouvir de novo quantas vezes quiser; o
                # tempo das repetições entra na latência, então repetir custa o
                # bônus de velocidade — mas nunca custa acerto.
                elapsed = 0
                pediu_dica = False
                while True:
                    with base.Timer() as timer:
                        given = console.input("  > ")
                    elapsed += timer.elapsed_ms
                    key = given.strip().lower()
                    if key in REPLAY_KEYS and exercise.speak_before:
                        if not silent:
                            _speak(exercise.speak_before)
                        continue
                    # Símbolo E som juntos, porque quem pede dica no meio de uma
                    # palavra que não reconhece quer as duas coisas, e obrigar a
                    # decorar duas teclas para isso é atrito à toa.
                    #
                    # A dica é paga: 🥔 para 'cartof' não é contexto, é a
                    # resposta. Continua valendo acerto, mas por meio crédito e
                    # com o agendador avisado — ver `grading.after_hint`.
                    if key in HINT_KEYS:
                        deu_dica = False
                        if item is not None and art.has_art(item):
                            console.print(art.render(item))
                            deu_dica = True
                        # Falta um `speak_before` quando o modo não toca nada
                        # sozinho — múltipla escolha, por exemplo. Aí vale ler o
                        # próprio enunciado, desde que ele esteja em romeno: no
                        # sentido PT→RO a palavra romena É a resposta.
                        falar = exercise.speak_before or (
                            exercise.prompt if exercise.prompt_style == "ro" else None
                        )
                        if falar and not silent:
                            _speak(falar)
                            deu_dica = True
                        pediu_dica = pediu_dica or deu_dica
                        if not deu_dica:
                            console.print(Text("  sem dica para esta", style="dim"))
                        continue
                    break

                if not given.strip():
                    console.print(Text("  (pulado)\n", style="dim"))
                    continue

                now = datetime.now(UTC)
                result = base.answer(
                    exercise,
                    base.resolve_choice(exercise, given),
                    latency_ms=elapsed,
                    store=store,
                    scheduler=scheduler,
                    session_id=session_id,
                    now=now,
                    hinted=pediu_dica,
                )
                reward = game.record(result, now)

                line = Text("  ") + feedback.render(result.grade)
                line.append_text(feedback.render_reward(reward))

                # Depois de responder o desenho não estraga mais nada, e é aqui
                # que ele volta TODA revisão — mostrar uma vez na vida, na
                # estreia, não constrói associação nenhuma.
                if item is not None and not estreia:
                    console.print(art.beside(item, line))
                else:
                    console.print(line)

                if exercise.note and (exercise.always_note or not result.grade.ok):
                    console.print(Text(f"  {exercise.note}", style="hint"))

                # A ficha completa é o momento de ensinar, e ele vem DEPOIS da
                # tentativa: errar uma palavra que você nunca viu não custa nada
                # e deixa a explicação com onde grudar.
                if estreia:
                    example = next(
                        (lib.sentences[s] for s in item.examples if s in lib.sentences), None
                    )
                    console.print(cards.intro_card(item, example=example))
                for extra in feedback.render_unlocks(reward):
                    console.print(extra)

                answered += 1
                correct += bool(result.grade.ok)

                if not silent and exercise.speak_after:
                    _speak(exercise.speak_after)
                console.print()

                if lives and not result.grade.ok:
                    left -= 1
                    if left <= 0:
                        console.print(Text("  sem vidas — a luta acabou\n", style="bold err"))
                        break
        except (KeyboardInterrupt, EOFError):
            console.print(
                Text("\n\ninterrompido — o que já foi respondido está salvo", style="warn")
            )

        summary = store.end_session(session_id)
        outcome = game.finish(datetime.now(UTC))
        quests_hoje = store.load_quests(datetime.now().date())

    console.print(feedback.render_outcome(summary, outcome, quests_hoje))
    return answered, correct, left


@app.command()
def review(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Quantos itens na sessão")] = 15,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    deck: Annotated[str | None, typer.Option("--deck", "-d")] = None,
    pos: Annotated[str | None, typer.Option("--pos", "-p")] = None,
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    mode: Annotated[
        str | None,
        typer.Option("--mode", "-m", help="traducao | escolha | lacuna (padrão: mistura)"),
    ] = None,
    silent: Annotated[bool, typer.Option("--silent", "-s", help="Sem áudio")] = False,
) -> None:
    """Sessão de estudo. O modo sobe de dificuldade conforme o item amadurece."""
    import random

    from dor.core.selection import build_queue
    from dor.modes import mixer
    from dor.storage.repos import Store

    lib = load_library()
    rng = random.Random()
    allow = {mode} if mode else None

    with Store() as store:
        queue = build_queue(lib, store, limit=limit, level=level, deck=deck, pos=pos, tag=tag)
    if not queue:
        console.print(Text("nada para revisar agora — volte mais tarde", style="ok"))
        return

    pool = list(lib.vocab.values())

    def exercises(store: Store):
        for item in queue:
            card = store.get_card(item.id)
            exercise = mixer.pick(item, card, lib, pool, rng=rng, allow=allow)
            yield exercise, "novo" if card.is_new else ""

    _run_session(
        exercises,
        total=len(queue),
        mode_label=mode or "misto",
        silent=silent,
        lib=lib,
    )


@app.command()
def drill(
    rule_id: Annotated[str | None, typer.Argument(help="ID da regra (ex.: g.gen.neutru)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 12,
    listar: Annotated[bool, typer.Option("--list", help="Só listar as regras")] = False,
    level: Annotated[str | None, typer.Option("--level", "-l", help="Filtra a lista por nível")] = None,
    teoria: Annotated[bool, typer.Option("--teoria", "-t", help="Só ler a regra, sem treinar")] = False,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Treino de gramática, com exercícios gerados a partir das regras."""
    import random

    from dor.modes import grammar_drill
    from dor.storage.repos import Store
    from dor.ui import cards

    lib = load_library()

    if listar or not rule_id:
        rules = [r for r in lib.grammar.values() if level is None or r.level == level.upper()]
        table = Table(box=None, padding=(0, 2))
        table.add_column("regra", style="bright_yellow", no_wrap=True)
        table.add_column("título", style="pt")
        table.add_column("nível", style="dim")
        table.add_column("exercícios", justify="right")
        total = 0
        for rule in sorted(rules, key=lambda r: (r.level, r.id)):
            n = len(grammar_drill.matching_items(rule, lib))
            total += n
            table.add_row(
                rule.id,
                rule.title,
                rule.level,
                # Regra sem drill não tem zero exercícios: ela é de leitura. O
                # "0" fazia parecer conteúdo quebrado.
                Text(str(n), style="ok") if n else Text("teoria", style="dim"),
            )
        console.print(table)
        console.print(
            Text(f"\n{len(rules)} regras  ·  ", style="dim")
            + Text(f"{total} exercícios gerados do vocabulário", style="ok")
        )
        console.print(Text("rode:  dor drill <regra>   ·   só ler:  dor drill <regra> -t", style="hint"))
        return

    rule = lib.grammar.get(rule_id)
    if rule is None:
        console.print(Text(f"regra desconhecida: {rule_id}", style="err"))
        raise typer.Exit(1)

    pool = grammar_drill.matching_items(rule, lib)
    console.print(cards.rule_card(rule, exercises=len(pool)))

    if not pool:
        # Regra de teoria (pronomes, ordem das palavras) não se gera a partir do
        # vocabulário. Mostrar a ficha e sair é a resposta certa, não um erro.
        if rule.drill:
            console.print(Text(f"a regra {rule.id} não encontra itens no acervo", style="err"))
            raise typer.Exit(1)
        return
    if teoria:
        return

    rng = random.Random()
    total = min(limit, len(pool))
    picks = rng.sample(pool, total)

    def exercises(store: Store):
        for item in picks:
            exercise = grammar_drill.build(rule, lib, item=item, rng=rng)
            if exercise:
                yield exercise, ""

    _run_session(exercises, total=total, mode_label=grammar_drill.MODE, silent=silent, lib=lib)


def _prewarm(texts: list[str], *, rate: str | None = None) -> bool:
    """Sintetiza tudo antes da sessão. Devolve False se não há áudio nenhum."""
    from rich.progress import BarColumn, Progress, TextColumn

    from dor.audio import tts

    if not tts.available_providers():
        console.print(
            Text("nenhum provedor de TTS — instale com: pip install -e \".[audio]\"", style="err")
        )
        return False

    unique = list(dict.fromkeys(texts))
    with Progress(
        TextColumn("  preparando áudio"),
        BarColumn(bar_width=24),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("", total=len(unique))
        made, failed = tts.prewarm(
            unique, rate=rate, on_progress=lambda done, _: progress.update(task, completed=done)
        )

    if failed == len(unique):
        console.print(Text("não consegui sintetizar nenhum áudio — sem rede?", style="err"))
        return False
    if failed:
        console.print(Text(f"{failed} áudio(s) falharam; a sessão segue sem eles", style="warn"))
    return True


@app.command()
def listen(
    limit: Annotated[int, typer.Option("--limit", "-n")] = 12,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    deck: Annotated[str | None, typer.Option("--deck", "-d")] = None,
    mode: Annotated[
        str, typer.Option("--mode", "-m", help="ditado | escuta | misto")
    ] = "misto",
    frases: Annotated[bool, typer.Option("--frases", help="Ditar frases, não palavras")] = False,
) -> None:
    """Sessão de escuta: ditado (escreve em romeno) e compreensão (traduz)."""
    import random

    from dor.core.selection import build_queue
    from dor.modes import dictation, listening
    from dor.storage.repos import Store

    lib = load_library()
    rng = random.Random()

    with Store() as store:
        queue = build_queue(lib, store, limit=limit, level=level, deck=deck)
    if not queue:
        console.print(Text("nada para revisar agora — volte mais tarde", style="ok"))
        return

    if not _prewarm([i.ro for i in queue]):
        raise typer.Exit(1)

    def exercises(store: Store):
        for item in queue:
            card = store.get_card(item.id)
            escolhido = mode if mode != "misto" else rng.choice(("ditado", "escuta"))
            if escolhido == "ditado":
                yield dictation.build(item, lib, use_sentence=frases, rng=rng), (
                    "novo" if card.is_new else ""
                )
            else:
                yield listening.build(item, lib, rng=rng), "novo" if card.is_new else ""

    _run_session(exercises, total=len(queue), mode_label=mode, silent=False, lib=lib)


@app.command()
def pairs(
    limit: Annotated[int, typer.Option("--limit", "-n")] = 10,
    contrast: Annotated[
        str | None, typer.Option("--contrast", "-c", help='Filtra por contraste, ex.: "ț"')
    ] = None,
    listar: Annotated[bool, typer.Option("--list", help="Só listar os pares")] = False,
) -> None:
    """Pares mínimos: ouça e diga qual das duas palavras foi."""
    import random

    from dor.modes import minimal_pairs
    from dor.storage.repos import Store

    lib = load_library()
    pool = list(lib.pairs.values())
    if contrast:
        pool = [p for p in pool if contrast in p.contrast]

    if not pool:
        console.print(Text("nenhum par com esse filtro", style="warn"))
        raise typer.Exit(1)

    if listar:
        table = Table(box=None, padding=(0, 2))
        table.add_column("contraste", style="bright_yellow")
        table.add_column("a", style="ro")
        table.add_column("", style="pt")
        table.add_column("b", style="ro")
        table.add_column("", style="pt")
        table.add_column("nível", style="dim")
        for p in pool:
            table.add_row(p.contrast, p.a.ro, p.a.pt, p.b.ro, p.b.pt, p.level)
        console.print(table)
        return

    rng = random.Random()

    with Store() as store:
        due = set(store.due_item_ids())
        seen = store.seen_item_ids()
    # Vencidos primeiro, depois os nunca vistos, depois o resto.
    pool.sort(key=lambda p: (p.id not in due, p.id in seen))
    chosen = pool[:limit]

    if not _prewarm(minimal_pairs.audio_texts(chosen)):
        raise typer.Exit(1)

    def exercises(store: Store):
        for pair in chosen:
            yield minimal_pairs.build(pair, rng=rng), pair.contrast

    _run_session(exercises, total=len(chosen), mode_label=minimal_pairs.MODE, silent=False)


@app.command()
def shadow(
    limit: Annotated[int, typer.Option("--limit", "-n")] = 8,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    rate: Annotated[str, typer.Option("--rate", help="Ritmo da 1ª passada")] = None,
) -> None:
    """Shadowing: ouça devagar, repita em voz alta, ouça na velocidade normal."""
    import random
    import time

    from dor.audio import tts
    from dor.modes import shadowing

    lib = load_library()
    steps = shadowing.build(lib, limit=limit, level=level, rng=random.Random())
    if not steps:
        console.print(Text("não há frases para este filtro", style="warn"))
        raise typer.Exit(1)

    slow = rate or shadowing.SLOW_RATE
    texts = shadowing.audio_texts(steps)
    if not _prewarm(texts, rate=slow) or not _prewarm(texts, rate=shadowing.NORMAL_RATE):
        raise typer.Exit(1)

    console.print(
        Text(f"\n{len(steps)} frases", style="bold")
        + Text(
            f"  ·  devagar ({slow}) → sua vez → velocidade normal  ·  Ctrl+C encerra\n",
            style="dim",
        )
    )

    try:
        for n, step in enumerate(steps, 1):
            console.print(Text(f"{n}/{len(steps)}  ", style="dim") + Text(step.ro, style="ro"))
            console.print(Text(f"  {step.pt}", style="hint"))

            tts.play(tts.synthesize(step.ro, rate=slow))
            console.print(Text("  ↻ sua vez...", style="dim cyan"))
            time.sleep(step.pause_ms / 1000)
            tts.play(tts.synthesize(step.ro, rate=shadowing.NORMAL_RATE))
            console.print()
    except (KeyboardInterrupt, EOFError):
        console.print(Text("\nencerrado", style="warn"))
        return

    console.print(Text("gata! ", style="bold ok") + Text("(pronto)", style="dim"))


@app.command()
def podcast(
    mode: Annotated[
        str, typer.Option("--mode", "-m", help="drill | passive | sleep")
    ] = "drill",
    theme: Annotated[str | None, typer.Option("--theme", "-t", help="Tag do vocabulário")] = None,
    deck: Annotated[str | None, typer.Option("--deck", "-d")] = None,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    minutes: Annotated[float | None, typer.Option("--minutes", help="Duração alvo")] = None,
    count: Annotated[int | None, typer.Option("--items", "-n", help="Nº de itens")] = None,
    pause: Annotated[int, typer.Option("--pause", help="Pausa para responder, em ms")] = 1800,
    number: Annotated[int, typer.Option("--number", help="Nº do episódio")] = 1,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Arquivo de saída")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Só mostrar o roteiro")] = False,
) -> None:
    """Gera um episódio MP3 para ouvir offline, com transcrição e tags ID3."""
    import random

    from rich.progress import BarColumn, Progress, TextColumn

    from dor.audio import studio

    lib = load_library()
    try:
        episode = studio.plan(
            lib,
            mode=mode,
            theme=theme,
            deck=deck,
            level=level,
            count=count,
            minutes=minutes if count is None else None,
            pause_ms=pause,
            number=number,
            rng=random.Random(),
        )
    except studio.StudioError as exc:
        console.print(Text(str(exc), style="err"))
        raise typer.Exit(1) from exc

    head = Text()
    head.append(episode.title, style="ro")
    head.append(f"\nmodo {episode.mode}  ·  {len(episode.item_ids)} itens  ·  ", style="dim")
    head.append(f"{len(episode.segments)} falas  ·  ~{episode.estimated_seconds / 60:.1f} min", style="dim")
    console.print(Panel(head, border_style="bright_yellow"))

    if dry_run:
        for seg in episode.segments:
            style = "ro" if seg.lang == "ro" else "pt"
            console.print(
                Text(f"  {seg.label or '·':<14}", style="dim")
                + Text(seg.text, style=style)
                + Text(f"   ({seg.rate}, +{seg.pause_ms}ms)", style="dim")
            )
        return

    config.ensure_user_dirs()
    out = out or (config.EXPORT_DIR / f"dor_{episode.mode}_{episode.theme}_{number:02d}.mp3")

    with Progress(
        TextColumn("  sintetizando"),
        BarColumn(bar_width=24),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("", total=len(episode.segments))
        try:
            result = studio.render(
                episode, out, on_progress=lambda done, _: progress.update(task, completed=done)
            )
        except studio.StudioError as exc:
            console.print(Text(str(exc), style="err"))
            raise typer.Exit(1) from exc

    transcript = studio.write_transcript(episode, out.with_suffix(".md"), lib)
    studio.write_playlist(
        [(result.path, episode.title, result.seconds)], out.with_suffix(".m3u")
    )

    kb = result.path.stat().st_size / 1024
    console.print(
        Text("✓ ", style="ok")
        + Text(str(result.path), style="bright_yellow")
        + Text(f"\n  {result.seconds / 60:.1f} min  ·  {kb:.0f} KB", style="dim")
        + Text(f"\n  transcrição: {transcript.name}", style="dim")
        + Text(f"  ·  playlist: {out.with_suffix('.m3u').name}", style="dim")
    )


@app.command("export-anki")
def export_anki(
    deck: Annotated[str | None, typer.Option("--deck", "-d")] = None,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    theme: Annotated[str | None, typer.Option("--theme", "-t")] = None,
    audio: Annotated[bool, typer.Option("--audio", help="Incluir os MP3 do cache")] = False,
    sintetizar: Annotated[
        bool, typer.Option("--sintetizar", help="Gerar o áudio que faltar (precisa de rede)")
    ] = False,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
) -> None:
    """Exporta o vocabulário para o Anki (TSV + pasta de mídia)."""
    from dor.audio import tts
    from dor.storage import anki

    lib = load_library()
    items = filter_vocab(lib, level=level, deck=deck, tag=theme)
    if not items:
        console.print(Text("nada bate com esse filtro", style="warn"))
        raise typer.Exit(1)

    config.ensure_user_dirs()
    label = deck or theme or level or "tudo"
    target = out or (config.EXPORT_DIR / f"dor_anki_{label}.tsv")

    audio_for = None
    if audio or sintetizar:
        settings = config.Settings.load()

        def audio_for(item):  # noqa: F811 — só existe quando o áudio foi pedido
            path = tts.cache_path(item.ro, settings.voice, settings.rate)
            if path.exists():
                return path
            if not sintetizar:
                return None
            try:
                return tts.synthesize(item.ro)
            except tts.TTSError:
                return None

        if sintetizar and not _prewarm([i.ro for i in items]):
            audio_for = None

    result = anki.export(items, target, audio_for=audio_for)

    console.print(
        Text("✓ ", style="ok")
        + Text(str(result.path), style="bright_yellow")
        + Text(f"\n  {result.notes} notas", style="dim")
    )
    if result.media_dir:
        console.print(
            Text(f"  {result.media} áudios em {result.media_dir.name}", style="dim")
            + Text("\n  copie o conteúdo dessa pasta para collection.media do Anki", style="hint")
        )
    console.print(
        Text("  no Anki: Arquivo → Importar. O separador e os campos já vêm no arquivo.", style="hint")
    )


@app.command("export-audio")
def export_audio(
    deck: Annotated[str | None, typer.Option("--deck", "-d")] = None,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    theme: Annotated[str | None, typer.Option("--theme", "-t")] = None,
    frases: Annotated[bool, typer.Option("--frases", help="Exportar frases, não palavras")] = False,
    voice: Annotated[str | None, typer.Option("--voice", "-v", help="alina | emil")] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Pasta de destino")] = None,
) -> None:
    """Exporta um MP3 por palavra (ou frase) mais uma playlist, para ouvir offline."""
    import shutil

    from rich.progress import BarColumn, Progress, TextColumn

    from dor.audio import studio, tts
    from dor.core.loader import filter_vocab

    lib = load_library()
    aliases = {"alina": config.VOICE_FEMALE, "emil": config.VOICE_MALE}
    voice_id = aliases.get(voice or "", voice)

    if frases:
        entries = [
            (s.ro, s.pt, s.id)
            for s in lib.sentences.values()
            if level is None or s.level == level
        ]
    else:
        entries = [
            (i.ro, i.pt_main, i.id)
            for i in filter_vocab(lib, level=level, deck=deck, tag=theme)
        ]

    if not entries:
        console.print(Text("nada bate com esse filtro", style="warn"))
        raise typer.Exit(1)

    config.ensure_user_dirs()
    label = deck or theme or level or ("frases" if frases else "tudo")
    folder = out or (config.EXPORT_DIR / f"dor_{label}")
    folder.mkdir(parents=True, exist_ok=True)

    playlist: list[tuple[Path, str, float]] = []
    failed = 0

    with Progress(
        TextColumn("  exportando"),
        BarColumn(bar_width=24),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("", total=len(entries))
        for n, (ro, pt, item_id) in enumerate(entries, 1):
            try:
                cached = tts.synthesize(ro, voice=voice_id)
            except tts.TTSError:
                failed += 1
                progress.update(task, completed=n)
                continue
            safe = "".join(c if c.isalnum() else "_" for c in item_id)
            target = folder / f"{n:03d}_{safe}.mp3"
            # Copiar do cache em vez de sintetizar de novo: o mesmo áudio serve
            # às sessões de estudo e ao arquivo exportado.
            shutil.copyfile(cached, target)
            playlist.append((target, f"{ro} — {pt}", studio.duration_seconds(target)))
            progress.update(task, completed=n)

    studio.write_playlist(playlist, folder / "playlist.m3u")

    total_seconds = sum(s for _, _, s in playlist)
    console.print(
        Text("✓ ", style="ok")
        + Text(str(folder), style="bright_yellow")
        + Text(f"\n  {len(playlist)} arquivos  ·  {total_seconds / 60:.1f} min", style="dim")
    )
    if failed:
        console.print(Text(f"  {failed} falharam (sem rede?)", style="warn"))


@app.command()
def stats(
    weeks: Annotated[int, typer.Option("--weeks", "-w", help="Semanas no calendário")] = 13,
    compact: Annotated[bool, typer.Option("--compact", "-c", help="Só o essencial")] = False,
) -> None:
    """Painel de progresso: nível, calendário, pontos fracos e carga futura."""
    from datetime import date

    from dor import config as cfg
    from dor.game import achievements as ach
    from dor.game import streaks as streaks_mod
    from dor.game import xp as xp_mod
    from dor.storage.repos import Store
    from dor.ui import dashboard as dash
    from dor.ui.feedback import xp_bar

    today = date.today()
    with Store() as store:
        data = store.overview()
        forecast = store.forecast(7)
        total_xp = store.total_xp()
        streak = store.get_streak()
        quests = store.load_quests(today)
        daily = store.daily_row(today)
        unlocked = store.unlocked_achievements()
        history = store.daily_history(max(400, weeks * 7))
        item_stats = store.group_stats("item_id")
        weak = store.weak_items(limit=6)
        rule_stats = store.group_stats("direction", min_reviews=3)
        mode_stats = store.group_stats("mode", min_reviews=3)
        hours = store.hour_activity()
        active_days = store.review_days()

    if not data["revisões"]:
        console.print(Text("nenhuma revisão ainda — comece com `dor review`", style="hint"))
        return

    settings = cfg.Settings.load()
    progress = xp_mod.progress(total_xp)

    head = Text()
    head.append("nível ", style="dim")
    head.append(str(progress.level), style="bold magenta")
    head.append("  ")
    head.append_text(xp_bar(progress.ratio))
    head.append(f"  {progress.xp_into_level}/{progress.xp_for_next}", style="dim")
    head.append(f"   ·   {total_xp} XP no total\n\n", style="dim")

    head.append("streak ", style="dim")
    head.append(f"{streak.current} dia(s)", style="bold ok")
    head.append(f"  (recorde {streak.longest})", style="dim")
    head.append(f"   ❄ {streak.freezes} escudo(s)", style="cyan")
    if streaks_mod.at_risk(streak, today):
        head.append("   ⚠ estude hoje ou a sequência quebra", style="bold warn")
    head.append("\n\n")

    head.append("meta de hoje ", style="dim")
    head.append_text(xp_bar(daily["xp"] / settings.daily_goal_xp if settings.daily_goal_xp else 1))
    head.append(f"  {daily['xp']}/{settings.daily_goal_xp} XP", style="dim")
    if daily["goal_met"]:
        head.append("  ✓", style="bold ok")
    console.print(head)

    console.print(Text("missões de hoje", style="bold"))
    for quest in quests:
        mark = Text("  ✔ ", style="ok") if quest.done else Text("  · ", style="dim")
        line = mark + xp_bar(quest.ratio, width=12)
        line.append(f"  {quest.progress}/{quest.target}  ", style="dim")
        line.append(quest.title, style="pt" if not quest.done else "dim strike")
        line.append(f"  +{quest.reward_xp}", style="dim xp")
        console.print(line)

    if history:
        console.print(Text("\nconstância", style="bold"))
        for line in dash.heatmap(
            history, today=today, goal=settings.daily_goal_xp, weeks=max(1, weeks)
        ):
            console.print(line)

    console.print()
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(justify="right")
    t.add_row("Itens em estudo", str(data["itens_em_estudo"]))
    t.add_row("Revisões", str(data["revisões"]))
    t.add_row("Acurácia", Text(f"{data['acurácia']:.0%}", style="ok"))
    t.add_row("Respostas 'quase'", Text(str(data["quase"]), style="warn"))
    t.add_row("Vencendo agora", Text(str(data["vencendo_agora"]), style="warn"))
    if data["leeches"]:
        t.add_row("Itens travados", Text(str(data["leeches"]), style="err"))
    t.add_row("", "")
    t.add_row("Aprendendo", str(data["aprendendo"]))
    t.add_row("Em revisão", str(data["revisão"]))
    t.add_row("Reaprendendo", str(data["reaprendendo"]))
    if active_days:
        t.add_row("", "")
        t.add_row("Dias com estudo", str(active_days))
        t.add_row("Revisões por dia", f"{data['revisões'] / active_days:.0f}")
    console.print(t)

    if not compact:
        lib = load_library()

        tags = dash.by_tag(item_stats, lib.vocab)
        if tags:
            console.print(Text("\ndomínio por tema", style="bold"))
            console.print(dash.domain_table(tags[:8]))
            console.print(Text("  o pior tema vem primeiro — é por onde começar", style="hint"))

        if weak:
            console.print(Text("\nonde você tropeça", style="bold"))
            rows = []
            for stat in weak:
                item = lib.vocab.get(stat.key)
                rows.append((item.ro if item else stat.key, item.pt_main if item else "", stat))
            console.print(dash.weak_table(rows))

        if rule_stats:
            console.print(Text("\ngramática por regra", style="bold"))
            rule_stats.sort(key=lambda s: s.score)
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style="pt")
            table.add_column(justify="right")
            table.add_column(justify="right", style="dim")
            for stat in rule_stats[:8]:
                rule = lib.grammar.get(stat.key)
                table.add_row(
                    rule.title if rule else stat.key,
                    Text(f"{stat.score:.0%}", style=dash.accuracy_style(stat.score)),
                    f"{stat.reviews}×",
                )
            console.print(table)

        if mode_stats:
            console.print(Text("\npor modo de estudo", style="bold"))
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style="pt")
            table.add_column()
            table.add_column(justify="right", style="dim")
            for stat in sorted(mode_stats, key=lambda s: -s.reviews):
                table.add_row(
                    stat.key,
                    dash.bar(stat.score, 14, style=dash.accuracy_style(stat.score)),
                    f"{stat.score:.0%}  ({stat.reviews})",
                )
            console.print(table)

        if hours:
            console.print(Text("\nquando você estuda", style="bold"))
            console.print(Text("  0h", style="dim") + dash.hour_strip(hours) + Text("23h", style="dim"))
            top = dash.best_hour(hours)
            if top:
                hour, n, acc = top
                console.print(
                    Text(f"  seu melhor horário é por volta das {hour}h", style="hint")
                    + Text(f" — {acc:.0%} de acerto em {n} revisões", style="dim")
                )

    peak = max((n for _, n in forecast), default=0)
    if peak:
        console.print(Text("\nPróximos 7 dias", style="bold"))
        for day, n in forecast:
            bar = "█" * round(n / peak * 24)
            console.print(Text(f"  {day}  ", style="dim") + Text(f"{bar} {n}", style="ro"))

    if unlocked:
        console.print(Text(f"\nConquistas  {len(unlocked)}/{len(ach.CATALOG)}", style="bold"))
        for code in unlocked:
            item = ach.BY_CODE.get(code)
            if item:
                console.print(
                    Text("  ★ ", style="yellow")
                    + Text(item.title, style="bold")
                    + Text(f"  — {item.description}", style="hint")
                )


@app.command("grade")
def grade_cmd(
    resposta: Annotated[str, typer.Argument(help="O que o aluno digitou")],
    alvo: Annotated[list[str], typer.Argument(help="Uma ou mais respostas aceitas")],
    lang: Annotated[str, typer.Option("--lang", "-l", help="Idioma da resposta: ro ou pt")] = "ro",
) -> None:
    """Testa o motor de correção contra uma resposta — útil para calibrar conteúdo."""
    from dor.core.grading import grade as run_grade
    from dor.ui import feedback

    result = run_grade(resposta, list(alvo), lang=lang)
    console.print(feedback.render(result))


@app.command()
def music(
    genre: Annotated[str | None, typer.Option("--genre", "-g", help="trap, folclor, fusion...")] = None,
) -> None:
    """Lista os artistas do acervo cultural."""
    lib = load_library()
    artists = list(lib.artists.values())
    if genre:
        artists = [a for a in artists if genre in a.genre]

    if not artists:
        console.print(Text("nenhum artista com esse filtro", style="warn"))
        raise typer.Exit(1)

    for a in artists:
        head = Text()
        head.append(a.name, style="ro")
        head.append(f"  {' · '.join(a.genre)}", style="dim")
        if a.era:
            head.append(f"  {a.era}", style="dim")
        if a.difficulty:
            head.append(f"  [{a.difficulty}]", style="hint")
        if a.dominant_register:
            head.append("  ")
            head.append_text(register_badge(a.dominant_register))
        head.append(f"\n{a.why_pt}", style="pt")
        for tr in a.tracks:
            head.append(f"\n  ♪ {tr.title}", style="bright_yellow")
            if tr.year:
                head.append(f" ({tr.year})", style="dim")
            head.append(f" — {tr.why_pt}", style="hint")
        # Sem Panel: `box=None` não é moldura nenhuma para o Rich, é um erro em
        # tempo de renderização. A lista de artistas nunca precisou de moldura.
        console.print(head)
        console.print()


@app.command()
def backup(
    restaurar: Annotated[
        Path | None, typer.Option("--restaurar", "-r", help="Arquivo .db a restaurar")
    ] = None,
    listar: Annotated[bool, typer.Option("--list", help="Listar os backups existentes")] = False,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    sim: Annotated[bool, typer.Option("--sim", "-y", help="Não perguntar ao restaurar")] = False,
) -> None:
    """Salva ou restaura o progresso."""
    from dor.storage import backup as backup_mod

    if listar:
        found = backup_mod.list_backups()
        if not found:
            console.print(Text("nenhum backup ainda — rode `dor backup`", style="hint"))
            return
        table = Table(box=None, padding=(0, 2))
        table.add_column("arquivo", style="bright_yellow")
        table.add_column("quando", style="dim")
        table.add_column("revisões", justify="right", style="ok")
        table.add_column("tamanho", justify="right", style="dim")
        for info in found:
            table.add_row(
                info.path.name,
                f"{info.created:%d/%m/%Y %H:%M}",
                str(info.reviews),
                f"{info.bytes / 1024:.0f} KB",
            )
        console.print(table)
        return

    if restaurar is not None:
        try:
            incoming = backup_mod.inspect(restaurar)
        except backup_mod.BackupError as exc:
            console.print(Text(str(exc), style="err"))
            raise typer.Exit(1) from exc

        if not sim:
            atual = ""
            if config.DB_PATH.exists():
                try:
                    now = backup_mod.inspect(config.DB_PATH)
                    atual = f"\nseu progresso atual: {now.reviews} revisões, {now.items} itens"
                except backup_mod.BackupError:
                    pass
            console.print(
                Text(f"restaurar {incoming.reviews} revisões de {restaurar.name}?", style="warn")
                + Text(atual, style="dim")
                + Text("\n(o progresso atual será salvo em um backup automático antes)", style="hint")
            )
            if console.input("  digite 'sim' para confirmar: ").strip().lower() != "sim":
                console.print(Text("cancelado", style="dim"))
                return

        info = backup_mod.restore(restaurar)
        console.print(
            Text("✓ restaurado  ", style="ok")
            + Text(f"{info.reviews} revisões · {info.items} itens", style="dim")
        )
        return

    try:
        info = backup_mod.create(out)
    except backup_mod.BackupError as exc:
        console.print(Text(str(exc), style="err"))
        raise typer.Exit(1) from exc

    console.print(
        Text("✓ ", style="ok")
        + Text(str(info.path), style="bright_yellow")
        + Text(f"\n  {info.reviews} revisões · {info.items} itens · {info.bytes / 1024:.0f} KB", style="dim")
        + Text("\n  restaurar depois:  dor backup --restaurar <arquivo>", style="hint")
    )


@app.command()
def undo() -> None:
    """Desfaz a última resposta e reagenda o item."""
    from dor.storage.repos import Store

    with Store() as store:
        review = store.undo_last_review()

    if review is None:
        console.print(Text("não há resposta para desfazer", style="hint"))
        return

    lib = load_library()
    item = lib.vocab.get(review["item_id"])
    label = item.ro if item else review["item_id"]

    console.print(
        Text("✓ desfeito  ", style="ok")
        + Text(label, style="ro")
        + Text(f"  ({review['verdict']}, {review['mode']})", style="dim")
        + Text("\n  o agendamento foi recalculado a partir do histórico restante", style="hint")
    )


@app.command()
def destravar(
    palavra: Annotated[str | None, typer.Argument(help="Palavra ou ID; vazio = todas")] = None,
) -> None:
    """Tira a marca de 'travado' de um item que voltou a entrar."""
    from dor.storage.repos import Store

    lib = load_library()
    item_id = None
    if palavra:
        item = lib.vocab.get(palavra) or next(
            (i for i in lib.vocab.values() if i.ro.lower() == palavra.lower()), None
        )
        if item is None:
            console.print(Text(f"não encontrei '{palavra}'", style="err"))
            raise typer.Exit(1)
        item_id = item.id

    with Store() as store:
        travadas = store.leech_item_ids()
        n = store.unleech(item_id)

    if not n:
        if travadas:
            console.print(Text(f"{len(travadas)} item(ns) travado(s), mas nenhum bate", style="warn"))
        else:
            console.print(Text("nenhum item travado — nada a fazer", style="ok"))
        return

    console.print(
        Text(f"✓ {n} item(ns) destravado(s)", style="ok")
        + Text("\n  voltam a subir de dificuldade normalmente", style="hint")
    )


@app.command()
def settings(
    meta: Annotated[int | None, typer.Option("--meta", help="XP por dia")] = None,
    voz: Annotated[str | None, typer.Option("--voz", help="alina | emil")] = None,
    ritmo: Annotated[str | None, typer.Option("--ritmo", help="ex.: -20%, +0%")] = None,
    autoplay: Annotated[bool | None, typer.Option("--autoplay/--sem-autoplay")] = None,
) -> None:
    """Mostra ou altera suas preferências."""
    current = config.Settings.load()
    aliases = {"alina": config.VOICE_FEMALE, "emil": config.VOICE_MALE}

    changed = False
    if meta is not None:
        current.daily_goal_xp = max(10, meta)
        changed = True
    if voz is not None:
        current.voice = aliases.get(voz, voz)
        changed = True
    if ritmo is not None:
        current.rate = ritmo
        changed = True
    if autoplay is not None:
        current.autoplay = autoplay
        changed = True

    if changed:
        current.save()

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("meta diária", f"{current.daily_goal_xp} XP")
    t.add_row("voz", current.voice)
    t.add_row("ritmo", current.rate)
    t.add_row("autoplay", "sim" if current.autoplay else "não")
    t.add_row("arquivo", str(config.SETTINGS_PATH))
    console.print(t)
    if changed:
        console.print(Text("\n✓ salvo", style="ok"))
    else:
        console.print(Text("\nex.:  dor settings --meta 200 --voz emil", style="hint"))


@app.command()
def lupta(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Tamanho da luta")] = 12,
    vidas: Annotated[int, typer.Option("--vidas", "-v")] = 3,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Boss Battle: só as palavras que te derrubam, com vidas contadas."""
    import random

    from dor.modes import mixer, translation
    from dor.storage.repos import Store

    lib = load_library()
    rng = random.Random()

    with Store() as store:
        # O chefe é feito das SUAS palavras fracas, não de itens aleatórios.
        # Uma luta com vocabulário fácil não é desafio, é perda de tempo.
        fracas = [s.key for s in store.weak_items(min_reviews=2, limit=limit)]
        travadas = [i for i in store.leech_item_ids() if i not in fracas]
        ids = [i for i in [*fracas, *travadas] if i in lib.vocab][:limit]

    if len(ids) < 3:
        console.print(
            Text("você ainda não tem palavras fracas suficientes para uma luta.", style="warn")
            + Text("\nestude com `dor review` primeiro — o chefe é feito do seu histórico.", style="hint")
        )
        raise typer.Exit(1)

    rng.shuffle(ids)
    pool = list(lib.vocab.values())

    head = Text("LUPTĂ", style="bold red")
    head.append(f"   {len(ids)} palavras que você errou  ·  ", style="dim")
    head.append("♥" * vidas, style="bold red")
    head.append("\nsem múltipla escolha: aqui você produz, ou perde uma vida.", style="hint")
    console.print(Panel(head, border_style="red"))

    def exercises(store: Store):
        for item_id in ids:
            item = lib.vocab[item_id]
            card = store.get_card(item_id)
            # Produção forçada: a luta não aceita reconhecimento.
            exercise = mixer.pick(
                item, card, lib, pool, rng=rng, allow={translation.MODE}
            )
            yield exercise, ""

    answered, correct, left = _run_session(
        exercises, total=len(ids), mode_label="lupta", silent=silent, lives=vidas, lib=lib
    )

    if left <= 0:
        verdict = Text("derrota", style="bold err")
        verdict.append(f"\nvocê acertou {correct} de {answered} antes de cair.", style="pt")
        verdict.append("\nessas palavras voltam amanhã — o agendador já anotou.", style="hint")
    elif correct == answered and answered:
        verdict = Text("vitória perfeita", style="bold ok")
        verdict.append(f"\n{correct} de {answered}, com {left} vida(s) de sobra.", style="pt")
        verdict.append("\nessas palavras deixaram de ser suas fracas.", style="hint")
    else:
        verdict = Text("sobreviveu", style="bold warn")
        verdict.append(f"\n{correct} de {answered}, com {left} vida(s).", style="pt")
    console.print(Panel(verdict, border_style="red"))


@app.command()
def punte(
    ref: Annotated[str | None, typer.Argument(help="ID ou padrão (ex.: cao, ct)")] = None,
    kind: Annotated[str | None, typer.Option("--tipo", "-k", help="sunet | sufix")] = None,
    treinar: Annotated[bool, typer.Option("--treinar", "-t", help="Treinar a ponte")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 15,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Cognate Bridge: as correspondências que transformam português em romeno."""
    import random

    from dor.core.normalize import fold, normalize
    from dor.modes import bridge as bridge_mode
    from dor.ui import cards

    lib = load_library()
    bridges = list(lib.bridges.values())
    if kind:
        bridges = [b for b in bridges if b.kind == kind]
    if not bridges:
        console.print(Text("nenhuma ponte com esse filtro", style="warn"))
        raise typer.Exit(1)

    def loose(text: str) -> str:
        return fold(normalize(text))

    if ref is None:
        if treinar:
            # Sem ponte escolhida, treinar é a sessão MISTA: é ela que ensina a
            # escolher o padrão, não só a aplicá-lo.
            exercises = bridge_mode.build_mixed(bridges, limit=limit, rng=random.Random())
            _bridge_session(exercises, silent=silent)
            return

        table = Table(box=None, padding=(0, 2))
        table.add_column("ponte", style="bright_yellow", no_wrap=True, min_width=11)
        table.add_column("correspondência", no_wrap=True)
        table.add_column("exemplo", no_wrap=True)
        table.add_column("", style="hint", no_wrap=True)
        for b in sorted(bridges, key=lambda b: (b.kind, b.id)):
            first = b.examples[0]
            table.add_row(
                b.id.removeprefix("br."),
                Text(b.pt, style="pt") + Text("  →  ", style="dim") + Text(b.ro, style="ro"),
                Text(first["pt"], style="dim")
                + Text("  →  ", style="dim")
                + Text(first["ro"], style="ro"),
                "produtiva" if b.productive else "",
            )
        console.print(table)
        console.print(
            Text(f"\n{len(bridges)} pontes  ·  ", style="dim")
            + Text("dor punte <ponte>", style="hint")
            + Text("  ·  sessão misturada:  ", style="dim")
            + Text("dor punte -t", style="hint")
        )
        return

    needle = loose(ref)
    matches = [b for b in bridges if needle in loose(b.id)] or [
        b for b in bridges if needle in loose(b.pt) or needle in loose(b.title)
    ]
    if not matches:
        console.print(Text(f"não encontrei '{ref}'", style="err"))
        raise typer.Exit(1)

    b = matches[0]
    console.print(cards.bridge_card(b))
    if not treinar:
        return

    _bridge_session(bridge_mode.build_all(b, rng=random.Random())[:limit], silent=silent)


def _bridge_session(exercises: list, *, silent: bool) -> None:
    from dor.modes import bridge as bridge_mode
    from dor.storage.repos import Store

    if not exercises:
        console.print(Text("esta ponte não tem material de treino", style="hint"))
        return
    if not silent:
        _prewarm([e.speak_after for e in exercises if e.speak_after])

    def supply(store: Store):
        for exercise in exercises:
            yield exercise, ""

    _run_session(supply, total=len(exercises), mode_label=bridge_mode.MODE, silent=silent)


@app.command()
def zi(
    ref: Annotated[str | None, typer.Argument(help="ID ou parte do título (ex.: cafenea)")] = None,
    level: Annotated[str | None, typer.Option("--level", "-l")] = None,
    treinar: Annotated[bool, typer.Option("--treinar", "-t", help="Treinar as fórmulas")] = False,
    ouvir: Annotated[bool, typer.Option("--ouvir", "-o", help="Tocar o diálogo inteiro")] = False,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Vida cotidiana: o diálogo, as fórmulas, a rua e a etiqueta."""
    import random
    import time

    from dor.core.models import LEVEL_ORDER
    from dor.core.normalize import fold, normalize
    from dor.modes import scene as scene_mode
    from dor.storage.repos import Store
    from dor.ui import cards

    lib = load_library()
    scenes = sorted(lib.scenes.values(), key=lambda s: (LEVEL_ORDER.get(s.level, 9), s.id))
    if level:
        scenes = [s for s in scenes if s.level == level.upper()]
    if not scenes:
        console.print(Text("nenhuma cena com esse filtro", style="warn"))
        raise typer.Exit(1)

    def loose(text: str) -> str:
        return fold(normalize(text))

    if ref is None:
        table = Table(box=None, padding=(0, 2))
        table.add_column("nível", style="dim")
        table.add_column("cena", style="ro")
        table.add_column("onde", style="dim")
        table.add_column("o que você aprende", style="pt")
        for item in scenes:
            table.add_row(item.level, item.title, item.place_pt, item.goal_pt)
        console.print(table)
        console.print(Text("\nrode:  dor zi <cena>   ·   treinar:  -t   ·   ouvir:  -o", style="hint"))
        return

    needle = loose(ref)
    matches = [
        s
        for s in scenes
        if needle in loose(s.id) or needle in loose(s.title) or needle in loose(s.title_ro or "")
    ]
    if not matches:
        console.print(Text(f"não encontrei '{ref}'", style="err"))
        raise typer.Exit(1)

    item = matches[0]
    console.print(cards.scene_card(item))

    if ouvir and not silent:
        # Vozes alternadas: sem isso o diálogo vira monólogo e o ouvido não
        # separa quem está falando.
        from dor.audio import tts

        def voice_for(turn: dict[str, str]) -> str:
            return config.VOICE_FEMALE if turn["who"] == "ei" else config.VOICE_MALE

        falas = [(t["ro"], voice_for(t)) for t in item.turns]
        if _prewarm([ro for ro, _ in falas]):
            for ro, voice in falas:
                console.print(Text(f"  {ro}", style="ro"))
                try:
                    tts.play(tts.synthesize(ro, voice=voice))
                except tts.TTSError:
                    pass
                time.sleep(0.4)

    if not treinar:
        return

    exercises = scene_mode.build_all(item, rng=random.Random())
    if not exercises:
        console.print(Text("esta cena não tem fórmulas para treinar", style="hint"))
        return

    if not silent:
        _prewarm([e.speak_after for e in exercises if e.speak_after])

    def supply(store: Store):
        for exercise in exercises:
            yield exercise, ""

    _run_session(supply, total=len(exercises), mode_label=scene_mode.MODE, silent=silent)


@app.command()
def livros(
    ref: Annotated[str | None, typer.Argument(help="ID, título ou autor")] = None,
    level: Annotated[str | None, typer.Option("--level", "-l", help="A2, B1, B2, C1, C2")] = None,
    livre: Annotated[
        bool, typer.Option("--livre", help="Só o que está em domínio público")
    ] = False,
    treinar: Annotated[bool, typer.Option("--treinar", "-t", help="Estudar o glossário")] = False,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Biblioteca graduada: o que ler em romeno, e em que ordem."""
    import random

    from dor.core.models import LEVEL_ORDER
    from dor.core.normalize import fold, normalize
    from dor.modes import reading
    from dor.storage.repos import Store
    from dor.ui import cards

    lib = load_library()
    books = sorted(lib.books.values(), key=lambda b: (LEVEL_ORDER.get(b.level, 9), b.year or 0))
    if level:
        books = [b for b in books if b.level == level.upper()]
    if livre:
        books = [b for b in books if b.public_domain]
    if not books:
        console.print(Text("nenhum livro com esse filtro", style="warn"))
        raise typer.Exit(1)

    def loose(text: str) -> str:
        return fold(normalize(text))

    if ref is None:
        table = Table(box=None, padding=(0, 2))
        table.add_column("nível", style="dim")
        table.add_column("título", style="ro")
        table.add_column("autor", style="pt")
        table.add_column("gênero", style="dim")
        table.add_column("texto", justify="right")
        for book in books:
            table.add_row(
                book.level,
                book.title,
                book.author,
                book.kind_pt,
                Text("livre", style="ok") if book.public_domain else Text("comprar", style="dim"),
            )
        console.print(table)
        console.print(
            Text("\nordenada pela dificuldade real para quem fala português", style="hint")
        )
        console.print(Text("rode:  dor livros <título>   ·   treinar:  -t", style="hint"))
        return

    needle = loose(ref)
    matches = [b for b in books if needle in loose(b.id) or needle in loose(b.title)] or [
        b for b in books if needle in loose(b.author)
    ]
    if not matches:
        console.print(Text(f"não encontrei '{ref}'", style="err"))
        raise typer.Exit(1)

    book = matches[0]
    console.print(cards.book_card(book))

    if not treinar:
        return

    rng = random.Random()
    exercises = reading.build_all(book, rng=rng)
    if not exercises:
        console.print(Text("esta ficha não tem material de treino", style="hint"))
        return

    if not silent:
        falas = [e.speak_before or e.speak_after for e in exercises]
        _prewarm([f for f in falas if f])

    def supply(store: Store):
        for exercise in exercises:
            yield exercise, ""

    _run_session(supply, total=len(exercises), mode_label=reading.MODE, silent=silent)


@app.command()
def istorie(
    ref: Annotated[
        str | None, typer.Argument(help="ID, parte do título ou uma palavra (ex.: cafea)")
    ] = None,
    era: Annotated[str | None, typer.Option("--era", "-e", help="dacia, roma, fanariot...")] = None,
    palavras: Annotated[
        bool, typer.Option("--palavras", "-p", help="Só as camadas de vocabulário")
    ] = False,
) -> None:
    """A história da Romênia contada pelo que ela fez com a língua."""
    from dor.core.models import ERA_LABEL_PT
    from dor.core.normalize import fold, normalize
    from dor.ui import cards

    lib = load_library()
    events = lib.timeline
    if era:
        events = [e for e in events if e.era == era]
    if not events:
        console.print(Text("nenhum evento com esse filtro", style="warn"))
        raise typer.Exit(1)

    def loose(text: str) -> str:
        return fold(normalize(text))

    if palavras:
        table = Table(box=None, padding=(0, 2))
        table.add_column("palavra", style="ro", no_wrap=True)
        table.add_column("português", style="pt")
        table.add_column("veio de", style="dim")
        for event in events:
            for word in event.words:
                table.add_row(word["ro"], word["pt"], f"{event.title} ({event.when})")
        console.print(table)
        return

    if ref:
        needle = loose(ref)
        matches = [e for e in events if needle in loose(e.id) or needle in loose(e.title)]
        if not matches:
            # Buscar pela palavra: "de onde vem 'cafea'?" é a pergunta mais
            # provável de quem chega aqui.
            matches = [
                e for e in events if any(needle in loose(w["ro"]) for w in e.words)
            ]
        if not matches:
            console.print(Text(f"não encontrei '{ref}'", style="err"))
            raise typer.Exit(1)
        rules = {r.id: r.title for r in lib.grammar.values()}
        for event in matches[:3]:
            console.print(cards.event_card(event, rules=rules))
        return

    current = None
    for event in events:
        if event.era != current:
            current = event.era
            console.print(
                Text(f"\n{ERA_LABEL_PT.get(current, current)}", style="bold bright_cyan")
            )
        line = Text(f"  {event.when:>12}  ", style="dim")
        line.append(event.title, style="pt")
        if event.words:
            line.append(f"   {len(event.words)} palavras", style="hint")
        console.print(line)

    console.print(
        Text(f"\n{len(events)} eventos  ·  ", style="dim")
        + Text("dor istorie <evento>", style="hint")
        + Text("  ·  de onde vem uma palavra: ", style="dim")
        + Text("dor istorie cafea", style="hint")
    )


@app.command()
def lyrics(
    track_ref: Annotated[
        str | None, typer.Argument(help="ID ou parte do título (ex.: miorita)")
    ] = None,
    genre: Annotated[str | None, typer.Option("--genre", "-g")] = None,
    ler: Annotated[bool, typer.Option("--ler", "-r", help="Só a ficha, sem treinar")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 12,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Lyrics Lab: estuda uma faixa pelo glossário e pelos versos citáveis."""
    import random

    from dor.modes import lyrics as lyrics_mode
    from dor.storage.repos import Store
    from dor.ui import cards

    lib = load_library()
    tracks = lib.tracks
    if genre:
        tracks = [t for t in tracks if genre in lib.artists[t.artist_id].genre]

    if track_ref is None:
        table = Table(box=None, padding=(0, 2))
        table.add_column("faixa", style="ro")
        table.add_column("artista", style="pt")
        table.add_column("material", justify="right", style="dim")
        for track in tracks:
            n = len(lyrics_mode.usable_excerpt(track)) + len(track.glossary)
            table.add_row(
                track.title,
                track.artist_name,
                Text(f"{n} exercícios", style="ok") if n else Text("só ouvir", style="dim"),
            )
        console.print(table)
        console.print(Text("\nrode:  dor lyrics <faixa>", style="hint"))
        return

    # Busca sem diacrítico: quem digita "miorita" no terminal quer "Miorița".
    from dor.core.normalize import fold, normalize

    def loose(text: str) -> str:
        return fold(normalize(text))

    needle = loose(track_ref)
    matches = [t for t in tracks if needle in loose(t.id) or needle in loose(t.title)] or [
        t for t in tracks if needle in loose(t.artist_name)
    ]
    if not matches:
        console.print(Text(f"não encontrei '{track_ref}'", style="err"))
        raise typer.Exit(1)

    track = matches[0]
    artist = lib.artists.get(track.artist_id)
    console.print(cards.track_card(track, artist))

    rng = random.Random()
    exercises = lyrics_mode.build_all(track, rng=rng)[:limit]
    if ler or not exercises:
        return

    if not silent:
        falas = [e.speak_before or e.speak_after for e in exercises]
        _prewarm([f for f in falas if f])

    def supply(store: Store):
        for exercise in exercises:
            yield exercise, ""

    _run_session(supply, total=len(exercises), mode_label=lyrics_mode.MODE, silent=silent)


@app.command()
def slang(
    register: Annotated[str | None, typer.Option("--register", "-r")] = None,
    kind: Annotated[str | None, typer.Option("--kind", "-k", help="cuvant, expresie, proverb")] = None,
) -> None:
    """Lista gíria, expressões e provérbios com o espelho em português."""
    lib = load_library()
    items = list(lib.slang.values())
    if register:
        items = [i for i in items if i.register == register]
    if kind:
        items = [i for i in items if i.kind == kind]

    if not items:
        console.print(Text("nenhuma entrada com esse filtro", style="warn"))
        raise typer.Exit(1)

    table = Table(box=None, padding=(0, 2))
    table.add_column("romeno", style="ro")
    table.add_column("português", style="pt")
    table.add_column("registro")
    table.add_column("espelho PT-BR", style="bright_green")
    table.add_column("origem", style="dim italic")

    for i in items:
        table.add_row(
            i.ro,
            ", ".join(i.pt),
            register_badge(i.register),
            i.pt_mirror or "",
            etymology_note(i.etymology).split(" — ")[0],
        )
    console.print(table)
    console.print(Text(f"\n{len(items)} entrada(s)", style="dim"))


# --------------------------------------------------------------------------- #
# acervo pessoal: versuri, jurnal, atualizar
# --------------------------------------------------------------------------- #


def _local_or_hint():
    """Carrega o acervo pessoal e põe na tela o que estiver malformado.

    Erro de conteúdo aqui não derruba a sessão: o acervo é editado à mão toda
    semana, e um arquivo torto não pode esconder os outros nove.
    """
    from dor.core.local import load_local

    content = load_local()
    for issue in content.issues:
        console.print(Text(f"  ⚠ {issue}", style="warn"))
    return content


def _piece_table(pieces, *, kind_label: str) -> Table:
    table = Table(box=None, padding=(0, 2))
    table.add_column("id", style="bright_yellow", no_wrap=True)
    table.add_column(kind_label, style="pt")
    table.add_column("de", style="dim")
    table.add_column("semana", style="dim", no_wrap=True)
    table.add_column("partes", justify="right", style="dim")
    for piece in pieces:
        table.add_row(
            piece.id,
            piece.title,
            piece.author or piece.source or "",
            piece.week,
            str(len(piece.parts)),
        )
    return table


def _study_piece(piece, *, limit: int, silent: bool) -> None:
    """Ficha primeiro, exercício depois — a mesma ordem do resto do app."""
    import random

    from dor.modes import lote as lote_mode
    from dor.storage.repos import Store
    from dor.ui import cards

    console.print(cards.piece_card(piece))

    exercises = lote_mode.exercises_for(piece, rng=random.Random(), limit=limit)
    if not exercises:
        console.print(
            Text("sem glossário nem lacuna nesta peça — é material de leitura", style="hint")
        )
        return

    def supply(store: Store):
        for exercise in exercises:
            yield exercise, ""

    _run_session(
        supply,
        total=len(exercises),
        mode_label=lote_mode.mode_for(piece),
        silent=silent,
    )


def _acervo_vazio(kind: str) -> None:
    console.print(Text(f"nada de {kind} no acervo pessoal ainda.", style="warn"))
    console.print(
        Text(f"o material fica em {config.LOCAL_DIR} — fora do repositório.", style="hint")
    )
    console.print(Text(f"esqueleto:  dor atualizar --modelo {kind}", style="hint"))
    console.print(Text("importar:   dor atualizar", style="hint"))


@app.command()
def versuri(
    faixa: Annotated[str | None, typer.Argument(help="ID ou pedaço do título")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Máximo de exercícios")] = 12,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """Música parte por parte: o verso, a tradução, a gíria e o exercício."""
    from dor.core.local import find

    content = _local_or_hint()
    pieces = content.of_kind("versuri")
    if not pieces:
        _acervo_vazio("versuri")
        raise typer.Exit(1)

    if faixa is None:
        console.print(_piece_table(pieces, kind_label="faixa"))
        console.print(Text("\nestude uma:  dor versuri <id>", style="hint"))
        return

    piece = find(content, faixa, kind="versuri")
    if piece is None:
        console.print(Text(f"não achei a faixa '{faixa}'", style="err"))
        raise typer.Exit(1)
    _study_piece(piece, limit=limit, silent=silent)


@app.command()
def jurnal(
    noticia: Annotated[str | None, typer.Argument(help="ID ou pedaço do título")] = None,
    semana: Annotated[str | None, typer.Option("--semana", "-w", help="Ex.: 2026-W34")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Máximo de exercícios")] = 12,
    silent: Annotated[bool, typer.Option("--silent", "-s")] = False,
) -> None:
    """O jornal da semana: notícia em romeno, com glossário e exercício."""
    from dor.core.local import find

    content = _local_or_hint()
    pieces = content.of_kind("jurnal")
    if semana:
        pieces = [p for p in pieces if p.week == semana]
    if not pieces:
        _acervo_vazio("jurnal")
        raise typer.Exit(1)

    if noticia is None:
        console.print(_piece_table(pieces, kind_label="notícia"))
        console.print(Text("\nleia uma:  dor jurnal <id>", style="hint"))
        return

    piece = find(content, noticia, kind="jurnal")
    if piece is None:
        console.print(Text(f"não achei a notícia '{noticia}'", style="err"))
        raise typer.Exit(1)
    _study_piece(piece, limit=limit, silent=silent)


#: Esqueleto do arquivo de lote. Sai pelo `--modelo` em vez de virar seção de
#: documentação: modelo que não se copia direto do terminal envelhece calado.
TEMPLATE_LOTE: dict[str, Any] = {
    "meta": {"id": "", "kind": "", "week": "", "title": ""},
    "pieces": [
        {
            "id": "",
            "title": "",
            "author": "",
            "source": "",
            "link": "",
            "level": "B1",
            "why_pt": "por que vale estudar esta peça",
            "parts": [
                {
                    "at": "0:00",
                    "ro": ["linha em romeno"],
                    "pt": ["tradução da linha"],
                    "explica_pt": "o que está acontecendo aqui",
                    "glossary": [{"ro": "", "pt": "", "register": "colocvial", "note": ""}],
                    "cloze_answer": "",
                }
            ],
        }
    ],
}


def _slug(text: str) -> str:
    """Pedaço de nome de arquivo a partir de um título."""
    from dor.core.normalize import fold, normalize

    limpo = re.sub(r"[^a-z0-9]+", "_", fold(normalize(text)))
    return limpo.strip("_") or "faixa"


def _lote_da_letra(caminho: Path, *, titulo: str | None, artista: str | None) -> dict[str, Any]:
    """Transforma um .txt colado num esqueleto de lote, uma parte por estrofe.

    A estrofe é a unidade certa: é o pedaço que o comentário consegue explicar
    inteiro sem virar aula de linha. Linha em branco separa — que é como todo
    site de letra já entrega o texto.
    """
    from dor.core.local import current_week

    bruto = caminho.read_text(encoding="utf-8")
    estrofes = [
        [linha.strip() for linha in bloco.splitlines() if linha.strip()]
        for bloco in re.split(r"\n\s*\n", bruto)
    ]
    estrofes = [e for e in estrofes if e]
    if not estrofes:
        raise ValueError("arquivo vazio")

    week = current_week()
    nome = titulo or caminho.stem
    piece_id = f"{_slug(artista or 'faixa')}.{_slug(nome)}"
    return {
        "meta": {
            "id": f"{week.lower()}-{_slug(nome)}",
            "kind": "versuri",
            "week": week,
            "title": nome,
        },
        "pieces": [
            {
                "id": piece_id,
                "title": nome,
                "author": artista or "",
                "level": "B1",
                "why_pt": "",
                "parts": [
                    {
                        "at": f"estrofe {n}",
                        "ro": estrofe,
                        "pt": [],
                        "explica_pt": "",
                        "glossary": [],
                    }
                    for n, estrofe in enumerate(estrofes, 1)
                ],
            }
        ],
    }


def _read_lote(path):
    """Lê e valida UM arquivo de lote. Devolve o payload ou None, com o erro na tela.

    Separado do `load_local` porque aqui o silêncio é proibido: importar é uma
    ação do usuário, e um arquivo que não entrou precisa dizer por quê.
    """
    import json

    from dor.core.loader import check_schema
    from dor.core.local import SCHEMA

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        console.print(Text(f"  ✗ {path.name}: JSON inválido — {exc}", style="err"))
        return None

    issues = check_schema(path, SCHEMA, payload)
    if issues:
        console.print(Text(f"  ✗ {path.name} não entrou:", style="err"))
        for issue in issues:
            console.print(Text(f"      {issue}", style="err"))
        return None
    return payload


@app.command()
def atualizar(
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", "-m", help="Imprime o esqueleto de um lote: versuri | jurnal"),
    ] = None,
    letra: Annotated[
        Path | None,
        typer.Option("--letra", "-l", help="Arquivo .txt com a letra colada, para virar lote"),
    ] = None,
    titulo: Annotated[str | None, typer.Option("--titulo", help="Título da faixa")] = None,
    artista: Annotated[str | None, typer.Option("--artista", help="Quem canta")] = None,
    tudo: Annotated[
        bool, typer.Option("--tudo", help="Mostra todas as semanas, não só as quatro últimas")
    ] = False,
) -> None:
    """Importa o lote da semana e mostra o acervo pessoal por semana.

    O ciclo é semanal e manual de propósito: quem escolhe a música e a notícia
    é uma pessoa, e o app não sai à internet sozinho. Este comando é o momento
    em que o material da semana entra no acervo e vira exercício.
    """
    import json
    import shutil

    from dor.core.local import KIND_LABEL_PT, current_week, load_local

    if modelo is not None:
        if modelo not in KIND_LABEL_PT:
            console.print(Text(f"tipo desconhecido: {modelo} (use versuri ou jurnal)", style="err"))
            raise typer.Exit(1)
        skeleton = json.loads(json.dumps(TEMPLATE_LOTE))
        week = current_week()
        skeleton["meta"].update(id=f"{week.lower()}-{modelo}", kind=modelo, week=week)
        console.print_json(json.dumps(skeleton, ensure_ascii=False))
        return

    config.ensure_user_dirs()

    # A letra vem SEMPRE de um arquivo seu. O app monta a estrutura — uma parte
    # por estrofe — e deixa tradução, comentário e glossário em branco, que é o
    # trabalho de anotação da semana. O texto da faixa é seu e fica aqui.
    if letra is not None:
        if not letra.exists():
            console.print(Text(f"não achei o arquivo {letra}", style="err"))
            raise typer.Exit(1)
        try:
            lote = _lote_da_letra(letra, titulo=titulo, artista=artista)
        except (OSError, ValueError) as exc:
            console.print(Text(f"não deu para ler a letra: {exc}", style="err"))
            raise typer.Exit(1) from exc

        destino = config.INBOX_DIR / f"{lote['meta']['id']}.json"
        destino.write_text(
            json.dumps(lote, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        partes = len(lote["pieces"][0]["parts"])
        console.print(Text(f"esqueleto criado — {partes} estrofe(s)", style="bold ok"))
        console.print(Text(f"  {destino}", style="pt"))
        console.print(
            Text(
                "anote tradução, explicação e glossário e rode `dor atualizar` para importar.",
                style="hint",
            )
        )
        return

    # 1. A caixa de entrada vira acervo — um arquivo por vez, e só se validar.
    importados: list[str] = []
    for path in sorted(config.INBOX_DIR.glob("*.json")):
        payload = _read_lote(path)
        if payload is None:
            continue
        meta = payload["meta"]
        destino = config.LOCAL_DIR / meta["kind"]
        destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / f"{meta['week']}-{meta['id']}.json"
        shutil.move(str(path), alvo)
        importados.append(f"{KIND_LABEL_PT[meta['kind']]}: {alvo.name}")

    if importados:
        console.print(Text("importado", style="bold ok"))
        for linha in importados:
            console.print(Text(f"  {linha}", style="pt"))
        console.print()

    # 2. O retrato do acervo, semana a semana.
    content = load_local()
    if not content.pieces:
        console.print(Text("acervo pessoal vazio.", style="warn"))
        console.print(Text(f"solte um lote em {config.INBOX_DIR} e rode de novo.", style="hint"))
        console.print(Text("esqueleto:  dor atualizar --modelo jurnal", style="hint"))
        return

    semanas = content.weeks()
    if not tudo:
        semanas = semanas[:4]

    hoje = current_week()
    table = Table(box=None, padding=(0, 2))
    table.add_column("semana", no_wrap=True)
    table.add_column("música", style="pt")
    table.add_column("jornal", style="pt")
    for week in semanas:
        da_semana = [p for p in content.pieces.values() if p.week == week]
        musica = [p.title for p in da_semana if p.kind == "versuri"]
        jornal = [p.title for p in da_semana if p.kind == "jurnal"]
        rotulo = Text(week, style="bold ok" if week == hoje else "bright_yellow")
        table.add_row(rotulo, "\n".join(musica), "\n".join(jornal))
    console.print(table)

    if hoje not in content.weeks():
        console.print(Text(f"\nnada de {hoje} ainda — a semana está aberta.", style="warn"))
    console.print(Text("\nestudar:  dor versuri   ·   dor jurnal", style="hint"))


if __name__ == "__main__":
    app()
