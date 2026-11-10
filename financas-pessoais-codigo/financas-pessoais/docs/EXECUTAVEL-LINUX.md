# Executável para Linux

Este pacote é para **Linux x86_64**, gerado e verificado no **Debian 13**, com glibc 2.41. Não é um executável para Windows ou macOS; esses sistemas devem usar o código-fonte e o procedimento de empacotamento do README.md.

1. Extraia a pasta inteira em um diretório seu.
2. Abra um terminal dentro da pasta extraída.
3. Execute:

```bash
./FinancasPessoais
```

Para ver os dados fictícios, separados dos dados reais:

```bash
./FinancasPessoais --demo
```

Se o gerenciador de arquivos não preservar a permissão de execução:

```bash
chmod +x FinancasPessoais
```

Não é necessário instalar Python ou pacotes Python para usar este executável. As bibliotecas gráficas do sistema precisam estar instaladas; o README descreve os componentes de Qt/X11 normalmente necessários. O modo normal exige uma sessão gráfica. Os testes neste ambiente usaram o plugin Qt `offscreen`, sem monitor físico.

Mantenha `_internal` ao lado do programa. Não mova apenas o arquivo executável para outro lugar. Não coloque o banco dentro de `_internal`: o programa usa a pasta de dados do usuário, exibida em Configurações.

A aplicação funciona sem internet. O banco não é criptografado. Faça backups e mantenha uma cópia em outra mídia.

Foram verificadas duas inicializações seguidas do executável, criação automática do banco e ausência de erros no registro de inicialização. A suíte do código-fonte valida o fluxo financeiro e a persistência entre processos. A compatibilidade com outras distribuições Linux e o funcionamento em uma sessão gráfica física devem ser conferidos no computador de uso.
