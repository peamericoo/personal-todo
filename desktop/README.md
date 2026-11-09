# Cliente desktop

Consulte o [README principal](../README.md) para os requisitos, a instalação por plataforma e a configuração MCP.

O Linux/Kubuntu é o caminho validado. O cliente usa GTK 3, Python e consultas MCP resumidas; a lista é carregada em páginas e mantida em memória durante a sessão. A pesquisa e a navegação usam esse cache; atualize para ver alterações feitas em outro cliente. Com uma bandeja StatusNotifierItem disponível, fechar a janela a oculta e clicar no ícone a reabre. O botão **Sair** encerra o processo. Sem bandeja, fechar encerra normalmente.

## Uso

- Alterne lista e grade no cabeçalho; selecione uma pasta na árvore.
- Clique no título de uma tarefa para editar prazo, tags, lembrete e descrição. A descrição é Markdown, com prévia e atalhos; não é um editor completo de blocos. Use Tab para focar uma tarefa e Espaço para abrir a prévia ampliada. A renderização CommonMark usa python3-markdown-it, com visualização básica de reserva se indisponível.
- Clique com o botão direito em uma lista ou use o lápis para personalizá-la. Nome é sincronizado no servidor; emoji ou ícone é local. Use Excluir para remover a lista ou o grupo e todos os seus descendentes após confirmação.
- Histórico mostra as tarefas atualmente concluídas e a última atualização, não um registro imutável de eventos.
- O som original de conclusão usa `paplay` ou `pw-play` no Linux; `TODO_SOUND=0` o desativa.

As divisórias laterais podem ser arrastadas e suas larguras ficam salvas localmente. Os calendários GTK selecionam prazos e lembretes. O editor aceita até três tags por atividade; clique com o botão direito em uma tag para escolher sua cor; essa escolha fica salva neste computador e não é sincronizada nem escolhida pela IA.

## Lembretes

No Linux, o instalador cria uma entrada de início automático da sessão gráfica para `reminders-linux.sh`. O processo usa o endereço e a chave fornecidos por variáveis de ambiente ou pelo arquivo `~/.config/personal-todo/connection.json` descrito no README principal. Ele consulta o servidor a cada 60 segundos e registra os lembretes entregues localmente para evitar repetição. A máquina e a sessão devem estar ativas; se o horário passar enquanto estiver desligada, o aviso é tentado na próxima sincronização.

O caminho macOS usa `osascript` e ainda precisa de teste e empacotamento. Windows ainda não possui entrega habilitada: aplicações desktop precisam de registro e AppUserModelID adequados. Nenhuma garantia de funcionamento de lembretes ou bandeja fora do Linux/Kubuntu é feita nesta versão.
