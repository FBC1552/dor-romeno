"""Montagem da fila de estudo.

Regra: o que está vencido vem primeiro, do mais atrasado para o mais recente;
o espaço que sobrar é preenchido com itens novos, embaralhados para não estudar
sempre na ordem do arquivo JSON.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

from dor.core.loader import Library, filter_vocab
from dor.core.models import VocabItem
from dor.storage.repos import Store


def build_queue(
    lib: Library,
    store: Store,
    *,
    limit: int = 20,
    level: str | None = None,
    deck: str | None = None,
    pos: str | None = None,
    tag: str | None = None,
    include_new: bool = True,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[VocabItem]:
    now = now or datetime.now(UTC)
    rng = rng or random.Random()

    candidates = filter_vocab(lib, level=level, deck=deck, pos=pos, tag=tag)
    by_id = {i.id: i for i in candidates}

    queue: list[VocabItem] = [
        by_id[item_id] for item_id in store.due_item_ids(now) if item_id in by_id
    ][:limit]

    if include_new and len(queue) < limit:
        seen = store.seen_item_ids()
        new = [i for i in candidates if i.id not in seen]
        rng.shuffle(new)
        queue.extend(new[: limit - len(queue)])

    return queue
