"""Uma única fronteira de subprocesso; fixtures nunca invocam yt-dlp."""
import json
import re
import subprocess
import time
from urllib.parse import quote_plus


# Filtro "sp" da busca do YouTube e o limite de resultados de cada tipo.
# EgIIAw== = enviados nesta semana (relevância); CAMSAggC = enviados hoje, ordem por views
# (testado em 27/11/2026: devolve views na própria busca e vídeos com menos de 24 h).
FILTROS = {'buscas': ('EgIIAw%253D%253D', 'por_nicho_busca'),
           'buscas24h': ('CAMSAggC', 'por_nicho_24h')}


class Indisponivel(RuntimeError):
    pass


class Fonte:
    def __init__(self, config, fixtures=None):
        self.config = config
        self.fixtures = fixtures
        self.ultima = None

    def obter(self, tipo, chave):
        if self.fixtures is not None:
            arquivo = self.fixtures / (tipo + '.json')
            dados = json.loads(arquivo.read_text(encoding='utf-8'))[chave]
            if isinstance(dados, dict) and 'erro' in dados:
                if dados.get('indisponivel'):
                    raise Indisponivel(dados['erro'])
                raise RuntimeError(dados['erro'])
            return dados
        if self.ultima is not None:
            time.sleep(max(0, self.config['pausa_s'] - (time.monotonic() - self.ultima)))
        comando = ['yt-dlp', '--ignore-config', '--socket-timeout', '20',
                   '--retries', '1', '--extractor-retries', '1',
                   # Sem youtube:lang=pt: com ele o yt-dlp lê "3,4 mil" como 34 e perde os inscritos.
                   '--geo-bypass-country', self.config['regiao']]
        if tipo in FILTROS:
            filtro, limite = FILTROS[tipo]
            url = 'https://www.youtube.com/results?search_query=' + quote_plus(chave) + '&sp=' + filtro
            comando += ['--flat-playlist', '-J', '--playlist-end', str(self.config[limite]), url]
        elif tipo == 'canais':
            comando += ['--flat-playlist', '-J', '--playlist-end', '20',
                        'https://www.youtube.com/channel/' + chave + '/videos']
        else:
            comando += ['--skip-download', '-J', 'https://www.youtube.com/watch?v=' + chave]
        try:
            resultado = subprocess.run(comando, capture_output=True, text=True, timeout=120)
        finally:
            self.ultima = time.monotonic()
        if resultado.returncode:
            erro = resultado.stderr[-2000:]
            if re.search(r'private video|video unavailable|has been removed|has been deleted', erro, re.I):
                raise Indisponivel(erro)
            raise RuntimeError(erro or 'yt-dlp falhou sem mensagem')
        return json.loads(resultado.stdout)
