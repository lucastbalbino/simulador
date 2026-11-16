# Simulador Sweet Village

Simulador de proposta do Sweet Village (VPA Urbanismo) pela Tabela Price. Ele existe em dois lugares, gerados da mesma fonte:

1. **Artefato no claude.ai**, título "Simulador Tabela Price", usado internamente pelos corretores. Se o link não for informado na conversa, encontre o artefato pela ação `list` do Artifact.
2. **Site no GitHub Pages** (https://lucastbalbino.github.io/simulador/), servido a partir de `index.html` na branch `main`.

Sempre publique nos dois lugares juntos.

## Arquivos

1. `src/simulador.html`: fonte única, sem doctype, head ou body.
2. `build.py`: gera `index.html` (site, título "Simulador Sweet Village") e `.artefato/index.html` (artefato, título "Simulador Tabela Price"), cada um com o cabeçalho HTML completo. A pasta `.artefato/` fica fora do git.
3. `index.html`: arquivo gerado. Não edite à mão.
4. `scripts/tabela_vendas.py`: gera `tabela-de-vendas.xlsx`, a tabela de vendas para imprimir, servida em https://lucastbalbino.github.io/simulador/tabela-de-vendas.xlsx. Ver "Tabela de vendas" abaixo.

## Como publicar um ajuste

1. Edite `src/simulador.html`.
2. Rode `python3 build.py`.
3. Republique o artefato (slug `8c1348af-9be3-469d-9565-e9c90961a178`, link https://claude.ai/artifact/JJESWkgnCW2sntTf2A77Xu). Pegue a versão atual com `get_artifact` e publique com `publish_files`, enviando `.artefato/index.html` como `index.html` e `data/lotes.json` como `data/lotes.json` (o artefato não aceita arquivos .xlsx), com `base_version`, `shared_live: "public"` e `artifact_title: "Simulador Tabela Price"` (o artefato está compartilhado com link público). A capability `downloads` já declarada continua. Se só houver a ferramenta antiga `Artifact`, publique `src/simulador.html` com o `url` e `files: {"data/lotes.json": "data/lotes.json"}`, sem `capabilities`.
4. Faça commit e push na `main`. O Pages atualiza em um ou dois minutos.

## Regras do simulador

1. Juros fixos de 0,90% a.m. (constante `JUROS` no código) nos planos com juros, sem campo no formulário e sem equivalência anual. A taxa aparece no painel azul e no texto legal.
2. Sinal sem juros, em até 3x sem aprovação (constante `NS_LIVRE`). Pedido do Lucas em 16/11/2026: o campo "Sinal dividido em" é um número que vai até 12x (`NS_MAX`); acima de 3x o campo fica em destaque de alerta e a dica diz "Mais de 3x. Somente após aprovação da diretoria.", e a imagem e o resumo levam o mesmo aviso. Padrão: 1x e 5% do valor de venda (constante `SINAL_PCT`) acima de 24 mensais e 10% (`SINAL_PCT_CURTO`) até 24 mensais, acompanhando o valor de venda e o plano até o corretor digitar outro sinal.
3. As mensais começam no mês seguinte à última parcela do sinal. Igual ao CV, os juros contam a partir da 1ª mensal, que sai sem juros, e cada parcela é contada em meses cheios de calendário a partir dela.
4. Acima de 24 mensais, valor da mensal e valor da anual ficam abertos: o corretor digita um e o outro é calculado para quitar o saldo. Até 24 mensais não há anuais e a mensal é sempre calculada.
5. Padrões: venda de R$ 179.900,00; sinal de 5%; 220 mensais; 15 anuais de R$ 2.990,00; 1ª anual em 31/12 do ano corrente (31/12/2026 hoje). Em dezembro o padrão passa a 31/12 do ano seguinte, porque a 1ª anual precisa vencer depois do mês do sinal.
6. O aviso legal ("Simulação meramente ilustrativa... não gera qualquer compromisso da VPA Urbanismo") aparece no rodapé, na imagem baixada e no resumo copiado.
7. O botão "Baixar imagem" gera um PNG da ficha da simulação (desenhado em canvas). Dentro do claude.ai, a imagem usa a capability `downloads`; no site, baixa direto. O código decide pela presença de `window.claude`.
8. Com o computador, a página precisa caber numa tela só (cerca de 620 px de altura). No celular, os campos ficam em duas colunas.
9. Datas e prazos aparecem só no sinal e no incentivo de construção (dez/29). Mensais e anuais mostram apenas a quantidade e o valor, no painel, na imagem e no resumo.
10. A taxa de juros não aparece como linha na imagem. Ela fica no texto legal: "As parcelas mensais e anuais já incluem juros de 0,90% ao mês pela Tabela Price, contados a partir da 1ª parcela mensal."
11. Textos em português, sem travessões nem hífens como recurso de formatação.
12. Ao escolher quadra e lote, o valor de venda é preenchido com o valor da tabela do CV, e a dica diz "Valor da tabela do CV". Pedido do Lucas em 16/11/2026: o campo continua editável para o corretor simular um desconto. Abaixo da tabela, o campo fica em destaque de alerta e a dica diz "Desconto de X%. Somente após aprovação da diretoria."; a imagem e o resumo mostram o valor de tabela e o desconto com o mesmo aviso. Acima da tabela, a dica mostra o valor do CV, sem alerta. O lote escolhido aparece no painel, na imagem e no resumo. Quadra e lote têm destaque em verde (rótulo e borda), por serem os campos principais.
13. Não há campo de data da proposta: ela é sempre datada de hoje, e os vencimentos partem da data atual.
14. A 1ª anual é uma data escolhida pelo corretor (campo "Data da 1ª anual"); as demais vêm a cada 12 meses. No cálculo vale só o mês da data: cada anual é contada em meses cheios a partir do mês da 1ª mensal, como no CV. A 1ª anual precisa vencer depois do mês da última parcela do sinal.
15. Incentivo de construção (nome da série no CV): parcela única de 2% do valor de venda em dez/2029 (constantes `INC_PCT` e `INC_MES`), dispensada ao apresentar o habite-se. Como no CV, ela sai do saldo pelo valor cheio e as mensais e anuais quitam o restante. Aparece no painel azul, na imagem e no resumo. Pedido do Lucas em 16/11/2026: no formulário o corretor escolhe "Com" (padrão) ou "Sem" incentivo, porque em alguns casos não há incentivo. Sem incentivo, o painel mostra "Sem incentivo", a parcela sai da imagem e do resumo, e as mensais e anuais quitam o valor todo. A aba e a planilha da tabela de vendas sempre incluem o incentivo.
16. Planos curtos, iguais às tabelas de 12x e 24x do CV: de 1 a 12 mensais, sem juros (constante `CURTO_SEM_JUROS`); de 13 a 24 mensais, com juros de 0,90% a.m. pela mesma convenção do plano longo (constante `CURTO_MAX`). Nos dois não há anuais (os campos ficam travados, com a dica "Sem anuais em até 24x"), o sinal padrão é 10% e o incentivo de construção continua, como no CV. O texto legal, o resumo, o painel e a imagem dizem "sem juros" quando é o caso. A tabela de 12x do CV tem sinal mais 11 mensais. Conferido em 14/11/2026: Quadra 04, Lote 16, R$ 164.990,00, sinal de 10%, 11 mensais sem juros dá R$ 13.199,20, igual ao CV.
17. Correção (informação do Lucas em 14/11/2026): até 24 mensais as parcelas não têm correção; acima de 24 mensais, as mensais e anuais são corrigidas pelo IPCA, além dos juros. O simulador não calcula o IPCA: os valores são os de hoje, e o painel ("com juros de 0,90% ao mês e correção pelo IPCA"), o texto legal, o resumo, o rodapé e a tabela de vendas avisam que a correção não está incluída.
18. Aba "Tabela de vendas" (endereço `#tabela`; o simulador é `#simulador`), com as abas no lugar do subtítulo do cabeçalho. Mostra todos os lotes de `data/lotes.json` com sinal de `SINAL_TABELA` (5%), incentivo de construção e a mensal de cada plano de `PLANOS_TABELA` (12, 24, 48, 82, 130, 162, 200 e 220) e de `PLANO_ANUAIS_TABELA` (220) com as anuais padrão, calculados pela mesma função `calc` do simulador. Tem filtro por quadra, e tocar no número do lote abre a simulação dele. "Imprimir" aparece só no site (o claude.ai bloqueia a impressão); "Baixar planilha" baixa `tabela-de-vendas.xlsx` no site e, no artefato, abre o link da planilha no site (o artefato não serve .xlsx). Os valores batem centavo por centavo com a planilha.

## Tabela de vendas

1. Pedido do Lucas em 14/11/2026: uma planilha para os corretores terem em mãos e imprimirem, parecida com a antiga "Tabela de vendas" em Excel, com todos os lotes e planos.
2. `scripts/tabela_vendas.py` lê `data/lotes.json` e as regras e constantes de `src/simulador.html` (juros, incentivo, limites dos planos curtos, `SINAL_TABELA`, `PLANOS_TABELA`, `PLANO_ANUAIS_TABELA`, anual e número de anuais padrão), para dar os mesmos valores do simulador e da aba "Tabela de vendas". Para mudar os planos, mude as constantes no simulador. Colunas: quadra, lote, área, valor de venda, sinal, incentivo de construção e a mensal dos planos 12x (sem juros), 24x, 48x, 82x, 130x, 162x, 200x e 220x (só mensais, com juros) e 220x com 15 anuais de R$ 2.990,00 (1ª anual em dezembro).
3. Decisão do Lucas: na tabela o sinal é sempre 5% (constante `SINAL_TABELA`), à vista no ato, para a coluna ser fixa.
4. Todos os lotes mostram todos os planos.
4a. Os grupos do cabeçalho seguem o tipo de plano: "Sem juros" (12x), "Com juros" (24x), "Com juros e IPCA, só mensais" (48x a 220x) e "Com juros, IPCA e 15 anuais". As notas dizem que a correção do IPCA não está nos valores.
5. As parcelas são fórmulas do Excel (`PMT` com pagamento no início, igual à convenção do CV) que leem a aba "Parâmetros". O script grava também o valor calculado de cada fórmula, para o arquivo aparecer completo no celular. A impressão é em A4 deitado, em até duas folhas, com o cabeçalho repetido.
6. O robô roda o script a cada leitura do CV. O arquivo só é regravado quando os lotes, as regras ou o mês de referência mudam (assinatura guardada nas propriedades do arquivo).

## Integração com o CV CRM

1. `scripts/sync_cv.py` lê o Sweet Village em `https://vpa.cvcrm.com.br/api/v1/cadastros/empreendimentos/4` (headers `email` e `token`, vindos dos segredos `CVCRM_EMAIL` e `CVCRM_TOKEN`). O cadastro do empreendimento lista só a tabela de preço mais recente, então o robô procura as outras pelos ids próximos dos que conhece (`/v1/cadastros/empreendimentos/4/tabelasdepreco/{id}?tabelasemjson=true`; ids de outros empreendimentos voltam vazios) e registra a lista numa anotação "Tabelas do Sweet Village no CV". Entre as aprovadas e vigentes, usa:
   a. a tabela de 220x (nome com "220" e sem "vista", preferindo a que tem anuais e o maior id; `CVCRM_TABELA_PREFERIDA` no workflow, hoje `black friday;15 anuais`, dá preferência por nome). Ela dá os lotes disponíveis e os preços. `CVCRM_ID_TABELA` fixa outra pelo id.
   b. a tabela de 24x (nome com "24x", ou `CVCRM_TABELA_CURTA`). Lotes disponíveis nela que não estão na de 220x também entram, com o preço dela. Decisão do Lucas em 14/11/2026: não existe lote vendido só em até 24x; todos os lotes valem para todos os planos.
   Grava em `data/lotes.json` a tabela de 220x (`tabela`, `idtabela`), a de 24x (`tabela_curta`, `idtabela_curta`) e os lotes. O preço vem do `valor_total` da tabela; o campo `valor` da unidade é zero. Sem tabela de 220x aprovada e vigente, o robô dá erro e mantém a lista publicada.
   Em 14/11/2026 as tabelas Black Friday (vigentes até 30/11/2026) são 46 (220x sem anuais), 47 (12x), 48 (220x com 15 anuais), 49 (24x) e 50 (à vista). Todas têm o mesmo `valor_total` por lote. A de 220x tem 53 lotes disponíveis; 13 lotes (Quadra 01 L2, L3, L7, L8, L9 e Quadra 02 L1 a L8) só aparecem nas de 12x, 24x e à vista, e entram no simulador como os demais. Antes desse ajuste, de 10/11 às 14h47 até 14/11, o robô usou por engano a de 24x e depois a à vista, porque o CV passou a listar só elas (os preços eram os mesmos).
   Para conferir tabelas sem gravar nada, rode o workflow pelo botão Run workflow com o campo `consultar` (ids separados por vírgula). O resumo de cada uma aparece nas anotações "Consulta tabela".
   Decisão do Lucas: do CV o simulador usa **apenas o valor de venda** (`valor_total`). Mensal e anual são calculadas pelo próprio simulador, sem usar as séries da tabela do CV. Quadra, lote e área vêm do CV só para identificar o lote.
   As tabelas do CV guardam as séries pelo valor sem juros e aplicam a Tabela Price a 0,90% a.m. (`juros_futuro_mensal`) na coluna "Valor com juros", com juros contados a partir da 1ª mensal e parcelas contadas em meses cheios. A de 12x não tem juros. O simulador segue a mesma convenção: com a mesma anual e a mesma data, a mensal bate centavo por centavo com o CV. Exemplo conferido em 30/10/2026: Quadra 04, Lote 16, R$ 170.441,07, sinal 1x de R$ 17.044,11, 200 mensais, 15 anuais de R$ 3.657,13 com a 1ª em dez/2027 dá mensal de R$ 1.368,21 nos dois.
2. `.github/workflows/atualizar-lotes.yml` roda de hora em hora e também pelo botão Run workflow. Depois da leitura, gera a tabela de vendas. Só faz commit quando a lista de lotes ou a tabela mudam.
3. Erros e o resumo de cada leitura aparecem como anotações da execução (o script imprime `::error` e `::notice`).
4. O site lê `data/lotes.json`, atualizado pelo robô. O artefato do claude.ai não lê arquivos de fora, então lê a cópia de `data/lotes.json` publicada junto com ele, que só muda quando o artefato é republicado. Sem o arquivo, os campos de quadra e lote ficam escondidos e o valor de venda é digitado.
5. Nunca coloque o token em código ou em arquivo do repositório, e nunca grave lotes fictícios em `data/lotes.json`, porque o repositório e o site são públicos.
