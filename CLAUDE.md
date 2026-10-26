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
6. O aviso legal ("Simulação meramente ilustrativa... não gera qualquer compromisso da VPA Urbanismo") aparece no rodapé, na imagem baixada e no resumo copiado.
7. O botão "Baixar imagem" gera um PNG da ficha da simulação (desenhado em canvas). Dentro do claude.ai, a imagem usa a capability `downloads`; no site, baixa direto. O código decide pela presença de `window.claude`.
8. Com o computador, a página precisa caber numa tela só (cerca de 620 px de altura). No celular, os campos ficam em duas colunas.
9. Datas e prazos aparecem só no sinal. Mensais e anuais mostram apenas a quantidade e o valor, no painel, na imagem e no resumo.
10. A taxa de juros não aparece como linha na imagem. Ela fica no texto legal: "As parcelas mensais e anuais já incluem juros de 0,90% ao mês pela Tabela Price, contados a partir da última parcela do sinal."
11. Textos em português, sem travessões nem hífens como recurso de formatação.
12. Ao escolher quadra e lote, o valor de venda é preenchido com o valor da tabela do CV e fica travado. O lote escolhido aparece no painel, na imagem e no resumo.

## Integração com o CV CRM

1. `scripts/sync_cv.py` lê o Sweet Village em `https://vpa.cvcrm.com.br/api/v1/cadastros/empreendimentos/4` (headers `email` e `token`, vindos dos segredos `CVCRM_EMAIL` e `CVCRM_TOKEN`) para descobrir a tabela de preço aprovada e vigente (hoje a 45, "Sweet Village Macaé 220X com 15 ANUAIS"). Depois lê `/v1/cadastros/empreendimentos/4/tabelasdepreco/{idtabela}?tabelasemjson=true`, que traz todos os lotes com bloco (quadra), unidade (lote), área, situação e `valor_total`. Grava em `data/lotes.json` só os lotes com situação "Disponível". O preço não vem no cadastro do lote (o campo `valor` da unidade é zero). Para fixar outra tabela, defina `CVCRM_ID_TABELA` no workflow.
   Nas séries da tabela do CV, a mensal aparece sem juros (os 0,90% entram como "juros futuro"), e a anual base é 1% do valor. O simulador aplica a Tabela Price sobre o saldo, por isso a mensal dele é maior que a mensal da tabela do CV.
2. `.github/workflows/atualizar-lotes.yml` roda de hora em hora e também pelo botão Run workflow. Só faz commit quando a lista de lotes muda.
3. Erros e o resumo de cada leitura aparecem como anotações da execução (o script imprime `::error` e `::notice`).
4. O site lê `data/lotes.json`. Sem esse arquivo, e sempre no artefato do claude.ai (que não lê arquivos de fora), os campos de quadra e lote ficam escondidos e o valor de venda é digitado.
5. Nunca coloque o token em código ou em arquivo do repositório, e nunca grave lotes fictícios em `data/lotes.json`, porque o repositório e o site são públicos.
