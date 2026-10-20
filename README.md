# Chromebooks da escola

Python 3.12+, Flask, HTML/CSS/JavaScript sem frameworks visuais, SQLite local e adaptador Turso. Inventário fixo: **CH-001 a CH-020**.

## Recursos da TI — atualização de 20/10/2026

Manutenção por código com redução real de capacidade; lembrete de entrega agendada; edição de pedidos pendentes; prorrogação com revalidação; correções justificadas e auditadas; retomada da atualização após seleção; contas individuais com perfis de técnico/gestor; CSV com os filtros do histórico; diagnóstico e backup lógico com restauração local validada. Consulte **[OPERACAO.md](OPERACAO.md)** para ativar contas, agendar cópias e recuperar dados.

A primeira conta deve ser de gestor. Até criá-la, a senha administrativa atual continua funcionando; depois disso o acesso é por usuário individual e senha. Nenhuma conta é criada com senha padrão. A migração desta atualização cria somente tabelas adicionais e preserva os registros existentes.

## Funcionamento atual

**Toda entrega é realizada pela TI.** O formulário público cria um pedido, nunca um empréstimo já entregue.

- **Pedir agora:** nome, sala, quantidade e hora prevista de devolução. O início solicitado é o horário do envio.
- **Agendar entrega:** os mesmos dados mais a hora desejada para a entrega.
- Pedidos e agendamentos são para **hoje**, no fuso `America/Sao_Paulo`. A devolução deve ser posterior ao início. Digitar `1430` formata `14:30`; ambos são aceitos no servidor, inclusive sem JavaScript.
- A TI seleciona **exatamente os códigos dos aparelhos entregues**, na quantidade solicitada. Só então o sistema registra o horário real e muda o pedido para “Em uso”.
- Na devolução, a TI marca **os códigos recebidos**. A devolução pode ser parcial; os demais continuam emprestados.
- A TI pode cancelar um pedido que ainda não foi entregue. Ele continua no histórico.
- Não existe atribuição automática nem devolução apenas por quantidade. Professores não têm contas ou acesso ao histórico.

## Salas e horários de uso

Salas autorizadas: **101, 103, 105, 106, 107, 108, 109, 111, 113, 114, 115, 116, 201, 202, 203, 205, 206, 207, 208, 209, 210, 211, 212, 213 e 215**. O catálogo único fica em `rooms.py`; **2010 não é uma sala válida**.

- O professor escolhe uma opção da lista. A consulta considera todo o intervalo informado e mostra **SALA EM USO** nas salas com conflito. Não expõe nomes de professores nem dados de empréstimos na consulta pública.
- Pedidos pendentes e empréstimos ativos bloqueiam a sala no intervalo. Por exemplo, 09h–10h permite outro pedido às 10h, mas impede 09h30–10h30. A regra vale mesmo quando ainda há Chromebooks livres.
- Pedir agora usa o instante do envio como início; agendar usa o início informado. A sala, o início solicitado e a previsão de devolução ficam no pedido e na auditoria. A entrega real fica em `confirmed_at`, sem substituir o início solicitado nos novos registros.
- Cancelamento e devolução completa liberam a sala. Devolução parcial mantém o bloqueio. Empréstimos atrasados bloqueiam novos intervalos até a devolução completa; uma reserva já existente também será revalidada na entrega.
- A verificação final ocorre dentro da mesma transação de escrita do pedido ou da entrega. Duas requisições concorrentes não conseguem reservar a mesma sala em intervalos sobrepostos. A consulta visual é informativa e se renova ao alterar horários e a cada 30 segundos com a página visível.
- Sem JavaScript ou com falha na consulta visual, o servidor continua validando o pedido. Um pedido pendente vencido não bloqueia intervalos posteriores e deve ser cancelado pela TI se não for mais necessário.
- Salas antigas e horários já gravados são preservados, sem remapeamento automático. Se houver pedidos sobrepostos criados antes desta regra, a TI deve conferir e cancelar o pedido pendente incorreto. Não são apagados registros históricos.

## Disponibilidade e concorrência

Pedidos pendentes reservam **capacidade no intervalo**, mas não um código específico. Aparelhos indisponíveis reduzem a capacidade; reduções que comprometam reservas já existentes são destacadas para revisão pela TI. A disponibilidade considera a ocupação máxima simultânea, não a soma de todos os pedidos do dia. Os intervalos são `[início, fim)`: uma reserva pode começar exatamente quando outra termina.

Empréstimos efetivamente entregues continuam ocupando códigos até a TI registrar a devolução. A previsão permite planejar reservas futuras, mas **não libera fisicamente aparelhos**. Um empréstimo atrasado passa a contar como indisponível em qualquer intervalo futuro até a devolução.

A entrega revalida o intervalo desde o horário real da operação (inclusive quando a TI entrega antes do início agendado), os pedidos concorrentes e os códigos ainda em uso. Uma reserva não garante entrega se equipamentos anteriores atrasarem. A TI recebe erro e deve conferir a situação física; o sistema não escolhe substitutos automaticamente.

Pedidos não entregues cujo prazo já acabou permanecem no histórico/painel até cancelamento. Não podem ser entregues com previsão vencida e não reservam períodos posteriores ao próprio fim.

Mutações usam `BEGIN IMMEDIATE`, rollback e uma chave única de operação. Um índice único impede duas alocações abertas do mesmo aparelho. Reenviar o mesmo formulário com os mesmos dados não duplica pedido, entrega, devolução ou auditoria. Alterar dados de uma operação já utilizada exige abrir um formulário novo.

O número “Aparelhos disponíveis” do painel **não é a disponibilidade para qualquer agendamento**. A verificação do intervalo sempre ocorre no servidor, ao enviar e ao entregar.

## Primeira instalação no Windows

Extraia o ZIP. Abra a pasta que contém `app.py`, clique na barra de endereço do Explorador, digite `powershell` e pressione Enter.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env
```

Copie a chave gerada para `SECRET_KEY`. Para SQLite, mantenha as variáveis Turso comentadas. Gere o hash da senha da TI:

```powershell
.\.venv\Scripts\python.exe scripts/create_admin_hash.py
```

Digite uma senha com pelo menos 12 caracteres; ela não aparece enquanto você digita. Copie a linha `ADMIN_PASSWORD_HASH=...` exibida para o `.env`. Salve sem compartilhar o arquivo.

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe app.py
```

Abra `http://127.0.0.1:5000/retirada` para o formulário e `http://127.0.0.1:5000/admin` para a TI. Esses endereços locais não funcionam em outro aparelho. Pare com `Ctrl+C`. Para iniciar novamente, execute apenas o comando de `app.py` na mesma pasta. Não exponha o servidor Flask de desenvolvimento diretamente à internet.

## Atualização e preservação dos dados

1. Pare o servidor. Guarde uma cópia completa da instalação anterior.
2. Atualize os arquivos de código, preservando `.env`, `instance/` e seu banco configurado em `LOCAL_DB_PATH`.
3. Instale as dependências. A versão de 20/10 cria automaticamente somente as tabelas adicionais de manutenção/contas em uma transação; preserve um backup antes da publicação. Para primeira instalação ou atualização de versões anteriores ao esquema de 14/10/2026, execute `scripts/init_db.py` antes de abrir a aplicação. Consulte `OPERACAO.md`.
4. O script cria um **backup consistente via SQLite** do arquivo local existente, ao lado dele, com extensão `.backup-DATA.sqlite`. Se o backup falhar, a migração não começa. Guarde o backup em local protegido.
5. A migração é aditiva, transacional e repetível. Mantém pedidos, status e a tabela original `loan_devices`; adiciona as tabelas de alocações verificadas, auditoria e operações. Nenhum empréstimo anterior vira entrega nova automaticamente.

### Conferência dos códigos antigos

Versões anteriores atribuíam códigos automaticamente e devolviam por quantidade. Esses códigos não comprovam quais aparelhos foram fisicamente entregues.

- Empréstimos antigos ativos e encerrados ficam marcados como **não conferidos**.
- Enquanto existir empréstimo antigo ativo não conferido, novos pedidos e entregas ficam bloqueados. As devoluções de empréstimos novos já conferidos continuam permitidas.
- Em **Histórico e conferência**, a TI seleciona os códigos realmente ainda com o professor e informa o motivo/evidência da conferência. A quantidade esperada usa o saldo registrado na versão anterior; se o saldo também estiver incorreto, interrompa a operação e revise o caso com backup. O sistema não inventa uma correção de quantidade.
- Para um empréstimo antigo encerrado, a TI pode conferir os códigos do histórico com base em evidência. Se não houver evidência, deixe-o sinalizado; registros encerrados não bloqueiam o estoque.
- A conferência mantém a tabela original e grava auditoria com os valores anteriores, os códigos informados, a justificativa e a data da correção.
- Devoluções antigas por quantidade, anteriores à conferência de um empréstimo parcialmente aberto, continuam sem identificação física comprovada. A interface sinaliza essa limitação.
- Registros antigos sem horário de entrega ou de devolução necessário não são preenchidos por suposição: exigem revisão assistida antes da conferência.
- Horários antigos são preservados; a conferência de códigos não comprova nem altera retroativamente o horário físico de entrega.

Não substitua o banco antigo por um banco vazio. O ZIP final não contém dados reais ou credenciais. Para restaurar um backup, pare todos os processos antes de substituir o banco e mantenha código compatível com a versão restaurada.

## Alertas e atualização do painel

- O painel consulta o servidor a cada **15 segundos**, inclusive para recuperar o horário de referência.
- Há um aviso visual e, se ativado, sonoro a partir de cinco minutos antes da previsão; há outro no prazo. A precisão normal é a da consulta, até cerca de 15 segundos após o instante previsto.
- Os alertas de **devolução** incluem somente empréstimos entregues, com saldo em aberto e códigos conferidos. Existem também avisos separados de novo pedido pendente e de chegada do horário de entrega agendada. Cancelados e totalmente devolvidos não geram novos avisos.
- Se o painel for aberto depois do prazo, emite apenas o aviso do prazo; não reproduz também o aviso de cinco minutos atrasado.
- A TI pode clicar em **Ativar som** ou interagir no painel para liberar o áudio. O botão **Silenciar som** mantém os avisos visuais e lembra a preferência neste navegador; para voltar a ouvir, clique em **Ativar som**. Não são solicitadas notificações do sistema operacional.
- Os avisos emitidos são identificados por pedido, prazo e fase no `localStorage` do navegador. Não repetem a cada consulta ou recarga. Outro navegador, limpeza de dados ou armazenamento bloqueado pode voltar a avisar. A interface informa quando o armazenamento está bloqueado.
- Seleções e formulários em edição são preservados: os alertas continuam atualizando, mas a lista não é substituída enquanto há edição. Envie o formulário ou clique em **Descartar seleção e atualizar** para retomar as listas sem gravar uma movimentação.
- Se a sessão expirar, os dados do painel são removidos e é solicitado novo login. Falhas de rede são indicadas.

**O painel precisa permanecer aberto e o dispositivo acordado.** Navegadores podem suspender timers e áudio em segundo plano; isto não é um serviço de notificação garantida com o navegador fechado.

## Segurança e limites

- Senhas somente como hash; contas individuais opcionais na ativação, com perfis de gestor e técnico. Sessão assinada, HttpOnly, SameSite=Lax, Secure em HTTPS e validade absoluta de 8 horas, sem renovação pelo polling. Alterar senha/perfil/situação invalida sessões da conta; até a primeira conta, a rotação de `ADMIN_PASSWORD_HASH` invalida o acesso compartilhado.
- CSRF em todos os POSTs e identificador de operação assinado, vinculado à sessão e com validade de 8 horas. Ações de alteração não aceitam GET.
- Consultas parametrizadas, validação no servidor, escape HTML do Jinja, limite de corpo de 16 KiB, CSP e proibição de enquadramento em iframe. Respostas não são cacheadas.
- Limites persistentes no banco: 10 tentativas de login e 30 envios públicos por endereço de conexão em janelas de 10 minutos. Guarda apenas HMAC do endereço, nunca o IP em texto; os registros vencidos são eliminados em novas verificações.
- O aplicativo não confia em cabeçalhos `X-Forwarded-For` enviados pelo cliente. Atrás de proxy, valide qual endereço o ambiente entrega em `remote_addr`: usuários podem compartilhar o mesmo limite. Isso é uma barreira básica, não uma proteção completa contra ataques distribuídos.
- Auditoria identifica o usuário das novas movimentações quando contas individuais estão ativadas. Registros anteriores mantêm a identificação disponível na época; não se inventa um responsável. Não há e-mail, notificações do sistema operacional ou frameworks de frontend.
- O histórico consulta todo o banco, com filtros por professor/número do pedido, sala, data de início e situação, paginando 50 registros. A filtragem acontece no servidor e funciona sem JavaScript. Há um link para conferências antigas pendentes, independentemente da página. A exportação CSV considera todos os resultados dos mesmos filtros, sem o limite visual de página.
- O formulário é público: a aplicação não comprova que quem preenche é professor. A entrega física pela TI é a conferência operacional.

## Turso e Vercel

O adaptador usa `turso_serverless==0.1.0` e requer Turso compatível com esse SDK. Na Vercel, a ausência de `TURSO_DATABASE_URL` gera uma resposta 503 com orientação; **não há fallback para SQLite temporário**.

Antes de publicar, configure um banco remoto de homologação com as variáveis `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `SECRET_KEY` e `ADMIN_PASSWORD_HASH`. Faça backup pelo provedor antes de migrar um banco remoto existente. A inicialização remota exige autorização explícita no comando:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py --remote
```

O script não faz download nem backup do Turso. Não execute contra produção sem backup e autorização. Teste no banco de homologação pedido, reserva concorrente, seleção de códigos, entrega, devolução parcial, cancelamento, conferência e reenvio antes do deploy. Confira suporte a transações, índice único parcial, PRAGMAs e migração no engine/versão contratado.

Depois dessa validação, importe o repositório na Vercel, configure as variáveis de produção e `COOKIE_SECURE=1`, e teste o endereço HTTPS. O ponto de entrada é `app.py`. Confira as configurações atuais do provedor antes de publicar. Não envie `.env`, tokens, bancos ou backups ao GitHub.

Somente depois de validar o endereço definitivo crie o QR Code para `https://SEU-DOMINIO/retirada`. Não use `/admin` ou `127.0.0.1` no QR. Atualizar a branch conectada à Vercel pode disparar um deploy automático, conforme a configuração do projeto. A validação local não confirma o funcionamento no banco de produção.

## Testes e organização

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Testes de alertas (Node.js 20+ apenas para desenvolvimento):

```powershell
node --test tests/test_alerts.cjs tests/test_dashboard.cjs
```

Os testes Python usam bancos temporários, desativam `.env` e Turso, e fixam o relógio em São Paulo. Consulte `REVISAO.md` para os resultados efetivamente executados e limitações.

- `app.py`: rotas, autenticação, CSRF, tokens, cabeçalhos e renderização.
- `services.py`: intervalos, entregas/devoluções, auditoria e idempotência.
- `database.py`: adaptador, transações, esquema e migração aditiva.
- `scripts/init_db.py`: backup local e inicialização/migração explícita.
- `rooms.py`: catálogo único das 25 salas.
- `static/request.js`: horários, agendamento e consulta de ocupação das salas.
- `static/devices.js`: contagem e validação visual dos códigos selecionados.
- `static/alerts.js` / `dashboard.js`: decisão de alertas, som e polling.
- `templates/`: formulário, painel, seleção de códigos, histórico e erros.

### Painel, histórico e som

O painel mostra a quantidade de pedidos atrasados e prioriza esses empréstimos na lista de uso. Abra “Selecionar aparelhos para entrega” ou “Selecionar aparelhos devolvidos” para registrar a movimentação pelos códigos físicos.

No histórico, os filtros combinados de professor/número, sala, data de início e situação pesquisam todos os registros, com 50 resultados por página. Abra um registro para ver aparelhos e movimentações. Os dados completos de auditoria continuam preservados no banco.

Os avisos usam um toque de duas frases, semelhante a uma notificação de celular. O controle Ativar/Silenciar som fica no topo do painel. Quando o som não está silenciado, clicar no painel ou usar o teclado também libera o áudio quando o navegador exigir; o indicador informa o estado. Após navegar ou recarregar, pode ser necessária outra interação. Confira também o volume e se o site está silenciado no navegador.

Um pedido pendente ainda não avisado neste navegador gera um aviso visual e sonoro, inclusive ao abrir o painel. Empréstimos entregues, conferidos e com aparelhos ainda em uso geram avisos cinco minutos antes e no prazo de devolução. Cada evento é lembrado neste navegador para não repetir a cada consulta. Vários eventos na mesma consulta produzem um único toque. Se o áudio estiver bloqueado, um toque fica aguardando a interação no painel.

Mantenha o painel aberto e o dispositivo acordado. Navegadores podem suspender áudio e consultas em abas em segundo plano ou com a tela bloqueada; não há garantia de alarme nessas condições. A consulta ocorre a cada 15 segundos, portanto um pedido novo ou prazo pode levar até a próxima consulta para gerar o aviso, além do tempo de rede.


### Verificação opcional no navegador

Com Node.js e Playwright disponíveis, execute `node tests/browser/smoke.cjs`. O teste inicia um servidor local exclusivo na porta 8765, usa banco SQLite temporário e relógio fixo, e fecha o servidor ao concluir. Não usa `.env` ou dados reais. Instale o Playwright fora do ambiente de produção; `CHROMIUM_PATH` permite informar um executável Chromium já instalado. `PYTHON_BIN` permite selecionar o Python com as dependências deste projeto. `SCREENSHOT_DIR` é opcional para salvar capturas de tela.

O cenário cobre pedido imediato/agendado, sala ocupada, entrega pelos códigos, devolução parcial/completa, preservação das seleções, som, filtros do histórico, formulário sem JavaScript e larguras de 320 a 1280 pixels. Não confirma alto-falantes físicos nem Turso/Vercel.

O teste adicional `node tests/browser/management.cjs` verifica os novos fluxos de manutenção, edição, prorrogação, correção, contas, exportação e backup em banco temporário. Execute os testes de navegador separadamente, pois usam a mesma porta local.
