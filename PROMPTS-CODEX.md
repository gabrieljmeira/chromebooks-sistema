# Regras para continuar este projeto

Os prompts antigos descreviam atribuição automática e foram substituídos pelos requisitos atuais do usuário. Leia `README.md` e `REVISAO.md` antes de alterar o código.

1. Toda entrega é feita pela TI. Pedir agora e agendar criam pedidos pendentes.
2. Manter o escopo de horários no mesmo dia, no fuso de São Paulo, até solicitação explícita para ampliar.
3. Reservar capacidade por intervalo, considerando pedidos imediatos, agendamentos, empréstimos e atrasos. Revalidar na entrega real.
4. A TI escolhe os códigos na entrega e na devolução. Não voltar a atribuir códigos automaticamente ou aceitar devoluções somente por quantidade.
5. Preservar as operações atômicas, o índice de aparelho em uso e a proteção contra repetição. Acrescentar regressões significativas ao alterar regras.
6. Cancelar somente pedidos não entregues, preservando o histórico.
7. Não tratar os códigos legados como verdade. Manter o original, exigir conferência e registrar correções auditadas.
8. Alertar no próprio painel a cinco minutos do prazo e no prazo, apenas para empréstimos entregues e ainda abertos. Manter ativação/silenciamento, deduplicação e atualização sem perder formulários em edição. Não adicionar notificações do sistema operacional.
9. Manter Flask, SQL explícito e HTML/CSS/JS simples. Não adicionar frameworks, contas de professores ou serviços externos sem necessidade demonstrada.
10. Não publicar, fazer push, deploy, alterar bancos reais ou expor dados sem pedido do usuário. Testes remotos devem usar homologação autorizada.
11. Preservar `.env`, bancos e backups. Migrações devem ser repetíveis e sem exclusão de histórico. Não remover verificações TLS ou de pacotes.
12. Reportar somente os testes executados. Não repetir os números de outra conversa como prova da versão atual.

13. Usar apenas as 25 salas de `rooms.py`, incluindo **210**, nunca 2010. Validar catálogo no servidor.
14. Reservar a sala no intervalo de pedidos pendentes/ativos. Sobreposição deve retornar **SALA EM USO**, inclusive com estoque livre. Revalidar dentro da transação no pedido e na entrega, considerando antecipações e atrasos; devolução parcial não libera a sala.
15. Preservar início solicitado e horário real de entrega em campos distintos. Não renomear salas antigas nem reescrever horários sem evidência.
16. Histórico usa filtros no servidor sobre todo o banco e paginação de 50 registros. Preservar acesso às conferências legadas.
17. Manter a melhoria visual leve: sala e prazos em destaque, contador da seleção, estados claros e layouts móveis. Não substituir o projeto por outro framework.
