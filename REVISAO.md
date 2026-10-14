# Revisão do ZIP — 13/10/2026

## Origem e escopo

Fonte: `chromebooks-sistema-main.zip` anexado pelo usuário. Não continha o conjunto relatado de 108 testes Python / 7 JavaScript nem os fluxos completos de entrega pela TI. Continha a versão com entrega imediata no envio, atribuição automática e devolução por quantidade.

O ZIP foi extraído em uma pasta separada; o checkout anterior, o repositório remoto e dados de usuário não foram alterados. Nenhum banco real veio no arquivo. Não houve push nem deploy.

## Principais mudanças

- Pedir agora e agendar hoje criam pedidos pendentes. A TI efetua todas as entregas.
- Reservas usam a capacidade máxima simultânea no intervalo. Atrasados não são liberados pelo relógio.
- Seleção obrigatória de códigos exatos na entrega e devolução parcial/total. Cancelamento de pendentes preserva histórico.
- Transações, índice único de aparelho em uso, tokens assinados e operações persistentes impedem duplicidade e conflitos.
- Migração aditiva mantém `loan_devices` como original; códigos anteriores precisam de conferência. Bloqueio preventivo para empréstimos legados abertos, justificativa e auditoria de correções.
- Backup SQLite consistente antes da migração local. Turso exige `--remote`, sem fallback local na Vercel.
- Sessões com vencimento absoluto de oito horas (inclusive após atualização de cookie), invalidação por mudança de senha, CSRF, cabeçalhos, validações, escaping e limites persistentes de tentativas.
- Polling com preservação de edição, alertas de cinco minutos/prazo, deduplicação por navegador, controle de som e destaque de atrasos. Sem notificações do sistema operacional.
- Interface responsiva em cartões e seletores de códigos com alvos de toque; orientação coerente com entrega pela TI.

## Verificações executadas

- **102 testes Python aprovados**, sem falhas ou skips, em SQLite local.
- **10 testes JavaScript aprovados**, sem falhas ou skips, para decisões de alerta.
- Navegador Chromium com servidor Flask real e banco temporário: formulário e agendamento, entrega selecionada, devolução parcial/completa, histórico, ausência de seleção automática e formulário público sem JavaScript.
- Larguras emuladas: 320, 360, 390, 412, 768 e 1280 px. Sem transbordamento horizontal no formulário; painel/histórico também conferidos no tamanho móvel.
- Polling preservou códigos selecionados. Alertas nas duas fases, sem repetição por polling ou recarga, com relógio de resposta controlado para os cenários de prazo.
- Ativação e silenciamento do Web Audio por clique no Chromium. Não foi aferido áudio em alto-falante físico.
- Backup criado pelo script e reaberto com conteúdo original; migrações repetidas, legado sem coluna de devolução e empréstimo antigo fora dos 300 recentes.
- Concorrência com conexões distintas: pedidos, entrega do mesmo aparelho, devolução repetida, cancelamento versus entrega e reenvio da mesma operação.
- Rollback após falha intermediária e restrição de unicidade no próprio banco.
- Dependências: `pip check` sem incompatibilidades no ambiente utilizado.

Ambiente: Linux / Python 3.12, Flask 3.1.3, python-dotenv 1.2.4, tzdata 2026.5, turso_serverless 0.1.0, pytest 9.1.1. Node e Chromium usados apenas na validação.

## Limitações restantes

- **Turso e Vercel não foram testados de verdade:** credenciais remotas ausentes. Validar transações, isolamento, índice parcial e migração em homologação antes de publicar.
- Windows nativo, Safari/iPhone e Android físicos não estavam disponíveis. A interface foi testada em Chromium com tamanhos de tela emulados.
- Alertas não funcionam com painel fechado, dispositivo suspenso ou áudio bloqueado. A consulta tem intervalo de 15 segundos. Estado de deduplicação é por navegador; apagar o armazenamento ou usar outro navegador permite novos avisos.
- Senha administrativa compartilhada não identifica uma pessoa na auditoria. Os limites de tentativas usam o endereço de conexão entregue pela infraestrutura; conferir comportamento do proxy antes de produção.
- A conferência de legado corrige códigos com justificativa, não inventa saldo ou horário físico. Saldos inconsistentes precisam de revisão assistida. Devoluções antigas por quantidade podem continuar sem código comprovado.
- Histórico visual limitado aos 300 recentes, mais empréstimos legados ativos não conferidos. Banco e auditoria completos são preservados.
- Agendamentos são somente para o mesmo dia. Não há notificações externas, e-mail, login de professores, paginação ou exportação.

## Entrega

O pacote deve conter somente código, exemplos sem segredos, testes e documentação. Não incluir `.env`, `.venv`, `.git`, bancos, backups, caches ou dados dos testes. O SHA-256 e a comparação com o ZIP original acompanham o arquivo final no diretório de entrega.

## Ajustes posteriores: painel, histórico e som

- Painel com ações recolhidas, indicador de pedidos atrasados e prioridade por atraso/prazo.
- Histórico com busca e filtros nos registros carregados; movimentações legíveis, preservando a auditoria original no banco.
- Preferência sonora persistida, teste audível de três sinais e indicação de desbloqueio do áudio após navegação.
- Validação: 103 testes Python e 10 testes JavaScript aprovados. Chromium com banco temporário: agendamento, entrega, devolução parcial/completa, preservação de seleção no polling, busca/filtros, emissão de áudio no teste e no prazo, persistência da preferência e deduplicação dos alertas.
- Conferência visual do painel em viewport móvel de 390 px; formulário em seis larguras de 320 a 1280 px. Não houve teste em telefone físico nem confirmação auditiva em alto-falante real; a automação verificou a criação dos sinais de áudio no navegador.
- Nenhuma migração ou alteração de dados existentes é necessária para estes ajustes.

### Aviso de novos pedidos e toque de notificação

Removidos os controles Testar som/Ativar/Silenciar. O áudio é liberado por clique ou teclado no painel e usa um toque original em duas frases. Pedidos pendentes ainda não avisados geram notificação; preservados os alertas de cinco minutos e do prazo, com deduplicação por navegador. Consulta a cada 15 segundos. Nenhuma alteração no banco.

Validação: 104 testes Python e 12 JavaScript aprovados. Os testes novos verificam o feed autenticado de pedidos pendentes e, com Web Audio/DOM simulados, desbloqueio por interação, emissão dos toques, agrupamento e ausência de repetição. Não confirmam volume percebido em celular ou alto-falante físico.
