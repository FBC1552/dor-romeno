"""Equivalências em português — o que conta como a mesma resposta.

Quem estuda 'ce faci' e digita "como está" acertou. Se o app marca errado
porque a ficha diz "como vai", o aluno aprende a adivinhar a string da ficha em
vez de aprender romeno — e para de confiar na correção, que é pior.

Duas camadas, nesta ordem:

1. **Palavras vazias.** "como está você" e "como está" são a mesma resposta.
   Pronome solto e reforço à toa saem antes da comparação, o que resolve a
   maior parte dos casos sem tabela nenhuma.

2. **Grupos de equivalência.** Fórmulas fixas que o português diz de várias
   maneiras — cumprimentar, agradecer, se despedir. Cada grupo é uma lista de
   ditos intercambiáveis NAQUELE uso.

O casamento é por grupo compartilhado, nunca por fecho transitivo: duas
respostas casam quando aparecem juntas em ALGUM grupo, e não porque existe uma
corrente entre elas. E um dito que já é tradução fichada de alguma palavra fica
em um grupo só — senão ele mesmo vira a corrente, e "oi" acaba aceito para
'ce faci', que é pergunta. O teste `test_synonyms.py` guarda essa regra.

Isto vale só para o **português**. Do lado romeno, variante aceita é caso a
caso e mora no campo `accepts` da própria palavra: aqui não se afrouxa o que se
está aprendendo a produzir.
"""

from __future__ import annotations

from functools import cache

from dor.core.normalize import fold, normalize

#: Palavras que não mudam a resposta quando aparecem sozinhas.
#:
#: Deliberadamente minúscula. A tentação é incluir "aí", "então", "tá" — e aí
#: "e aí" vira "e", que casa com qualquer coisa. Só entram aqui pronomes de
#: tratamento, que o português deixa cair sem mudar nada. O resto vai para os
#: grupos, onde cada variante é uma decisão explícita.
FILLER_PT = frozenset({"voce", "vc", "tu"})

#: Grupos de ditos intercambiáveis. Um mesmo dito pode estar em vários grupos;
#: duas respostas casam quando dividem PELO MENOS UM grupo.
EQUIVALENT_PT: tuple[tuple[str, ...], ...] = (
    # chegar
    #
    # "e aí" não está aqui nem no grupo de 'como vai', e a ausência é o ponto:
    # em português ele serve para os dois usos, então entrar em qualquer um dos
    # grupos o transformaria em ponte entre eles — 'bună' passaria a aceitar
    # "como vai" e 'ce faci' passaria a aceitar "oi". Ambíguo assim só vale
    # como tradução literal, listada na palavra que o aceita.
    ("oi", "olá", "opa", "salve", "fala", "oii"),
    # perguntar como a pessoa está
    (
        "como vai",
        "como está",
        "como estás",
        "como vai você",
        "como você está",
        "como tá",
        "tudo bem",
        "tudo bom",
        "tudo certo",
        "como vão as coisas",
        "como andam as coisas",
        "beleza",
        "como é que vai",
    ),
    # despedir
    ("tchau", "até logo", "até mais", "adeus", "falou", "xau", "até a próxima", "até breve"),
    # agradecer
    ("obrigado", "obrigada", "valeu", "agradeço", "muito obrigado", "muito obrigada", "grato"),
    # responder a um agradecimento
    ("de nada", "por nada", "imagina", "disponha", "não há de quê", "que isso"),
    # pedir
    ("por favor", "por gentileza", "faz favor", "se faz favor"),
    # se desculpar
    (
        "desculpa",
        "desculpe",
        "desculpas",
        "me desculpe",
        "perdão",
        "foi mal",
        "mil desculpas",
    ),
    # lamentar
    ("sinto muito", "lamento", "que pena", "meus pêsames"),
    # abrir passagem
    ("com licença", "dá licença", "licença"),
    # se apresentar
    ("prazer", "muito prazer", "prazer em conhecer", "prazer em conhecê-lo"),
    # estar bem — sem "tudo bem", que é resposta fichada de 'ce faci' e faria
    # a mesma ponte indevida (ver o grupo de chegada)
    ("bem", "tá bom", "ok", "beleza", "tranquilo", "de boa", "legal"),
    # à mesa
    ("bom apetite", "bom proveito"),
    # brinde e espirro
    ("saúde", "tim-tim", "à sua saúde"),
    # concordar
    ("sim", "claro", "isso", "isso mesmo", "com certeza"),
    # perguntar o preço
    ("quanto custa", "quanto é", "quanto fica", "qual o preço"),
    # não compreender
    ("não entendi", "não entendo", "não compreendi", "não peguei"),
    # parabenizar
    ("parabéns", "feliz aniversário", "felicidades"),
)


def _strip_filler(text: str) -> str:
    """Tira pronome solto e reforço vazio, preservando frase de uma palavra só.

    A guarda do resultado vazio importa: "você" pode ser a resposta inteira de
    algum item, e nesse caso não é palavra vazia coisa nenhuma.
    """
    kept = [t for t in text.split() if t not in FILLER_PT]
    if not kept:
        return text
    return " ".join(kept)


def pt_key(text: str) -> str:
    """Chave de comparação do português: sem acento, sem caixa, sem enchimento."""
    return _strip_filler(fold(normalize(text)))


@cache
def _index() -> dict[str, frozenset[int]]:
    """Mapa dito -> grupos a que pertence, montado uma vez por processo."""
    index: dict[str, set[int]] = {}
    for n, group in enumerate(EQUIVALENT_PT):
        for phrase in group:
            index.setdefault(pt_key(phrase), set()).add(n)
    return {k: frozenset(v) for k, v in index.items()}


def groups_of(text: str) -> frozenset[int]:
    return _index().get(pt_key(text), frozenset())


def equivalent(given: str, target: str) -> bool:
    """As duas respostas dizem a mesma coisa em português?

    Primeiro a igualdade depois do enchimento ("como vai você" = "como vai"),
    depois o grupo em comum ("como está" = "como vai").
    """
    a, b = pt_key(given), pt_key(target)
    if a == b:
        return True
    return bool(groups_of(given) & groups_of(target))
