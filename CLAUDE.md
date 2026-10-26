# Simulador Sweet Village

Simulador de proposta do Sweet Village (VPA Urbanismo) pela Tabela Price. Ele existe em dois lugares, gerados da mesma fonte:

1. **Artefato no claude.ai**, título "Simulador Tabela Price", usado internamente pelos corretores. Se o link não for informado na conversa, encontre o artefato pela ação `list` do Artifact.
2. **Site no GitHub Pages** (https://lucastbalbino.github.io/simulador/), servido a partir de `index.html` na branch `main`.

Sempre publique nos dois lugares juntos.

## Arquivos

1. `src/simulador.html`: fonte única, no formato de página do artefato (sem doctype, head ou body).
2. `build.py`: gera `index.html` a partir da fonte, com o cabeçalho HTML completo do site.
3. `index.html`: arquivo gerado. Não edite à mão.

## Como publicar um ajuste

1. Edite `src/simulador.html`.
2. Rode `python3 build.py`.
3. Republique o artefato com a ferramenta Artifact usando `src/simulador.html` e o `url` do artefato (leia o artefato antes com `action: "read"`). Omita `capabilities` no redeploy para manter a `downloads` já declarada.
4. Faça commit e push na `main`. O Pages atualiza em um ou dois minutos.

## Regras do simulador

1. Juros fixos de 0,90% a.m., com o campo travado e sem equivalência anual na tela.
2. Sinal em até 3x sem juros. Padrão: 1x e 10% do valor de venda, acompanhando o valor de venda até o corretor digitar outro sinal.
3. As mensais começam no mês seguinte à última parcela do sinal, e os juros do saldo contam a partir dessa mesma parcela.
4. Valor da mensal e valor da anual ficam abertos: o corretor digita um e o outro é calculado para quitar o saldo.
5. Padrões: venda de R$ 179.900,00; 220 mensais; 15 anuais de R$ 2.990,00; 1ª anual no mês 12.
6. O aviso legal ("Simulação meramente ilustrativa... não gera qualquer compromisso da VPA Urbanismo") aparece no rodapé, no PDF e no resumo copiado.
7. Dentro do claude.ai, o PDF usa a capability `downloads`. No site, o PDF baixa direto. O código decide pela presença de `window.claude`.
8. Com o computador, a página precisa caber numa tela só (cerca de 620 px de altura). No celular, os campos ficam em duas colunas.
9. Textos em português, sem travessões nem hífens como recurso de formatação.
