# Controle de Chromebooks — escola

MVP simples em **Python + Flask** para controle de **20 Chromebooks identificados de CH-001 a CH-020**.

## Como funciona

- **Professor (sem login):** abre `/retirada` pelo QR Code, informa nome, sala, quantidade e data/horário previstos para devolver. A data/hora de solicitação é registrada automaticamente.
- **TI (senha administrativa):** acessa `/admin`, confirma a entrega física, vê os Chromebooks atribuídos e confirma a devolução.
- **Histórico da TI:** `/admin/historico`. Os nomes e detalhes nunca aparecem publicamente.
- **Estados:** pendente → em uso → devolvido, ou pendente → cancelado.
- **Estoque:** pedidos pendentes NÃO reservam equipamentos. Somente a confirmação pela TI retira equipamentos do estoque; confirmações são feitas em transação. Quando o empréstimo termina, os equipamentos voltam a estar disponíveis.

## Rodar no computador (Windows, PowerShell)

Tenha **Python 3.12 ou superior** instalado. Abra o PowerShell na pasta do projeto (a que contém `app.py`). Os comandos abaixo usam o Python da venv diretamente, sem precisar ativar scripts ou mudar a política do PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env
```

No `.env`, substitua `SECRET_KEY` pelo valor aleatório gerado, sem espaços extras. Para usar **SQLite local**, mantenha `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` comentadas e não definidas no ambiente do terminal. Mantenha `COOKIE_SECURE` desativado ao usar HTTP local. `tzdata`, incluído nas dependências, fornece o fuso `America/Sao_Paulo` também no Windows.

Gere o hash da senha administrativa:

```powershell
.\.venv\Scripts\python.exe scripts/create_admin_hash.py
```

Digite uma senha de pelo menos 12 caracteres (ela não aparece ao digitar). Copie a linha `ADMIN_PASSWORD_HASH=...` exibida e substitua a linha de exemplo no `.env`. Salve o arquivo. Não envie `.env` para o Git nem compartilhe a senha com professores.

Inicialize o banco, execute os testes e inicie o sistema:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe app.py
```

O SQLite fica em `instance/chromebooks.db`. Repetir a inicialização não apaga empréstimos nem duplica os 20 equipamentos. Os testes usam bancos temporários separados e não carregam o `.env`.

Abra no navegador:

- Professores: `http://127.0.0.1:5000/retirada`
- TI: `http://127.0.0.1:5000/admin`

Para parar, use `Ctrl+C`. Nas próximas vezes, basta abrir o PowerShell na pasta do projeto e executar `.\.venv\Scripts\python.exe app.py`. O servidor local só funciona enquanto o programa roda. Evite expor o servidor de desenvolvimento diretamente à internet.

## Configurar Turso para Vercel

A Vercel pode executar Flask sem servidor sempre ligado, mas **não oferece SQLite local persistente**. Use o Turso remoto e guarde chaves nas **variáveis de ambiente** da Vercel.

1. Crie sua conta no Turso e um banco **Turso Database** (não libSQL), por exemplo com `turso db create chromebooks-escola --tursodb` no CLI Turso.
2. Descubra o endereço com `turso db show chromebooks-escola` e crie um token apropriado com `turso db tokens create chromebooks-escola`. Consulte a documentação do CLI se os comandos mudarem.
3. Configure as variáveis `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `SECRET_KEY` e `ADMIN_PASSWORD_HASH` no `.env` local para inicializar o banco remoto.
4. Execute `python scripts/init_db.py` **uma vez** com essas variáveis, e confirme que os 20 equipamentos foram criados.
5. Execute localmente o app ligado ao Turso e teste solicitação, confirmação, devolução e histórico. **A integração real com Turso ainda não foi verificada sem credenciais.**
6. Publique os arquivos num repositório Git privado; importe na Vercel como projeto Flask (ponto de entrada `app.py`). No painel da Vercel, adicione as quatro variáveis. **Não envie `.env` nem tokens para o GitHub.**
7. No navegador abra `https://seu-projeto.vercel.app/retirada`, gere um QR Code apontando para essa URL e coloque na sala após aprovação da escola.

A Vercel reconhece `app.py` automaticamente. Não é necessário `vercel.json` para este projeto, segundo a documentação atual.

> ATENÇÃO: antes do uso real, peça aprovação da coordenação/TI, faça backup dos dados e valide políticas de acesso, privacidade e retenção. A senha única simplifica o sistema, mas não identifica qual integrante da TI realizou cada alteração. Não armazenar nomes em serviços externos sem autorização da escola. Adicione proteção contra tentativas repetidas de senha, abuso de formulários e teste o controle de estoque com requisições simultâneas no banco remoto antes de colocar em produção.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

A suíte cobre regras de negócio em SQLite local (incluindo confirmações simultâneas), inicialização repetida, painel com mais de 100 pedidos, fluxo HTTP com o cliente de testes Flask, autenticação e rejeição de CSRF inválido. Turso remoto e Vercel ainda requerem validação adicional. Os comandos Windows foram documentados; a execução desta etapa foi validada em Linux com Python 3.12, sem uma máquina Windows disponível.

## Arquivos

```text
app.py                  # Rotas Flask, formulários, sessão e senha da TI
services.py             # Regras: pedidos, confirmação, devolução, histórico

database.py             # SQLite local / Turso remoto e criação das tabelas
templates/              # HTML simples, responsivo
static/styles.css       # Visual limpo, sem frameworks visuais
scripts/init_db.py      # Inicializa DB e registra CH-001 a CH-020
scripts/create_admin_hash.py

tests/test_services.py  # Testes básicos de inventário
PROMPTS-CODEX.md        # Passo a passo completo para evoluir no Codex
```

## Limitações atuais / próximos ajustes

- Senha compartilhada de TI, sem rastrear individualmente quem aprovou. Pode evoluir para usuários separados.
- Histórico apresenta os 300 registros mais recentes, sem paginação/exportação.
- Confirmação devolve todos os Chromebooks de um empréstimo; não há devolução parcial ou registro de avaria.
- Sem serviço de e-mail ou notificações.
- Formulário público tem CSRF e honeypot, mas precisa de **rate limit persistente** para produção.
- Testes em Turso remoto, concorrência entre funções Vercel e segurança da autenticação devem ser realizados antes da publicação oficial.

Leia `PROMPTS-CODEX.md` para os prompts prontos para copiar no Codex.
