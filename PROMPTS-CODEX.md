# Prompts do Codex — Controle de Chromebooks

> **Regra atual, alterada a pedido do usuário:** o professor registra a retirada diretamente, com baixa imediata de estoque e horário automático. Informa apenas a hora prevista para devolver no mesmo dia. A TI não aprova retiradas: acompanha o painel e registra a quantidade devolvida, incluindo devoluções parciais. Preserve essa regra ao usar os prompts abaixo; trechos sobre pedidos pendentes, confirmação de entrega ou ausência de devolução parcial descrevem o fluxo antigo e foram substituídos. Consulte o README para o funcionamento atual.

Abra a pasta do projeto no Codex. Execute estes prompts **em sequência**, conferindo as mudanças de cada etapa. Eles partem dos arquivos já incluídos; **não peça ao Codex para recomeçar do zero**. Faça commits entre etapas e nunca forneça credenciais reais no chat.

---

## Prompt 1 — Análise inicial e execução local

```text
Você está trabalhando neste repositório de um controle escolar de Chromebooks. Leia README.md e todos os arquivos existentes antes de editar. O objetivo é um MVP muito simples visualmente, usando Python 3.12+, Flask, HTML/CSS/JS vanilla, SQLite para testes locais e Turso remoto em produção na Vercel. Existem exatamente 20 Chromebooks numerados CH-001 a CH-020. Somente professores podem solicitar, mas o formulário é público, sem login. Só a TI acessa /admin mediante senha administrativa. Não adicione cadastro nem login para professores, nem React, Next.js, Bootstrap ou dependências visuais desnecessárias.
Primeiro analise problemas reais do código atual. Configure ou corrija as dependências e rode os testes locais, inicialize o banco em ambiente local isolado e verifique se as rotas têm sintaxe correta. Corrija erros sem reescrever o projeto. Ao final, liste os comandos exatos para iniciar no Windows e tudo que você efetivamente testou. Nunca diga que passou se não executou.
```

## Prompt 2 — Formulário público simples

```text
Aprimore a página pública /retirada já existente. Público: professores, sem qualquer login. Campos: nome do professor, quantidade entre 1 e 20 respeitando estoque disponível, sala, data/hora prevista de devolução; hora do envio automática pelo servidor. Use português do Brasil, layout limpo, responsivo, sem animações e acessível em celular. Depois do envio, mostrar confirmação apenas com número de protocolo, sem mostrar nomes de outros professores. Não adicione páginas nem complexidade sem necessidade.
Valide todos os campos no backend, recuse datas inválidas e quantidades acima do estoque e trate erros legíveis. Não permita ao formulário aprovar retiradas nem marcar devoluções. Preserve proteção CSRF e honeypot. Adicione testes de rota HTTP com Flask test_client para casos válidos e inválidos. Exiba exatamente os arquivos modificados.
```

## Prompt 3 — Painel da TI protegido

```text
Aprimore /admin, /admin/login e /admin/historico. O painel só pode ser acessado com senha administrativa armazenada exclusivamente como hash configurado em variável de ambiente ADMIN_PASSWORD_HASH. Use sessão assinada Flask, cookie HttpOnly, Secure em HTTPS, SameSite, CSRF nas ações e POST para operações que alteram dados. Nunca inclua senha fixa nem secrets no repositório. Login deve ser pequeno e direto, sem cadastro ou contas de professores.
No painel, mostrar 20 equipamentos no total, disponíveis, emprestados, solicitações pendentes e atrasos; listar pedidos com nome, sala, quantidade, horários e botões Confirmar entrega, Cancelar e Confirmar devolução. Quando a TI confirma, registrar hora REAL e atribuir automaticamente os códigos CH-001...CH-020 que estão livres. Histórico apenas na TI, com horários reais e previstos. Mantenha o visual discreto e limpo. Teste autorização: pessoa deslogada nunca acessa detalhes nem altera dados.
```

## Prompt 4 — Banco e consistência de estoque

```text
Revise database.py e services.py para garantir que nenhuma confirmação possa emprestar mais de 20 Chromebooks ou usar o mesmo equipamento em dois empréstimos ativos. Solicitações pendentes não reservam estoque; estoque só muda após confirmação da TI. Use transações atômicas com bloqueio/isolamento adequados e recuse confirmação se a disponibilidade mudou, sem comprometer outros registros. Para SQLite local, teste concorrência com duas confirmações simultâneas. Os códigos CH-001 a CH-020 são únicos e persistentes. Nunca apague o histórico ao devolver. Evite duplicação de registro ao clicar duas vezes. Adicione índices necessários sem ORM complexo. Mantenha funções claras e pequenas.
```

## Prompt 5 — Integração real Turso

```text
Implemente e valide de verdade o modo Turso remoto para produção serverless na Vercel, mantendo SQLite local durante o desenvolvimento. O projeto já usa turso_serverless, previsto para bancos Turso Database (engine nova, não libSQL). Consulte a documentação atual antes de mudar APIs ou versões. Confirme o formato de URL, transações BEGIN IMMEDIATE, commit/rollback, placeholders de SQL, last_insert_rowid e rows/cursor com o SDK real. Se houver incompatibilidade, corrija o adaptador e os serviços com alteração mínima. Não exponha TURSO_DATABASE_URL, TURSO_AUTH_TOKEN ou ADMIN_PASSWORD_HASH. Crie um script de smoke test que leia credenciais do ambiente e cheque inicialização, criação de pedido, confirmação, devolução e histórico sem alterar dados de produção sem permissão. Se não houver credenciais ou acesso à rede, reporte claramente o que não foi testado e forneça o procedimento para eu validar.
```

## Prompt 6 — Testes de segurança e casos extremos

```text
Adicione testes automatizados para fluxos e segurança: /retirada público e sem login; /admin exige autenticação; senha errada falha; ações administrativas com CSRF; entrada malformada; HTML escapado; quantidades 0/21; devolução passada; alterações indevidas; dupla confirmação; dupla devolução; disponibilidade depois da devolução; dois professores tentando levar mais unidades do que restam. Adicione rate limiting compartilhado/persistente ao formulário público e à tentativa de senha, compatível com múltiplas instâncias serverless, sem guardar IP completo indefinidamente. Não use estado global em memória como única proteção. Crie comandos de execução e reporte os testes realmente executados. Preserve interface leve.
```

## Prompt 7 — Publicação Vercel e QR Code

```text
Prepare este Flask app para deploy na Vercel seguindo a documentação ATUAL da Vercel para Python/Flask. Não converta o backend para Node. A Vercel reconhecerá app.py, então só adicione vercel.json se de fato necessário. Configure variáveis SECRET_KEY, ADMIN_PASSWORD_HASH, TURSO_DATABASE_URL e TURSO_AUTH_TOKEN como env vars; nunca crie credenciais fictícias que pareçam reais e nunca faça commit de .env. Garanta que nenhum SQLite local seja usado em produção serverless e que não haja dependência de armazenamento persistente no filesystem da Vercel. Atualize README.md com passos de GitHub→Vercel, init de banco remoto, smoke test após deploy, domínio HTTPS e geração de QR Code apontando SOMENTE para /retirada. Respeite as condições de uso do plano contratado. Não publique automaticamente sem minha autorização.
```

## Prompt 8 — Revisão final e entrega para escola

```text
Faça uma revisão final do projeto sem aumentar sua complexidade ou ornamentação: português claro, tipografia padrão, cartões discretos, responsividade, bom contraste e mensagens de erro úteis. Confira o fluxo completo: professor solicita sem login → TI entra com senha → confirma entrega → sistema associa Chromebooks livres → TI registra devolução → histórico permanece. Registre as limitações: sem rastreio de qual técnico operou (senha compartilhada), sem devolução parcial, necessidade de supervisão física, backups e política de proteção dos dados dos professores. Produza um CHECKLIST-PUBLICACAO.md para entregar à equipe de TI e rode toda a suíte de testes. Só declare recursos concluídos se funcionarem e estiverem testados.
```

---

### Prompt extra opcional — melhorias futuras (somente depois do MVP)

```text
Agora que o MVP foi aprovado, proponha melhorias PEQUENAS e opcionais para a TI: pesquisa e filtros por nome/data/sala, exportação CSV somente para TI, registro individual de equipamento com defeito e possibilidade de devolução parcial. Antes de implementar, liste impacto na base de dados, riscos, necessidade de migração e qual mudança entrega maior valor. NÃO adicione tudo sem eu escolher.
```
