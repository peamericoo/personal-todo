# Personal To-Do

Gerenciador pessoal de tarefas com aplicativo desktop GTK e servidor MCP escrito em Rust. Organize grupos, pastas, tarefas e subtarefas; use prazos, lembretes, tags e descrições em Markdown. O servidor mantém os dados em SQLite e pode ser acessado por clientes MCP compatíveis.

> **Estado do projeto:** o caminho Linux/Kubuntu foi testado. macOS e Windows ainda são experimentais: não há instaladores `.app`/`.exe`, bandeja validada ou garantia de notificações nesses sistemas. A seção de cada plataforma informa os limites.

## Requisitos do servidor

- Rust estável e Cargo, ou Docker.
- Um token secreto de pelo menos 32 caracteres.
- Um diretório persistente para o banco SQLite. Use uma única instância do servidor e faça backups do banco e dos arquivos WAL/SHM de forma consistente.

### Iniciar com Rust (Linux/macOS)

```sh
git clone https://github.com/peamericoo/personal-todo.git
cd personal-todo
cargo build --release --locked
export MCP_TOKEN="$(openssl rand -hex 32)"
export DATABASE_PATH="$PWD/todo.sqlite3"
export PORT=8080
./target/release/personal-todo
```

Guarde o token em local seguro: a mesma chave será usada no desktop e nos clientes MCP. Um novo token invalida a chave anterior. O servidor disponibiliza `/health` e `/mcp`. Para uso remoto, exponha o serviço **por HTTPS**; nunca publique a chave ou o banco no Git.

### Docker

```sh
docker build -t personal-todo .
docker run --name personal-todo -p 8080:8080 \
  -e MCP_TOKEN="$MCP_TOKEN" -e DATABASE_PATH=/data/todo.sqlite3 \
  -v personal-todo-data:/data personal-todo
```

Defina `MCP_TOKEN` antes de executar o comando. O volume preserva os dados entre recriações do container; ele não substitui um backup.

## Aplicativo desktop

O cliente não inclui Electron. A janela utiliza Python + GTK 3 e consulta o servidor por MCP. O uso real de memória depende do sistema e da quantidade de tarefas; não há meta universal de consumo garantida.

### Linux / Kubuntu — testado

```sh
sudo apt install python3 python3-gi gir1.2-gtk-3.0 libnotify-bin
./desktop/install-linux.sh
```

Abra **Personal To-Do** no menu e informe o endereço MCP e o token em **Conexão**. No KDE com StatusNotifierItem disponível, fechar a janela a mantém na bandeja; clique no ícone para reabri-la. O botão **Sair** fecha o processo. Quando não há bandeja compatível, fechar encerra a janela normalmente.

Para habilitar lembretes em segundo plano, o processo precisa ter acesso ao endereço e à chave após o login. Uma opção é criar `~/.config/personal-todo/connection.json` com permissões restritas, contendo o endereço e o **caminho para um arquivo** com o token (não o próprio token):

```json
{"url":"https://seu-servidor.example/mcp","token_file":"/caminho/privado/token.txt"}
```

Proteja ambos os arquivos (`chmod 600`). Execute novamente `./desktop/install-linux.sh` após configurar. O serviço de lembretes verifica o servidor aproximadamente a cada minuto e é iniciado na sessão gráfica. A janela pode estar fechada, mas a sessão deve estar ativa, com computador e rede disponíveis. O intervalo de consulta pode manter um servidor em nuvem ativo e afetar custos.

### macOS — experimental

Instale Homebrew, Python, GTK 3 e PyGObject para o mesmo interpretador; por exemplo, `brew install pygobject3 gtk+3`. Execute `python3 desktop/app.py`. Para lembretes, configure `TODO_MCP_URL` e `TODO_MCP_TOKEN_FILE` e execute `python3 desktop/reminders.py` na sessão do usuário. O sistema pode solicitar permissão de notificação. Essa configuração ainda não foi validada em um Mac, não instala um `.app` e não garante funcionamento na barra de menus ou início automático.

### Windows — experimental

Instale MSYS2 UCRT64 e as dependências GTK 3 e PyGObject do mesmo ambiente, seguindo a [documentação oficial do GTK](https://www.gtk.org/docs/installations/windows/). Execute `python desktop/app.py` nesse terminal. Não existe instalador `.exe` nem bandeja validada. **Notificações Windows ainda não estão habilitadas**: é necessário empacotar e registrar a aplicação corretamente antes de garantir a entrega. Não dependa de lembretes nessa plataforma por enquanto.

## Conectar por MCP

O servidor implementa **MCP Streamable HTTP stateless** em `/mcp`, protegido pelo cabeçalho `Authorization: Bearer <token>`. Configure o cliente MCP que preferir com a URL HTTPS do seu servidor e esse cabeçalho. O formato exato de configuração depende do cliente. Nunca compartilhe o token em capturas de tela ou commits.

Ferramentas: `criar_item`, `listar_itens`, `obter_item`, `atualizar_item` e `excluir_item`. A listagem é resumida e paginada (`limite`, `cursor`, `proximo_cursor`); use `detalhes=true` ou `obter_item` para descrições. Prazos usam `DD/MM/AAAA`; lembretes aceitam ISO 8601 com fuso e são guardados em UTC. Tags são listas de até 12 nomes. Excluir um item também exclui seus descendentes.

## Testes

```sh
cargo build --release --locked
python3 tests/integration.py
python3 tests/reminders.py
/usr/bin/python3 tests/desktop_ui.py  # Linux com sessão gráfica e bandeja compatível
```

`tests/frame_rate.py` faz uma medição pontual da animação em uma sessão gráfica; não garante 60 fps em todos os computadores. Consulte [desktop/README.md](desktop/README.md) para detalhes e limitações.

## Licença

MIT. Consulte [LICENSE](LICENSE).
