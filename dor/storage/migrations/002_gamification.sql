-- Um registro por dia de calendário LOCAL (não UTC): a streak segue o dia do
-- usuário, não o do servidor. Estudar às 23h e à 1h são dois dias.
CREATE TABLE daily (
    day      TEXT    PRIMARY KEY,   -- YYYY-MM-DD local
    xp       INTEGER NOT NULL DEFAULT 0,
    reviews  INTEGER NOT NULL DEFAULT 0,
    correct  INTEGER NOT NULL DEFAULT 0,
    seconds  INTEGER NOT NULL DEFAULT 0,
    goal_met INTEGER NOT NULL DEFAULT 0
);

-- Linha única. O CHECK impede que um bug crie um segundo "usuário" silencioso.
CREATE TABLE streak (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    current     INTEGER NOT NULL DEFAULT 0,
    longest     INTEGER NOT NULL DEFAULT 0,
    freezes     INTEGER NOT NULL DEFAULT 0,
    last_active TEXT
);

INSERT INTO streak (id) VALUES (1);

CREATE TABLE quests (
    day       TEXT    NOT NULL,
    code      TEXT    NOT NULL,
    target    INTEGER NOT NULL,
    progress  INTEGER NOT NULL DEFAULT 0,
    reward_xp INTEGER NOT NULL,
    done      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, code)
);

CREATE TABLE achievements (
    code        TEXT PRIMARY KEY,
    unlocked_at TEXT NOT NULL
);

-- XP por revisão fica no histórico: permite recalcular a curva depois sem
-- perder o que já foi ganho.
ALTER TABLE reviews ADD COLUMN xp INTEGER NOT NULL DEFAULT 0;
