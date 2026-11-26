"""O acervo pessoal: música parte por parte e jornal da semana.

Este material vive fora do repositório, em `%LOCALAPPDATA%/dor/conteudo`, e é
editado à mão toda semana. Os testes aqui defendem duas coisas: que arquivo
torto não derruba o acervo inteiro, e que a caixa de entrada nunca vaza para o
estudo antes de passar pelo `dor atualizar`.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from dor import config
from dor.cli import app
from dor.core.local import current_week, find, load_local

LOTE = {
    "meta": {"id": "2026-w10-jurnal", "kind": "jurnal", "week": "2026-W10", "title": "Semana 10"},
    "pieces": [
        {
            "id": "n.energie",
            "title": "Factura la energie",
            "source": "Digi24",
            "level": "A2",
            "parts": [
                {
                    "at": "lide",
                    "ro": ["Iarna, factura la energie crește mult."],
                    "pt": ["No inverno, a conta de energia sobe muito."],
                    "explica_pt": "'factura' é conta a pagar, não só de cartão.",
                    "glossary": [
                        {"ro": "factură", "pt": "conta / fatura"},
                        {"ro": "a crește", "pt": "crescer / subir"},
                    ],
                    "cloze_answer": "factura",
                }
            ],
        }
    ],
}


@pytest.fixture
def acervo(tmp_path, monkeypatch):
    """Acervo pessoal isolado — nada toca o material real da máquina."""
    local = tmp_path / "conteudo"
    inbox = local / "inbox"
    inbox.mkdir(parents=True)
    monkeypatch.setattr(config, "USER_DIR", tmp_path)
    monkeypatch.setattr(config, "LOCAL_DIR", local)
    monkeypatch.setattr(config, "INBOX_DIR", inbox)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "progress.db")
    return local


def _escreve(directory, payload, name="lote.json"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# carregamento
# --------------------------------------------------------------------------- #


def test_acervo_ausente_nao_e_erro(tmp_path):
    """O caso comum é não existir: quase todo mundo nunca colou nada."""
    content = load_local(tmp_path / "nao-existe")
    assert content.pieces == {}
    assert content.issues == []


def test_le_lote_valido_com_semana_e_tipo(acervo):
    _escreve(acervo / "jurnal", LOTE)
    content = load_local(acervo)

    peca = content.pieces["n.energie"]
    assert peca.kind == "jurnal"
    assert peca.week == "2026-W10"
    assert peca.parts[0].pairs[0] == (
        "Iarna, factura la energie crește mult.",
        "No inverno, a conta de energia sobe muito.",
    )


def test_caixa_de_entrada_nao_entra_no_estudo(acervo):
    """Rascunho não vira exercício. `dor atualizar` é quem promove."""
    _escreve(acervo / "inbox", LOTE)
    assert load_local(acervo).pieces == {}


def test_arquivo_torto_nao_derruba_os_outros(acervo):
    _escreve(acervo / "jurnal", LOTE)
    _escreve(acervo / "jurnal", {"meta": {"id": "x"}}, name="quebrado.json")

    content = load_local(acervo)
    assert "n.energie" in content.pieces, "um arquivo inválido não pode esconder os válidos"
    assert content.issues


def test_busca_por_pedaco_do_titulo(acervo):
    _escreve(acervo / "jurnal", LOTE)
    content = load_local(acervo)
    assert find(content, "energie") is content.pieces["n.energie"]
    assert find(content, "factura") is content.pieces["n.energie"]
    assert find(content, "energie", kind="versuri") is None


def test_semana_atual_no_formato_iso():
    week = current_week()
    assert len(week) == 8 and week[4:6] == "-W"


# --------------------------------------------------------------------------- #
# exercícios
# --------------------------------------------------------------------------- #


def test_glossario_vira_traducao_e_verso_vira_lacuna(acervo):
    from dor.modes import lote as lote_mode

    _escreve(acervo / "jurnal", LOTE)
    peca = load_local(acervo).pieces["n.energie"]
    exercicios = lote_mode.exercises_for(peca)

    assert len(exercicios) == 3, "duas entradas de glossário e uma lacuna"
    assert all(e.mode == "jurnal" for e in exercicios), "o rótulo de sessão é o tipo da peça"
    lacuna = exercicios[-1]
    assert "____" in lacuna.prompt
    assert lacuna.answers == ["factura"]


def test_lacuna_sem_alvo_e_simplesmente_omitida(acervo):
    from dor.modes import lote as lote_mode

    sem_alvo = json.loads(json.dumps(LOTE))
    del sem_alvo["pieces"][0]["parts"][0]["cloze_answer"]
    _escreve(acervo / "jurnal", sem_alvo)

    peca = load_local(acervo).pieces["n.energie"]
    assert len(lote_mode.exercises_for(peca)) == 2


# --------------------------------------------------------------------------- #
# comandos
# --------------------------------------------------------------------------- #


@pytest.fixture
def run(acervo):
    runner = CliRunner()
    return lambda *args: runner.invoke(app, list(args))


def test_jurnal_sem_acervo_explica_onde_por_o_material(run):
    result = run("jurnal")
    assert result.exit_code == 1
    assert "acervo pessoal" in result.output
    assert "dor atualizar" in result.output


def test_atualizar_promove_a_caixa_de_entrada(run, acervo):
    _escreve(acervo / "inbox", LOTE)

    result = run("atualizar")
    assert result.exit_code == 0
    assert "importado" in result.output
    assert not list((acervo / "inbox").glob("*.json")), "o arquivo sai da caixa ao entrar"
    assert load_local(acervo).pieces, "e passa a valer para o estudo"


def test_atualizar_recusa_lote_invalido_e_diz_por_que(run, acervo):
    _escreve(acervo / "inbox", {"meta": {"id": "x", "kind": "jurnal"}, "pieces": []})

    result = run("atualizar")
    assert "não entrou" in result.output
    assert list((acervo / "inbox").glob("*.json")), "lote recusado fica onde estava"


def test_atualizar_monta_esqueleto_a_partir_da_letra_colada(run, acervo, tmp_path):
    """A letra é sempre do usuário: o app estrutura, não busca nem inventa."""
    letra = tmp_path / "faixa.txt"
    letra.write_text("primul vers\nal doilea vers\n\na treia linie\n", encoding="utf-8")

    result = run("atualizar", "--letra", str(letra), "--titulo", "Proba", "--artista", "Cineva")
    assert result.exit_code == 0
    assert "2 estrofe" in result.output

    gerado = json.loads(next((acervo / "inbox").glob("*.json")).read_text(encoding="utf-8"))
    assert gerado["meta"]["kind"] == "versuri"
    assert gerado["pieces"][0]["parts"][0]["ro"] == ["primul vers", "al doilea vers"]
    assert gerado["pieces"][0]["parts"][0]["pt"] == [], "tradução é trabalho de anotação"


def test_modelo_sai_pronto_para_copiar(run):
    result = run("atualizar", "--modelo", "versuri")
    assert result.exit_code == 0
    assert '"kind"' in result.output and "versuri" in result.output


def test_modelo_recusa_tipo_desconhecido(run):
    assert run("atualizar", "--modelo", "podcast").exit_code == 1
