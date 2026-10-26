#!/usr/bin/env python3
"""Lê os lotes do Sweet Village no CV CRM e gera data/lotes.json para o simulador.

Roda no GitHub Actions. O e-mail e o token ficam nos segredos do repositório
(CVCRM_EMAIL e CVCRM_TOKEN) e nunca vão para o arquivo publicado. O arquivo
gerado tem só quadra, lote, área e valor dos lotes disponíveis.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SAIDA = RAIZ / 'data' / 'lotes.json'

EMAIL = os.environ.get('CVCRM_EMAIL', '').strip()
TOKEN = os.environ.get('CVCRM_TOKEN', '').strip()
DOMINIO = os.environ.get('CVCRM_DOMINIO', 'vpa').strip()
ID_EMP = os.environ.get('CVCRM_ID_EMPREENDIMENTO', '4').strip()
POR_PAGINA = 100
DISPONIVEL = 1  # situacao_mapa_disponibilidade: 1 Disponível, 2 Reservada, 3 Vendida, 4 Bloqueada, 5 Em processo de reserva
FUSO = dt.timezone(dt.timedelta(hours=-3))


def aviso(tipo, titulo, msg):
    """Anotação do GitHub Actions (aparece no resumo da execução)."""
    msg = str(msg).replace('%', '%25').replace('\r', '').replace('\n', '%0A')
    print(f'::{tipo} title={titulo}::{msg}')


def numero(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace('R$', '').replace(' ', '')
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def lista(v):
    if v is None:
        return []
    if isinstance(v, dict):
        return [v]
    return list(v)


def buscar(pagina):
    base = os.environ.get('CVCRM_BASE_URL') or f'https://{DOMINIO}.cvcrm.com.br'  # BASE_URL só para testes
    url = (f'{base}/api/v1/cadastros/empreendimentos/{ID_EMP}'
           f'?limite_dados_unidade={POR_PAGINA}&pagina_unidade={pagina}')
    req = urllib.request.Request(url, headers={'email': EMAIL, 'token': TOKEN, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode('utf-8', 'replace')[:300]
        causas = {
            401: 'E-mail ou token incorretos ou vencidos. Confira os segredos CVCRM_EMAIL e CVCRM_TOKEN.',
            403: 'O usuário de integração não tem permissão de leitura de empreendimentos na API.',
            404: f'Endereço não encontrado. Confira o subdomínio "{DOMINIO}" e o ID {ID_EMP} do empreendimento.',
            429: 'Limite de requisições do CV atingido. A próxima execução tenta de novo.',
        }
        aviso('error', f'CV CRM respondeu {e.code}', causas.get(e.code, corpo))
        sys.exit(1)
    except urllib.error.URLError as e:
        aviso('error', 'Sem conexão com o CV CRM', f'{DOMINIO}.cvcrm.com.br: {e.reason}')
        sys.exit(1)


def tabela_m2(emp):
    """Valor do m² da tabela vigente e aprovada, usado só se o lote vier sem valor."""
    hoje = dt.date.today().isoformat()
    melhor = 0.0
    for t in lista(emp.get('tabela')):
        vm = numero(t.get('valor_metro'))
        if vm <= 0:
            continue
        de, ate = (t.get('data_vigencia_de') or '')[:10], (t.get('data_vigencia_ate') or '')[:10]
        vigente = (not de or de <= hoje) and (not ate or hoje <= ate)
        if str(t.get('aprovado', 'S')).upper() == 'S' and vigente:
            return vm
        melhor = melhor or vm
    return melhor


def main():
    if not EMAIL or not TOKEN:
        aviso('notice', 'CV CRM ainda não configurado',
              'Cadastre os segredos CVCRM_EMAIL e CVCRM_TOKEN no repositório para o robô ler os lotes.')
        return

    unidades, vistos, emp, pagina, paginas = [], set(), None, 1, 1
    while pagina <= paginas and pagina <= 200:
        dados = buscar(pagina)
        emp = emp or dados
        novos = 0
        for etapa in lista(dados.get('etapas')):
            for bloco in lista(etapa.get('blocos')):
                for pg in lista(bloco.get('paginacao')):
                    paginas = max(paginas, int(numero(pg.get('paginas_total'))) or 1)
                for u in lista(bloco.get('unidades')):
                    chave = str(u.get('idunidade') or (bloco.get('nome'), u.get('nome')))
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    novos += 1
                    unidades.append((bloco, u))
        if novos == 0:
            break
        pagina += 1
        time.sleep(0.4)

    vm = tabela_m2(emp or {})
    lotes, contagem, sem_preco, por_m2 = [], {}, 0, 0
    for bloco, u in unidades:
        sit = (lista(u.get('situacao')) or [{}])[0]
        codigo = int(numero(sit.get('situacao_mapa_disponibilidade')))
        nome_sit = sit.get('nome_situacao_mapa_disponibilidade') or str(codigo)
        contagem[nome_sit] = contagem.get(nome_sit, 0) + 1
        if codigo != DISPONIVEL:
            continue
        area = round(numero(u.get('area_privativa')), 2)
        valor = round(numero(u.get('valor')), 2)
        if valor <= 0 and vm > 0 and area > 0:
            valor, por_m2 = round(area * vm, 2), por_m2 + 1
        if valor <= 0:
            sem_preco += 1
            continue
        lotes.append({'quadra': str(bloco.get('nome', '')).strip(), 'lote': str(u.get('nome', '')).strip(),
                      'area': area, 'valor': valor})

    if not unidades:
        aviso('error', 'Nenhum lote retornado', f'O empreendimento {ID_EMP} não trouxe unidades. Confira o ID.')
        sys.exit(1)

    lotes.sort(key=lambda l: (chave_natural(l['quadra']), chave_natural(l['lote'])))
    aviso('notice', 'Leitura do CV concluída',
          f'Empreendimento: {(emp or {}).get("nome", ID_EMP)}. Unidades lidas: {len(unidades)}. '
          f'Situações: {json.dumps(contagem, ensure_ascii=False)}. Disponíveis com preço: {len(lotes)}. '
          f'Preço pelo m² da tabela: {por_m2}. Disponíveis sem preço: {sem_preco}. '
          f'Exemplos: {json.dumps(lotes[:3], ensure_ascii=False)}')

    anterior = None
    if SAIDA.exists():
        try:
            anterior = json.loads(SAIDA.read_text(encoding='utf-8')).get('lotes')
        except (ValueError, OSError):
            anterior = None
    if anterior == lotes:
        print('Lotes sem mudança desde a última leitura.')
        return
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps({
        'empreendimento': (emp or {}).get('nome', ''),
        'atualizado_em': dt.datetime.now(FUSO).isoformat(timespec='minutes'),
        'lotes': lotes,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'data/lotes.json atualizado com {len(lotes)} lotes.')


def chave_natural(s):
    partes, num = [], ''
    for c in s.lower():
        if c.isdigit():
            num += c
        else:
            if num:
                partes.append((0, int(num), ''))
                num = ''
            partes.append((1, 0, c))
    if num:
        partes.append((0, int(num), ''))
    return partes


if __name__ == '__main__':
    main()
