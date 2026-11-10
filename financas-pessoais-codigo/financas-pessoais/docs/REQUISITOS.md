# Mapa dos requisitos

| Área | Implementação |
|---|---|
| Desktop local e offline | Python/PySide6; sem servidor ou chamadas de rede; instalação de dependências documentada |
| Persistência | SQLite na pasta de dados do usuário, inicialização automática, esquema v2 e migração v1 → v2 |
| Interface PT-BR | Tema escuro, oito áreas, formulários com validação, atalhos e tabelas ordenáveis |
| Visão geral | Saldos, realizados/previstos, comparativo, gráficos, alertas e composição de indicadores |
| Lançamentos | Criação, edição, duplicação, exclusão, filtros, etiquetas e alterações em lote |
| Contas e categorias | Saldos iniciais separados, subcategorias, arquivamento e reativação |
| Cálculos | Centavos inteiros, transferências simétricas, transações e apuração por competência/caixa |
| Séries | Parcelas exatas, calendário ancorado, recorrências finitas, chaves únicas e edição por alcance |
| Cartões | Limite, fechamento, faturas, compras/parcelas, estornos e pagamentos parciais/totais |
| Orçamentos | Limite mensal por categoria, apuração, disponibilidade e alertas em 80%/100% |
| Metas | Prazo, valor desejado, aportes editáveis e progresso sem movimentação financeira automática |
| Relatórios | Totais, categorias, caixa realizado/previsto, saldos mensais e orçamentos |
| CSV/PDF | Exportações; importação com mapeamento, prévia, validação, duplicatas e confirmação |
| Backup | Manual, automático, retenção, restauração validada e cópias preventivas |
| Privacidade | Sem telemetria; log mínimo; bloqueio de instância; distinção explícita entre local e criptografado |
| Entrega | Fontes modulares, versões, instalação/atualização, execução offline, empacotamento, dados fictícios e testes |

As decisões de calendário, cartão, recorrência finita, edição de séries e bases de relatório estão detalhadas em MANUAL.md. A restauração do programa usa SQLite; a exportação JSON é uma cópia legível de todas as tabelas.
