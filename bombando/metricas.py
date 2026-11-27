"""Métricas reproduzíveis; valores ausentes continuam ausentes."""
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

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
from .quemfala import detectar
from .canais import linha_base

FATOR_CONTEUDO = 3
FATOR_CONVIDADO = 1.5
PORTE_PEQUENO = 10_000
PORTE_GRANDE = 500_000
CATEGORIAS = ('Conteúdo', 'Quem fala', 'Quem posta', 'Conteúdo + quem fala', 'Misto', 'Sem dados')

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


def velocidade_recente(fotos, hoje):
    """Views/h entre fotos reais, numa janela de até três dias."""
    medidas = [(date.fromisoformat(f['dia']), f['views']) for f in fotos
               if numero(f.get('views')) is not None]
    medidas.sort()
    if len(medidas) < 2:
        return None
    fim, views = medidas[-1]
    if not 0 <= (hoje - fim).days <= 1:
        return None
    for inicio, antes in medidas[:-1]:
        dias = (fim - inicio).days
        if 0 < dias <= 3:
            return (views - antes) / (dias * 24)
    return None


def bonus_relevancia(video):
    ritmo = max(0, video['velocidade_recente'] or 0)
    media = video['velocidade'] or 0
    idade_dias = (video['idade_h'] or 0) / 24
    volume = math.log1p(ritmo / 100)
    retomada = math.log1p(max(0, ritmo - media) / max(100, media))
    permanencia = min(1, ritmo / 100) * min(1, idade_dias / 30)
    return volume + retomada + permanencia


def ultimas_24h(video, agora):
    """Ritmo e nota de um vídeo com menos de 24 h; None se não for dessa janela.

    Sem foto anterior não há ritmo recente: vale views/h desde a publicação. Sem data
    mas achado hoje pela busca "enviados hoje", usa views/24 (piso: a idade é < 24 h)."""
    if video.get('indisponivel'):
        return None
    views = video['views'] if video['views'] is not None else numero(video.get('views_busca'))
    idade = video['idade_h']
    if idade is not None:
        if idade >= 24:
            return None
        ritmo = views / max(idade, 1) if views is not None else None
    else:
        achado = video.get('achado_24h')
        if not achado or agora - datetime.fromisoformat(achado) >= timedelta(hours=24):
            return None
        ritmo = views / 24 if views is not None else None
    if ritmo is None:
        return None
    return dict(ritmo_24h=ritmo, nota_24h=math.log1p(ritmo) + math.log1p(video['multiplicador'] or 0))


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


def montar(db, agora, config=None):
    videos = []
    for linha in db.execute('SELECT * FROM videos ORDER BY id'):
        video = dict(linha)
        video['nichos'] = [r[0] for r in db.execute('SELECT nicho FROM video_nichos WHERE video_id=? ORDER BY nicho', (video['id'],))]
        video['fotos'] = [dict(r) for r in db.execute('SELECT * FROM fotos WHERE id=? ORDER BY dia', (video['id'],))]
        video.update(calcular(video['publicado'], video['fotos'], agora))
        cache = db.execute('SELECT * FROM canais WHERE channel_id=?', (video['channel_id'],)).fetchone()
        base = dict(cache) if cache else {}
        if base.get('amostra') is not None:
            base.update(linha_base(json.loads(base['amostra']), video['id'], agora))
        inscritos = numero(video['fotos'][-1].get('inscritos')) if video['fotos'] else None
        if inscritos is None:
            inscritos = numero(base.get('inscritos'))
        video.update(detectar(video['titulo'], video.get('descricao'), (config or {}).get('pessoas')))
        video.update(classificar(video['views'], base.get('mediana_views'), inscritos,
                                video['pessoa'], video['formato_convidado'], video['trecho_convidado']))
        video['n_amostra'] = base.get('n_amostra', 0)
        video['canal_atualizado'] = base.get('atualizado')
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
    return dict(videos=videos, nichos=nichos, assuntos={'geral': assuntos(ativos), 'nichos': tendencias},
                porque={'geral': resumir(ativos),
                        'nichos': {n: resumir([v for v in ativos if n in v['nichos']], n) for n in nichos}})


def formatar(valor, contagem=False):
    # Contagens (inscritos, mediana) sem casa decimal; razões e % com uma.
    modelo = '{:,.0f}' if contagem else '{:,.1f}'
    return modelo.format(valor).replace(',', '_').replace('.', ',').replace('_', '.')


def classificar(views, mediana, inscritos, pessoa=None, convidado=False, trecho=None):
    views, mediana, inscritos = numero(views), numero(mediana), numero(inscritos)
    porte = (None if inscritos is None else 'pequeno' if inscritos < PORTE_PEQUENO
             else 'grande' if inscritos > PORTE_GRANDE else 'médio')
    fator = views / mediana if views is not None and mediana else None
    sinal = bool(pessoa or convidado)
    if fator is None:
        categoria = 'Sem dados'
        motivo = 'Sem views confirmadas ou linha de base positiva do canal.'
    else:
        if fator >= FATOR_CONTEUDO:
            categoria = 'Conteúdo + quem fala' if sinal else 'Conteúdo'
        elif fator >= FATOR_CONVIDADO and sinal:
            categoria = 'Quem fala'
        elif fator < FATOR_CONVIDADO and porte == 'grande':
            categoria = 'Quem posta'
        else:
            categoria = 'Misto'
        motivo = f'{formatar(fator)}× o normal do canal (mediana {formatar(mediana, True)})'
        motivo += f' · canal {porte} ({formatar(inscritos, True)} inscritos)' if porte else ' · porte desconhecido'
        if sinal:
            motivo += f' · sinal de convidado: {pessoa or trecho or "formato com convidado"}'
    return dict(fator_canal=fator, mediana_views=mediana, porte=porte,
                categoria=categoria, motivo=motivo)


def resumir(videos, nicho='geral'):
    videos = [v for v in videos if not v.get('indisponivel') and v['views'] is not None]
    total_views = sum(v['views'] for v in videos)
    categorias = []
    for categoria in CATEGORIAS:
        grupo = [v for v in videos if v['categoria'] == categoria]
        views = sum(v['views'] for v in grupo)
        categorias.append(dict(categoria=categoria, videos=len(grupo), views=views,
                               pct_videos=100 * len(grupo) / len(videos) if videos else 0,
                               pct_views=100 * views / total_views if total_views else 0))
    prefixo = 'No geral' if nicho == 'geral' else f'Em {nicho}'
    pesos = {c['categoria']: c['pct_views'] for c in categorias}
    conteudo = pesos['Conteúdo'] + pesos['Conteúdo + quem fala']
    if not videos or not total_views:
        conclusao = f'{prefixo}, ainda não há views suficientes para uma conclusão.'
    elif pesos['Sem dados'] >= 50:
        conclusao = f'{prefixo}, {formatar(pesos["Sem dados"])}% das views estão sem linha de base; ainda não é possível concluir.'
    elif conteudo > 50:
        conclusao = f'{prefixo}, {formatar(conteudo)}% das views vêm de vídeos com pelo menos 3× o normal do canal: o sinal de CONTEÚDO predomina.'
    elif pesos['Quem posta'] > 50:
        conclusao = f'{prefixo}, {formatar(pesos["Quem posta"])}% das views estão em canais grandes no ritmo normal: o sinal de QUEM POSTA predomina.'
    elif pesos['Quem fala'] > 50:
        conclusao = f'{prefixo}, {formatar(pesos["Quem fala"])}% das views têm sinal de convidado e superam o normal: o sinal de QUEM FALA predomina.'
    else:
        conclusao = f'{prefixo}, as views se distribuem entre sinais mistos, sem predominância clara.'
    bolha = furaram_bolha(videos, minimo_views=0, limite=5)
    return dict(categorias=categorias, total_videos=len(videos), total_views=total_views,
                conclusao=conclusao, furaram_bolha=[v['id'] for v in bolha])


def furaram_bolha(videos, minimo_views, limite=None):
    candidatos = (v for v in videos if not v['indisponivel'] and (v['views'] or 0) > minimo_views
                  and (v['fator_canal'] or 0) >= FATOR_CONTEUDO and v['porte'] in ('pequeno', 'médio'))
    return sorted(candidatos, key=lambda v: (-v['fator_canal'], v['id']))[:limite]
