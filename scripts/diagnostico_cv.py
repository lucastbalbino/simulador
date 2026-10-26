#!/usr/bin/env python3
"""Diagnóstico temporário: descobre onde o CV guarda o preço dos lotes do Sweet Village.

Imprime só a estrutura das respostas (nomes de campos e tipos) e campos de preço,
nunca dados pessoais, porque as anotações de um repositório público são públicas.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

EMAIL = os.environ.get('CVCRM_EMAIL', '').strip()
TOKEN = os.environ.get('CVCRM_TOKEN', '').strip()
BASE = f"https://{os.environ.get('CVCRM_DOMINIO', 'vpa').strip()}.cvcrm.com.br/api"
ID_EMP = os.environ.get('CVCRM_ID_EMPREENDIMENTO', '4').strip()
SENSIVEL = re.compile(r'(cpf|cnpj|documento|email|telefone|celular|cliente|nome_cliente|proprietario|comprador|corretor|usuario)', re.I)
CHAVE_PRECO = re.compile(r'(valor|preco|preço|price|total|metro|m2)', re.I)


def nota(titulo, msg):
    msg = str(msg).replace('%', '%25').replace('\r', '').replace('\n', '%0A')
    print(f'::notice title={titulo}::{msg[:3800]}')


def get(caminho):
    req = urllib.request.Request(BASE + caminho, headers={'email': EMAIL, 'token': TOKEN, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            bruto = r.read().decode('utf-8', 'replace')
            tipo = r.headers.get('Content-Type', '')
            return r.status, tipo, bruto
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read().decode('utf-8', 'replace')[:300]
    except urllib.error.URLError as e:
        return 0, '', str(e.reason)


def esqueleto(v, prof=0, max_prof=6):
    """Estrutura do JSON: nomes e tipos; valores só de campos de preço numéricos."""
    if prof > max_prof:
        return '...'
    if isinstance(v, dict):
        out = {}
        for k, x in list(v.items())[:40]:
            if SENSIVEL.search(k):
                out[k] = '<omitido>'
            elif isinstance(x, (dict, list)):
                out[k] = esqueleto(x, prof + 1, max_prof)
            elif CHAVE_PRECO.search(k) or k in ('nome', 'unidade', 'bloco', 'quadra', 'lote', 'etapa', 'forma', 'tipo', 'idtabela', 'idunidade', 'aprovado'):
                out[k] = x if not isinstance(x, str) else x[:40]
            else:
                out[k] = type(x).__name__
        return out
    if isinstance(v, list):
        return [esqueleto(x, prof + 1, max_prof) for x in v[:2]] + ([f'... +{len(v) - 2}'] if len(v) > 2 else [])
    return type(v).__name__


def main():
    if not EMAIL or not TOKEN:
        nota('Diagnóstico', 'Segredos ausentes.')
        return

    st, tipo, bruto = get(f'/v1/cadastros/empreendimentos/{ID_EMP}?limite_dados_unidade=3&pagina_unidade=1')
    emp = json.loads(bruto) if st == 200 else {}
    nota('Tabelas do empreendimento', json.dumps(emp.get('tabela'), ensure_ascii=False))
    unidade = None
    for et in (emp.get('etapas') or []):
        for bl in (et.get('blocos') or []):
            for u in (bl.get('unidades') or []):
                unidade = unidade or u
    if unidade:
        nota('Campos de uma unidade', json.dumps(esqueleto(unidade), ensure_ascii=False))
        ca = [c.get('nome_referencia') for c in (unidade.get('campos_adicionais') or [])]
        nota('Campos adicionais da unidade', json.dumps(ca, ensure_ascii=False))

    for caminho in (
        f'/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/detalhada?tabelasemjson=true&aprovado=S',
        f'/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/detalhada?tabelasemjson=true',
        f'/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco',
    ):
        st, tipo, bruto = get(caminho)
        try:
            corpo = json.loads(bruto)
            resumo = json.dumps(esqueleto(corpo), ensure_ascii=False)
        except ValueError:
            resumo = f'(não é JSON, {len(bruto)} caracteres) ' + re.sub(r'\s+', ' ', bruto[:300])
        nota(f'{st} {caminho.split(ID_EMP, 1)[1]}', f'{tipo} | {resumo}')


if __name__ == '__main__':
    sys.exit(main())
