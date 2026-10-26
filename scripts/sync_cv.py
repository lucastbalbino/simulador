#!/usr/bin/env python3
"""Lê os lotes do Sweet Village no CV CRM e gera data/lotes.json para o simulador.

Roda no GitHub Actions. O e-mail e o token ficam nos segredos do repositório
(CVCRM_EMAIL e CVCRM_TOKEN) e nunca vão para o arquivo publicado. O arquivo
gerado tem só quadra, lote, área e valor total dos lotes disponíveis, lidos da
tabela de preço aprovada e vigente do empreendimento.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SAIDA = RAIZ / 'data' / 'lotes.json'

EMAIL = os.environ.get('CVCRM_EMAIL', '').strip()
TOKEN = os.environ.get('CVCRM_TOKEN', '').strip()
DOMINIO = os.environ.get('CVCRM_DOMINIO', 'vpa').strip()
ID_EMP = os.environ.get('CVCRM_ID_EMPREENDIMENTO', '4').strip()
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


def buscar(caminho):
    base = os.environ.get('CVCRM_BASE_URL') or f'https://{DOMINIO}.cvcrm.com.br'  # BASE_URL só para testes
    req = urllib.request.Request(f'{base}/api{caminho}', headers={'email': EMAIL, 'token': TOKEN, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode('utf-8', 'replace')[:300]
        causas = {
            401: 'E-mail ou token incorretos ou vencidos. Confira os segredos CVCRM_EMAIL e CVCRM_TOKEN.',
            403: 'O usuário de integração não tem permissão para ler empreendimentos ou tabelas de preço na API.',
            404: f'Endereço não encontrado. Confira o subdomínio "{DOMINIO}" e o ID {ID_EMP} do empreendimento.',
            429: 'Limite de requisições do CV atingido. A próxima execução tenta de novo.',
        }
        aviso('error', f'CV CRM respondeu {e.code}', causas.get(e.code, corpo))
        sys.exit(1)
    except urllib.error.URLError as e:
        aviso('error', 'Sem conexão com o CV CRM', f'{DOMINIO}.cvcrm.com.br: {e.reason}')
        sys.exit(1)


def escolher_tabela(emp):
    """Tabela aprovada e vigente do empreendimento; prefere a de 220 parcelas se houver mais de uma."""
    fixa = os.environ.get('CVCRM_ID_TABELA', '').strip()
    tabelas = [t for t in lista(emp.get('tabela')) if isinstance(t, dict) and t.get('idtabela')]
    if fixa:
        return next((t for t in tabelas if str(t.get('idtabela')) == fixa), {'idtabela': fixa, 'nome': f'Tabela {fixa}'}), True
    hoje = dt.date.today().isoformat()

    def vigente(t):
        de, ate = (t.get('data_vigencia_de') or '')[:10], (t.get('data_vigencia_ate') or '')[:10]
        return (not de or de <= hoje) and (not ate or hoje <= ate)

    aprovadas = [t for t in tabelas if str(t.get('aprovado', 'S')).upper() == 'S']
    vigentes = [t for t in aprovadas if vigente(t)]
    for grupo, eh_vigente in ((vigentes, True), (aprovadas, False)):
        if grupo:
            grupo = sorted(grupo, key=lambda t: ('220' not in str(t.get('nome', '')), str(t.get('data_vigencia_de') or '')), reverse=False)
            return grupo[0], eh_vigente
    return None, False


def main():
    if not EMAIL or not TOKEN:
        aviso('notice', 'CV CRM ainda não configurado',
              'Cadastre os segredos CVCRM_EMAIL e CVCRM_TOKEN no repositório para o robô ler os lotes.')
        return

    # 1. Empreendimento: nome e tabela de preço atual
    emp = buscar(f'/v1/cadastros/empreendimentos/{ID_EMP}?limite_dados_unidade=1&pagina_unidade=1')
    tabela, vigente = escolher_tabela(emp)
    if not tabela:
        aviso('error', 'Nenhuma tabela de preço aprovada', 'O CV não retornou tabela aprovada para o empreendimento. A lista publicada foi mantida.')
        sys.exit(1)
    if not vigente:
        aviso('warning', 'Tabela fora da vigência', f'Usando "{tabela.get("nome")}", que não está vigente hoje. Confira a tabela no CV.')

    # 2. Tabela de preço com todos os lotes: quadra, lote, área, situação e valor total
    idt = str(tabela.get('idtabela'))
    dados = buscar(f'/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/{idt}?tabelasemjson=true')
    dados = (lista(dados) or [{}])[0]
    unidades = lista(dados.get('unidades'))
    if not unidades:
        aviso('error', 'Tabela sem lotes', f'A tabela {idt} não trouxe unidades. A lista publicada foi mantida.')
        sys.exit(1)

    lotes, contagem, sem_preco = [], {}, 0
    for u in unidades:
        sit = str(u.get('situacao') or '').strip()
        contagem[sit] = contagem.get(sit, 0) + 1
        if not sit.lower().startswith('dispon'):
            continue
        valor = round(numero(u.get('valor_total')), 2)
        if valor <= 0:
            sem_preco += 1
            continue
        lotes.append({
            'quadra': str(u.get('bloco') or '').strip().title(),
            'lote': str(u.get('unidade') or '').strip(),
            'area': round(numero(u.get('area_privativa')), 2),
            'valor': valor,
        })

    lotes.sort(key=lambda l: (chave_natural(l['quadra']), chave_natural(l['lote'])))
    nome_tab = dados.get('tabela') or tabela.get('nome') or idt
    aviso('notice', 'Leitura do CV concluída',
          f'Empreendimento: {emp.get("nome", ID_EMP)}. Tabela: {nome_tab} (id {idt}, vigência '
          f'{tabela.get("data_vigencia_de", "")} a {tabela.get("data_vigencia_ate", "")}). Lotes na tabela: {len(unidades)}. '
          f'Situações: {json.dumps(contagem, ensure_ascii=False)}. Disponíveis publicados: {len(lotes)}. '
          f'Disponíveis sem preço: {sem_preco}. Exemplos: {json.dumps(lotes[:3], ensure_ascii=False)}')

    anterior = None
    if SAIDA.exists():
        try:
            anterior = json.loads(SAIDA.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            anterior = None
    if anterior and anterior.get('lotes') == lotes and anterior.get('tabela') == nome_tab:
        print('Lotes sem mudança desde a última leitura.')
        return
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps({
        'empreendimento': emp.get('nome', ''),
        'tabela': nome_tab,
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
