# Controle de Chromebooks

Sistema de gestão de empréstimos de Chromebooks para uso em sala de aula. Centraliza os pedidos dos professores e permite à equipe de TI acompanhar a disponibilidade, registrar os equipamentos entregues e conferir cada devolução.

O inventário contempla **20 Chromebooks, de CH-001 a CH-020**. A entrega é realizada pela TI tanto nos pedidos imediatos quanto nos agendamentos.

## Como funciona

1. **Solicitação:** o professor informa nome, sala, quantidade e horário de devolução. Em **Pedir agora**, o início é imediato; em **Agendar entrega**, também informa a data e o horário em que precisará dos equipamentos. Antes do envio, confere o resumo e confirma o pedido.
2. **Disponibilidade:** o sistema verifica a ocupação da sala e a capacidade do inventário no intervalo solicitado.
3. **Entrega:** a TI atende o pedido e registra os códigos dos Chromebooks efetivamente entregues.
4. **Devolução:** a TI confere os equipamentos recebidos e registra a devolução parcial ou completa. O histórico preserva a movimentação.

Os agendamentos podem ser feitos para **hoje, amanhã ou depois de amanhã**, com horários no fuso **Brasília**. A entrega e a devolução acontecem na mesma data.

## Recursos

| Área | Recursos |
| --- | --- |
| Solicitações dos professores | Pedidos imediatos e agendados, seleção de sala, quantidade e período de uso |
| Painel da TI | Acompanhamento dos pedidos, seleção rápida dos aparelhos disponíveis em ordem numérica, entrega por código, devoluções parciais e controle de atrasos |
| Disponibilidade | Quantidade disponível exibida no formulário conforme o período, verificação de conflitos por sala e exclusão de equipamentos em manutenção |
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

O sistema impede que um mesmo Chromebook seja vinculado a dois empréstimos ativos.

## Alertas no painel

O painel acompanha os pedidos e emite avisos para novos pedidos, início de entregas agendadas e devoluções — cinco minutos antes do prazo e no vencimento.

Para ouvir os alertas, é necessário habilitar o som no navegador e manter o painel aberto, com o computador ativo. Os avisos sonoros dependem dessa sessão do navegador e não funcionam como notificações com a página fechada.
