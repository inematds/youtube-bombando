"""Métricas reproduzíveis; valores ausentes continuam ausentes."""
import math
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone

STOPWORDS = set('''a o as os um uma uns umas de da do das dos e é em no na nos nas
por para com sem que se ao aos à às como mais muito sua seu seus suas eu você voce
me meu minha este esta esse essa isso isto the a an and or of to in on for with
is are was were how what why this that it your you my our from by at be i we
hoje novo nova video vídeo sobre não nao já ja can do does vs
ou cada usar quando qual quais quem onde tudo todo toda todos todas fazer faz fiz
ser ter tem está esta estão foi vai vou pode podem precisa agora aqui ali pra pro
até ate mas mesmo só so bem tão tao dia dias vez coisa coisas entre depois antes
nunca sempre ainda então entao porque porquê lo la ele ela eles elas nós nos vc
get new now all not just will has have more most best top part parte ep shorts'''.split())
MIN_VIDEOS_POR_TERMO = 2  # termo de um título só não é "assunto em alta"


def numero(valor):
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor):
        return max(0, valor)
    return None


def calcular(publicado, fotos, agora):
    idade = None
    if publicado:
        instante = datetime.fromisoformat(publicado)
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        idade = max(0, (agora - instante).total_seconds() / 3600)
    fotos = sorted(fotos, key=lambda foto: foto['dia'])
    ultima = fotos[-1] if fotos else {}
    views, inscritos = numero(ultima.get('views')), numero(ultima.get('inscritos'))
    velocidade = views / max(idade, 1) if views is not None and idade is not None else None
    ganho = None
    if len(fotos) > 1 and ultima['dia'] == agora.date().isoformat():
        anterior = fotos[-2]
        dias = (date.fromisoformat(ultima['dia']) - date.fromisoformat(anterior['dia'])).days
        antes = numero(anterior.get('views'))
        if dias > 0 and views is not None and antes is not None:
            ganho = (views - antes) / dias
    return dict(idade_h=idade, views=views, velocidade=velocidade, ganho_24h=ganho,
                multiplicador=views / inscritos if views is not None and inscritos else None)


def assuntos(videos):
    pesos, vistos = defaultdict(float), defaultdict(int)
    for video in sorted(videos, key=lambda v: v['nota'], reverse=True)[:30]:
        tokens = re.findall(r'[^\W_]+', video['titulo'].lower(), re.UNICODE)
        bons = lambda t: len(t) > 1 and t not in STOPWORDS and not t.isnumeric()
        termos = {t for t in tokens if bons(t)}
        termos.update(a + ' ' + b for a, b in zip(tokens, tokens[1:]) if bons(a) and bons(b))
        for termo in termos:
            pesos[termo] += video['velocidade'] or 0
            vistos[termo] += 1
    minimo = MIN_VIDEOS_POR_TERMO if len(videos) >= 5 else 1
    validos = [(t, p) for t, p in pesos.items() if p > 0 and vistos[t] >= minimo]
    return [dict(termo=t, peso=p, videos=vistos[t]) for t, p in sorted(validos, key=lambda x: (-x[1], x[0]))[:15]]


def montar(db, agora):
    videos = []
    for linha in db.execute('SELECT * FROM videos ORDER BY id'):
        video = dict(linha)
        video['nichos'] = [r[0] for r in db.execute('SELECT nicho FROM video_nichos WHERE video_id=? ORDER BY nicho', (video['id'],))]
        video['fotos'] = [dict(r) for r in db.execute('SELECT * FROM fotos WHERE id=? ORDER BY dia', (video['id'],))]
        video.update(calcular(video['publicado'], video['fotos'], agora))
        video['notas'] = {}
        video['nota'] = 0
        videos.append(video)
    nichos = [r[0] for r in db.execute('SELECT nome FROM nichos ORDER BY nome')]
    ativos = [v for v in videos if not v['indisponivel']]
    for nicho in nichos:
        grupo = [v for v in ativos if nicho in v['nichos']]
        velocidades = [v['velocidade'] for v in grupo if v['velocidade'] is not None]
        media = statistics.mean(velocidades) if velocidades else 0
        desvio = statistics.pstdev(velocidades) if velocidades else 0
        for v in grupo:
            z = (v['velocidade'] - media) / desvio if desvio and v['velocidade'] is not None else 0
            v['notas'][nicho] = z + math.log1p(v['multiplicador'] or 0)
    for v in videos:
        v['nota'] = max(v['notas'].values(), default=0)
    tendencias = {n: assuntos([v for v in ativos if n in v['nichos']]) for n in nichos}
    return dict(videos=videos, nichos=nichos, assuntos={'geral': assuntos(ativos), 'nichos': tendencias})
