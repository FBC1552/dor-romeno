"""Biblioteca graduada e a mesma trava de citação da música."""

from __future__ import annotations

import pytest

from dor.core.loader import load_library
from dor.core.models import LEVEL_ORDER, Book
from dor.core.quoting import accepted_pt, public_lines
from dor.modes import reading


@pytest.fixture(scope="module")
def lib():
    return load_library()


def livro(**kwargs) -> Book:
    base = {
        "id": "bk.teste",
        "title": "Teste",
        "author": "Alguém",
        "level": "B1",
        "kind": "roman",
        "why_pt": "porque sim",
    }
    return Book(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# trava de citação
# --------------------------------------------------------------------------- #


def test_trecho_sem_dominio_publico_nao_vira_exercicio():
    protegido = livro(excerpt={"lines": [{"ro": "o frază", "pt": "uma frase", "cloze": "frază"}]})
    assert reading.usable_excerpt(protegido) == []
    assert reading.build_all(protegido) == []


def test_marca_no_livro_nao_substitui_a_marca_no_trecho():
    """`public_domain` no livro é metadado de catálogo. Quem autoriza a citação
    é a marca no próprio trecho — é ele que vai para a tela."""
    b = livro(
        public_domain=True,
        excerpt={"lines": [{"ro": "o frază", "pt": "uma frase", "cloze": "frază"}]},
    )
    assert reading.usable_excerpt(b) == []


def test_livro_protegido_ainda_rende_glossario():
    b = livro(glossary=[{"ro": "pământ", "pt": "terra"}])
    assert len(reading.build_all(b)) == 1


def test_trava_e_a_mesma_para_musica_e_literatura():
    """Uma função só: se um dia a regra mudar, muda nos dois lugares."""
    excerpt = {"public_domain": True, "lines": [{"ro": "a", "pt": "b", "cloze": "a"}]}
    assert public_lines(excerpt)
    assert public_lines({**excerpt, "public_domain": "true"}) == []


def test_acervo_real_so_cita_dominio_publico(lib):
    for book in lib.books.values():
        if book.excerpt and book.excerpt.get("public_domain") is True:
            assert book.public_domain is True, f"{book.id}: trecho livre em livro marcado protegido"


def test_nenhum_autor_vivo_tem_trecho_citado(lib):
    """Cărtărescu e Țîbuleac estão no catálogo; o texto deles, não."""
    for book in lib.books.values():
        if not book.public_domain:
            assert not reading.usable_excerpt(book), book.id


# --------------------------------------------------------------------------- #
# catálogo
# --------------------------------------------------------------------------- #


def test_ha_biblioteca(lib):
    assert len(lib.books) >= 12


def test_todo_livro_diz_por_que_ler_e_o_que_esperar(lib):
    """'Por que ler' vende o livro; 'o que esperar' evita que ele seja
    abandonado na página 20."""
    for book in lib.books.values():
        assert book.why_pt.strip(), book.id
        assert book.difficulty_pt and book.difficulty_pt.strip(), book.id


def test_todo_livro_diz_onde_achar(lib):
    for book in lib.books.values():
        assert book.where_pt, book.id


def test_niveis_e_generos_sao_validos(lib):
    from dor import config
    from dor.core.models import KIND_LABEL_PT

    for book in lib.books.values():
        assert book.level in config.LEVELS, book.id
        assert book.kind in KIND_LABEL_PT, book.id


def test_a_escada_comeca_no_facil_e_termina_no_dificil(lib):
    niveis = {b.level for b in lib.books.values()}
    assert "A2" in niveis, "sem porta de entrada, a biblioteca não serve a iniciante"
    assert niveis & {"C1", "C2"}, "sem topo, não há para onde subir"


def test_ordenacao_por_nivel_nao_e_alfabetica():
    assert LEVEL_ORDER["A2"] < LEVEL_ORDER["B1"] < LEVEL_ORDER["C2"]


def test_referencias_a_historia_apontam_para_eventos_reais(lib):
    for book in lib.books.values():
        for hid in book.history_refs:
            assert hid in lib.history, f"{book.id} → {hid}"


def test_os_classicos_livres_estao_presentes(lib):
    """Creangă, Eminescu, Caragiale e Rebreanu: os quatro autores de domínio
    público que sustentam a metade inicial da escada."""
    autores = {b.author for b in lib.books.values() if b.public_domain}
    assert {"Ion Creangă", "Mihai Eminescu", "Ion Luca Caragiale", "Liviu Rebreanu"} <= autores


# --------------------------------------------------------------------------- #
# exercícios
# --------------------------------------------------------------------------- #


def test_trecho_livre_gera_lacuna(lib):
    book = lib.books["bk.capra_cu_trei_iezi"]
    exercicios = reading.build_all(book)
    lacunas = [e for e in exercicios if e.direction == "trecho"]
    assert lacunas
    assert "____" in lacunas[0].prompt


def test_enunciado_traz_a_traducao_da_frase(lib):
    book = lib.books["bk.capra_cu_trei_iezi"]
    linha = reading.usable_excerpt(book)[0]
    exercicio = reading.build_line(book, linha)
    assert linha["pt"] in exercicio.instruction


def test_a_nota_credita_o_autor(lib):
    book = lib.books["bk.luceafarul"]
    for exercicio in reading.build_all(book):
        assert "Eminescu" in exercicio.note


def test_toda_linha_citada_gera_exercicio(lib):
    for book in lib.books.values():
        for line in reading.usable_excerpt(book):
            assert reading.build_line(book, line) is not None, f"{book.id}: {line['cloze']}"


def test_glossario_limpa_o_comentario_da_resposta():
    assert accepted_pt("tempo (época) / clima") == ["tempo", "clima"]
