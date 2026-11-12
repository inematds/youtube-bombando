"""Persistência SQLite compartilhada pelas etapas."""
import sqlite3


def abrir(caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(caminho)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY, titulo TEXT NOT NULL, canal TEXT,
            channel_id TEXT, duracao REAL, views_busca INTEGER,
            descoberto TEXT NOT NULL, publicado TEXT,
            indisponivel INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS nichos (nome TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS video_nichos (
            video_id TEXT REFERENCES videos(id), nicho TEXT REFERENCES nichos(nome),
            PRIMARY KEY (video_id, nicho)
        );
        CREATE TABLE IF NOT EXISTS fotos (
            id TEXT REFERENCES videos(id), dia TEXT, views INTEGER, likes INTEGER,
            comentarios INTEGER, inscritos INTEGER, PRIMARY KEY (id, dia)
        );
        CREATE TABLE IF NOT EXISTS rodadas (
            instante TEXT PRIMARY KEY, nichos INTEGER, novos INTEGER,
            fotos INTEGER, erros TEXT, fixtures INTEGER
        );
    ''')
    db.execute("""CREATE TABLE IF NOT EXISTS canais (
        channel_id TEXT PRIMARY KEY, nome TEXT, inscritos INTEGER,
        mediana_views REAL, n_amostra INTEGER, atualizado TEXT,
        amostra TEXT
    )""")
    colunas = {r[1] for r in db.execute('PRAGMA table_info(videos)')}
    if 'descricao' not in colunas:
        db.execute('ALTER TABLE videos ADD COLUMN descricao TEXT')
    db.commit()
    return db
