#!/usr/bin/env python3
"""Gera tabela-de-vendas.xlsx, a tabela de vendas do Sweet Village para imprimir.

Lê os lotes disponíveis de data/lotes.json (gerado pelo robô do CV) e as regras do
simulador em src/simulador.html, para que a tabela e o simulador deem os mesmos valores.
Cada lote tem sinal de 5%, incentivo de construção de 2% em dez/29 e a mensal de cada
plano: 12x sem juros, 24x a 220x só com mensais e 220x com 15 anuais, com juros de 0,90%
ao mês pela Tabela Price contados a partir da 1ª mensal. Acima de 24x as parcelas têm
correção pelo IPCA, que a tabela não inclui. Os planos, o sinal da tabela e as regras vêm
das constantes de src/simulador.html, a mesma fonte da aba "Tabela de vendas" do simulador.

As parcelas são fórmulas do Excel. O script grava também o valor já calculado de cada
fórmula, para a planilha aparecer completa em visualizadores de celular que não calculam.
Só regrava o arquivo quando os lotes, os parâmetros ou o mês de referência mudam.
"""
import base64
import datetime as dt
import hashlib
import io
import json
import math
import pathlib
import re
import sys
import zipfile
from decimal import ROUND_HALF_UP, Decimal

from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.packaging.custom import StringProperty
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LOTES = RAIZ / 'data' / 'lotes.json'
FONTE = RAIZ / 'src' / 'simulador.html'
SAIDA = RAIZ / 'tabela-de-vendas.xlsx'
FUSO = dt.timezone(dt.timedelta(hours=-3))
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
         'setembro', 'outubro', 'novembro', 'dezembro']
MES_CURTO = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


NAVY = '1F3A71'
NAVY_CLARO = 'DCE3F0'
VERDE = '1E6B47'
ZEBRA = 'F3F5F9'
CINZA = '5F6A80'
ARIAL = 'Arial'


def regras_do_simulador():
    """Constantes do simulador, para a tabela seguir as mesmas regras."""
    s = FONTE.read_text(encoding='utf-8')

    def num(padrao):
        m = re.search(padrao, s)
        if not m:
            sys.exit(f'Não achei {padrao} em src/simulador.html')
        return float(m.group(1).replace('.', '').replace(',', '.')) if ',' in m.group(1) else float(m.group(1))

    planos = re.search(r'PLANOS_TABELA = \[([\d,\s]+)\]', s)
    if not planos:
        sys.exit('Não achei PLANOS_TABELA em src/simulador.html')
    logos = re.findall(r'<img class="logo-color" src="data:image/png;base64,([^"]+)"', s)
    return {
        'juros': num(r'var JUROS = ([\d.]+)'),
        'inc': num(r'INC_PCT = ([\d.]+)'),
        'sem_juros_ate': int(num(r'CURTO_SEM_JUROS = (\d+)')),
        'curto_max': int(num(r'CURTO_MAX = (\d+)')),
        'sinal_tabela': num(r'var SINAL_TABELA = ([\d.]+)'),
        'planos': [int(x) for x in planos.group(1).replace(' ', '').split(',') if x],
        'plano_anuais': int(num(r'PLANO_ANUAIS_TABELA = (\d+)')),
        'anual': num(r'id="valAnual"[^>]*value="([\d.,]+)"'),
        'n_anuais': int(num(r'id="na"[^>]*value="(\d+)"')),
        'inc_mes': re.search(r"INC_MES = '([^']+)'", s).group(1),
        'logo_sv': logos[0] if logos else None,
        'logo_vpa': logos[1] if len(logos) > 1 else None,
    }


def arred(x):
    """ROUND do Excel: metade para longe do zero, com 2 casas, sobre os 15 dígitos que o Excel considera."""
    return float(Decimal(format(x, '.15g')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def pmt_antecipada(i, n, pv):
    """PMT(i; n; -pv; 0; 1): a 1ª parcela vence no início e sai sem juros, como no CV."""
    if i == 0:
        return pv / n
    return pv * i / ((1 + i) * (1 - (1 + i) ** -n))


def referencia(hoje):
    """Mês da proposta e meses entre a 1ª mensal e a 1ª anual (31/12, como no simulador).

    Sinal à vista no ato, 1ª mensal no mês seguinte. A 1ª anual é dezembro deste ano ou,
    em dezembro, do ano que vem.
    """
    ano_anual = hoje.year + 1 if hoje.month == 12 else hoje.year
    a0 = (ano_anual - hoje.year) * 12 + (12 - hoje.month)   # meses do mês atual até a 1ª anual
    m1 = 1
    return a0 - m1, f'dez/{str(ano_anual)[2:]}', MES_CURTO[(hoje.month) % 12] + '/' + str(hoje.year + (1 if hoje.month == 12 else 0))[2:]


def montar(dados, r, hoje):
    lotes = dados['lotes']
    PLANOS, PLANO_ANUAIS, SINAL_TABELA = r['planos'], r['plano_anuais'], r['sinal_tabela']
    deslocamento, mes_anual, mes_1a_mensal = referencia(hoje)
    i = r['juros']
    fator_anuais = (1 - (1 + i) ** (-12 * r['n_anuais'])) / (1 - (1 + i) ** -12) * (1 + i) ** -deslocamento
    atualizado = dt.datetime.fromisoformat(dados['atualizado_em']) if dados.get('atualizado_em') else None

    wb = Workbook()
    ws = wb.active
    ws.title = 'Tabela de vendas'
    pr = wb.create_sheet('Parâmetros')
    cache = {}   # (aba, célula) -> valor já calculado de cada fórmula
    P = "'Parâmetros'!"

    fino = Side(style='thin', color='C9D1DE')
    forte = Side(style='medium', color=NAVY)
    centro = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # ---------- Parâmetros ----------
    pr['A1'] = 'Parâmetros da tabela de vendas'
    pr['A1'].font = Font(name=ARIAL, size=13, bold=True, color=NAVY)
    pr['A2'] = ('As células em azul são as premissas. As parcelas da tabela recalculam se elas mudarem, mas os títulos não. '
                'O robô gera a tabela de novo quando a lista de lotes do CV muda ou o mês vira.')
    pr['A2'].font = Font(name=ARIAL, size=9, color=CINZA)
    pr['A2'].alignment = Alignment(wrap_text=True, vertical='top')
    pr.merge_cells('A2:D2')
    pr.row_dimensions[2].height = 30
    for c, t in zip('ABCD', ['Premissa', '', 'Valor', 'Origem']):
        pr[f'{c}3'] = t or None
        pr[f'{c}3'].font = Font(name=ARIAL, size=9, bold=True, color='FFFFFF')
        pr[f'{c}3'].fill = PatternFill('solid', fgColor=NAVY)
    linhas = [
        ('Juros ao mês', i, '0.00%', 'Simulador e tabelas do CV (0,90% a.m.)'),
        ('Sinal, em % do valor de venda', SINAL_TABELA, '0%', 'Definido pelo Lucas para a tabela de vendas'),
        ('Incentivo de construção, em % do valor', r['inc'], '0%', f'Simulador e CV: parcela única em {r["inc_mes"]}, dispensada com o habite-se'),
        ('Sem juros até (mensais)', r['sem_juros_ate'], '0', 'Definido pelo Lucas: até 12 mensais sem juros'),
        ('Valor de cada anual (R$)', r['anual'], '#,##0.00', 'Padrão do simulador'),
        ('Número de anuais', r['n_anuais'], '0', 'Padrão do simulador'),
        ('Meses da 1ª mensal até a 1ª anual', deslocamento, '0',
         f'Proposta em {MESES[hoje.month - 1]}: 1ª mensal em {mes_1a_mensal}, 1ª anual em {mes_anual}'),
    ]
    for k, (rot, val, fmt, origem) in enumerate(linhas, start=4):
        pr[f'A{k}'] = rot
        pr[f'C{k}'] = val
        pr[f'C{k}'].number_format = fmt
        pr[f'C{k}'].font = Font(name=ARIAL, size=10, color='0000FF')
        pr[f'D{k}'] = origem
        for c in 'AD':
            pr[f'{c}{k}'].font = Font(name=ARIAL, size=10, color='000000' if c == 'A' else CINZA)
    pr['A11'] = 'Valor presente das anuais, por R$ 1 de anual'
    pr['A11'].font = Font(name=ARIAL, size=10)
    pr['C11'] = '=(1-(1+C4)^(-12*C9))/(1-(1+C4)^(-12))*(1+C4)^(-C10)'
    pr['C11'].number_format = '0.0000'
    pr['C11'].font = Font(name=ARIAL, size=10)
    pr['D11'] = 'Fórmula: anuais a cada 12 meses, descontadas até a 1ª mensal'
    pr['D11'].font = Font(name=ARIAL, size=10, color=CINZA)
    cache[('Parâmetros', 'C11')] = fator_anuais
    pr.column_dimensions['A'].width = 40
    pr.column_dimensions['B'].width = 2
    pr.column_dimensions['C'].width = 14
    pr.column_dimensions['D'].width = 70
    pr.page_setup.orientation = 'landscape'
    pr.page_setup.paperSize = pr.PAPERSIZE_A4
    pr.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    pr.page_setup.fitToWidth = 1
    pr.page_setup.fitToHeight = 1

    # ---------- Cabeçalho ----------
    ncol = 6 + len(PLANOS) + 1                     # A..O
    ultima = get_column_letter(ncol)
    larguras = [8, 6, 9, 13, 11, 12] + [11] * len(PLANOS) + [13]
    for k, w in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(k)].width = w
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 22
    for chave, ancora, larg in (('logo_vpa', 'A1', 329), ('logo_sv', f'{get_column_letter(ncol - 1)}1', 320)):
        if r.get(chave):
            img = XLImage(io.BytesIO(base64.b64decode(r[chave])))
            img.height, img.width = 44, round(44 * larg / 168)
            ws.add_image(img, ancora)
    ws.merge_cells('D1:L1')
    ws['D1'] = 'TABELA DE VENDAS'
    ws['D1'].font = Font(name=ARIAL, size=16, bold=True, color=NAVY)
    ws['D1'].alignment = Alignment(horizontal='center', vertical='bottom')
    ws.merge_cells('D2:L2')
    ws['D2'] = f'Sweet Village, {MESES[hoje.month - 1]} de {hoje.year}'
    ws['D2'].font = Font(name=ARIAL, size=11, color=VERDE, bold=True)
    ws['D2'].alignment = Alignment(horizontal='center', vertical='top')
    ws.merge_cells(f'A3:{ultima}3')
    quando = f'{atualizado:%d/%m/%Y} às {atualizado:%H:%M}' if atualizado else ''
    ws['A3'] = (f'Lotes disponíveis no CV CRM em {quando}. Valores em R$, para propostas de {MESES[hoje.month - 1]} '
                f'de {hoje.year}, com sinal à vista no ato e 1ª mensal em {mes_1a_mensal}.')
    ws['A3'].font = Font(name=ARIAL, size=9, color=CINZA)
    ws['A3'].alignment = Alignment(horizontal='center', vertical='center')

    # Linha 5: grupos; linha 6: colunas
    cab = PatternFill('solid', fgColor=NAVY)
    grupo = PatternFill('solid', fgColor=NAVY_CLARO)
    for col, texto in ((1, 'Quadra'), (2, 'Lote'), (3, 'Área (m²)'), (4, 'Valor de venda'),
                       (5, f'Sinal {SINAL_TABELA:.0%}'), (6, f'Incentivo de construção {r["inc"]:.0%} em {r["inc_mes"]}')):
        L = get_column_letter(col)
        ws.merge_cells(f'{L}5:{L}6')
        ws[f'{L}5'] = texto
    # Grupos: sem juros; com juros (até 24x); com juros e IPCA (acima de 24x)
    def categoria(n):
        return 0 if n <= r['sem_juros_ate'] else 1 if n <= r['curto_max'] else 2
    rotulos = ['Sem juros', 'Com juros', 'Com juros e IPCA, só mensais']
    k = 0
    while k < len(PLANOS):
        j = k
        while j < len(PLANOS) and categoria(PLANOS[j]) == categoria(PLANOS[k]):
            j += 1
        a, b = get_column_letter(7 + k), get_column_letter(6 + j)
        if a != b:
            ws.merge_cells(f'{a}5:{b}5')
        ws[f'{a}5'] = rotulos[categoria(PLANOS[k])]
        k = j
    anual_txt = f'{r["anual"]:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    ws[f'{ultima}5'] = f'Com juros, IPCA e {r["n_anuais"]} anuais de R$ {anual_txt}'
    for k, n in enumerate(PLANOS + [PLANO_ANUAIS], start=7):
        c = ws.cell(row=6, column=k, value=n)
        c.number_format = '0"x"'
    ws.row_dimensions[5].height = 30
    ws.row_dimensions[6].height = 30
    for col in range(1, ncol + 1):
        for row in (5, 6):
            c = ws.cell(row=row, column=col)
            c.alignment = centro
            c.border = Border(left=fino, right=fino, top=fino, bottom=fino)
            if row == 5 and col >= 7:
                c.fill, c.font = grupo, Font(name=ARIAL, size=9, bold=True, color=NAVY)
            else:
                c.fill, c.font = cab, Font(name=ARIAL, size=9 if row == 5 or col < 7 else 11, bold=True, color='FFFFFF')

    # ---------- Lotes ----------
    lin = 7
    quadra_ant = None
    for idx, l in enumerate(lotes):
        V = float(l['valor'])
        s = arred(V * SINAL_TABELA)
        inc = arred(V * r['inc'])
        saldo = V - s - inc
        q = re.sub(r'(?i)^\s*quadra\s*', '', l['quadra']) or l['quadra']
        ws.cell(row=lin, column=1, value=q)
        ws.cell(row=lin, column=2, value=l['lote'])
        ws.cell(row=lin, column=3, value=float(l.get('area') or 0) or None).number_format = '#,##0.00'
        ws.cell(row=lin, column=4, value=V).number_format = '#,##0.00'
        ws.cell(row=lin, column=5, value=f'=ROUND(D{lin}*{P}$C$5,2)')
        ws.cell(row=lin, column=6, value=f'=ROUND(D{lin}*{P}$C$6,2)')
        cache[('Tabela de vendas', f'E{lin}')] = s
        cache[('Tabela de vendas', f'F{lin}')] = inc
        so_curto = bool(l.get('ate24'))
        for k, n in enumerate(PLANOS, start=7):
            L = get_column_letter(k)
            if so_curto and n > r['curto_max']:
                continue
            ws.cell(row=lin, column=k, value=(
                f'=ROUND(IF({L}$6<={P}$C$7,(D{lin}-E{lin}-F{lin})/{L}$6,'
                f'PMT({P}$C$4,{L}$6,-(D{lin}-E{lin}-F{lin}),0,1)),2)'))
            cache[('Tabela de vendas', f'{L}{lin}')] = arred(pmt_antecipada(0 if n <= r['sem_juros_ate'] else i, n, saldo))
        if not so_curto:
            ws.cell(row=lin, column=ncol, value=(
                f'=ROUND(PMT({P}$C$4,{ultima}$6,-(D{lin}-E{lin}-F{lin}-{P}$C$8*{P}$C$11),0,1),2)'))
            cache[('Tabela de vendas', f'{ultima}{lin}')] = arred(pmt_antecipada(i, PLANO_ANUAIS, saldo - r['anual'] * fator_anuais))
        else:
            ws.merge_cells(start_row=lin, start_column=9, end_row=lin, end_column=ncol)
            ws.cell(row=lin, column=9, value=f'Lote vendido só em até {r["curto_max"]}x ou à vista')
        # estilo da linha
        fundo = PatternFill('solid', fgColor=ZEBRA) if idx % 2 else None
        topo = forte if quadra_ant is not None and q != quadra_ant else fino
        for col in range(1, ncol + 1):
            c = ws.cell(row=lin, column=col)
            c.font = Font(name=ARIAL, size=9, bold=col in (1, 2), italic=so_curto and col >= 9,
                          color=CINZA if so_curto and col >= 9 else '000000')
            c.border = Border(left=fino, right=fino, top=topo, bottom=fino)
            if fundo:
                c.fill = fundo
            if col <= 2 or (so_curto and col >= 9):
                c.alignment = Alignment(horizontal='center', vertical='center')
            elif col >= 5:
                c.number_format = '#,##0.00'
        quadra_ant = q
        lin += 1
    fim = lin - 1

    # ---------- Notas ----------
    notas = [
        f'Sinal de {SINAL_TABELA:.0%} do valor de venda, à vista no ato e sem juros. Incentivo de construção de {r["inc"]:.0%} do valor, '
        f'em parcela única em {r["inc_mes"]}, dispensado ao apresentar o habite-se. As mensais quitam o restante.',
        f'Até {r["sem_juros_ate"]} mensais, sem juros. Acima de {r["sem_juros_ate"]} mensais, juros de {i * 100:.2f}% ao mês pela Tabela Price, '
        'contados a partir da 1ª mensal. Nos planos de 24x a 220x as parcelas são só mensais. Na última coluna, '
        f'{r["n_anuais"]} anuais de R$ {r["anual"]:,.2f} a cada 12 meses, a 1ª em {mes_anual}.',
        f'Até {r["curto_max"]}x, as parcelas não têm correção. Acima de {r["curto_max"]}x, as parcelas são corrigidas pelo IPCA, '
        'e os valores da tabela não incluem essa correção.',
        'No simulador, até 24 mensais o sinal padrão é de 10%, e acima de 24 o padrão tem anuais. Para chegar aos valores '
        'desta tabela, use sinal de 5% e, nas colunas só de mensais, zero anuais. A tabela também está na aba "Tabela de vendas" do simulador.',
        'Tabela meramente ilustrativa, sem valor de proposta, oferta ou reserva, que não gera qualquer compromisso da VPA Urbanismo. '
        'Valores e condições sujeitos a alteração sem aviso prévio, à disponibilidade do lote e à aprovação da empresa. '
        'Não inclui ITBI, custos de escritura e registro.',
    ]
    lin = fim + 2
    for t in notas:
        t = t.replace('0.90%', '0,90%')
        t = re.sub(r'R\$ (\d{1,3}(?:,\d{3})*)\.(\d{2})', lambda m: 'R$ ' + m.group(1).replace(',', '.') + ',' + m.group(2), t)
        ws.merge_cells(f'A{lin}:{ultima}{lin}')
        ws[f'A{lin}'] = t
        ws[f'A{lin}'].font = Font(name=ARIAL, size=8.5, color=CINZA)
        ws[f'A{lin}'].alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[lin].height = 24
        lin += 1

    # ---------- Impressão ----------
    ws.freeze_panes = 'C7'
    ws.print_title_rows = '5:6'
    ws.print_area = f'A1:{ultima}{lin - 1}'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 2   # cabe em até duas folhas; com menos lotes, não amplia
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5
    ws.print_options.horizontalCentered = True
    ws.oddFooter.left.text = 'Sweet Village, VPA Urbanismo'
    ws.oddFooter.left.size = 8
    ws.oddFooter.right.text = 'Página &P de &N'
    ws.oddFooter.right.size = 8
    ws.sheet_view.showGridLines = False
    wb.calculation.fullCalcOnLoad = True
    return wb, cache


def gravar_com_valores(wb, cache, destino):
    """Salva e põe em cada fórmula o valor já calculado (<v>), para visualizadores que não calculam."""
    buf = io.BytesIO()
    wb.save(buf)
    nomes = {ws.title: f'xl/worksheets/sheet{k}.xml' for k, ws in enumerate(wb.worksheets, start=1)}
    por_arquivo = {}
    for (aba, ref), v in cache.items():
        por_arquivo.setdefault(nomes[aba], {})[ref] = v
    entrada = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, 'w', zipfile.ZIP_DEFLATED) as z:
        for item in entrada.infolist():
            dados = entrada.read(item.filename)
            if item.filename in por_arquivo:
                xml = dados.decode('utf-8')
                valores = por_arquivo[item.filename]

                def pôr(m):
                    v = valores.get(m.group(2))
                    if v is None:
                        return m.group(0)
                    return f'{m.group(1)}<f>{m.group(3)}</f><v>{repr(float(v))}</v></c>'
                xml, n = re.subn(r'(<c r="([A-Z]+\d+)"[^>]*>)<f>(.*?)</f>(?:<v\s*/>|<v></v>)?</c>', pôr, xml)
                dados = xml.encode('utf-8')
            z.writestr(item, dados)
    destino.write_bytes(saida.getvalue())


def main():
    dados = json.loads(LOTES.read_text(encoding='utf-8'))
    if not dados.get('lotes'):
        print('Sem lotes em data/lotes.json. Tabela não gerada.')
        return
    r = regras_do_simulador()
    hoje = dt.datetime.now(FUSO).date()
    # Assinatura: lotes, regras e mês de referência. Igual à do arquivo atual, nada muda.
    base = json.dumps({'lotes': dados['lotes'], 'atualizado': dados.get('atualizado_em'),
                       'regras': {k: v for k, v in r.items() if not k.startswith('logo')},
                       'mes': f'{hoje:%Y-%m}', 'versao': 2}, sort_keys=True)
    assinatura = hashlib.sha256(base.encode()).hexdigest()[:16]
    if SAIDA.exists():
        try:
            atual = {p.name: p.value for p in load_workbook(SAIDA, read_only=True).custom_doc_props.props}
            if atual.get('assinatura') == assinatura:
                print('Tabela de vendas sem mudança.')
                return
        except Exception:
            pass
    wb, cache = montar(dados, r, hoje)
    wb.custom_doc_props.append(StringProperty(name='assinatura', value=assinatura))
    gravar_com_valores(wb, cache, SAIDA)
    n = len(dados['lotes'])
    print(f'tabela-de-vendas.xlsx gerada com {n} lotes ({sum(1 for l in dados["lotes"] if l.get("ate24"))} só até 24x).')


if __name__ == '__main__':
    main()
