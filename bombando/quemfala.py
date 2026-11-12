"""Sinais lexicais de pessoa/convidado, sem inferir participação real."""
import re

PESSOAS = [
    'Sam Altman', 'Elon Musk', 'Jensen Huang', 'Dario Amodei', 'Demis Hassabis',
    'Andrej Karpathy', 'Mark Zuckerberg', 'Satya Nadella', 'Sundar Pichai',
    'Ilya Sutskever', 'Yann LeCun', 'Geoffrey Hinton', 'Fei-Fei Li', 'Andrew Ng',
    'Lex Fridman', 'Joe Rogan', 'Bill Gates', 'Steve Jobs', 'Trump', 'Lula',
    'Primo Rico', 'Thiago Nigro', 'Flow Podcast',
]
NOME = r'[A-ZÀ-Ý][a-zà-ÿ]+(?:[ -][A-ZÀ-Ý][a-zà-ÿ]+)+'
PADROES = [
    # Só formato explícito de convidado; "| Nome", "#24" e Title Case solto davam falso positivo
    # (nome do próprio canal, "Graph Engineering", "Inteligência Artificial").
    rf'(?i:\b(?:entrevista|conversa|papo|bate-papo|podcast|live|palestra)\s+com)\s+({NOME})',
    rf'(?i:\b(?:ft|feat)\.)\s*({NOME})?',
    r'(?i:\b(?:entrevista|podcast|palestra|interview)\b)',
]


def detectar(titulo, descricao=None, pessoas=None):
    pessoa = trecho_pessoa = trecho_formato = None
    for texto in (titulo or '', descricao or ''):
        if pessoa is None:
            for nome in PESSOAS if pessoas is None else pessoas:
                match = re.search(r'(?<!\w)' + re.escape(nome) + r'(?!\w)', texto, re.I)
                if match:
                    pessoa, trecho_pessoa = nome, match.group()
                    break
        for padrao in PADROES:
            match = re.search(padrao, texto)
            if match:
                if trecho_formato is None:
                    trecho_formato = match.group()
                if pessoa is None and match.lastindex:
                    pessoa = match.group(1)
    return dict(pessoa=pessoa, formato_convidado=trecho_formato is not None,
                trecho_pessoa=trecho_pessoa, trecho_convidado=trecho_formato)
