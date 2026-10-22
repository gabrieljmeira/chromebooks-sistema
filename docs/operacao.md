# Operação da TI

## Banco e atualização

As tabelas adicionais de manutenção, contas e auditoria administrativa são criadas em uma transação na primeira conexão de cada instância. São apenas `CREATE TABLE IF NOT EXISTS`: não se apagam ou reescrevem empréstimos existentes. O esquema básico anterior continua obrigatório. Faça uma cópia do banco antes de publicar; um rollback do código anterior pode ignorar as indisponibilidades cadastradas nesta versão e deve ser acompanhado pela TI.

Na Vercel, configure `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` para Production. As URLs `turso://`, `libsql://` e `https://` são aceitas. Alterar uma variável exige novo deploy. `LOCAL_DB_PATH` vale somente para execução local. Consulte [Instalação](instalacao.md) para configurar um ambiente novo.

Valide `/saude` (200, `{"status":"ok"}`), faça login e confira **Sistema**. Falhas de configuração/conexão retornam 503 com orientação, sem mostrar credenciais. O comando `python scripts/check_config.py` confere o ambiente local configurado no `.env`, sem imprimir valores; ele não lê automaticamente as variáveis da Vercel.

## Contas individuais

Até existir a primeira conta, a senha compartilhada funciona como antes. Em **Contas**, crie a primeira conta como **Gestor da TI**. Você será desconectado e deverá entrar com usuário e senha novos. Depois disso `ADMIN_PASSWORD_HASH` não permite mais acesso ao painel, mesmo que uma conta seja desativada. Alterações da senha individual são feitas em **Minha senha** ou por um gestor em **Contas**; não dependem de deploy.

Técnicos registram entregas, devoluções, manutenção, edição, prorrogação e correções, e exportam o histórico. Gestores também administram contas, consultam Sistema e baixam backups completos. A última conta de gestor ativa não pode ser desativada ou rebaixada. Senhas têm mínimo de 12 caracteres; hashes são gerados no servidor e não são apresentados nas telas ou na auditoria. Mudanças de senha, perfil ou situação invalidam as sessões da conta. O prazo absoluto das sessões continua sendo de oito horas.

Quem já administra as credenciais do banco pode recuperar uma conta com `python scripts/reset_account.py USUARIO`. O programa solicita a nova senha duas vezes sem exibi-la, reativa a conta como gestor e registra a recuperação na auditoria. Execute somente no computador administrativo configurado para o banco correto. Não há recuperação por rota pública nem retorno automático à senha compartilhada.

## Empréstimos e manutenção

- **Selecionar disponíveis:** na entrega, o botão seleciona a quantidade do pedido em ordem numérica, pulando os aparelhos em uso ou manutenção. Substitui as marcações anteriores e permite ajuste manual. Se faltar estoque, fica desabilitado e informa a quantidade disponível. Confira os códigos físicos e clique em **Registrar entrega** para concluir; a seleção por si só não registra a movimentação.
- **Aparelhos:** marque um código como indisponível com justificativa. Ele sai dos seletores de entrega e reduz a capacidade dos intervalos futuros. Um aparelho emprestado precisa ser recebido antes de entrar em manutenção. Liberar também exige motivo. A auditoria guarda as alterações; as últimas 50 aparecem nesta tela.
- Reservas antigas não são apagadas quando um defeito reduz o estoque. O painel identifica pedidos cuja capacidade ficou insuficiente; a TI ajusta os pedidos ou aguarda a liberação física dos aparelhos.
- **Editar pedido:** disponível antes da entrega, para professor, sala, quantidade e horários de hoje. O início original já passado pode ser mantido, mas não alterado para outro horário passado. Registros de outro dia devem ser cancelados e refeitos. A edição verifica sala e capacidade na mesma transação e guarda antes/depois e motivo.
- **Prorrogar devolução:** somente empréstimos em uso com códigos conferidos, para um horário posterior de hoje. Verifica conflitos de sala e capacidade considerando os aparelhos ainda emprestados; não libera nem muda os códigos.
- **Corrigir registro:** corrige um código informado por engano ou um recebimento incorreto, em um aparelho por vez. Não representa uma troca física. O registro original da entrega/devolução permanece na auditoria, junto do antes/depois e justificativa. Códigos com períodos de entrega sobrepostos são rejeitados. Reabrir um recebimento também confere manutenção, sala e reservas; em caso de conflito, a TI precisa reconciliar a situação real antes de corrigir.
- Uma correção que registra recebimento de um aparelho ainda em uso usa o horário atual. Ao trocar somente o código de um recebimento já registrado, seu horário é mantido. Horários históricos de entrega não são inventados nem editados.
- **Descartar seleção e atualizar:** limpa os formulários locais e retoma as listas atuais do painel. Nenhuma movimentação é gravada por esse botão.

## Alertas

Além dos novos pedidos e dos avisos de devolução (cinco minutos antes e no prazo), pedidos agendados pendentes avisam quando chega seu início. O lembrete é emitido uma vez por pedido/horário neste navegador, durante o intervalo válido. Editar o início cria um novo horário de lembrete. Entregar, cancelar ou vencer o prazo remove o pedido desse fluxo.

Mantenha o painel aberto, interaja para ativar o som e confira volume e suspensão do computador. A consulta continua a cada 15 segundos. Não há garantia com aba suspensa, navegador fechado ou sessão encerrada; não são notificações externas. A indicação de áudio no navegador não confirma o funcionamento físico do alto-falante.

## Relatório e backup

**Histórico → Exportar resultado em CSV** exporta todos os pedidos que combinam com os filtros, além da página visível. Inclui horários, códigos e aparelhos ainda em uso; textos que poderiam virar fórmulas são neutralizados. O CSV é um relatório, não um backup.

**Sistema → Baixar backup completo** gera uma leitura consistente de todas as tabelas do aplicativo em JSON, incluindo auditoria, contas e hashes de senha. Guarde esses arquivos em local de acesso restrito à TI, separado do computador que executa o sistema. Não envie cópias ao GitHub. O diretório `backups/` é ignorado pelo Git.

Também é possível usar, com as credenciais do banco correto em um `.env` local:

```bat
python -m pip install -r requirements.txt
python scripts/backup_db.py --directory backups
```

O programa cria um arquivo novo com data/hora e nunca sobrescreve uma cópia. Código de saída 0 indica sucesso; 1 indica falha. Em sistemas que suportam permissões POSIX, o arquivo é criado com modo 0600; no Windows restrinja o acesso à pasta pela TI.

Para programar diariamente no Windows, use o **Agendador de Tarefas** no computador da TI. Na ação **Iniciar um programa**, informe o caminho completo de `python.exe` usado no projeto. Nos argumentos, informe o caminho completo de `scripts\backup_db.py` e a opção `--directory` com o diretório de cópias escolhido. Coloque aspas nos caminhos com espaços. O script encontra o `.env` pela pasta do projeto. Configure o horário, confira **Último Resultado = 0x0** e teste a execução manual. O computador precisa estar ligado e com rede.

O agendamento é configurado separadamente da publicação do site. Confira também a retenção e a recuperação das cópias disponibilizadas pelo Turso.

## Recuperação validada

Teste periodicamente uma cópia em um **arquivo novo**, sem tocar no banco em produção. O utilitário recebe dois argumentos: o caminho do backup JSON e o caminho de destino do SQLite. Consulte a interface do comando:

```bat
python scripts/restore_backup.py --help
```

O comando confere formato, tabelas/colunas conhecidas, chaves estrangeiras, integridade SQLite e inventário CH-001 a CH-020. Publica o arquivo somente após essas verificações. Recusa destinos já existentes e backups acima de 100 MB; para volumes maiores, faça restauração assistida. Nenhum SQL vindo do JSON é executado.

Para verificar o banco restaurado, execute uma cópia local do projeto com `LOCAL_DB_PATH` apontando para esse arquivo, `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` ausentes e `VERCEL` ausente. Confira inventário, códigos ainda emprestados, manutenção, contas e histórico. Evite confundir o painel de teste com produção.

O utilitário não sobrescreve Turso remoto. Uma recuperação de produção exige pausar novas movimentações, preservar uma cópia do estado atual e importar a cópia validada para um banco Turso separado usando as ferramentas do provedor. Valide-o antes de trocar URL/token na Vercel e fazer redeploy. Não apague o banco anterior enquanto a recuperação não estiver conferida.
