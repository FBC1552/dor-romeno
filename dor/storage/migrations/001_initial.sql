-- Estado de agendamento por item.
--
-- As colunas `stability` e `difficulty` guardam os parâmetros do FSRS. Quando o
-- agendador em uso é o SM-2 de reserva, as mesmas colunas guardam intervalo (em
-- dias) e fator de facilidade — a reutilização é deliberada, para que trocar de
-- agendador não exija migração nem duplicar esquema.
CREATE TABLE items_state (
    item_id     TEXT    PRIMARY KEY,
    stability   REAL,
    difficulty  REAL,
    step        INTEGER,
    state       INTEGER NOT NULL DEFAULT 1,   -- 1 aprendendo, 2 revisão, 3 reaprendendo
    due_at      TEXT,                          -- ISO-8601 UTC
    last_review TEXT,
    reps        INTEGER NOT NULL DEFAULT 0,
    lapses      INTEGER NOT NULL DEFAULT 0,
    leech       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_items_state_due ON items_state (due_at);

-- Histórico bruto. Nunca é sobrescrito: é dele que saem as estatísticas, o
-- gráfico de retenção e uma eventual reotimização dos parâmetros do FSRS.
CREATE TABLE reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      TEXT    NOT NULL,
    mode         TEXT    NOT NULL,
    direction    TEXT,
    rating       INTEGER NOT NULL,   -- 1 again, 2 hard, 3 good, 4 easy
    verdict      TEXT    NOT NULL,   -- certo | quase | errado
    credit       REAL    NOT NULL,
    latency_ms   INTEGER,
    answer_given TEXT,
    session_id   INTEGER,
    ts           TEXT    NOT NULL
);

CREATE INDEX idx_reviews_item ON reviews (item_id);
CREATE INDEX idx_reviews_ts   ON reviews (ts);

CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    mode       TEXT    NOT NULL,
    started_at TEXT    NOT NULL,
    ended_at   TEXT,
    items_seen INTEGER NOT NULL DEFAULT 0,
    correct    INTEGER NOT NULL DEFAULT 0,
    credit_sum REAL    NOT NULL DEFAULT 0
);
