# Área da Tesouraria: livro-caixa do mês para o tesoureiro

Data: 2026-11-14. Estado: aguardando aprovação.

## Intenção

Hoje o tesoureiro só consegue **registrar** lançamentos no sistema. O resto da
rotina dele (fechar o caixa do mês, separar dinheiro de Pix, saber o saldo do
caixa e o do banco, apresentar um relatório) acontece fora daqui, em caderno,
planilha ou extrato.

A Tesouraria é uma área própria, só para essa rotina. O objetivo é que ele abra
o mês, lance entradas e saídas, confira o caixa, feche o mês e imprima o
relatório sem sair do sistema, e que os saldos **sempre fechem**.

O pedido é por ferramentas novas para o tesoureiro. Sigilo não é o motivo. O
acesso restrito é consequência, não objetivo.

## Decidido com o Washington

- **Duas contas:** Caixa (dinheiro físico) e Banco. O saldo total é a soma.
- **Entrada em dinheiro** vai para o Caixa. **Entrada por Pix** vai para o Banco.
- **Saída** sai do Caixa ou do Banco, à escolha dele no lançamento.
- **Depósito** (Caixa para Banco) não é entrada nem saída: só muda o dinheiro de
  lugar entre as contas.
- **Contribuições feitas no portal** do membro chegam como **"a confirmar"**. O
  tesoureiro compara com o extrato, escolhe conta e forma e confirma. Só depois
  contam nos saldos. Hoje elas entram direto, sem conferência.
- **Abordagem B:** livro-caixa novo e separado, não uma evolução da tabela de
  lançamentos atual.
- **O menu "Financeiro" sai do painel principal.**
- **Categorias:** o tesoureiro **cria, edita e exclui**. Com lançamentos, a
  categoria não é apagada: é arquivada (ver regras).
- **Comissão de Contas** audita as contas. Precisa de acesso próprio de leitura
  (ver "Acesso"). Os detalhes (somente leitura e parecer por mês fechado) são
  proposta minha, ainda não confirmada por ele.
- **Contas a pagar:** o tesoureiro quer **controlar** o que vence e pagar por
  aqui (registrando o pagamento), sem integração bancária. Há contas **que se
  repetem todo mês** (luz, água, internet, aluguel) e contas parceladas.
- O tesoureiro pediu: Caixa do Mês, entradas (dízimos e ofertas), saídas, saldo
  do caixa, saldo do banco, total de dinheiro, total de Pix, ofertas especiais
  e relatório financeiro. Pediu também sugestões.

## Objetivos

- Tela **Caixa do Mês** com o resumo do mês e os movimentos dele.
- Entradas por categoria: dízimos, ofertas e **ofertas especiais** (com destino,
  somadas à parte).
- Entradas separadas por forma: **em dinheiro** e **por Pix**.
- Saídas por categoria.
- **Saldo do Caixa, saldo do Banco e saldo total**, sempre calculados do mesmo
  jeito e coerentes entre telas e relatório.
- **Fila "A confirmar"** para as contribuições do portal.
- **Conferência do caixa:** ele informa quanto contou, o sistema mostra a
  diferença para o saldo calculado.
- **Conta a pagar:** descrição, beneficiário, categoria de saída, valor
  previsto, vencimento, situação (em aberto, paga, cancelada), recorrência de
  origem (opcional) e, quando paga, o movimento de saída que ela gerou, o valor
  pago, a data e a conta.
- **Conta recorrente (modelo):** descrição, beneficiário, categoria, valor
  estimado, dia do vencimento, data de início, **número de parcelas** (vazio =
  sem fim), ativa. Cada mês ganha a sua **conta a pagar** a partir dele.
- **Parecer da Comissão de Contas:** mês fechado, resultado (aprovado ou
  aprovado com ressalvas), texto, autor, data. Um por comissário por mês; pode
  ser substituído, e a troca fica no histórico.
- **Fechamento do mês:** congela os números; o saldo final vira o inicial do mês
  seguinte.
- **Editar e excluir** lançamentos, com histórico de quem fez o quê e quando.
- **Categorias** criadas, editadas, arquivadas e excluídas por ele.
- **Contas a pagar** com vencimento, alerta de vencidas e a vencer, e botão
  **Pagar**, que gera a saída no caixa. Contas **recorrentes mensais** e
  **parceladas** se renovam sozinhas, sem ele recadastrar.
- **Perfil da Comissão de Contas**, só leitura, com **parecer por mês fechado**.
- **Relatório financeiro mensal em PDF** (e a mesma versão na tela), pronto para
  apresentar.

## Não objetivos (nesta entrega)

- Importar extrato do banco (OFX/CSV) ou integrar com banco ou Pix.
- Comprovante anexado ao lançamento (envolve privacidade do arquivo; fica para
  depois, ver "Para depois").
- Orçamento previsto contra realizado.
- Recibo ou declaração anual de dízimo para o membro.
- Mais de duas contas, mais de uma moeda, contabilidade de partidas dobradas.
- Cobrar ou receber pagamento pelo sistema, ou **pagar de verdade** (Pix, boleto)
  a partir daqui: "pagar" significa registrar o pagamento já feito.
- Fluxo de **autorização** de despesa (pastor ou Diretoria aprovando antes de
  pagar).
- Aviso automático (e-mail ou push) de conta a vencer: não há agendador.

## Anti-objetivos (seria falha mesmo funcionando)

- Qualquer número na tela que não bata com a soma dos movimentos.
- Contribuição "a confirmar" alterando saldo antes de confirmada.
- Alterar mês fechado sem deixar rastro.
- Excluir um lançamento sem rastro (a exclusão é lógica e fica no histórico).
- A Diretoria ou a Comissão de Contas conseguirem editar o caixa.
- Uma conta paga e o caixa mostrarem valores diferentes.
- A recorrência gerar a mesma conta duas vezes no mesmo mês.
- Perder o histórico financeiro que já existe.

## Restrições

- Django 6, Python 3.14. SQLite em desenvolvimento, Postgres (Neon) em produção.
  As migrações precisam rodar nos dois.
- Valores em `Decimal`, duas casas. Nunca `float`.
- Sem tarefas agendadas (Vercel e Render gratuitos): nada pode depender de cron.
  Fechamento e saldos são calculados na hora ou no fechamento manual.
- O PDF usa `reportlab`, que já é dependência (certificados).
- Padrão visual do painel (fichas, faixa de resumo, listas, formulários com
  prévia) e acessibilidade já adotados.

## Abordagens consideradas

1. **A. Evoluir a tabela de lançamentos atual.** Menor e mais segura, mas mistura
   o histórico sem conta/forma com o modelo novo e prende o desenho ao que já
   existe. Não escolhida.
2. **B. Livro-caixa novo e separado (escolhida pelo Washington).** Modelo limpo,
   saldos calculados de uma fonte só. Custo: trabalho maior e um período em que
   convivem a tabela antiga (somente leitura) e a nova.
3. Só relatórios sobre os dados atuais: descartada, pois sem conta e forma de
   pagamento os saldos de caixa e banco não existem para calcular.

## Desenho

### Modelos novos (app `core`, ou app `tesouraria` a critério do construtor)

- **Ajustes da Tesouraria** (um registro só): data de início e saldos de
  abertura do Caixa e do Banco. Só o que for **a partir dessa data** conta nos
  saldos.
- **Categoria:** nome, tipo (entrada ou saída), ativa (arquivada quando
  inativa). "Oferta especial" é uma
  categoria de entrada marcada como especial. Vêm criadas: Dízimos, Ofertas,
  Ofertas especiais; saídas a definir com ele (ver "Calls do construtor").
- **Movimento:** data, tipo (entrada ou saída), valor, categoria, descrição,
  conta (Caixa ou Banco; vazia enquanto "a confirmar"), forma (dinheiro, Pix ou
  outra), situação (a confirmar, confirmado, recusado), origem (tesouraria ou
  portal), membro (opcional), destino (texto, só para oferta especial), criado
  por, criado e alterado em, exclusão lógica.
- **Transferência:** data, conta de origem, conta de destino, valor, observação.
  Depósito é Caixa para Banco; saque é Banco para Caixa.
- **Fechamento do mês:** mês, saldos iniciais e finais gravados, valor contado no
  caixa (opcional), diferença, quem fechou e quando, observação.
- **Histórico (auditoria):** quem, quando, ação (criou, editou, excluiu,
  confirmou, recusou, fechou, reabriu) e o antes e o depois.

### Regras de saldo (uma função só, usada por todas as telas e pelo PDF)

- Saldo da conta em uma data = saldo de abertura + entradas confirmadas na conta
  − saídas da conta + transferências que entram − transferências que saem, para
  movimentos a partir da data de início e até a data.
- Movimentos "a confirmar" e "recusado" **não** entram em saldo nenhum.
- Saldo total = Caixa + Banco.
- **Entradas em dinheiro** e **entradas por Pix** do mês são fluxos do mês (soma
  das entradas confirmadas por forma), não saldos.
- Lançar antes da data de início é bloqueado. Lançar em mês fechado é bloqueado;
  reabrir é uma ação explícita do tesoureiro e fica no histórico.
- Saldo de Caixa negativo gera aviso, não bloqueio.

### Categorias

- Criar e editar livremente. Nome único por tipo.
- **Excluir:** só se nenhum movimento, conta a pagar ou recorrência usa a
  categoria. Se usa, a ação oferece **arquivar** (some das escolhas novas e
  continua nos relatórios antigos). Arquivada pode ser reativada.
- Ofertas especiais seguem como categoria de entrada marcada como especial.

### Contas a pagar

- Conta em aberto **não altera saldo**. Vencida é a de vencimento anterior a
  hoje; a vencer, as demais em aberto.
- **Pagar** pede: valor pago (padrão = valor previsto, pode ter multa ou
  desconto), data, conta (Caixa ou Banco) e forma. Em uma única operação cria a
  saída confirmada e marca a conta paga. Se algo falhar, nada fica pela metade.
- **Desfazer pagamento** é permitido enquanto o mês estiver aberto: cancela a
  saída e volta a conta para "em aberto", com histórico.
- Editar e **cancelar** conta em aberto. Conta paga só se altera desfazendo o
  pagamento. Nada é apagado de verdade; o cancelamento fica no histórico.
- **Recorrência sem agendador:** ao abrir a Tesouraria ou uma tela de mês, o
  sistema garante, de forma idempotente (uma conta por recorrência por mês), as
  contas daquele mês e do seguinte. O valor nasce igual ao estimado; o
  tesoureiro ajusta o valor da conta do mês antes de pagar (luz e água variam).
- **Parcelada** é uma recorrência com número de parcelas: cada conta mostra
  "3/10" e a série termina sozinha.
- No Caixa do Mês: vencimentos do mês, total já pago, total ainda a pagar e o
  **saldo depois de pagar o que falta** (saldo total menos as contas em aberto
  do mês).

### Regras de borda (minhas decisões)

- **Fechar o mês** é bloqueado enquanto houver contribuição "a confirmar" com
  data dentro dele: o tesoureiro precisa confirmar ou recusar cada uma. Os
  meses se fecham em ordem, sem pular.
- **Confirmar uma contribuição** cuja data cai em mês já fechado exige trocar a
  data para um mês aberto; o formulário avisa e não deixa salvar sem isso.
- **Data de início e saldos de abertura** só podem ser alterados enquanto nenhum
  mês tiver sido fechado.
- O autor de uma contribuição vinda do portal é o usuário do membro, no
  histórico.
- Recusar exige um motivo curto, que o membro enxerga no portal.

### Telas (menu próprio da Tesouraria)

- **Caixa do Mês** (início): seletor de mês, faixa com saldo anterior, entradas,
  saídas, saldo do Caixa, saldo do Banco e saldo total; blocos de dinheiro contra
  Pix e de ofertas especiais por destino; lista dos movimentos; ações Nova
  entrada, Nova saída, Depósito, Conferir caixa, Fechar mês.
- **Contas a pagar:** abas Vencidas, A vencer e Pagas, com total de cada uma;
  nova conta, editar, cancelar, **Pagar** e desfazer pagamento; cadastro das
  recorrentes e parceladas.
- **A confirmar:** fila das contribuições do portal. Para cada uma: confirmar
  (escolhendo conta e forma, podendo ajustar a data) ou recusar (com motivo).
- **Lançamentos:** todos os movimentos, com filtros por mês, tipo, categoria,
  conta e forma, e histórico por lançamento.
- **Ofertas especiais:** total por destino, com os lançamentos de cada um.
- **Relatório:** relatório do mês na tela e em PDF; resumo do ano.
- **Configurações:** abertura (data e saldos) e **categorias** (criar, editar,
  arquivar, excluir).
- **Parecer** (aparece no Caixa do Mês e no Relatório de um mês fechado): a
  Comissão registra o seu; todos os que têm acesso leem.
- **Histórico anterior:** lista somente leitura dos lançamentos antigos.

### Acesso

- **Tesoureiro** e **superusuário:** tudo.
- **Comissão de Contas** (perfil novo): leitura de tudo da Tesouraria (Caixa do
  Mês, lançamentos, contas a pagar, fechamentos, conferências, relatórios e o
  **histórico completo de alterações**), mais o **parecer** por mês fechado.
  Não vê "A confirmar" para agir nem edita nada. Vê o membro de cada
  contribuição? Proposta: **sim**, pois auditar dízimo exige conferir a origem;
  Diretoria **não** vê o nome do membro, só o total.
- **Diretoria (Admin):** somente leitura em Caixa do Mês e Relatório.
- **Secretário, Diácono, Pastor, membros:** sem acesso.
- O Tesoureiro, ao entrar, cai direto na Tesouraria e tem um atalho "Ir para o
  painel" (continua sendo um perfil administrativo da igreja). Para Diretoria e
  superusuário, aparece um atalho "Tesouraria" na barra do topo, sem item no
  menu lateral do painel.

### Portal do membro

- A contribuição declarada cria um movimento de **entrada** com situação "a
  confirmar" e sem conta. O membro vê "aguardando confirmação" até o tesoureiro
  agir; o total de contribuições do portal conta só as confirmadas.
- O texto do portal (que já avisa que não há cobrança bancária) continua valendo.

### Migração do que existe

- A tabela antiga de lançamentos **não é migrada** para o livro novo: não tem
  conta nem forma, então qualquer atribuição seria chute. Ela fica intacta e
  somente leitura, em "Histórico anterior".
- O tesoureiro informa a data de início e os saldos de abertura reais do Caixa e
  do Banco; a partir dela o livro novo vale.
- Saem: a página Financeiro e seu item de menu, a tela de novo lançamento antigo,
  o bloco "Saldo do período" do início do painel e os números financeiros de
  Relatórios. Saem junto `financial_access_required`, `can_access_finance` e
  `show_finances`, trocados pelas permissões novas.

## Acréscimo do Washington (14/11, depois da aprovação)

O nome do membro **precisa ficar gravado** em cada contribuição, para a igreja
ter a **relação de dizimistas** (membros que devolvem dízimo). A máscara para a
Diretoria é só de exibição. A relação é uma tela própria, visível ao tesoureiro
e à Comissão, e a categoria de dízimo é marcada como tal.

## Calls minhas (conferir)

1. Acesso da Diretoria **somente leitura** e fim do acesso de Secretário e
   Diácono ao financeiro.
2. Tesoureiro cai direto na Tesouraria ao entrar; Diretoria e superusuário
   acessam por atalho no topo.
3. "Total de dinheiro" entendido como **entradas em dinheiro do mês**. O saldo
   somado das duas contas aparece como "Saldo total".
4. Tabela antiga **não migrada**, só consultável; saldos de abertura informados
   por ele.
5. Saque (Banco para Caixa) permitido, além do depósito.
6. Comprovante anexado **fora** desta entrega.
8. **Comissão de Contas:** perfil novo, somente leitura, com parecer por mês
   fechado, e vê o nome do membro nas contribuições (a Diretoria não).
9. **Recorrência calculada ao abrir a tela**, não por agendador, e parcelada
   tratada como recorrência com fim.
10. **Categoria com uso é arquivada, não apagada.**
11. Sem fluxo de autorização de despesa nesta entrega.
7. Exclusão é lógica (some das listas, fica no histórico).

## Para depois

Comprovante anexado (decidir antes onde o arquivo fica guardado e quem o vê),
importação de extrato, orçamento previsto contra realizado, declaração anual de
dízimo ao membro, notificar o tesoureiro quando chegar contribuição nova.

## Calls do construtor

- Lista inicial de categorias de saída (sugestão: Água e luz, Manutenção,
  Missões, Ajuda social, Material, Outros), editável pelo tesoureiro.
- Se os modelos ficam em app novo ou em `core`.
- Layout do PDF dentro do padrão da igreja, incluindo linhas de assinatura.
- Textos de interface, estados vazios e mensagens, no tom do resto do painel.

## Entrega em etapas (para o plano)

1. Modelos, regras de saldo, categorias (criar, editar, arquivar, excluir),
   ajustes de abertura e Caixa do Mês com entrada, saída e depósito.
2. Contas a pagar: cadastro, pagar e desfazer, vencidas e a vencer, saldo
   depois de pagar o que falta.
3. Recorrentes e parceladas, com geração idempotente.
4. Fila "A confirmar" e mudança do portal.
5. Fechamento, conferência do caixa, histórico de alterações e ofertas
   especiais.
6. Perfil da Comissão de Contas e parecer por mês fechado.
7. Relatório em PDF e na tela.
8. Acesso novo, remoção do Financeiro antigo e do menu, "Histórico anterior".
