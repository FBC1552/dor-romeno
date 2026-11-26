"""Podcast Studio.

O planejamento é puro e testado a fundo. A montagem depende de rede (síntese) e
do ffmpeg, então tem um único teste de integração que se pula sozinho quando
algum dos dois falta.
"""

from __future__ import annotations

import random

import pytest

from dor import config
from dor.audio import studio
from dor.core.loader import load_library


@pytest.fixture(scope="module")
def lib():
    return load_library()


@pytest.fixture
def rng():
    return random.Random(20260816)


# --------------------------------------------------------------------------- #
# planejamento
# --------------------------------------------------------------------------- #


def test_plano_drill_tem_intro_e_outro(lib, rng):
    ep = studio.plan(lib, mode="drill", count=3, rng=rng)
    assert ep.segments[0].label == "intro"
    assert ep.segments[-1].label == "outro"
    assert ep.segments[0].lang == "pt"


def test_bloco_drill_poe_a_pausa_antes_da_traducao(lib, rng):
    """A pausa é a janela para lembrar sozinho. Entregar o português antes
    dela transforma o episódio em audiolivro."""
    ep = studio.plan(lib, mode="drill", count=1, pause_ms=2000, rng=rng)
    corpo = [s for s in ep.segments if s.label not in ("intro", "outro")]
    alvo, traducao, confirmacao = corpo
    assert alvo.lang == "ro" and alvo.pause_ms == 2000
    assert traducao.lang == "pt"
    assert confirmacao.lang == "ro"


def test_drill_troca_o_timbre_entre_as_duas_falas_romenas(lib, rng):
    ep = studio.plan(lib, mode="drill", count=1, rng=rng)
    ro = [s for s in ep.segments if s.lang == "ro"]
    assert ro[0].voice != ro[1].voice
    assert ro[1].rate.startswith("-"), "a confirmação deve vir mais devagar"


def test_modo_passivo_nao_fala_portugues(lib, rng):
    """É para ouvir de fundo — narração em português quebraria o propósito."""
    ep = studio.plan(lib, mode="passive", count=6, rng=rng)
    assert all(s.lang == "ro" for s in ep.segments)


def test_modo_passivo_alterna_vozes(lib, rng):
    ep = studio.plan(lib, mode="passive", count=6, rng=rng)
    assert len({s.voice for s in ep.segments}) == 2


def test_modo_sleep_e_lento_e_repetido(lib, rng):
    ep = studio.plan(lib, mode="sleep", count=2, rng=rng)
    corpo = [s for s in ep.segments if s.label not in ("intro", "outro")]
    assert all(s.rate.startswith("-") for s in corpo)
    ro = [s.text for s in corpo if s.lang == "ro"]
    assert len(ro) == 2 * len(set(ro)), "cada palavra deve ser dita duas vezes"


def test_modo_desconhecido_falha_alto(lib, rng):
    with pytest.raises(studio.StudioError):
        studio.plan(lib, mode="karaoke", count=2, rng=rng)


def test_filtro_sem_resultado_falha_alto(lib, rng):
    with pytest.raises(studio.StudioError):
        studio.plan(lib, theme="inexistente", count=2, rng=rng)


def test_count_limita_os_itens(lib, rng):
    ep = studio.plan(lib, mode="drill", count=4, rng=rng)
    assert len(ep.item_ids) == 4


def test_count_maior_que_o_acervo_nao_estoura(lib, rng):
    ep = studio.plan(lib, mode="passive", count=9999, rng=rng)
    assert len(ep.item_ids) == len(lib.vocab)


def test_minutos_viram_quantidade_de_itens(lib, rng):
    curto = studio.plan(lib, mode="drill", minutes=1, rng=rng)
    longo = studio.plan(lib, mode="drill", minutes=5, rng=rng)
    assert len(longo.item_ids) > len(curto.item_ids)


def test_estimativa_cresce_com_a_pausa(lib, rng):
    rapido = studio.plan(lib, mode="drill", count=5, pause_ms=500, rng=rng)
    lento = studio.plan(lib, mode="drill", count=5, pause_ms=4000, rng=rng)
    assert lento.estimated_seconds > rapido.estimated_seconds


def test_filtra_por_tema(lib, rng):
    ep = studio.plan(lib, mode="passive", theme="bebida", count=99, rng=rng)
    for item_id in ep.item_ids:
        assert "bebida" in lib.vocab[item_id].tags


def test_todo_segmento_tem_texto_e_voz(lib, rng):
    for mode in studio.MODES:
        ep = studio.plan(lib, mode=mode, count=3, rng=rng)
        for seg in ep.segments:
            assert seg.text.strip()
            assert seg.voice
            assert seg.lang in ("ro", "pt")


def test_vozes_batem_com_o_idioma_do_segmento(lib, rng):
    """Narrar português com voz romena sairia com sotaque de robô confuso."""
    for mode in studio.MODES:
        ep = studio.plan(lib, mode=mode, count=3, rng=rng)
        for seg in ep.segments:
            esperado = "ro-RO" if seg.lang == "ro" else "pt-BR"
            assert seg.voice.startswith(esperado), f"{seg.label}: {seg.voice} para {seg.lang}"


def test_vozes_usadas_estao_no_config(lib, rng):
    conhecidas = {
        config.VOICE_FEMALE,
        config.VOICE_MALE,
        config.VOICE_PT_FEMALE,
        config.VOICE_PT_MALE,
    }
    for mode in studio.MODES:
        ep = studio.plan(lib, mode=mode, count=3, rng=rng)
        assert {s.voice for s in ep.segments} <= conhecidas


# --------------------------------------------------------------------------- #
# filtro do ffmpeg
# --------------------------------------------------------------------------- #


def test_filtro_tem_uma_cadeia_por_segmento(lib, rng):
    ep = studio.plan(lib, mode="drill", count=3, rng=rng)
    script = studio._filter_script(ep.segments)
    assert script.count("aformat") == len(ep.segments)
    assert f"concat=n={len(ep.segments)}" in script


def test_filtro_so_acrescenta_silencio_quando_ha_pausa():
    segs = [
        studio.Segment("a", "ro", "v", pause_ms=0),
        studio.Segment("b", "ro", "v", pause_ms=500),
    ]
    script = studio._filter_script(segs)
    assert script.count("apad") == 1
    assert "apad=pad_dur=0.500" in script


def test_filtro_normaliza_o_formato_de_toda_entrada():
    """Concatenação exige formato idêntico; sem isso o ffmpeg falha feio."""
    segs = [studio.Segment("x", "ro", "v") for _ in range(3)]
    script = studio._filter_script(segs)
    assert script.count(f"sample_rates={studio.SAMPLE_RATE}") == 3


# --------------------------------------------------------------------------- #
# transcrição e playlist
# --------------------------------------------------------------------------- #


def test_transcricao_lista_o_conteudo(lib, rng, tmp_path):
    ep = studio.plan(lib, mode="drill", count=3, rng=rng)
    path = studio.write_transcript(ep, tmp_path / "ep.md", lib)
    texto = path.read_text(encoding="utf-8")
    assert ep.title in texto
    for item_id in ep.item_ids:
        assert lib.vocab[item_id].ro in texto


def test_playlist_tem_cabecalho_e_duracoes(tmp_path):
    alvo = tmp_path / "p.m3u"
    studio.write_playlist([(tmp_path / "a.mp3", "Episódio 1", 90.4)], alvo)
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "#EXTM3U"
    assert linhas[1] == "#EXTINF:90,Episódio 1"
    assert linhas[2] == "a.mp3"


def test_duracao_de_arquivo_inexistente_nao_explode(tmp_path):
    assert studio.duration_seconds(tmp_path / "nao_existe.mp3") == 0.0


# --------------------------------------------------------------------------- #
# integração (rede + ffmpeg)
# --------------------------------------------------------------------------- #


def test_render_produz_um_mp3_tocavel(lib, rng, tmp_path):
    from dor.audio import tts

    if not tts.available_providers():
        pytest.skip("nenhum provedor de TTS")
    try:
        studio.ffmpeg_exe()
    except studio.StudioError:
        pytest.skip("ffmpeg ausente")

    ep = studio.plan(lib, mode="drill", count=2, pause_ms=600, rng=rng)
    try:
        result = studio.render(ep, tmp_path / "ep.mp3")
    except studio.StudioError as exc:
        pytest.skip(f"montagem indisponível: {exc}")

    assert result.path.exists()
    assert result.path.stat().st_size > 1000
    assert result.seconds > 1.0
    assert result.segments == len(ep.segments)

    from mutagen.easyid3 import EasyID3

    assert EasyID3(result.path)["title"] == [ep.title]
