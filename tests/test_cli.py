"""A camada de comandos: tela inicial, preferências e a luta.

Aqui o alvo é o comportamento visível — o que o usuário vê ao digitar `dor`
sem argumento, e as guardas que impedem um comando de explodir num acervo
vazio.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dor import config
from dor.cli import app


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """Cada teste com o seu diretório de usuário — nada toca o progresso real."""
    for name, sub in (
        ("USER_DIR", ""),
        ("DB_PATH", "progress.db"),
        ("AUDIO_CACHE_DIR", "audio_cache"),
        ("EXPORT_DIR", "exports"),
        ("SETTINGS_PATH", "settings.json"),
    ):
        monkeypatch.setattr(config, name, tmp_path / sub if sub else tmp_path)
    return tmp_path


@pytest.fixture
def run(user_dir):
    runner = CliRunner()
    return lambda *args: runner.invoke(app, list(args))


# --------------------------------------------------------------------------- #
# tela inicial
# --------------------------------------------------------------------------- #


def test_dor_sem_argumento_nao_despeja_o_help(run):
    """Quem chega sem lembrar o comando quer saber o que fazer AGORA."""
    result = run()
    assert result.exit_code == 0
    assert "comece por" in result.output
    assert "dor review" in result.output


def _linha(output: str, comando: str) -> str:
    return next(line for line in output.splitlines() if comando in line)


def test_tela_inicial_lista_todas_as_atividades(run):
    """A queixa que originou este teste: `dor` só recomendava `dor review`.

    Um app com doze modos que anuncia um é, para quem o usa, um app de um modo.
    """
    from dor.cli import HOME_ACTIVITIES

    result = run()
    for comando, descricao, _ in HOME_ACTIVITIES:
        assert comando in result.output, comando
        # a descrição quebra em várias linhas no painel; a primeira palavra basta
        assert descricao.split()[0] in result.output, descricao


def test_todo_comando_do_cardapio_existe_de_verdade():
    """Cardápio é promessa: item que não abre é pior do que item ausente."""
    from dor.cli import HOME_ACTIVITIES, app

    registrados = {
        (c.name or c.callback.__name__).replace("_", "-") for c in app.registered_commands
    }
    prometidos = {comando.split()[1] for comando, _, _ in HOME_ACTIVITIES}
    assert prometidos <= registrados, prometidos - registrados


def test_rotulo_de_sessao_do_cardapio_bate_com_os_modos_reais():
    """Se um rótulo mudar de nome, o selo 'novo' fica preso para sempre —
    a atividade nunca casaria com nenhuma sessão gravada."""
    import importlib
    import pkgutil

    from dor import modes
    from dor.cli import HOME_ACTIVITIES

    reais = {"misto", "lupta"}
    for info in pkgutil.iter_modules(modes.__path__):
        modulo = importlib.import_module(f"dor.modes.{info.name}")
        if hasattr(modulo, "MODE"):
            reais.add(modulo.MODE)
        reais.update(getattr(modulo, "MODES", ()))

    declarados = {m for _, _, modos in HOME_ACTIVITIES for m in modos}
    assert declarados <= reais, declarados - reais


def test_selo_novo_some_depois_de_experimentar(run, user_dir):
    from dor.storage.repos import Store

    # Na tela de estreia o selo não aparece — ali TUDO é novo e marcar as doze
    # linhas não informaria nada. Uma palavra estudada já tira a tela de lá.
    with Store() as store:
        store.save_card(store.get_card("ro.casa"))

    assert "novo" in _linha(run().output, "dor drill")

    with Store() as store:
        store.start_session("gramatica")

    assert "novo" not in _linha(run().output, "dor drill")
    assert "novo" in _linha(run().output, "dor pairs"), "só a atividade usada perde o selo"


def test_help_continua_disponivel(run):
    result = run("--help")
    assert result.exit_code == 0
    assert "review" in result.output


# --------------------------------------------------------------------------- #
# preferências
# --------------------------------------------------------------------------- #


def test_settings_mostra_sem_alterar(run):
    result = run("settings")
    assert result.exit_code == 0
    assert "meta diária" in result.output
    assert not config.SETTINGS_PATH.exists(), "só mostrar não deve escrever no disco"


def test_settings_salva_o_que_muda(run):
    assert run("settings", "--meta", "200").exit_code == 0
    assert config.Settings.load().daily_goal_xp == 200


def test_settings_aceita_apelido_de_voz(run):
    run("settings", "--voz", "emil")
    assert config.Settings.load().voice == config.VOICE_MALE


def test_meta_nao_pode_ser_ridicula(run):
    """Meta zero quebraria a barra de progresso e a própria ideia de meta."""
    run("settings", "--meta", "0")
    assert config.Settings.load().daily_goal_xp >= 10


def test_settings_desliga_o_autoplay(run):
    run("settings", "--sem-autoplay")
    assert config.Settings.load().autoplay is False


# --------------------------------------------------------------------------- #
# luta
# --------------------------------------------------------------------------- #


def test_lupta_recusa_quem_nao_tem_historico(run):
    """O chefe é feito das SUAS palavras fracas: sem histórico não há chefe."""
    result = run("lupta")
    assert result.exit_code == 1
    assert "dor review" in result.output


# --------------------------------------------------------------------------- #
# comandos de leitura não explodem
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "args",
    [
        ("validate",),
        ("list", "--pos", "adj"),
        ("show", "casă"),
        ("drill", "--list"),
        ("drill", "g.pron.dativ", "-t"),
        ("slang",),
        ("music",),
        ("lyrics",),
        ("lyrics", "miorita", "--ler"),
        ("istorie",),
        ("istorie", "cafea"),
        ("istorie", "--palavras"),
        ("livros",),
        ("livros", "capra"),
        ("zi",),
        ("zi", "cafenea"),
        ("punte",),
        ("punte", "cao"),
        ("grade", "piata", "piață"),
        ("backup", "--list"),
        ("undo",),
        ("destravar",),
    ],
)
def test_comando_de_leitura_roda_limpo(run, args):
    result = run(*args)
    assert result.exit_code == 0, f"{args}: {result.output}"


@pytest.mark.parametrize(
    "args",
    [
        ("show", "zzzz"),
        ("lyrics", "zzzz"),
        ("istorie", "zzzz"),
        ("livros", "zzzz"),
        ("zi", "zzzz"),
        ("punte", "zzzz"),
        ("list", "--pos", "zzzz"),
    ],
)
def test_busca_sem_resultado_falha_com_mensagem(run, args):
    """Sair com erro é certo; sair com traceback não."""
    result = run(*args)
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_export_anki_escreve_o_arquivo(run, user_dir):
    result = run("export-anki", "--deck", "a1_casa")
    assert result.exit_code == 0
    assert (user_dir / "exports" / "dor_anki_a1_casa.tsv").exists()


def test_backup_sem_progresso_falha_com_mensagem(run):
    result = run("backup")
    assert result.exit_code == 1
    assert "progresso" in result.output


def test_destravar_palavra_inexistente_falha(run):
    result = run("destravar", "zzzz")
    assert result.exit_code == 1


def test_stats_sem_historico_nao_quebra(run):
    result = run("stats")
    assert result.exit_code == 0
    assert "dor review" in result.output
