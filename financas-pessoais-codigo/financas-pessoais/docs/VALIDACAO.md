# Validação da versão 1.0.0

Ambiente: Debian GNU/Linux 13 (trixie), x86_64, Python 3.12.14. Interface PySide6 6.8.3 com Qt em modo `offscreen` (sem monitor). As bibliotecas principais e transitivas usadas estão registradas no arquivo de versões.

## Resultado

**23 testes aprovados.** A saída do pytest inclui avisos de depreciação internos do Matplotlib/PyParsing; eles não impedem geração de gráficos ou PDF.

Comando:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

A suíte verifica:

- Conversão monetária sem arredondamento por ponto flutuante e calendário de meses curtos.
- Saldos após pagamento, edição, pendência, cancelamento, exclusão e reabertura.
- Transferência com efeito simétrico em duas contas e sem receita/despesa.
- Reversão integral de operações em lote/importações quando uma linha é inválida.
- Parcelas com soma exata em centavos.
- Recorrências sem duplicação, reabertura e limites por data.
- Edição desta/próximas/toda a série, preservação das datas de realização e exclusão de série.
- Compras no fechamento e depois dele, vencimentos e faturas de parcelas.
- Pagamentos parciais/totais, estornos e ausência de dupla contagem em despesas.
- Dívida/limite pelo valor total de parcelamento de cartão confirmado.
- Projeção de faturas em aberto como saídas de caixa, sem repetir pagamentos parciais.
- Orçamentos com subcategorias, metas sem despesa e arquivamento de conta.
- Backup, retenção, restauração, reabertura, arquivo inválido e preferências inválidas.
- Migração v1 → v2 com preservação de dados e backup preventivo.
- Prévia CSV, duplicatas, erros por linha, importação pela interface e exportações CSV/JSON/PDF.
- Primeiro cadastro e primeira movimentação usando os próprios formulários Qt.
- Abertura das oito telas, manual, redimensionamento da janela, tradução dos botões padrão do Qt e bloqueio exclusivo da pasta.
- Duas execuções completas do ponto de entrada em processos separados: criar e fechar, depois reabrir e conferir saldo, com chamadas de rede bloqueadas por instrumentação do teste.

O teste de persistência entre processos grava R$ 100,00 como saldo inicial e uma receita de R$ 43,21, fecha a aplicação e confirma R$ 143,21 na execução seguinte.

O executável Linux foi iniciado duas vezes com o plugin Qt offscreen, verificando inicialização automática do banco, backups e ausência de erros de inicialização. Ele inclui NumPy 2.2.4 e fontes para o PDF.

Foram gerados uma captura da interface e um PDF com dados fictícios em pasta separada. Eles são exemplos da implementação real, não telas substitutas da aplicação.

## Limites da validação

O Qt foi exercitado em modo sem monitor. A apresentação em um monitor físico e as diferenças de tema/escala do sistema devem ser verificadas no computador de uso. Windows e macOS não foram executados neste ambiente. O manual contém o procedimento de instalação e de geração de executável para cada sistema; executáveis são específicos do sistema de destino.
