"""Descobre vídeos e preserva a associação com todos os nichos."""
import re


LIMITES = {'buscas': 'por_nicho_busca', 'buscas24h': 'por_nicho_24h'}


def descobrir(db, fonte, nichos, agora, registrar, tipo='buscas'):
    """tipo='buscas' = semana; 'buscas24h' = enviados hoje, e marca achado_24h."""
    novos = certos = 0
    for nicho in nichos:
        try:
            resposta = fonte.obter(tipo, nicho['busca'])
            entradas = resposta['entries']
            if not isinstance(entradas, list):
                raise ValueError('entries deve ser uma lista')
            with db:
                db.execute('INSERT OR IGNORE INTO nichos VALUES (?)', (nicho['nome'],))
            for video in entradas[:fonte.config[LIMITES[tipo]]]:
                try:
                    if not isinstance(video, dict) or not re.fullmatch(r'[\w-]{11}', video.get('id', ''), re.ASCII):
                        raise ValueError('entrada sem ID válido de vídeo')
                    with db:
                        cursor = db.execute('''INSERT OR IGNORE INTO videos
                            (id,titulo,canal,channel_id,duracao,views_busca,descoberto)
                            VALUES (?,?,?,?,?,?,?)''', (video['id'], video.get('title') or video['id'],
                            video.get('channel') or video.get('uploader'), video.get('channel_id'),
                            video.get('duration'), video.get('view_count'), agora.isoformat()))
                        novos += cursor.rowcount
                        if tipo == 'buscas24h':
                            db.execute('''UPDATE videos SET achado_24h=?,
                                views_busca=COALESCE(?,views_busca) WHERE id=?''',
                                (agora.isoformat(), video.get('view_count'), video['id']))
                        db.execute('INSERT OR IGNORE INTO video_nichos VALUES (?,?)',
                                   (video['id'], nicho['nome']))
                except (ValueError, TypeError, KeyError) as erro:
                    registrar(f"entrada em {nicho['nome']}: {erro}")
            certos += 1
        except Exception as erro:
            registrar(f"nicho {nicho['nome']}: {erro}")
    return certos, novos
