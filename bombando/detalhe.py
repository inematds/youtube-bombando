"""Acompanha a janela recente com uma foto diária por vídeo."""
from datetime import datetime, timedelta, timezone
from .fonte import Indisponivel
from .metricas import calcular, numero


def candidatos(db, config, agora, nicho=None):
    limite = (agora - timedelta(days=config['dias_acompanhar'])).isoformat()
    linhas = db.execute('''SELECT * FROM videos WHERE descoberto>=? AND indisponivel=0
        AND NOT EXISTS (SELECT 1 FROM fotos WHERE fotos.id=videos.id AND dia=?)
        AND (? IS NULL OR EXISTS (SELECT 1 FROM video_nichos WHERE video_id=videos.id AND nicho=?))''',
        (limite, agora.date().isoformat(), nicho, nicho)).fetchall()
    def prioridade(video):
        fotos = [dict(r) for r in db.execute('SELECT * FROM fotos WHERE id=? ORDER BY dia', (video['id'],))]
        instante = agora
        if fotos:
            instante = datetime.fromisoformat(fotos[-1]['dia']).replace(tzinfo=timezone.utc) + timedelta(hours=12)
        velocidade = calcular(video['publicado'], fotos, instante)['velocidade']
        return (-(velocidade or 0), video['descoberto'], video['id'])
    return sorted(linhas, key=prioridade)[:config['max_detalhes_por_rodada']]


def acompanhar(db, fonte, agora, registrar, nicho=None):
    total = 0
    for video in candidatos(db, fonte.config, agora, nicho):
        try:
            dados = fonte.obter('detalhes', video['id'])
            publicado = None
            if dados.get('timestamp') is not None:
                publicado = datetime.fromtimestamp(dados['timestamp'], timezone.utc).isoformat()
            elif dados.get('upload_date'):
                publicado = datetime.strptime(dados['upload_date'], '%Y%m%d').replace(tzinfo=timezone.utc).isoformat()
            with db:
                db.execute('UPDATE videos SET publicado=COALESCE(?,publicado) WHERE id=?', (publicado, video['id']))
                db.execute('INSERT INTO fotos VALUES (?,?,?,?,?,?)', (video['id'], agora.date().isoformat(),
                    *(numero(dados.get(campo)) for campo in ('view_count', 'like_count', 'comment_count', 'channel_follower_count'))))
            total += 1
        except Indisponivel as erro:
            with db:
                db.execute('UPDATE videos SET indisponivel=1 WHERE id=?', (video['id'],))
            registrar(f"vídeo {video['id']} indisponível: {erro}")
        except Exception as erro:
            registrar(f"vídeo {video['id']}: {erro}")
    return total
