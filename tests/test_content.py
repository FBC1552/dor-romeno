"""Guarda-corpo do conteúdo.

Estes testes rodam contra os JSON reais do repositório. Qualquer deck novo que
alguém adicionar passa por aqui automaticamente — é o que impede que um typo
num arquivo de vocabulário só apareça no meio de uma sessão de estudo.
"""

from __future__ import annotations

import pytest

from dor import config
from dor.core.loader import filter_vocab, load_library


@pytest.fixture(scope="module")
def lib():
    return load_library()


def test_conteudo_sem_problemas(lib):
    assert lib.issues == [], "\n".join(str(i) for i in lib.issues)


def test_ha_conteudo_de_cada_tipo(lib):
    for label, n in lib.counts().items():
        assert n > 0, f"nenhum item de {label}"


def test_registros_sao_validos(lib):
    for item in lib.vocab.values():
        assert item.register in config.REGISTERS, f"{item.id}: registro '{item.register}'"
    for item in lib.slang.values():
        assert item.register in config.REGISTERS, f"{item.id}: registro '{item.register}'"


def test_niveis_sao_validos(lib):
    for item in lib.vocab.values():
        assert item.level in config.LEVELS, f"{item.id}: nível '{item.level}'"


def test_substantivos_tem_genero(lib):
    """Sem gênero não dá para gerar drill de artigo nem de plural."""
    for item in filter_vocab(lib, pos="noun"):
        assert item.gender in ("m", "f", "n"), f"{item.id} não declara gênero"


def test_verbos_tem_presente_com_seis_pessoas(lib):
    for item in filter_vocab(lib, pos="verb"):
        prezent = item.forms.get("prezent")
        if prezent is None:
            continue
        assert isinstance(prezent, list) and len(prezent) == 6, (
            f"{item.id}: 'prezent' precisa de 6 formas, tem {prezent}"
        )


def test_cloze_target_existe_na_frase(lib):
    for s in lib.sentences.values():
        if s.cloze_target:
            assert s.cloze_target in s.ro, f"{s.id}: '{s.cloze_target}' não está em '{s.ro}'"


def test_frase_aparece_como_exemplo_da_palavra_que_ela_usa(lib):
    """O elo é escrito uma vez só, na frase, e o loader fecha o outro lado.
    Sem isso, frase nova fica invisível para o modo lacuna."""
    for s in lib.sentences.values():
        for vid in s.vocab:
            assert s.id in lib.vocab[vid].examples, f"{vid} não conhece {s.id}"


def test_boa_parte_do_vocabulario_tem_frase_de_contexto(lib):
    """Palavra sem frase não gera exercício de lacuna — vira só flashcard."""
    from dor.modes import cloze

    com_frase = [i for i in lib.vocab.values() if cloze.candidates(lib, i)]
    assert len(com_frase) >= len(lib.vocab) * 0.4


def test_traducoes_nao_sao_vazias(lib):
    for item in lib.vocab.values():
        assert item.pt and all(p.strip() for p in item.pt), f"{item.id} tem tradução vazia"


def test_drills_de_gramatica_encontram_itens(lib):
    """Uma regra com drill que não casa com nada gera exercício zero — bug silencioso."""
    for rule in lib.grammar.values():
        if not rule.drill:
            continue
        query = dict(rule.drill["query"])
        matches = filter_vocab(lib, **query)
        assert matches, f"{rule.id}: o drill não encontra nenhum item com {query}"


def test_drill_consegue_resolver_o_campo_alvo(lib):
    for rule in lib.grammar.values():
        if not rule.drill:
            continue
        target = rule.drill["to"]
        matches = filter_vocab(lib, **rule.drill["query"])
        resolved = [m for m in matches if m.form(target)]
        assert resolved, f"{rule.id}: nenhum item resolve o campo alvo '{target}'"


def test_ponte_com_portugues_esta_bem_formada(lib):
    for item in lib.vocab.values():
        if item.cognate_pt:
            assert item.cognate_pt["confidence"] in ("alto", "medio", "baixo")
        if item.false_friend:
            assert item.false_friend["looks_like"] != item.false_friend["actually_means"]


def test_musica_nao_guarda_letra_integral(lib):
    """Trava de direito autoral: no máximo 4 versos, e só se for domínio público."""
    for track in lib.tracks:
        if not track.excerpt:
            continue
        lines = track.excerpt["lines"]
        assert len(lines) <= 4, f"{track.id}: {len(lines)} versos — máximo é 4"
        assert track.excerpt.get("public_domain") is True, (
            f"{track.id}: trecho armazenado sem marcar public_domain"
        )
