# Manual e decisões financeiras

## Navegação e datas

A barra lateral abre Visão geral, Lançamentos, Contas, Cartões, Orçamentos, Metas, Relatórios e Configurações. A barra superior seleciona mês, ano ou intervalo personalizado. Clique **Aplicar** após mudar datas. Os indicadores de receitas/despesas e a listagem de contas usam o período aplicado. A consulta aceita até dez anos de cada vez para evitar relatórios desnecessariamente grandes.

A consulta de faturas usa o mês informado na própria tela Cartões; limite e dívida total são sempre os valores atuais do cartão. Metas e aportes mostram todo o histórico. As telas explicam essas bases. Orçamentos exibem os meses que intersectam o intervalo e apuram cada mês inteiro.

Datas são exibidas como DD/MM/AAAA; mês de fatura e orçamento usa AAAA-MM, com indicação explícita no campo. Valores são exibidos como R$ 1.234,56. Nos formulários, aceite `1.234,56`, `1234,56`, `1234.56` ou inteiros em reais; mais de duas casas decimais são recusadas. Internamente o banco e os cálculos usam centavos inteiros, sem ponto flutuante. Só os gráficos convertem para reais na renderização.

Atalhos: `Ctrl+N` novo lançamento; `Ctrl+F` pesquisar; `Ctrl+E` editar lançamento selecionado; `F5` atualizar; `Ctrl+Q` fechar. Tab e Shift+Tab navegam nos formulários. Enter aplica a pesquisa. Duplo clique nas tabelas abre edição quando indicado. Cabeçalhos das tabelas ordenam as linhas; valores e datas têm ordenação numérica/cronológica. Ctrl/Shift permitem selecionar várias linhas.

## Saldos e situações

O saldo de uma conta em uma data é seu saldo inicial mais os movimentos realizados até aquela data. Antes da data de referência, seu saldo apurado é zero: o programa não inventa histórico anterior ao saldo inicial. A referência não pode ser movida para depois de uma movimentação realizada. O saldo inicial nunca entra como receita nos relatórios.

- Receita: previsto, pendente, recebido ou cancelado.
- Despesa: previsto, pendente, pago ou cancelado.
- Transferência: previsto, pendente, pago ou cancelado.
- Pagamento de fatura: pago ou cancelado.
- Estorno de cartão: recebido ou cancelado.

Previsto e pendente são duas formas de planejamento; ambos estão fora do saldo realizado. Datas futuras de realização são recusadas: use previsto/pendente até a movimentação acontecer. A data de competência pode diferir da de pagamento. Cancelar limpa a data de realização e retira o efeito financeiro. Editar/excluir recalcula os totais a partir dos dados atuais; não existem saldos acumulados que possam ficar desatualizados.

Transferências usam um único registro com origem e destino e são gravadas em transação. Retiram o valor de uma conta e colocam na outra, sem receita/despesa. Selecione contas diferentes. O saldo consolidado considera também contas arquivadas. Contas podem ficar negativas, pois cheque especial e dívidas reais precisam ser representáveis.

Arquive contas, categorias e cartões pela edição. Eles ficam fora de novos lançamentos, mas os lançamentos anteriores podem ser consultados e editados preservando a referência arquivada. É possível reativar o cadastro. Uma categoria admite um nível de subcategoria; não há ciclos. Categorias principais incluem subcategorias ao filtrar e calcular orçamentos. Alterações de categoria são aplicadas ao histórico que a referencia.

## Competência, caixa e painel

**Competência:** data de competência. Receita recebida e despesa paga entram nos realizados; previsto/pendente ficam em totais próprios. Compra confirmada no cartão é despesa, mesmo que a fatura ainda não tenha sido paga. Estorno confirmado reduz a despesa na data de competência do estorno. Pagamento de fatura é excluído para não duplicar a compra. Transferências são excluídas.

**Caixa:** data de pagamento/recebimento para realizados; vencimento para previstos/pendentes. Compra e estorno de cartão não movimentam conta bancária, portanto não aparecem como saída/entrada de caixa. Pagamento de fatura é uma saída de caixa. A parte em aberto das faturas (incluindo compras previstas) é projetada como saída no vencimento, deduzindo pagamentos e estornos confirmados. A projeção reflete o estado atual dos registros, não uma fotografia histórica do planejamento. Um crédito de fatura não é tratado como recebimento bancário automático. Registre eventual devolução efetiva do emissor como receita na conta, usando uma categoria apropriada.

Na listagem, a base Caixa seleciona registros por data efetiva ou vencimento para facilitar inspeção; ela ainda mostra as compras de cartão identificadas como tais. Para totais de caixa, use a base Caixa em **Relatórios**, que aplica as regras acima.

O painel separa realizados e previstos, mostra saldo no fim do período e saldos atuais por conta, despesas por categoria, evolução mensal e alertas. Clique nos indicadores para ver sua composição. Despesas líquidas podem ser negativas em um período com estornos de compras anteriores. Clique nas barras de categoria para consultar suas despesas; estornos também podem ser consultados filtrando seu tipo. A comparação usa o mês anterior, ano anterior ou intervalo imediatamente anterior de mesma duração, conforme o seletor. Alertas de vencimentos/faturas seguem o intervalo; o alerta de limite excedido é atual.

## Parcelamentos e recorrências

**Parcelamento:** informe o valor total, quantidade e periodicidade. As parcelas somam exatamente o total. Por exemplo, R$ 100,00 em três parcelas gera R$ 33,34 + R$ 33,33 + R$ 33,33. Cada parcela é identificada no nome. A competência e o vencimento avançam da primeira ocorrência.

**Recorrência:** o valor é por ocorrência. Defina quantidade (1–1.200), periodicidade diária, semanal, mensal ou anual e intervalo entre períodos. Uma data de encerramento opcional limita a quantidade. A geração é finita e completa na criação; para continuar depois da quantidade contratada, crie uma nova série. Essa escolha evita movimentos infinitos e projeções ocultas.

O dia é ancorado na data original: 31/01 → 28 ou 29/02 → 31/03. Recorrência anual de 29/02 usa 28/02 nos anos não bissextos. Em contas e recorrências, só a primeira ocorrência usa a situação e o pagamento informados; as seguintes nascem previstas e precisam ser confirmadas quando realizadas. No parcelamento de uma compra confirmada no cartão (situação pago), todas as parcelas reconhecem a dívida na mesma data da compra e o valor total consome limite imediatamente; as competências e faturas avançam mês a mês. O pagamento das faturas libera o limite gradualmente. Se o parcelamento inteiro for cadastrado como previsto/pendente, ele permanece apenas na projeção até a confirmação das parcelas.

As ocorrências têm uma chave única por série e índice. Reabrir o programa não duplica lançamentos. Excluir uma ocorrência de série a cancela, conservando sua chave. Excluir esta e próximas encerra a série a partir dela; excluir toda a série remove suas ocorrências e desativa a geração.

Na edição, escolha ocorrência, esta e próximas ou toda a série. Para o conjunto escolhido são propagados descrição, valor, tipo, categoria, conta, destino, cartão, observações e etiquetas. **O valor em edição representa cada parcela selecionada**, e não um novo total da série. Datas e situação mudam apenas na ocorrência aberta, preservando pagamentos anteriores e o calendário das demais. Alterações incompatíveis com situações anteriores são recusadas integralmente. Para redefinir um calendário inteiro, exclua as próximas ocorrências e crie uma nova série com as novas datas.

## Cartões e faturas

O mês de fatura é o mês do fechamento. Compra até o dia de fechamento, inclusive, pertence à fatura daquele mês; depois dele, à fatura seguinte. Se o vencimento for igual ou anterior ao fechamento, ele fica no mês seguinte. Dias inexistentes usam o último dia do mês. A fatura existente preserva o vencimento já gravado; mudanças no cadastro do cartão afetam novas faturas.

Na compra de cartão, a situação **pago** significa que a compra foi confirmada pelo usuário. Isso reconhece despesa e dívida; não significa que a fatura foi paga. Previsto/pendente não consome limite realizado e aparece como planejamento. A dívida total é compras confirmadas menos estornos e pagamentos confirmados. O limite disponível é limite cadastrado menos dívida. O programa avisa se estiver excedido, sem impedir o registro de uma dívida que já ocorreu.

Selecione o cartão e a fatura e use **Pagar fatura**. Escolha conta e valor. Reduza o valor sugerido para pagar parcialmente. O pagamento retira dinheiro da conta, reduz dívida e libera limite. Ele não repete a despesa por competência. Pagamentos maiores que o saldo aberto da fatura são recusados; uma fatura não transfere automaticamente saldo para outra. Juros ou tarifas efetivos devem ser registrados como novas despesas do cartão na categoria adequada. O sistema não inventa juros nem calcula crédito rotativo.

**Registrar estorno** pede cartão, fatura original e categoria da compra. Um estorno confirmado reduz a despesa e a dívida sem mexer na conta. A soma dos estornos não pode superar as compras confirmadas daquela fatura no momento do registro. Estorno após pagamento pode deixar crédito negativo na fatura, aumentando o limite disponível. Esse crédito é exibido, sem criar receita bancária. O usuário pode corrigir ou cancelar compras e pagamentos; a dívida é recalculada e eventualmente pode virar crédito. Não há redistribuição silenciosa dos pagamentos entre meses.

## Orçamentos e metas

Um orçamento define limite por categoria e mês. O gasto usa despesas confirmadas por competência menos estornos confirmados. Mostra gasto, disponível e percentual inteiro; alerta em 80%, limite atingido em 100% e ultrapassado acima de 100%. Uma categoria principal inclui suas subcategorias. Orçamentos sobrepostos são independentes: não some o orçamento principal e o da subcategoria como se fossem limites distintos de um total.

Metas têm nome, valor desejado e prazo. Aportes mostram o progresso acumulado e podem ser editados/excluídos. Eles não alteram o saldo das contas nem são despesas. Se a reserva foi transferida entre contas reais, cadastre a transferência separadamente em Lançamentos. A exclusão da meta remove seus aportes após confirmação, preservando todos os lançamentos financeiros.

## Importar e exportar

O CSV exportado usa UTF-8 com BOM, ponto e vírgula, cabeçalhos PT-BR, valores brasileiros e datas brasileiras. Exporta a seleção filtrada na tela Lançamentos, incluindo a composição de um indicador quando aberta. Campos de texto que poderiam virar fórmulas em uma planilha recebem apóstrofo de proteção. CSV é para intercâmbio de lançamentos: para uma cópia exata completa, use backup SQLite ou JSON.

Para importar:

1. Cadastre previamente as contas, categorias e cartões citados no arquivo.
2. Abra **Importar CSV**. UTF-8 e Windows-1252 são aceitos; o programa detecta ponto e vírgula, vírgula ou tabulação.
3. Mapeie as colunas. Descrição, Valor e Competência são obrigatórias. As demais são opcionais.
4. Se faltarem conta ou categoria nas colunas, escolha os padrões no formulário. Cartão em despesa substitui a conta padrão.
5. Gere a prévia. Cada linha mostra o número do arquivo e o erro ou a marca de possível duplicata. Não ocorre gravação nessa fase.
6. Corrija o arquivo e reabra se necessário. Ao mudar o mapeamento, gere novamente a prévia.
7. Por padrão, linhas com erro e possíveis duplicatas são ignoradas. A opção de incluir duplicatas é explícita. Confira o resumo e confirme a quantidade válida a gravar.
8. A confirmação grava em uma transação. Se uma regra falhar durante a gravação, todas as linhas da operação são desfeitas.

O detector de duplicatas considera descrição, tipo, valor, competência, conta e cartão, tanto no banco quanto no arquivo. É uma indicação, não uma prova: duas compras legítimas iguais podem ser marcadas. A situação padrão é **pendente**. Para realizado, importe pago/recebido e a data de pagamento. Vencimento vazio usa competência. Faturas usam AAAA-MM. A exportação de séries como CSV não conserva a vinculação de série; a cópia SQLite conserva tudo.

Em Relatórios, o PDF inclui receitas/despesas, categorias, fluxo de caixa mensal realizado/previsto, saldos de fim de mês por conta e cumprimento dos orçamentos. Os dados do primeiro e do último mês do fluxo respeitam o intervalo; saldos representam a posição na data indicada; orçamento usa o mês completo e diz isso no título. Campos extensos quebram linhas no PDF.

## Segurança operacional e limites

- Tudo funciona localmente sem internet após instalar as dependências.
- Não há criptografia embutida, senha fictícia de proteção, sincronização, login ou conexão bancária.
- Uma instância por pasta de dados evita gravações concorrentes pela interface.
- Não edite o SQLite por outro programa enquanto a aplicação estiver aberta.
- SQLite usa chaves estrangeiras e transações, com sincronização completa em disco.
- Mudanças só são gravadas quando os formulários passam pelas regras. Exclusões e importações exigem confirmação.
- Backups são consistentes, validados e preventivos antes de migração/restauração. Arquivos de versões futuras são recusados.
- A exportação JSON é legível e completa; não há importação JSON no programa. O caminho de restauração é um backup SQLite.
- O valor máximo de um lançamento é R$ 999.999.999.999,99. Não há cálculos de investimentos, impostos, juros automáticos, múltiplas moedas ou integração bancária nesta versão.
- Não apague o arquivo de bloqueio enquanto houver outra instância aberta. Se o processo encerrar inesperadamente, o Qt verifica o processo proprietário ao tentar adquirir o bloqueio novamente.
- O argumento avançado `--dados CAMINHO` escolhe outra pasta de dados. Ele é mutuamente exclusivo com `--demo`; o programa recusa a combinação para preservar a separação dos exemplos.
