"""Regressão offline do método, cache, migração e integração 1.1."""
import json
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from bombando.banco import abrir
from bombando.canais import atualizar, linha_base
from bombando.fonte import Fonte
from bombando.metricas import classificar, montar, resumir
from bombando.quemfala import detectar
import test_rodada_fixtures as integracao

RAIZ = integracao.RAIZ

AGORA = datetime(2026, 11, 12, tzinfo=timezone.utc)


class MetodoTest(unittest.TestCase):
    def test_mediana_exclui_proprio_e_recentes_com_data(self):
        entradas = [dict(id='proprio', view_count=999999, upload_date='20260101'),
                    dict(id='novo', view_count=1, upload_date='20261110'),
                    dict(id='limite', view_count=100, upload_date='20261109'),
                    dict(id='antigo', view_count=300, upload_date='20260101')]
        self.assertEqual(linha_base(entradas, 'proprio', AGORA), dict(mediana_views=200, n_amostra=2))

    def test_sem_datas_exclui_dois_primeiros_e_nao_dois_apos_proprio(self):
        entradas = [dict(id=str(i), view_count=v) for i,v in enumerate([9000,8000,100,300,900])]
        self.assertEqual(linha_base(entradas, '4', AGORA), dict(mediana_views=200, n_amostra=2))
        self.assertEqual(linha_base(entradas, '0', AGORA), dict(mediana_views=300, n_amostra=3))

    def test_amostra_vazia_zero_invalida_duplicada_e_teto(self):
        self.assertEqual(linha_base([], 'x', AGORA), dict(mediana_views=None,n_amostra=0))
        entradas = [None, {}, dict(id='a', view_count=0), dict(id='a', view_count=100),
                    dict(id='b', view_count=None), dict(id='c', view_count=float('nan'))]
        self.assertEqual(linha_base(entradas, 'x', AGORA), dict(mediana_views=0,n_amostra=1))
        entradas = [dict(id=str(i), view_count=100 if i<20 else 90000) for i in range(25)]
        self.assertEqual(linha_base(entradas, 'x', AGORA), dict(mediana_views=100,n_amostra=18))

    def test_regras_e_limites(self):
        casos = [(300, 100, 10000, None, False, 'Conteúdo'),
                 (150, 100, 10000, 'Sam Altman', False, 'Quem fala'),
                 (149, 100, 500001, None, False, 'Quem posta'),
                 (300, 100, 10000, None, True, 'Conteúdo + quem fala'),
                 (299, 100, 500000, None, False, 'Misto'),
                 (150, 100, 500001, None, False, 'Misto'),
                 (149, 100, 500001, 'Sam Altman', True, 'Quem posta'),
                 (1, None, 10000, None, False, 'Sem dados'),
                 (1, 0, 10000, None, False, 'Sem dados'),
                 (None, 100, 10000, None, False, 'Sem dados')]
        for views,mediana,inscritos,pessoa,convidado,categoria in casos:
            with self.subTest(categoria=categoria,views=views):
                self.assertEqual(classificar(views,mediana,inscritos,pessoa,convidado)['categoria'],categoria)
        for inscritos, porte in [(9999,'pequeno'),(10000,'médio'),(500000,'médio'),(500001,'grande'),(None,None)]:
            self.assertEqual(classificar(100,100,inscritos)['porte'],porte)
        self.assertEqual(classificar(0,100,100)['fator_canal'],0)
        self.assertIn('3,0×',classificar(300,100,100)['motivo'])

    def test_pessoas_e_formatos_com_evidencia(self):
        for titulo in ['entrevista com Maria Silva', 'ft. Maria Silva', 'feat. Maria Silva', 'Entrevista',
                       'Podcast de IA', 'Palestra']:
            with self.subTest(titulo=titulo):
                d=detectar(titulo)
                self.assertTrue(d['formato_convidado'])
                self.assertTrue(d['trecho_convidado'])
        self.assertEqual(detectar('SAM ALTMAN e IA')['pessoa'],'Sam Altman')
        self.assertEqual(detectar('IA', 'Uma conversa com Elon Musk')['pessoa'],'Elon Musk')
        self.assertEqual(detectar('Teste', pessoas=[])['pessoa'],None)
        self.assertEqual(detectar('Ana Souza fala', pessoas=['Ana Souza'])['pessoa'],'Ana Souza')
        self.assertIsNone(detectar('Lulatico e Trumpismo')['pessoa'])
        self.assertFalse(detectar('Automação com agentes inteligentes')['formato_convidado'])
        # Falsos positivos vistos na 1ª coleta real (12/11/2026): não são convidados.
        for titulo in ['IA | Maria Silva', 'IA - MARIA SILVA', 'IA #123', 'Agentes com Graph Engineering',
                       'Guia com Inteligência Artificial']:
            with self.subTest(falso=titulo):
                self.assertFalse(detectar(titulo)['formato_convidado'])
                self.assertIsNone(detectar(titulo)['pessoa'])
        self.assertEqual(detectar('Papo com Maria Silva')['pessoa'], 'Maria Silva')

    def test_resumo_percentuais_top5_e_ausencias(self):
        videos=[]
        for i in range(7):
            v=dict(id=str(i), views=100, indisponivel=False)
            v.update(classificar(100,10+i,1000))
            videos.append(v)
        videos.append(dict(id='sem',views=100,indisponivel=False,**classificar(100,None,None)))
        videos.append(dict(id='privado',views=900000,indisponivel=True,**classificar(900000,100,100)))
        videos.append(dict(id='ausente',views=None,indisponivel=False,**classificar(None,100,100)))
        resumo=resumir(videos,'IA')
        self.assertEqual(resumo['total_videos'],8)
        self.assertEqual(resumo['total_views'],800)
        self.assertEqual(resumo['furaram_bolha'],['0','1','2','3','4'])
        self.assertEqual(sum(c['pct_views'] for c in resumo['categorias']),100)
        self.assertEqual(sum(c['pct_videos'] for c in resumo['categorias']),100)
        self.assertIn('CONTEÚDO',resumo['conclusao'])
        self.assertIn('ainda não',resumir([])['conclusao'])
        self.assertIn('não é possível concluir',resumir([videos[7]])['conclusao'])

    def test_migracao_preserva_banco_antigo(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho=Path(pasta)/'b.db'
            db=sqlite3.connect(caminho)
            db.execute('''CREATE TABLE videos(id TEXT PRIMARY KEY,titulo TEXT NOT NULL,canal TEXT,
                       channel_id TEXT,duracao REAL,views_busca INTEGER,descoberto TEXT NOT NULL,
                       publicado TEXT,indisponivel INTEGER NOT NULL DEFAULT 0)''')
            db.execute("INSERT INTO videos(id,titulo,descoberto) VALUES ('id','Título','2026-11-12')")
            db.commit(); db.close()
            for _ in range(2):
                db=abrir(caminho)
                self.assertEqual(db.execute('SELECT titulo,descricao FROM videos').fetchone()[:],('Título',None))
                db.close()


class CanaisIntegracaoTest(unittest.TestCase):
    setUp = integracao.RodadaTest.setUp
    rodar = integracao.RodadaTest.rodar
    dados = integracao.RodadaTest.dados
    alterar_fixture = integracao.RodadaTest.alterar_fixture

    def test_cache_limite_e_falha_isolada(self):
        self.rodar()
        db=abrir(self.raiz/'dados/bombando.db'); self.addCleanup(db.close)
        config=json.loads((self.raiz/'config.json').read_text())
        fonte=Fonte(config,self.raiz/'fixtures')
        agora=datetime.now(timezone.utc)
        erros=[]
        with db:
            db.execute('UPDATE canais SET atualizado=?',((agora.date()-timedelta(days=7)).isoformat(),))
        with patch.object(fonte,'obter',side_effect=AssertionError('cache válido')):
            self.assertEqual(atualizar(db,fonte,agora,erros.append),(0,0))
        with db:
            db.execute('UPDATE canais SET atualizado=?',((agora.date()-timedelta(days=8)).isoformat(),))
        esperado=next(v['channel_id'] for v in sorted(montar(db,agora)['videos'],key=lambda v:-v['nota']) if v['channel_id'])
        config['max_canais_por_rodada']=1
        with patch.object(fonte,'obter',wraps=fonte.obter) as obter:
            self.assertEqual(atualizar(db,fonte,agora,erros.append),(1,1))
            self.assertEqual(obter.call_args.args,('canais',esperado))
        config['max_canais_por_rodada']=120
        with db:
            db.execute("UPDATE canais SET atualizado='2000-01-01'")
        self.alterar_fixture('canais.json',lambda d:d.update({'UCdemo1':{'erro':'timeout'}}))
        self.assertEqual(atualizar(db,fonte,agora,erros.append),(1,2))
        self.assertIn('UCdemo1',erros[-1])
        self.assertEqual(db.execute("SELECT atualizado FROM canais WHERE channel_id='UCdemo1'").fetchone()[0],'2000-01-01')

    def test_so_canais_nao_descobre_nem_fotografa(self):
        self.rodar()
        antes=self.dados()
        self.args.so_canais=True
        with patch('bombando.rodada.descobrir',side_effect=AssertionError('descoberta proibida')), patch('bombando.rodada.acompanhar',side_effect=AssertionError('foto proibida')):
            self.assertEqual(self.rodar()[0],0)
        depois=self.dados()
        self.assertEqual([v['fotos'] for v in antes['videos']],[v['fotos'] for v in depois['videos']])
        self.assertEqual(depois['rodada']['novos'],0)
        self.assertEqual(depois['rodada']['fotos'],0)

    def test_painel_metodo_descricao_e_filtro(self):
        self.rodar()
        dados=self.dados()
        v=next(v for v in dados['videos'] if v['id']=='n8nDemo0001')
        self.assertEqual(v['pessoa'],'Sam Altman')
        self.assertEqual(v['categoria'],'Quem fala')
        self.assertEqual(v['mediana_views'],12000)
        self.assertEqual(dados['porque']['geral']['total_videos'],2)
        self.assertEqual(dados['porque']['nichos']['chatgpt']['total_views'],72000)
        pagina=(self.raiz/'painel/index.html').read_text()
        self.assertIn('Por que bombou?',pagina)
        self.assertIn('value="fator_canal"',pagina)
        self.assertIn('images=false',pagina)
        self.assertIn('data.porque.nichos[nicho]',pagina)

    def test_mediana_por_video_mesmo_canal(self):
        self.alterar_fixture('buscas.json',lambda d:[e.update(channel_id='UCdemo1') for n in d.values() for e in n['entries'] if e['id']=='n8nDemo0001'])
        self.alterar_fixture('canais.json',lambda d:d['UCdemo1'].update(entries=[
            dict(id='iaDemo00001',view_count=100,upload_date='20260101'),
            dict(id='n8nDemo0001',view_count=1000,upload_date='20260101'),
            dict(id='outro',view_count=300,upload_date='20260101')]))
        self.rodar()
        videos={v['id']:v for v in self.dados()['videos']}
        self.assertEqual(videos['iaDemo00001']['mediana_views'],650)
        self.assertEqual(videos['n8nDemo0001']['mediana_views'],200)

    def test_falha_canal_sem_dados_e_modo_canais_falha_total(self):
        self.alterar_fixture('canais.json',lambda d:d.update({k:{'erro':'timeout'} for k in d}))
        self.assertEqual(self.rodar()[0],0)
        self.assertTrue(all(v['categoria']=='Sem dados' for v in self.dados()['videos']))
        self.args.so_canais=True
        self.assertEqual(self.rodar()[0],1)

    def test_comando_canal_sem_rede(self):
        config=json.loads((RAIZ/'config.json').read_text())
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'{"entries":[]}','')) as run:
            Fonte(config).obter('canais','UCdemo1')
        comando=run.call_args.args[0]
        self.assertEqual(comando[-1],'https://www.youtube.com/channel/UCdemo1/videos')
        self.assertEqual(comando[comando.index('--playlist-end')+1],'20')
        self.assertEqual(run.call_args.kwargs['timeout'],120)
