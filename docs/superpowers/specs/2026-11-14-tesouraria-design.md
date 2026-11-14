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
- **Fechamento do mês:** congela os números; o saldo final vira o inicial do mês
  seguinte.
- **Editar e excluir** lançamentos, com histórico de quem fez o quê e quando.
- **Relatório financeiro mensal em PDF** (e a mesma versão na tela), pronto para
  apresentar.

## Não objetivos (nesta entrega)

- Importar extrato do banco (OFX/CSV) ou integrar com banco ou Pix.
- Comprovante anexado ao lançamento (envolve privacidade do arquivo; fica para
  depois, ver "Para depois").
- Orçamento previsto contra realizado.
- Recibo ou declaração anual de dízimo para o membro.
- Mais de duas contas, mais de uma moeda, contabilidade de partidas dobradas.
- Cobrar ou receber pagamento pelo sistema.

## Anti-objetivos (seria falha mesmo funcionando)

- Qualquer número na tela que não bata com a soma dos movimentos.
- Contribuição "a confirmar" alterando saldo antes de confirmada.
- Alterar mês fechado sem deixar rastro.
- Excluir um lançamento sem rastro (a exclusão é lógica e fica no histórico).
- A Diretoria conseguir editar o caixa.
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
- **Categoria:** nome, tipo (entrada ou saída), ativa. "Oferta especial" é uma
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
- **A confirmar:** fila das contribuições do portal. Para cada uma: confirmar
  (escolhendo conta e forma, podendo ajustar a data) ou recusar (com motivo).
- **Lançamentos:** todos os movimentos, com filtros por mês, tipo, categoria,
  conta e forma, e histórico por lançamento.
- **Ofertas especiais:** total por destino, com os lançamentos de cada um.
- **Relatório:** relatório do mês na tela e em PDF; resumo do ano.
- **Configurações:** abertura (data e saldos) e categorias.
- **Histórico anterior:** lista somente leitura dos lançamentos antigos.

### Acesso

- **Tesoureiro** e **superusuário:** tudo.
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

1. Modelos, regras de saldo, ajustes de abertura e Caixa do Mês com lançamento
   de entrada, saída e depósito.
2. Fila "A confirmar" e mudança do portal.
3. Fechamento, conferência do caixa, histórico e ofertas especiais.
4. Relatório em PDF e na tela.
5. Acesso novo, remoção do Financeiro antigo e do menu, "Histórico anterior".
