# Finanças Pessoais

Aplicação desktop local em **português brasileiro**, com Python, PySide6, SQLite, Matplotlib e ReportLab. Tema escuro, oito áreas de navegação e dados persistentes fora da instalação. Não possui servidor, integração bancária, telemetria, anúncios, assinaturas ou chamadas de rede. Depois de instalar as dependências, funciona sem internet.

## Início rápido

Recomendado: **Python 3.12 de 64 bits**. O código aceita Python 3.11–3.13. Instale o Python e extraia o pacote em uma pasta sua. Abra o terminal nessa pasta.

### Windows 10/11, 64 bits

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python iniciar.py
```

Nas próximas vezes, basta executar a última linha, ou `iniciar-windows.bat` depois da instalação. Não é necessário ativar o ambiente virtual no PowerShell.

### Linux, 64 bits

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python iniciar.py
```

Depois da instalação, `bash iniciar-linux.sh` também inicia o programa. Em Debian/Ubuntu, o Python pode exigir o pacote `python3-venv`. Para a interface gráfica com Qt, são necessárias as bibliotecas do sistema de vídeo, incluindo `libegl1`, `libopengl0`, `libxkbcommon0`, `libxcb-cursor0` e as bibliotecas X11/XCB. Se o Qt avisar que não conseguiu carregar o plugin `xcb`, instale esses componentes pelo gerenciador da sua distribuição. Os testes da interface neste pacote foram executados no Linux com o plugin Qt `offscreen`.

### macOS

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python iniciar.py
```

O procedimento de fonte é equivalente. Windows e macOS não foram testados neste ambiente Linux; os executáveis precisam ser gerados e validados no sistema de destino.

### Primeira movimentação

1. Abra **Contas → Cadastrar conta**. Informe nome, tipo, saldo inicial e a data desse saldo. Para registrar movimentos antigos, use uma referência igual ou anterior a eles.
2. Abra **Lançamentos → Novo lançamento** (`Ctrl+N`). Escolha receita/despesa, valor, categoria, conta e datas.
3. Uma receita realizada usa **recebido**; uma despesa realizada usa **pago**. Informe a data efetiva. **Previsto** e **pendente** não alteram o saldo realizado.
4. Clique em Salvar. A gravação é imediata e transacional. Feche e abra o programa: os dados permanecem no banco.
5. Use o período no topo e **Aplicar**. Para períodos antigos, ajuste esse filtro.

A janela também oferece cadastrar a primeira conta ao tentar criar o primeiro lançamento. O banco e as categorias iniciais são criados automaticamente.

## Demonstração, isolada dos dados reais

```bash
python iniciar.py --demo
```

Use o Python do ambiente virtual nos comandos acima. Esse modo grava em **FinancasPessoais-Demonstracao**, uma pasta independente. É possível editar e apagar os exemplos sem tocar na pasta padrão. A demonstração só é preenchida quando ainda não existem contas nessa pasta. Não há dados fictícios no banco real.

## Instalação sem internet na máquina de uso

A aplicação não precisa de internet em execução. Para instalar dependências sem rede, use outro computador com **o mesmo sistema operacional, arquitetura e versão do Python**:

```bash
python -m pip download -r requirements.txt -d pacotes-offline
```

Leve a pasta `pacotes-offline` junto do código e instale na máquina de uso:

```bash
python -m pip install --no-index --find-links pacotes-offline -r requirements.txt
```

Use o Python do ambiente virtual. O interpretador Python e as bibliotecas gráficas do sistema também precisam estar disponíveis. `requirements.txt` fixa as bibliotecas principais. `requirements-lock-linux-py312.txt` registra todas as versões do ambiente Linux/Python 3.12 validado; não use esse arquivo como garantia de portabilidade para outro sistema.

## Dados, backup e privacidade

Pasta padrão:

- Windows: `%LOCALAPPDATA%\FinancasPessoais`
- Linux: `$XDG_DATA_HOME/FinancasPessoais` ou `~/.local/share/FinancasPessoais`
- macOS: `~/Library/Application Support/FinancasPessoais`

O caminho completo do banco aparece em **Configurações**. A instalação e os dados ficam separados. Nunca substitua o banco por um arquivo de demonstração.

- **Criar backup** gera uma cópia SQLite consistente usando a API de backup, com validação.
- Backups automáticos são feitos ao abrir, a cada 30 minutos e ao fechar. Configure ativação e retenção em Configurações. Padrão: 15 cópias automáticas.
- A retenção só remove `automatico-*.sqlite3`. Backups manuais e preventivos são preservados.
- **Restaurar backup** valida integridade, versão, estrutura e referências, pede confirmação e faz um backup preventivo antes de substituir o banco.
- O backup preventivo fica na subpasta `backups`, ao lado do banco. A restauração atualiza as telas imediatamente.
- Antes de migrar um banco de versão anterior, é criado um backup preventivo. Migrações são transacionais.
- **Exportação completa (JSON)** inclui todas as tabelas e a versão do esquema. É uma cópia legível para portabilidade; a restauração pelo aplicativo usa **SQLite**, não JSON.
- Guarde backups em outra mídia. Backup na mesma unidade não protege contra perda física do disco.
- `erros.log` é local, com rotação, e registra nomes das operações e classes de erro, sem copiar descrições, valores ou consultas financeiras.
- Um bloqueio por pasta de dados impede duas instâncias simultâneas. Não coloque o banco em pasta de rede ou sincronização simultânea.

**Armazenamento local não é criptografia.** O banco SQLite, os backups, CSV, JSON e PDF podem ser lidos por quem tiver acesso aos arquivos. Não há senha de abertura nem alegação de proteção criptográfica. Use a conta do sistema operacional, suas permissões e, se necessário, criptografia de disco.

## Atualização

1. Faça um backup manual em Configurações e copie-o para outro local.
2. Feche o aplicativo.
3. Extraia a nova versão em uma nova pasta. Não mova nem apague sua pasta de dados.
4. Instale as dependências da versão nova no ambiente virtual dessa pasta e execute.
5. A versão do esquema é verificada no início. Bancos antigos são migrados com backup; bancos mais novos são recusados por versões antigas.
6. Confira saldos e relatórios antes de remover a instalação anterior.

Para voltar a uma versão antiga, mantenha uma cópia do banco anterior à migração. Não force uma versão antiga a abrir um banco mais novo.

## Gerar executável

O pacote de fontes inclui o procedimento. A entrega separada para Linux é específica de Debian 13 x86_64 (glibc 2.41). Não inclui um executável Windows ou macOS pré-compilado. **PyInstaller deve rodar no sistema de destino**, com o Python e a arquitetura de destino. Não há compilação cruzada Windows a partir de Linux.

Instale as dependências de desenvolvimento:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m PyInstaller --noconfirm --clean --windowed --onedir --name FinancasPessoais --collect-all matplotlib --collect-all numpy iniciar.py
```

Use o Python do ambiente virtual. No Windows, o programa estará em `dist\FinancasPessoais\FinancasPessoais.exe`; no Linux em `dist/FinancasPessoais/FinancasPessoais`; no macOS o PyInstaller gera o aplicativo correspondente. Distribua **a pasta inteira** produzida, incluindo `_internal`, e uma cópia deste manual. O executável é específico do sistema/arquitetura em que foi criado e depende das bibliotecas gráficas do sistema. Gere o Linux na distribuição mais antiga que pretende suportar; esta versão foi validada em Debian 13 x86_64, Python 3.12.

O modo `--onedir` evita extração temporária de centenas de arquivos a cada abertura. Não há necessidade de embutir banco: o banco do usuário nasce na pasta de dados. Para demonstrar um executável, execute-o com `--demo`.

## Estrutura e testes

- `financas/db.py`: esquema v1, migração v2, transações, backups, restauração e exportação completa.
- `financas/service.py`: regras de lançamentos, saldos, cartões, séries e orçamentos.
- `financas/money.py`: centavos, datas e divisão exata de parcelas.
- `financas/window.py`, `dialogs.py`, `widgets.py`: interface PySide6.
- `financas/reports.py`: CSV, prévia de importação, relatórios e PDF.
- `financas/demo.py`: dados fictícios opcionais.
- `tests/`: regras financeiras e fluxo real dos formulários Qt.
- `docs/MANUAL.md`: decisões de cálculo e operação em detalhes.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Em um servidor sem monitor, use `QT_QPA_PLATFORM=offscreen`. Os testes usam bancos temporários, sem acessar seus dados. Cobrem saldos, exclusões/cancelamentos/edições, fechamento e reabertura, transferências, arredondamento de parcelas, recorrências sem duplicação, alcance de séries, faturas/estornos/pagamentos parciais, fluxo de caixa previsto, categorias, metas, atomicidade em lote/importação, CSV/PDF, migração, retenção/restauração e bloqueio de instâncias.
