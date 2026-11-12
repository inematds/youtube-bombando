import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import fcntl
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bombando.banco import abrir
from bombando.detalhe import candidatos
from bombando.fonte import Fonte, Indisponivel
from bombando.metricas import montar
from bombando.rodada import executar

RAIZ = Path(__file__).resolve().parents[1]


class RodadaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        shutil.copy(RAIZ / 'config.json', self.raiz / 'config.json')
        shutil.copytree(RAIZ / 'tests/fixtures', self.raiz / 'fixtures')
        self.args = argparse.Namespace(fixtures=self.raiz / 'fixtures', so_painel=False, nicho=None)

    def rodar(self):
        saida = io.StringIO()
        with patch('subprocess.run', side_effect=AssertionError('Rede proibida nos testes de integração')), redirect_stdout(saida), redirect_stderr(saida):
            codigo = executar(self.args, self.raiz)
        return codigo, saida.getvalue()

    def dados(self):
        return json.loads((self.raiz / 'painel/dados.json').read_text())

    def alterar_fixture(self, arquivo, alterar):
        caminho = self.raiz / 'fixtures' / arquivo
        dados = json.loads(caminho.read_text())
        alterar(dados)
        caminho.write_text(json.dumps(dados))

    def test_rodada_inteira_indisponivel_e_idempotencia(self):
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0, saida)
        self.assertIn('rodada ok: 7 nichos, 3 novos, 2 fotos, 1 erros', saida)
        pagina = (self.raiz / 'painel/index.html').read_text()
        self.assertIn('Agentes de IA automatizam tarefas', pagina)
        self.assertIn('<svg', pagina)
        self.assertIn('Vídeo privado de demonstração', pagina)
        self.assertNotIn('<script src=', pagina)
        self.assertNotIn('<img ', pagina.split('<script id="dados"')[0])
        dados = self.dados()
        self.assertEqual(sum(v['indisponivel'] for v in dados['videos']), 1)
        self.assertEqual(len(dados['videos'][0]['nichos']), 7)
        self.assertEqual(len(list((self.raiz / 'painel/historico').glob('*.html'))), 1)
        embutido = pagina.split('<script id="dados" type="application/json">')[1].split('</script>')[0]
        self.assertEqual(json.loads(embutido), dados)
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn('0 novos, 0 fotos', saida)
        self.assertEqual(sum(len(v['fotos']) for v in self.dados()['videos']), 2)

    def test_falha_parcial_e_falha_total(self):
        self.alterar_fixture('buscas.json', lambda d: d.update({'chatgpt': {'erro': 'timeout'}}))
        self.assertEqual(self.rodar()[0], 0)
        self.assertEqual(self.dados()['rodada']['nichos'], 6)
        self.alterar_fixture('buscas.json', lambda d: d.update({k: {'erro': 'timeout'} for k in d}))
        self.assertEqual(self.rodar()[0], 1)
        self.assertEqual(self.dados()['rodada']['nichos'], 0)

    def test_so_painel_preserva_ultima_rodada(self):
        self.rodar()
        antes = self.dados()['rodada']
        self.args.so_painel = True
        with patch.object(Fonte, 'obter', side_effect=AssertionError('não pode coletar')):
            self.assertEqual(self.rodar()[0], 0)
        self.assertEqual(self.dados()['rodada'], antes)

    def test_nicho_filtro_e_inexistente(self):
        self.args.nicho = 'chatgpt'
        self.assertEqual(self.rodar()[0], 0)
        self.assertEqual(self.dados()['nichos'], ['chatgpt'])
        self.args.nicho = 'não existe'
        self.assertEqual(self.rodar()[0], 1)

    def test_lock_nao_inicia_segunda_rodada(self):
        (self.raiz / 'dados').mkdir()
        with (self.raiz / 'dados/.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn('já em execução', saida)
        self.assertFalse((self.raiz / 'dados/bombando.db').exists())

    def test_erro_transitorio_nao_marca_indisponivel(self):
        self.alterar_fixture('detalhes.json', lambda d: d.update({'iaDemo00001': {'erro': '429 Too Many Requests'}}))
        self.assertEqual(self.rodar()[0], 0)
        video = next(v for v in self.dados()['videos'] if v['id'] == 'iaDemo00001')
        self.assertEqual(video['indisponivel'], 0)
        self.assertEqual(video['fotos'], [])

    def test_entrada_invalida_nao_descarta_as_demais(self):
        self.alterar_fixture('buscas.json', lambda d: d['chatgpt']['entries'].insert(0, None))
        self.args.nicho = 'chatgpt'
        self.assertEqual(self.rodar()[0], 0)
        self.assertEqual(len(self.dados()['videos']), 3)

    def test_escapa_titulos_e_json(self):
        malicioso = '</script><img src=x onerror=alert(1)>'
        self.alterar_fixture('buscas.json', lambda d: d['chatgpt']['entries'][0].update(title=malicioso))
        self.args.nicho = 'chatgpt'
        self.rodar()
        pagina = (self.raiz / 'painel/index.html').read_text()
        self.assertNotIn(malicioso, pagina)
        self.assertIn('\\u003c/script', pagina)
        self.assertEqual(self.dados()['videos'][0]['titulo'], malicioso)

    def test_limite_janela_prioridade_e_nota(self):
        self.rodar()
        db = abrir(self.raiz / 'dados/bombando.db')
        self.addCleanup(db.close)
        agora = datetime.now(timezone.utc)
        ontem = (agora.date() - timedelta(days=1)).isoformat()
        publicado = (agora - timedelta(days=3)).isoformat()
        with db:
            db.execute('UPDATE fotos SET dia=?', (ontem,))
            db.execute('UPDATE videos SET publicado=?', (publicado,))
            db.execute('UPDATE fotos SET views=1000,inscritos=100 WHERE id=?', ('iaDemo00001',))
            db.execute('UPDATE fotos SET views=3000,inscritos=100 WHERE id=?', ('n8nDemo0001',))
        config = json.loads((self.raiz / 'config.json').read_text())
        config['max_detalhes_por_rodada'] = 1
        self.assertEqual([v['id'] for v in candidatos(db, config, agora)], ['n8nDemo0001'])
        videos = montar(db, agora)['videos']
        import math
        self.assertAlmostEqual(videos[0]['nota'], -1 + math.log1p(10))
        with db:
            db.execute('UPDATE videos SET descoberto=? WHERE id=?', ((agora - timedelta(days=8)).isoformat(), 'n8nDemo0001'))
        self.assertEqual([v['id'] for v in candidatos(db, config, agora)], ['iaDemo00001'])


class FonteTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((RAIZ / 'config.json').read_text())

    def test_comando_timeout_e_pausa_sem_executar(self):
        fonte = Fonte(self.config)
        retorno = subprocess.CompletedProcess([], 0, '{"entries": []}', '')
        with patch('subprocess.run', return_value=retorno) as run, patch('time.sleep') as sleep:
            fonte.obter('buscas', 'agentes de ia')
            fonte.obter('buscas', 'chatgpt')
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.kwargs['timeout'], 120)
        self.assertIn('--flat-playlist', run.call_args.args[0])
        self.assertIn('&sp=EgIIAw%253D%253D', run.call_args.args[0][-1])
        sleep.assert_called_once()

    def test_timeout_propaga(self):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('yt-dlp', 120)):
            with self.assertRaises(subprocess.TimeoutExpired):
                Fonte(self.config).obter('detalhes', 'iaDemo00001')

    def test_privado_classificado_e_json_invalido(self):
        retorno = subprocess.CompletedProcess([], 1, '', 'ERROR: Private video')
        with patch('subprocess.run', return_value=retorno):
            with self.assertRaises(Indisponivel):
                Fonte(self.config).obter('detalhes', 'privado0001')
        retorno = subprocess.CompletedProcess([], 0, 'não é json', '')
        with patch('subprocess.run', return_value=retorno):
            with self.assertRaises(json.JSONDecodeError):
                Fonte(self.config).obter('detalhes', 'iaDemo00001')
