# Instalação e configuração

## Requisitos

- Python 3.12.
- Node.js 20 ou superior para os testes JavaScript.
- Banco Turso para a hospedagem na Vercel. Na execução local, SQLite também é suportado.

## Ambiente local no Windows

Abra o PowerShell na pasta que contém `app.py`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Crie um arquivo `.env` na raiz do projeto, somente se ainda não existir. Gere a chave de sessão e o hash da senha inicial:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe scripts/create_admin_hash.py
```

Grave as duas linhas geradas no `.env`. A senha é solicitada sem exibição no terminal. Mantenha o arquivo restrito à administração da TI.

| Variável | Configuração |
| --- | --- |
| `SECRET_KEY` | Chave aleatória de pelo menos 32 caracteres |
| `ADMIN_PASSWORD_HASH` | Hash gerado pelo script; usado até a primeira conta individual |
| `LOCAL_DB_PATH` | Caminho do SQLite local; padrão `instance/chromebooks.db` |
| `TURSO_DATABASE_URL` | URL do banco Turso, quando utilizado |
| `TURSO_AUTH_TOKEN` | Token do mesmo banco Turso |
| `COOKIE_SECURE` | Valor `1` para execução local servida por HTTPS |

Para usar SQLite, deixe as variáveis Turso ausentes. Inicialize o banco local e execute a aplicação:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe app.py
```

O formulário fica em `http://127.0.0.1:5000/retirada` e o painel em `http://127.0.0.1:5000/admin`. O servidor de desenvolvimento atende ao teste local; não deve ser exposto diretamente à internet.

## Banco Turso e hospedagem

Configure `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` no ambiente de execução. URLs `turso://`, `libsql://` e `https://` são aceitas. Na Vercel, o aplicativo exige Turso e não usa um arquivo SQLite temporário como alternativa.

Um banco novo precisa ser inicializado. Para um banco remoto existente, preserve uma cópia antes de migrar e confira se as credenciais apontam para o destino correto. A inicialização remota exige a opção explícita:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py --remote
```

O ponto de entrada da aplicação é `app.py`. Mudanças nas variáveis da Vercel passam a valer em um novo deploy. O arquivo `.env` local não configura automaticamente a hospedagem.

Confira a disponibilidade pelo endpoint `/saude`, que retorna HTTP 200 e `status: ok` quando a conexão e o esquema básico estão disponíveis. O script `scripts/check_config.py` verifica o ambiente local sem imprimir credenciais.

## Atualizações

Preserve o `.env`, o banco e os backups ao atualizar o código. As tabelas auxiliares de manutenção e contas são criadas de forma aditiva na primeira conexão. Bancos de versões anteriores ao esquema de entregas verificadas precisam passar pelo script de inicialização.

Prepare e verifique as mudanças em uma branch antes de integrar a `main`. A publicação depende da integração configurada na hospedagem; confira o destino e as variáveis do ambiente antes de publicar.

Consulte [Operação](operacao.md) para ativação de contas, backups e recuperação.
