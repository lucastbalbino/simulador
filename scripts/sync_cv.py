#!/usr/bin/env python3
"""Lê os lotes do Sweet Village no CV CRM e gera data/lotes.json para o simulador.

Roda no GitHub Actions. O e-mail e o token ficam nos segredos do repositório
(CVCRM_EMAIL e CVCRM_TOKEN) e nunca vão para o arquivo publicado. O arquivo
gerado tem só quadra, lote, área e valor total dos lotes disponíveis, lidos da
tabela de 220x aprovada e vigente. Lotes que só estão na tabela de 24x entram
com "ate24": true, porque não são vendidos em mais de 24 mensais.
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


def normalizar(txt):
    import unicodedata
    txt = unicodedata.normalize('NFKD', str(txt or '')).encode('ascii', 'ignore').decode()
    return ' '.join(txt.lower().split())


def detalhe(idt):
    dados = buscar(f'/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/{idt}?tabelasemjson=true')
    return (lista(dados) or [{}])[0]


def ainda_vale(d):
    """A tabela continua aprovada e dentro da vigência, quando o CV informa esses campos."""
    aprovado = d.get('aprovado')
    if aprovado is not None and str(aprovado).strip().upper() not in ('S', 'SIM', 'TRUE', '1'):
        return False
    hoje = dt.date.today().isoformat()
    de, ate = str(d.get('data_vigencia_de') or '')[:10], str(d.get('data_vigencia_ate') or '')[:10]
    return (not de or de <= hoje) and (not ate or hoje <= ate)


def consultar(ids):
    """Só leitura: resume tabelas de preço pelo id, sem gravar nada. Usado pelo campo consultar do Run workflow."""
    base = os.environ.get('CVCRM_BASE_URL') or f'https://{DOMINIO}.cvcrm.com.br'
    alvos = [('QUADRA 04', '16'), ('QUADRA 04', '10'), ('QUADRA 01', '2')]
    for idt in ids:
        url = f'{base}/api/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/{idt}?tabelasemjson=true'
        req = urllib.request.Request(url, headers={'email': EMAIL, 'token': TOKEN, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = (lista(json.loads(r.read().decode('utf-8'))) or [{}])[0]
        except urllib.error.HTTPError as e:
            aviso('notice', f'Consulta tabela {idt}', f'CV respondeu {e.code}')
            continue
        unidades = lista(d.get('unidades'))
        cab = {k: v for k, v in d.items() if not isinstance(v, (list, dict))}
        exemplos = []
        for q, l in alvos:
            u = next((x for x in unidades if str(x.get('bloco') or '').strip().upper() == q and str(x.get('unidade') or '').strip() == l), None)
            if u:
                exemplos.append({'quadra': q, 'lote': l, 'situacao': u.get('situacao'), 'valor_total': u.get('valor_total'), 'series': u.get('series')})
        sit = {}
        for x in unidades:
            k = str(x.get('situacao') or '')
            sit[k] = sit.get(k, 0) + 1
        aviso('notice', f'Consulta tabela {idt}', json.dumps({'cabecalho': cab, 'situacoes': sit, 'exemplos': exemplos}, ensure_ascii=False)[:3800])


def detalhe_seguro(idt):
    """Tabela de preço pelo id, ou None quando o id não existe ou é de outro empreendimento."""
    base = os.environ.get('CVCRM_BASE_URL') or f'https://{DOMINIO}.cvcrm.com.br'
    url = f'{base}/api/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/{idt}?tabelasemjson=true'
    req = urllib.request.Request(url, headers={'email': EMAIL, 'token': TOKEN, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = (lista(json.loads(r.read().decode('utf-8'))) or [{}])[0]
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429):
            buscar(f'/v1/cadastros/empreendimentos/{ID_EMP}/tabelasdepreco/{idt}?tabelasemjson=true')  # mostra o erro e encerra
        return None
    except urllib.error.URLError as e:
        aviso('error', 'Sem conexão com o CV CRM', f'{DOMINIO}.cvcrm.com.br: {e.reason}')
        sys.exit(1)
    if not isinstance(d, dict) or not d.get('tabela') or str(d.get('idempreendimento') or ID_EMP) != ID_EMP:
        return None
    return d


def descobrir(emp, anterior):
    """Tabelas de preço do empreendimento.

    O CV lista no cadastro do empreendimento só a tabela mais recente. Para achar as outras
    (220x, 24x, 12x, à vista), o robô lê os ids próximos dos que já conhece. Ids de outros
    empreendimentos voltam vazios e são ignorados.
    """
    ids = set()
    for t in lista(emp.get('tabela')):
        if isinstance(t, dict) and str(t.get('idtabela') or '').isdigit():
            ids.add(int(t['idtabela']))
    for k in ('idtabela', 'idtabela_curta'):
        v = str((anterior or {}).get(k) or '')
        if v.isdigit():
            ids.add(int(v))
    if not ids:
        return []
    topo = max(ids)
    tabelas = [d for d in (detalhe_seguro(i) for i in range(topo + 4, max(0, topo - 16), -1)) if d]
    aviso('notice', 'Tabelas do Sweet Village no CV', json.dumps([
        {'idtabela': d.get('idtabela'), 'nome': d.get('tabela'), 'aprovado': d.get('aprovado'),
         'vigencia': f"{d.get('data_vigencia_de') or ''} a {d.get('data_vigencia_ate') or ''}", 'vale_hoje': ainda_vale(d)}
        for d in tabelas], ensure_ascii=False))
    return tabelas


def escolher(tabelas, variavel, eh_do_tipo, nome_tipo):
    """A tabela aprovada e vigente de um tipo. Termos em `variavel` (separados por ponto e vírgula)
    dão preferência por nome; sem eles, ou sem tabela que os tenha, vale a de maior id do tipo."""
    validas = [d for d in tabelas if ainda_vale(d)]
    termos = [normalizar(x) for x in os.environ.get(variavel, '').split(';') if x.strip()]
    if termos:
        casa = [d for d in validas if all(x in normalizar(d.get('tabela')) for x in termos)]
        if casa:
            return max(casa, key=lambda d: int(d.get('idtabela') or 0))
        aviso('warning', f'Tabela de {nome_tipo} preferida indisponível',
              f'Nenhuma tabela aprovada e vigente com "{" e ".join(termos)}" no nome. Usando a escolha automática.')
    tipo = [d for d in validas if eh_do_tipo(d)]
    if not tipo:
        return None
    return max(tipo, key=lambda d: ('anua' in normalizar(d.get('tabela')), int(d.get('idtabela') or 0)))


def eh_longa(d):
    n = normalizar(d.get('tabela'))
    return '220' in n and 'vista' not in n


def eh_curta(d):
    n = normalizar(d.get('tabela'))
    return ('24x' in n or str(d.get('plano_parcelamento') or '') == '24') and 'vista' not in n


def lotes_da(d):
    """Lotes disponíveis com preço, por (quadra, lote), e a contagem de situações."""
    lotes, situacoes, sem_preco = {}, {}, 0
    for u in lista(d.get('unidades')):
        sit = str(u.get('situacao') or '').strip()
        situacoes[sit] = situacoes.get(sit, 0) + 1
        if not sit.lower().startswith('dispon'):
            continue
        valor = round(numero(u.get('valor_total')), 2)
        if valor <= 0:
            sem_preco += 1
            continue
        lote = {
            'quadra': str(u.get('bloco') or '').strip().title(),
            'lote': str(u.get('unidade') or '').strip(),
            'area': round(numero(u.get('area_privativa')), 2),
            'valor': valor,
        }
        lotes[(lote['quadra'], lote['lote'])] = lote
    return lotes, situacoes, sem_preco


def exemplo_series(d):
    u = next((x for x in lista(d.get('unidades')) if str(x.get('situacao') or '').lower().startswith('dispon')), None)
    if not u:
        return None
    return {'tabela': d.get('tabela'), 'quadra': u.get('bloco'), 'lote': u.get('unidade'),
            'valor_total': u.get('valor_total'), 'series': u.get('series')}


def main():
    if os.environ.get('CVCRM_CONSULTAR', '').strip():
        consultar([x.strip() for x in os.environ['CVCRM_CONSULTAR'].split(',') if x.strip()])
        return
    if not EMAIL or not TOKEN:
        aviso('notice', 'CV CRM ainda não configurado',
              'Cadastre os segredos CVCRM_EMAIL e CVCRM_TOKEN no repositório para o robô ler os lotes.')
        return

    anterior = None
    if SAIDA.exists():
        try:
            anterior = json.loads(SAIDA.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            anterior = None

    emp = buscar(f'/v1/cadastros/empreendimentos/{ID_EMP}?limite_dados_unidade=1&pagina_unidade=1')
    tabelas = descobrir(emp, anterior)

    # Tabela longa (220 mensais com anuais): dá os preços e os lotes do simulador
    fixa = os.environ.get('CVCRM_ID_TABELA', '').strip()
    longa = detalhe_seguro(fixa) if fixa else escolher(tabelas, 'CVCRM_TABELA_PREFERIDA', eh_longa, '220x')
    if not longa:
        aviso('error', 'Nenhuma tabela de 220x aprovada e vigente',
              'O CV não tem tabela de 220x aprovada e vigente para o Sweet Village. A lista publicada foi mantida.')
        sys.exit(1)
    # Tabela curta (24x): lotes que só estão nela entram no simulador limitados a 24 mensais
    curta = escolher(tabelas, 'CVCRM_TABELA_CURTA', eh_curta, '24x')

    lotes_l, situacoes, sem_preco = lotes_da(longa)
    if not lista(longa.get('unidades')):
        aviso('error', 'Tabela sem lotes', f'A tabela {longa.get("idtabela")} não trouxe unidades. A lista publicada foi mantida.')
        sys.exit(1)
    lotes_c = lotes_da(curta)[0] if curta else {}
    so_curta = [dict(v, ate24=True) for k, v in lotes_c.items() if k not in lotes_l]
    lotes = list(lotes_l.values()) + so_curta
    lotes.sort(key=lambda l: (chave_natural(l['quadra']), chave_natural(l['lote'])))

    aviso('notice', 'Séries das tabelas (exemplo)', json.dumps(
        [x for x in (exemplo_series(longa), exemplo_series(curta) if curta else None) if x], ensure_ascii=False)[:3800])
    idl, nome_l = str(longa.get('idtabela')), longa.get('tabela')
    idc, nome_c = (str(curta.get('idtabela')), curta.get('tabela')) if curta else ('', '')
    aviso('notice', 'Leitura do CV concluída',
          f'Tabela de 220x: {nome_l} (id {idl}, vigência {longa.get("data_vigencia_de", "")} a {longa.get("data_vigencia_ate", "")}). '
          f'Tabela de 24x: {nome_c or "nenhuma"}{f" (id {idc})" if idc else ""}. '
          f'Situações na de 220x: {json.dumps(situacoes, ensure_ascii=False)}. Disponíveis sem preço: {sem_preco}. '
          f'Lotes publicados: {len(lotes)}, dos quais {len(so_curta)} só nas tabelas curtas (até 24x): '
          f'{", ".join(l["quadra"] + " L" + l["lote"] for l in so_curta) or "nenhum"}.')

    if (anterior and anterior.get('lotes') == lotes and anterior.get('tabela') == nome_l
            and str(anterior.get('idtabela') or '') == idl and str(anterior.get('idtabela_curta') or '') == idc):
        print('Lotes sem mudança desde a última leitura.')
        return
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps({
        'empreendimento': emp.get('nome', ''),
        'tabela': nome_l,
        'idtabela': int(idl) if idl.isdigit() else idl,
        'tabela_curta': nome_c,
        'idtabela_curta': int(idc) if idc.isdigit() else idc,
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
