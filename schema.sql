-- AgroTechNova Datencheck — SQLite Schema v1
-- Standalone-DB: data/datencheck.db

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Fehlerdefinition (
    Fehlercode       TEXT PRIMARY KEY,
    Schwere          TEXT NOT NULL,
    Owner            TEXT NOT NULL,
    Kurzbeschreibung TEXT NOT NULL,
    System           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fehlerdefinition_system
    ON Fehlerdefinition (System);
CREATE INDEX IF NOT EXISTS idx_fehlerdefinition_owner
    ON Fehlerdefinition (Owner);
CREATE INDEX IF NOT EXISTS idx_fehlerdefinition_schwere
    ON Fehlerdefinition (Schwere);

CREATE TABLE IF NOT EXISTS Fehlerliste (
    Fehlerid         INTEGER PRIMARY KEY AUTOINCREMENT,
    Fehlercode       TEXT NOT NULL,
    Ursprungstabelle TEXT NOT NULL,
    Ursprungs_ID     TEXT NOT NULL,
    FOREIGN KEY (Fehlercode) REFERENCES Fehlerdefinition (Fehlercode)
);

CREATE INDEX IF NOT EXISTS idx_fehlerliste_fehlercode
    ON Fehlerliste (Fehlercode);
CREATE INDEX IF NOT EXISTS idx_fehlerliste_ursprung
    ON Fehlerliste (Ursprungstabelle);
CREATE INDEX IF NOT EXISTS idx_fehlerliste_ursprung_id
    ON Fehlerliste (Ursprungstabelle, Ursprungs_ID);
