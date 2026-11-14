#!/usr/bin/env python3
"""Gera as duas páginas do simulador a partir de src/simulador.html.

index.html            site no GitHub Pages (título "Simulador Sweet Village")
.artefato/index.html  artefato do claude.ai (título "Simulador Tabela Price"), fora do git
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent

BASE = '''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{extra}<style>
:root {{ color-scheme: light; padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }}
body {{ margin: 0; }}
img {{ max-width: 100%; }}
[hidden] {{ display: none !important; }}
</style>
'''

SITE = ('<title>Simulador Sweet Village</title>\n'
        '<meta name="description" content="Simule as condições de pagamento do seu lote no Sweet Village, da VPA Urbanismo.">\n')


def montar(fonte, extra):
    fim = fonte.index('</style>') + len('</style>')
    estilos, corpo = fonte[:fim], fonte[fim:]
    return BASE.format(extra=extra) + estilos + '\n</head>\n<body>' + corpo + '\n</body>\n</html>\n'


def main():
    fonte = (RAIZ / 'src' / 'simulador.html').read_text(encoding='utf-8')
    titulo = re.match(r'\A\s*(<title>.*?</title>)[ \t]*\n', fonte, flags=re.S)
    meta = re.search(r'^(<meta name="claude:[^>]*>)[ \t]*\n', fonte, flags=re.M)
    # O <title> e a meta "claude:" da fonte valem só para o artefato; o site usa o cabeçalho SITE
    corpo = re.sub(r'\A\s*<title>.*?</title>[ \t]*\n', '', fonte, count=1, flags=re.S)
    corpo = re.sub(r'\A\s*<meta name="claude:[^>]*>[ \t]*\n', '', corpo, count=1)

    site = montar(corpo, SITE)
    (RAIZ / 'index.html').write_text(site, encoding='utf-8')
    print(f'index.html gerado ({len(site.encode())} bytes)')

    extra = ''.join(x.group(1) + '\n' for x in (titulo, meta) if x)
    artefato = montar(corpo, extra)
    pasta = RAIZ / '.artefato'
    pasta.mkdir(exist_ok=True)
    (pasta / 'index.html').write_text(artefato, encoding='utf-8')
    print(f'.artefato/index.html gerado ({len(artefato.encode())} bytes)')


if __name__ == '__main__':
    main()
