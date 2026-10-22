# Controle de Chromebooks

Sistema de gestão de empréstimos de Chromebooks para uso em sala de aula. Centraliza os pedidos dos professores e permite à equipe de TI acompanhar a disponibilidade, registrar os equipamentos entregues e conferir cada devolução.

O inventário contempla **20 Chromebooks, de CH-001 a CH-020**. A entrega é realizada pela TI tanto nos pedidos imediatos quanto nos agendamentos.

[Instalação e configuração](docs/instalacao.md) · [Manual de operação](docs/operacao.md)

## Como funciona

1. **Solicitação:** o professor informa nome, sala, quantidade e horário de devolução. Em **Pedir agora**, o início é imediato; em **Agendar entrega**, também informa o horário em que precisará dos equipamentos.
2. **Disponibilidade:** o sistema verifica a ocupação da sala e a capacidade do inventário no intervalo solicitado.
3. **Entrega:** a TI atende o pedido e registra os códigos dos Chromebooks efetivamente entregues.
4. **Devolução:** a TI confere os equipamentos recebidos e registra a devolução parcial ou completa. O histórico preserva a movimentação.

Os pedidos são feitos para o mesmo dia, com horários no fuso **America/Sao_Paulo**.

## Recursos

| Área | Recursos |
| --- | --- |
| Solicitações dos professores | Pedidos imediatos e agendados, seleção de sala, quantidade e período de uso |
| Painel da TI | Acompanhamento dos pedidos, entrega por código, devoluções parciais e controle de atrasos |
| Disponibilidade | Verificação de conflitos por sala, capacidade por período e exclusão de equipamentos em manutenção |
| Ajustes operacionais | Edição de pedidos pendentes, prorrogação de uso e correções com motivo e registro de auditoria |
| Alertas | Avisos sonoros de novos pedidos, entregas agendadas e devoluções próximas ou vencidas |
| Histórico | Consulta por protocolo, professor, sala, data e situação; exportação dos resultados em CSV |
| Administração | Contas individuais de técnicos e gestores, diagnósticos e backup completo em JSON |

O formulário dos professores é público. O painel da TI exige autenticação; recursos de contas, diagnósticos e backup completo são restritos aos gestores.

## Regras de disponibilidade

- **Sala reservada por período:** uma solicitação que sobreponha o horário de outra reserva na mesma sala recebe o aviso **SALA EM USO**.
- **Reserva de quantidade:** o pedido compromete a capacidade do inventário; os códigos físicos são definidos pela TI no momento da entrega.
- **Devolução conferida:** o horário previsto não libera automaticamente os equipamentos. Eles voltam a ficar disponíveis quando a TI registra o recebimento.
- **Devolução parcial:** os equipamentos ainda não recebidos continuam vinculados ao empréstimo, e a sala permanece ocupada até a conclusão.
- **Manutenção:** equipamentos indisponíveis não podem ser entregues e deixam de compor a capacidade disponível.

Essas validações também são executadas no servidor. O registro de entrega utiliza transações e restrições no banco para impedir que um mesmo Chromebook seja vinculado a dois empréstimos ativos.

## Alertas no painel

O painel consulta as atualizações a cada 15 segundos e emite avisos para novos pedidos, início de entregas agendadas e devoluções — cinco minutos antes do prazo e no vencimento.

Para ouvir os alertas, é necessário habilitar o som no navegador e manter o painel aberto, com o computador ativo. Os avisos sonoros dependem dessa sessão do navegador e não funcionam como notificações com a página fechada.

## Arquitetura

A aplicação utiliza **Python 3.12 e Flask** no servidor, com páginas renderizadas em HTML e recursos de CSS e JavaScript no navegador. A persistência suporta SQLite local e Turso em produção, com hospedagem na Vercel.

| Componente | Responsabilidade |
| --- | --- |
| `app.py` | Aplicação Flask, rotas e integração das funcionalidades |
| `services.py` | Regras de pedidos, disponibilidade, entregas e devoluções |
| `management.py` | Manutenção do inventário e ajustes operacionais |
| `accounts.py` | Contas da TI, permissões e sessões |
| `database.py` | Conexão e acesso ao banco de dados |
| `backups.py` | Exportação e validação de backups |
| `rooms.py` | Cadastro das salas disponíveis |
| `templates/` e `static/` | Interface dos professores e da TI |
| `scripts/` | Ferramentas administrativas e de configuração |
| `tests/` | Testes de regras de negócio, interface e fluxos operacionais |

### Banco de dados

Na execução local, o SQLite usa por padrão o arquivo `instance/chromebooks.db`, com caminho configurável por `LOCAL_DB_PATH`.

Na Vercel, os dados ficam no **Turso**, configurado por `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN`. O banco de produção é externo ao repositório; atualizar o código não substitui os dados. A configuração, os arquivos locais de banco e os backups não devem ser versionados.

## Executar localmente

Requisitos: **Python 3.12**. Os testes JavaScript também exigem **Node.js 20 ou superior**.

No PowerShell, dentro da pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Antes de iniciar, siga o guia de [instalação e configuração](docs/instalacao.md) para gerar a chave de sessão, definir o acesso inicial e preparar o arquivo `.env`.

Para executar com SQLite local:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe app.py
```

| Endereço local | Acesso |
| --- | --- |
| `http://127.0.0.1:5000/retirada` | Formulário dos professores |
| `http://127.0.0.1:5000/admin` | Painel da TI |
| `http://127.0.0.1:5000/saude` | Verificação de disponibilidade |

A senha inicial configurada por hash permite criar a primeira conta de gestor. Após a criação de contas individuais, o acesso passa a ser feito por essas contas. Consulte o [manual de operação](docs/operacao.md) para administrar usuários e permissões.

## Testes

Com o ambiente virtual ativo e as dependências instaladas:

```bash
python -m pytest -q
node --test tests/*.cjs
```

Os testes Python utilizam bancos temporários. A pasta `tests/` também contém verificações de interface e fluxos de navegador, com preparação própria de servidor e dados de teste.

## Publicação

A publicação na Vercel segue a integração Git do projeto: alterações integradas à `main` acionam o deploy de produção. As variáveis de ambiente devem ser configuradas na própria Vercel; o arquivo `.env` local não é enviado pelo repositório.

Após a publicação, confira o resultado do deploy e o endpoint `/saude`. Procedimentos de instalação, inicialização do banco e atualização estão no [guia de configuração](docs/instalacao.md); entrega, devolução, manutenção e recuperação estão no [manual de operação](docs/operacao.md).
