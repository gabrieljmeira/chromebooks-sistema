# Controle de Chromebooks

Sistema de pedidos, entregas e devoluções dos Chromebooks da escola. Professores solicitam os aparelhos e a equipe de TI registra a entrega e o recebimento pelos códigos **CH-001 a CH-020**.

## Funcionalidades

- Pedidos imediatos e agendamentos para o mesmo dia.
- Reserva de salas e aparelhos por intervalo de uso.
- Entrega pela TI e devolução parcial ou completa por código.
- Alertas de novos pedidos, entregas agendadas e prazos de devolução.
- Controle de manutenção e indisponibilidade dos aparelhos.
- Edição, prorrogação e correção de registros com justificativa e auditoria.
- Contas individuais com perfis de técnico e gestor.
- Histórico com filtros, exportação CSV e backup completo.

## Tecnologia

| Componente | Tecnologia |
| --- | --- |
| Aplicação | Python 3.12 e Flask |
| Interface | HTML, CSS e JavaScript |
| Banco local | SQLite |
| Banco de produção | Turso, compatível com SQLite |
| Hospedagem atual | Vercel |

O banco de produção está no Turso. Os dados não fazem parte deste repositório. A conexão é definida por `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` no ambiente de execução.

## Documentação

- [Instalação e configuração](docs/instalacao.md)
- [Operação, contas e recuperação de dados](docs/operacao.md)

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `app.py` | Rotas, autenticação e respostas HTTP |
| `services.py` | Reservas, entregas, devoluções e histórico |
| `management.py` | Manutenção, edição e correções auditadas |
| `accounts.py` | Contas e permissões da TI |
| `database.py` | Conexões, transações e esquema do banco |
| `backups.py` | Cópia e restauração de dados |
| `rooms.py` | Catálogo de salas |
| `templates/` e `static/` | Páginas e recursos da interface |
| `scripts/` | Ferramentas administrativas |
| `tests/` | Testes automatizados |

## Testes

Na pasta do projeto, com as dependências de desenvolvimento instaladas:

```sh
python -m pytest -q
node --test tests/*.cjs
```

Os testes Python usam bancos temporários e não acessam o Turso. Os fluxos de navegador ficam em `tests/browser/` e exigem Playwright com Chromium; execute `smoke.cjs` e `management.cjs` separadamente, pois ambos utilizam a porta 8765.

## Regras de operação

Toda entrega é realizada pela TI. Um pedido reserva capacidade, mas os códigos são definidos somente na entrega. A previsão de devolução não libera aparelhos sem confirmação do recebimento. Conflitos de sala e estoque são revalidados em transação ao salvar cada operação.

Os horários usam `America/Sao_Paulo`. O painel deve permanecer aberto, com som liberado e computador acordado, para emitir os alertas.
