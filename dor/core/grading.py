"""Veredito de resposta em três níveis.

A decisão central do app: rejeitar "piata" quando o aluno quis dizer "piață"
faz qualquer pessoa desinstalar no terceiro dia; aceitar sem comentar faz o
diacrítico nunca ser aprendido. Por isso existe o veredito do meio.

  certo   — resposta equivalente à esperada. Crédito integral.
  quase   — a palavra está certa e falta um acerto fino (diacrítico ou um
            deslize de digitação). Crédito parcial e correção explícita.
  errado  — outra palavra.

A direção importa: quando a resposta esperada é em **português**, erro de acento
não é erro nenhum — não estamos ensinando ortografia do português. Quando é em
**romeno**, o diacrítico é justamente parte do que se está aprendendo.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from dor.core.normalize import (
    compare_key,
    describe_diacritics,
    diacritic_diff,
    fold,
    levenshtein,
    normalize,
)
from dor.core.synonyms import equivalent as pt_equivalent

CREDIT_CORRECT = 1.0
CREDIT_ALMOST = 0.5
CREDIT_WRONG = 0.0


class Verdict(StrEnum):
    CORRECT = "certo"
    ALMOST = "quase"
    WRONG = "errado"


def _typo_budget(text: str) -> int:
    """Quantos deslizes de digitação tolerar, proporcional ao tamanho.

    Palavra curta com 2 erros já é outra palavra ('casă' vs 'masă' dista 1);
    por isso o orçamento só abre em palavras longas.
    """
    n = len(text)
    if n <= 4:
        return 0
    if n <= 8:
        return 1
    return 2


@dataclass
class Grade:
    verdict: Verdict
    credit: float
    given: str
    target: str
    """A resposta aceita mais próxima do que foi digitado."""
    distance: int = 0
    diacritics_only: bool = False
    hinted: bool = False
    """Respondida depois de pedir a dica. O símbolo de 🥔 para 'cartof' É a
    resposta, então acerto com dica não é recuperação da memória: continua
    valendo como acerto para o aluno, mas vale meio crédito e volta mais cedo."""
    loose: bool = False
    """Aceito por equivalência, não por igualdade: o aluno disse a mesma coisa
    com outras palavras. Vale crédito integral e uma nota mostrando a forma da
    ficha, para que ele saiba qual delas o app vai repetir."""
    missing_diacritics: list[str] = field(default_factory=list)
    hint: str | None = None

    @property
    def ok(self) -> bool:
        """Conta como acerto para efeito de sequência e agendamento."""
        return self.verdict is Verdict.CORRECT

    @property
    def is_almost(self) -> bool:
        return self.verdict is Verdict.ALMOST


def grade(
    given: str,
    accepted: list[str],
    *,
    lang: str = "ro",
    strict_diacritics: bool = False,
) -> Grade:
    """Avalia `given` contra todas as respostas aceitas e devolve a melhor nota.

    `lang` é o idioma da RESPOSTA esperada ("ro" ou "pt"), não o do enunciado.

    `strict_diacritics` desliga o perdão do acento. Existe para os pares
    mínimos: ali `cos` e `coș` são palavras distintas e distingui-las É o
    exercício, então dar crédito parcial por escolher a errada desmonta a
    atividade inteira. Fora desse caso, o perdão é o comportamento correto.
    """
    if not accepted:
        raise ValueError("grade() precisa de ao menos uma resposta aceita")

    given_clean = normalize(given)
    if not given_clean:
        return Grade(
            verdict=Verdict.WRONG,
            credit=CREDIT_WRONG,
            given=given,
            target=accepted[0],
            hint="Resposta vazia.",
        )

    best: Grade | None = None
    for candidate in accepted:
        result = _grade_one(given, given_clean, candidate, lang, strict_diacritics)
        if best is None or _rank(result) > _rank(best):
            best = result
        # Só corta cedo num acerto exato: se o primeiro casamento foi por
        # equivalência, ainda pode existir adiante a tradução que o aluno
        # digitou letra por letra — e é essa que merece aparecer.
        if best.verdict is Verdict.CORRECT and not best.loose:
            break
    assert best is not None

    # Numa resposta errada, apontar a tradução "mais próxima" é ruído: quem
    # digitou 'porta' para 'om' não quer ver '→ cara', quer ver '→ homem'.
    if best.verdict is Verdict.WRONG and best.target != accepted[0]:
        best = replace(best, target=accepted[0])
    return best


def after_hint(result: Grade) -> Grade:
    """Aplica o preço da dica a uma resposta já corrigida.

    Errar depois de ver a dica não é pior do que errar sem ela, então só o
    acerto paga. O veredito continua 'certo' de propósito: transformar em
    'quase' faria a tela dizer que a palavra está errada, que é mentira.
    """
    if result.verdict is not Verdict.CORRECT:
        return result
    return replace(result, hinted=True, credit=CREDIT_ALMOST)


def _rank(g: Grade) -> tuple[float, bool, int]:
    """Ordena candidatos: mais crédito, depois casamento exato, depois distância."""
    return (g.credit, not g.loose, -g.distance)


def _grade_one(
    given_raw: str, given: str, candidate: str, lang: str, strict_diacritics: bool = False
) -> Grade:
    target = normalize(candidate)

    # 1. Igualdade após normalizar. Cobre cedilha legada (ş -> ș) e maiúsculas,
    #    que nunca são erro do aluno.
    if given == target:
        return Grade(Verdict.CORRECT, CREDIT_CORRECT, given_raw, candidate)

    # 2. Igualdade ignorando artigo/partícula inicial: "a fi" vs "fi",
    #    "o livro" vs "livro".
    if compare_key(given, lang) == compare_key(target, lang):
        return Grade(Verdict.CORRECT, CREDIT_CORRECT, given_raw, candidate)

    given_folded = fold(given)
    target_folded = fold(target)

    # 3. Mesma palavra, diacríticos diferentes.
    if given_folded == target_folded:
        if lang == "pt":
            # Não é aula de português — acento em PT não vale correção.
            return Grade(Verdict.CORRECT, CREDIT_CORRECT, given_raw, candidate)
        if strict_diacritics:
            # Num par mínimo, o diacrítico não é detalhe: é a palavra.
            return Grade(
                verdict=Verdict.WRONG,
                credit=CREDIT_WRONG,
                given=given_raw,
                target=candidate,
                hint=f"'{given}' e '{target}' são palavras diferentes — o contraste é o exercício.",
            )
        missing = [t for _, _, t in diacritic_diff(given, target)]
        described = describe_diacritics(missing)
        return Grade(
            verdict=Verdict.ALMOST,
            credit=CREDIT_ALMOST,
            given=given_raw,
            target=candidate,
            diacritics_only=True,
            missing_diacritics=missing,
            hint=f"Faltou {described}." if described else "Atenção aos diacríticos.",
        )

    # 4. Mesma palavra ignorando prefixo, diacríticos diferentes.
    if fold(compare_key(given, lang)) == fold(compare_key(target, lang)):
        if lang == "pt":
            return Grade(Verdict.CORRECT, CREDIT_CORRECT, given_raw, candidate)
        if strict_diacritics:
            return Grade(Verdict.WRONG, CREDIT_WRONG, given_raw, candidate)
        return Grade(
            verdict=Verdict.ALMOST,
            credit=CREDIT_ALMOST,
            given=given_raw,
            target=candidate,
            diacritics_only=True,
            hint="Atenção aos diacríticos.",
        )

    # 5. Outra maneira de dizer a mesma coisa em português. 'ce faci' está
    #    fichado como "como vai"; quem responde "como está" acertou, e marcar
    #    errado só ensina a adivinhar a string da ficha.
    #
    #    Vem depois do perdão de acento de propósito: "ate logo" é a MESMA
    #    resposta mal acentuada, não uma equivalente — anunciar "também vale"
    #    ali sugeriria uma diferença que não existe.
    if lang == "pt" and pt_equivalent(given, target):
        return Grade(
            verdict=Verdict.CORRECT,
            credit=CREDIT_CORRECT,
            given=given_raw,
            target=candidate,
            loose=True,
            hint=f"também vale — na ficha: '{candidate}'",
        )

    # 6. Deslize de digitação: perto o bastante, sem diacrítico envolvido.
    budget = _typo_budget(target_folded)
    if budget:
        dist = levenshtein(given_folded, target_folded, max_dist=budget)
        if dist <= budget:
            return Grade(
                verdict=Verdict.ALMOST,
                credit=CREDIT_ALMOST,
                given=given_raw,
                target=candidate,
                distance=dist,
                hint="Quase — confira a grafia.",
            )

    # 7. Outra palavra.
    return Grade(
        verdict=Verdict.WRONG,
        credit=CREDIT_WRONG,
        given=given_raw,
        target=candidate,
        distance=levenshtein(given_folded, target_folded),
    )
