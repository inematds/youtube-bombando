"""Cache de amostras de canais; a mediana de cada vídeo exclui a si mesmo."""
import json
import statistics
from datetime import date, datetime, timedelta, timezone

CACHE_DIAS = 7
IDADE_MINIMA_DIAS = 3


def linha_base(entradas, video_id, agora):
    # Importação tardia evita ciclo com as métricas que consomem esta função.
    from .metricas import numero
    valores = []
    vistos = set()
    for indice, entrada in enumerate(entradas[:20]):
        if not isinstance(entrada, dict):
            continue
        ident = entrada.get('id')
        if ident == video_id or (ident and ident in vistos):
            continue
        if ident:
            vistos.add(ident)
        publicado = None
        try:
            if entrada.get('timestamp') is not None:
                publicado = datetime.fromtimestamp(entrada['timestamp'], timezone.utc)
            elif entrada.get('upload_date'):
                publicado = datetime.strptime(entrada['upload_date'], '%Y%m%d').replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            pass
        if publicado is not None:
            if agora - publicado < timedelta(days=IDADE_MINIMA_DIAS):
                continue
        elif indice < 2:
            continue
        views = numero(entrada.get('view_count'))
        if views is not None:
            valores.append(views)
    return dict(mediana_views=statistics.median(valores) if valores else None,
                n_amostra=len(valores))


def atualizar(db, fonte, agora, registrar, nicho=None):
    from .metricas import montar, numero
    videos = montar(db, agora, fonte.config)['videos']
    limite = agora - timedelta(days=fonte.config['dias_acompanhar'])
    canais = {}
    for v in sorted(videos, key=lambda v: (-v['nota'], v['id'])):
        if (v['channel_id'] and not v['indisponivel']
                and datetime.fromisoformat(v['descoberto']) >= limite
                and (nicho is None or nicho in v['nichos'])):
            canais.setdefault(v['channel_id'], v)
    tentativas = certos = 0
    for ident, video in canais.items():
        cache = db.execute('SELECT atualizado FROM canais WHERE channel_id=?', (ident,)).fetchone()
        if cache:
            try:
                idade = (agora.date() - date.fromisoformat(cache['atualizado'])).days
                if 0 <= idade <= CACHE_DIAS:
                    continue
            except (ValueError, TypeError):
                pass
        if tentativas >= fonte.config.get('max_canais_por_rodada', 120):
            break
        tentativas += 1
        try:
            dados = fonte.obter('canais', ident)
            entradas = dados['entries']
            if not isinstance(entradas, list):
                raise ValueError('entries deve ser uma lista')
            entradas = entradas[:20]
            base = linha_base(entradas, video['id'], agora)
            with db:
                db.execute('''INSERT INTO canais VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(channel_id) DO UPDATE SET nome=excluded.nome,
                    inscritos=excluded.inscritos, mediana_views=excluded.mediana_views,
                    n_amostra=excluded.n_amostra, atualizado=excluded.atualizado,
                    amostra=excluded.amostra''',
                    (ident, dados.get('channel') or dados.get('title') or video['canal'],
                     numero(dados.get('channel_follower_count')), base['mediana_views'],
                     base['n_amostra'], agora.date().isoformat(), json.dumps(entradas)))
            certos += 1
        except Exception as erro:
            registrar(f'canal {ident}: {erro}')
    return certos, tentativas
