#!/usr/bin/env python3
"""Entrada CLI e orquestração, com lock durante toda a rodada."""
import shutil
import argparse
import fcntl
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bombando.banco import abrir
from bombando.coleta import descobrir
from bombando.canais import atualizar
from bombando.detalhe import acompanhar
from bombando.fonte import Fonte
from bombando.metricas import montar
from bombando.painel import gerar

RAIZ = Path(__file__).resolve().parents[1]


def configurar(raiz):
    config = json.loads((raiz / 'config.json').read_text(encoding='utf-8'))
    config.setdefault('max_canais_por_rodada', 120)
    for chave in ('por_nicho_busca', 'dias_acompanhar', 'max_detalhes_por_rodada', 'max_canais_por_rodada'):
        valor = config[chave]
        if type(valor) is not int or valor < 1:
            raise ValueError(f'{chave} deve ser inteiro positivo')
    if not isinstance(config['pausa_s'], (int, float)) or not math.isfinite(config['pausa_s']) or config['pausa_s'] < 0:
        raise ValueError('pausa_s deve ser um número finito não negativo')
    for nicho in config['nichos']:
        if not nicho.get('nome') or not nicho.get('busca') or type(nicho.get('ativo')) is not bool:
            raise ValueError('nicho precisa de nome, busca e ativo booleano')
    if 'pessoas' in config and (not isinstance(config['pessoas'], list) or
            any(not isinstance(p, str) or not p.strip() for p in config['pessoas'])):
        raise ValueError('pessoas deve ser uma lista de nomes não vazios')
    return config


def executar(args, raiz=RAIZ):
    so_canais = getattr(args, 'so_canais', False)
    agora = datetime.now(timezone.utc)
    dados = raiz / 'dados'
    logs = dados / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    with (dados / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('rodada já em execução; ignorada')
            return 0
        logger = logging.getLogger('bombando')
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(logs / (agora.date().isoformat() + '.log'), encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        db = None
        try:
            config = configurar(raiz)
            nichos = [n for n in config['nichos'] if n['ativo'] and (not args.nicho or args.nicho == n['nome'])]
            if not nichos and not args.so_painel and not so_canais:
                raise ValueError('nenhum nicho ativo corresponde à seleção')
            db = abrir(dados / 'bombando.db')
            erros = []
            def registrar(mensagem):
                erros.append(mensagem)
                logger.error(mensagem)
            certos = novos = fotos = 0
            if not args.so_painel:
                fonte = Fonte(config, args.fixtures)
                if not so_canais:
                    certos, novos = descobrir(db, fonte, nichos, agora, registrar)
                    fotos = acompanhar(db, fonte, agora, registrar, args.nicho)
                canais_ok, canais_tentados = atualizar(db, fonte, agora, registrar, args.nicho)
                with db:
                    db.execute('INSERT INTO rodadas VALUES (?,?,?,?,?,?)',
                               (agora.isoformat(), certos, novos, fotos, json.dumps(erros, ensure_ascii=False), int(args.fixtures is not None)))
            resultado = montar(db, agora, config)
            ultima = db.execute('SELECT * FROM rodadas ORDER BY instante DESC LIMIT 1').fetchone()
            resultado['rodada'] = dict(ultima) if ultima else {}
            if ultima:
                resultado['rodada']['erros'] = json.loads(ultima['erros'])
            resultado['gerado_em'] = agora.isoformat()
            gerar(resultado, raiz / 'painel', agora)
            mensagem = f'rodada ok: {certos} nichos, {novos} novos, {fotos} fotos, {len(erros)} erros -> painel/index.html'
            logger.info(mensagem)
            print(mensagem)
            if so_canais:
                return 0 if canais_ok or not canais_tentados else 1
            return 0 if args.so_painel or certos else 1
        except Exception as erro:
            logger.exception('rodada interrompida')
            print(f'rodada falhou: {erro}', file=sys.stderr)
            return 1
        finally:
            if db is not None:
                db.close()
            logger.removeHandler(handler)
            handler.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--so-painel', action='store_true')
    modo.add_argument('--so-canais', action='store_true')
    parser.add_argument('--fixtures', type=Path)
    parser.add_argument('--nicho', metavar='NOME')
    args = parser.parse_args()
    if args.fixtures:
        # Teste nunca grava no banco nem no painel de verdade: roda numa cópia em dados/teste/.
        teste = RAIZ / 'dados' / 'teste'
        teste.mkdir(parents=True, exist_ok=True)
        shutil.copy(RAIZ / 'config.json', teste / 'config.json')
        args.fixtures = args.fixtures.resolve()
        codigo = executar(args, teste)
        print(f'(teste: painel em {teste / "painel/index.html"})')
        return codigo
    return executar(args)


if __name__ == '__main__':
    sys.exit(main())
