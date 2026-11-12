"""Uma única fronteira de subprocesso; fixtures nunca invocam yt-dlp."""
import json
import re
import subprocess
import time
from urllib.parse import quote_plus


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
                   '--extractor-args', f"youtube:lang={self.config['idioma']}",
                   '--geo-bypass-country', self.config['regiao']]
        if tipo == 'buscas':
            url = ('https://www.youtube.com/results?search_query=' + quote_plus(chave)
                   + '&sp=EgIIAw%253D%253D')
            comando += ['--flat-playlist', '-J', '--playlist-end',
                        str(self.config['por_nicho_busca']), url]
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
