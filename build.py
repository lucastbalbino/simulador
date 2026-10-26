#!/usr/bin/env python3
"""Gera index.html (site no GitHub Pages) a partir de src/simulador.html (fonte do artefato no claude.ai)."""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent

CABECALHO = '''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Simulador Sweet Village</title>
<meta name="description" content="Simule as condições de pagamento do seu lote no Sweet Village, da VPA Urbanismo.">
<style>
:root { color-scheme: light; padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
body { margin: 0; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
'''


def main():
    fonte = (RAIZ / 'src' / 'simulador.html').read_text(encoding='utf-8')
    # O <title> e a meta "claude:" valem só para o artefato; o site usa o cabeçalho acima
    fonte = re.sub(r'\A\s*<title>.*?</title>[ \t]*\n', '', fonte, count=1, flags=re.S)
    fonte = re.sub(r'\A\s*<meta name="claude:[^>]*>[ \t]*\n', '', fonte, count=1)
    fim = fonte.index('</style>') + len('</style>')
    estilos, corpo = fonte[:fim], fonte[fim:]
    saida = CABECALHO + estilos + '\n</head>\n<body>' + corpo + '\n</body>\n</html>\n'
    (RAIZ / 'index.html').write_text(saida, encoding='utf-8')
    print(f'index.html gerado ({len(saida.encode())} bytes)')


if __name__ == '__main__':
    main()
