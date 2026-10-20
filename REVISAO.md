# Atualização — operação completa da TI — 20/10/2026

Base: `c259075b853b805777064fb151aaf1fe82bc1112`. Esta seção descreve a versão atual; seções seguintes são históricas.

## Implementação

- Indisponibilidade/manutenção por código com justificativa, auditoria, bloqueio da entrega e redução da capacidade de reservas. Reservas comprometidas pelo estoque reduzido ou atrasos são destacadas; não são apagadas.
- Lembrete de início de entrega agendada, deduplicado por pedido e horário. Mantidos novos pedidos, pré-devolução e prazo.
- Edição de pendentes e prorrogação de empréstimos ativos com justificativa, revalidação transacional de sala/estoque e auditoria antes/depois.
- Correção de código/recebimento por alocação, guardando original na auditoria. Verifica sobreposição histórica do código, manutenção e conflitos na reabertura de recebimentos. Não inventa horários históricos de entrega.
- Botão para descartar a seleção local e retomar atualização do painel, sem gravar operações.
- Contas individuais com técnico/gestor, bootstrap pela senha atual até a criação do primeiro gestor, desativação e redefinição de acesso, senha própria, invalidação de sessões e impedimento de remover o último gestor ativo. Usuários são identificados nas novas movimentações.
- Exportação CSV sobre todos os resultados dos filtros, neutralizando fórmulas. Backup JSON completo consistente, restrito a gestores, e comandos de cópia/recuperação em arquivo local novo.
- Respostas 503 para falha de configuração/conexão do banco, endpoint de disponibilidade e diagnóstico autenticado. Nenhuma escrita é repetida automaticamente após falha de confirmação.
- Procedimentos de publicação, recuperação de conta, agendamento de backups no Windows e restauração em `OPERACAO.md`.

## Migração

São criadas quatro tabelas auxiliares, em uma transação, na primeira conexão de cada instância. Nenhuma tabela de empréstimos, código, senha ou horário existente é reescrita na migração. O esquema básico anterior continua necessário. Nenhuma conta nova é pré-configurada: a TI escolhe usuário e senha na tela Contas.

## Validação executada

- **149 testes Python aprovados** em SQLite temporário: regressão e novos cenários de manutenção, conflitos de edição/prorrogação, correções/reaberturas, auditoria, HTTP 503, perfis, troca de senha e invalidação de sessão, CSV com mais de uma página, backup/restauração e corrupção.
- **16 testes JavaScript aprovados**, incluindo lembrete agendado com limites do intervalo e deduplicação, e retomada da atualização.
- **Dois fluxos Chromium/Playwright com Flask real e banco temporário aprovados**: o fluxo anterior e a nova sequência de manutenção, edição, entrega, retomada da seleção, prorrogação, correção de código, recebimento/reabertura, auditoria, download CSV, ativação de contas, login individual, autorização e download do backup completo.
- Novas páginas de painel, contas, sistema e correção sem transbordamento em 320/390/768/1280 px; inventário em 390 px. Capturas de inventário e histórico com auditoria inspecionadas.
- Backup restaurado em banco novo comparado tabela a tabela, incluindo contas, manutenção e auditoria. Destino já existente e backup inválido recusados.

## Limites de operação

Os testes acima não usam dados nem credenciais de produção. O usuário confirmou o login em produção depois de corrigir `TURSO_DATABASE_URL`; a consulta pública de salas respondeu 200 antes desta atualização. Não houve criação de empréstimos reais para testar.

Backups no provedor, agendamento no computador da TI e recuperação/importação de um banco Turso separado exigem configuração/verificação operacional fora do código. Não foram ativados por esta publicação. A restauração automatizada entregue é para arquivo SQLite novo e validado; não sobrescreve Turso.

Permanecem agendamentos para hoje, formulário público de professores e limitações de áudio com navegador fechado/suspenso. Auditoria anterior mantém a identificação que existia à época. O assistente não possui sessão autenticada no painel da TI nem acesso autorizado aos logs da conta Vercel.

---

# Atualização — salas e painel da TI — 19/10/2026

Base inspecionada: branch `main`, commit `7dc4ea865f35439daab17d958c7208453d864e11`. Os fluxos anteriores de pedido imediato/agendado, entrega pela TI, códigos físicos, devolução parcial, auditoria, segurança e alertas já estavam presentes. As notas abaixo correspondem à atualização atual; as seções posteriores são o histórico de revisões anteriores.

## Mudanças verificadas

- Catálogo único com as 25 salas informadas, corrigindo **2010 para 210 na lista**. Nenhum dado histórico é renomeado automaticamente.
- Consulta pública de ocupação por intervalo, exibindo **SALA EM USO**, sem dados pessoais. Revalidação no servidor e na transação tanto ao pedir quanto ao entregar.
- Limites `[início,fim)`, sobreposições parciais, cancelamento, devolução parcial/completa, antecipação e atraso cobertos. A sala fica bloqueada mesmo quando sobra capacidade de aparelhos.
- Início solicitado deixa de ser sobrescrito pela entrega real. Valores anteriores são preservados; não se inventam horários antigos.
- Cartões da TI com sala, prazos e situação em destaque; aparelhos ainda em uso visíveis, contador da seleção, validação do grupo de códigos e preservação da edição no polling.
- Histórico com filtros por professor/número, sala, data e situação, aplicados no banco antes da paginação de 50 registros. Remove o limite visual de 300 e o script redundante de filtragem local.
- Controle de ativação/silenciamento com preferência persistida; mantidos toque, alertas de novo pedido, cinco minutos e prazo, além da deduplicação por navegador.
- Navegação por teclado, estados vazios e ajustes responsivos em formulário, painel, seleção e histórico.

## Evidências desta versão

- **131 testes Python aprovados** em SQLite temporário: regras anteriores, catálogo, concorrência na mesma sala, limites dos intervalos, liberação, atraso, validação sem JavaScript e histórico com mais de 300 registros.
- **14 testes JavaScript aprovados**: decisões de alerta, deduplicação, desbloqueio, agrupamento, silenciamento e ativação pelo teclado.
- **Chromium 153 / Playwright com servidor Flask real e SQLite temporário:** pedido imediato e agendado na mesma sala em intervalos adjacentes; bloqueio visual por sobreposição; entrega CH-004/CH-015; devolução parcial mantém a sala ocupada, total libera; seleção preservada durante polling; pré-alerta; preferência sonora; filtros e formulário sem JavaScript.
- Layout sem transbordamento horizontal no painel em **320, 360, 390, 412, 768 e 1280 px**, formulário em 320/390/768/1280 e histórico em 390 px. Capturas de painel, histórico e formulário inspecionadas. Não houve aferição de áudio em alto-falantes nem teste em dispositivos físicos.
- O teste de navegador é reproduzível em `tests/browser/smoke.cjs`, com servidor e banco exclusivos de teste.

## Atualização e limites

Esta mudança não altera o esquema do banco nem migra registros existentes. Sobre a revisão de 14/10, basta atualizar o código; a inicialização/migração segue necessária para bancos anteriores àquela revisão. Novos arquivos `rooms.py` e `static/devices.js` devem acompanhar a atualização.

Pedidos antigos que já se sobrepõem não são apagados. A nova validação pode bloquear sua entrega: a TI deve cancelar o pedido pendente incorreto após conferir. Salas antigas continuam no histórico. O início solicitado de entregas anteriores pode ter sido sobrescrito pela versão antiga; esta atualização não reconstrói esses valores.

As verificações desta revisão são locais. Não executamos mutações ou testes em Turso/Vercel reais. Atualizações da branch conectada podem iniciar um deploy automático; o teste local não prova sucesso desse deploy. Persistem as limitações de áudio com navegador fechado/suspenso, senha compartilhada e pedidos para o mesmo dia.

---

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
