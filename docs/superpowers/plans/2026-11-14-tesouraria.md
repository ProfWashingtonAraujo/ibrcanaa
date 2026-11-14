# Tesouraria Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao tesoureiro uma área própria (`/tesouraria/`) com livro-caixa de duas contas (Caixa e Banco), contas a pagar recorrentes, fila de contribuições a confirmar, fechamento do mês e relatório em PDF, e dar à Comissão de Contas um acesso de leitura com parecer por mês.

**Architecture:** App Django novo `tesouraria`, com modelos próprios e a regra de saldo em **uma só função** (`balances.py`), usada por telas e PDF. As telas reaproveitam o layout `admin_base.html` do painel, parametrizado por um contexto `shell`. A tabela antiga `core.Transaction` fica intacta e só de leitura. O Financeiro antigo só é removido na última tarefa, junto com a troca do portal, para o tesoureiro nunca ficar sem ferramenta.

**Tech Stack:** Django 6, Python 3.14, SQLite (dev) e Postgres/Neon (produção), `reportlab` (já instalado), crispy-forms bootstrap5, CSS único em `static/css/app.css`.

**Spec:** `docs/superpowers/specs/2026-11-14-tesouraria-design.md`

## Global Constraints

- Django 6, Python 3.14. Migrações devem rodar em SQLite e em Postgres.
- Valores sempre `Decimal` com duas casas. Nunca `float`.
- Sem agendador (Vercel e Render gratuitos): nada pode depender de cron.
- PDF só com `reportlab`; nenhuma dependência nova.
- Padrão visual e de acessibilidade já adotados no painel: fichas com cabeçalho de perfil, `stat-row`, listas `week-list`, formulários com `form-layout`, foco visível, rótulos de campo obrigatório, textos em português do Brasil.
- Exclusão sempre lógica (`deleted_at`); nada é apagado de verdade, exceto categoria sem uso.
- Contribuição "a confirmar" ou "recusada", movimento excluído e movimento anterior à data de início **nunca** entram em saldo.
- Lançar, editar, excluir, confirmar ou pagar em mês fechado é bloqueado no servidor, não só escondido na tela.
- Diretoria e Comissão são somente leitura. **Diretoria só abre o Caixa do Mês e o Relatório** e **não** vê o nome do membro (nem na descrição); a **Comissão abre todas as telas de leitura** e vê o nome.
- Rodar testes com: `DJANGO_DEBUG=True python manage.py test tesouraria`.

## Review Focus

1. Saldo errado por incluir o que não devia: pendente, recusado, excluído, anterior à data de início, ou depósito contado como entrada. Esperado: só confirmados, vivos e a partir do início; depósito move o saldo sem entrar em entradas nem saídas. (Task 3)
2. Vencimento dia 29, 30 ou 31 em mês curto, e parcelada que passa da última parcela. Esperado: vence no último dia do mês; a série para na última parcela; abrir a tela duas vezes não duplica. (Task 9)
3. Alterar mês fechado adivinhando a URL (editar, excluir, desfazer pagamento, confirmar contribuição datada no mês). Esperado: bloqueio no servidor com mensagem clara. (Tasks 6, 7, 8, 10)
4. Perfil somente leitura enviando POST direto. Esperado: 403 em toda ação de escrita para Diretoria e Comissão. (Task 12)
5. Nome do membro vazando para a Diretoria pela **descrição** do portal ("Dízimo via portal - Ana"), pelo relatório, pelo PDF ou pelo histórico. Esperado: texto neutro "Dízimo (contribuição de membro)". (Tasks 6, 12, 13)
6. Pagar uma conta com falha no meio (saída criada, conta não marcada). Esperado: tudo ou nada. (Task 8)

---

## File Structure

```
tesouraria/
  apps.py  __init__.py  admin.py  urls.py
  models.py            # modelos e enums
  permissions.py       # perfis, decoradores, landing_url, visibilidade de nomes
  visibility.py        # description_for(movement, user)
  audit.py             # record(), snapshot(), constantes de ação
  rules.py             # TreasuryError e guardas de mês e de data de início
  balances.py          # account_balance, opening_balance, month_summary
  payables.py          # pay_payable, undo_payment, cancel_payable
  recurring.py         # due_date_for, ensure_recurring
  pending.py           # create_portal_contribution, confirm_pending, reject_pending
  closing.py           # record_cash_count, close_month, reopen_month
  report.py            # build_report_context, render_report_pdf
  navigation.py        # build_treasury_nav
  context_processors.py
  forms.py  views.py
  templates/tesouraria/*.html
  migrations/
  tests/{helpers.py, test_*.py}
```

Rotas (namespace `tesouraria`, prefixo `/tesouraria/`): `home` (Caixa do Mês, `?mes=AAAA-MM`), `settings`, `categories`, `category_create`, `category_edit`, `category_delete`, `category_reactivate`, `movements`, `movement_create` (`?tipo=income|expense`), `movement_edit`, `movement_delete`, `transfer_create`, `transfer_delete`, `pending`, `pending_confirm`, `pending_reject`, `payables`, `payable_create`, `payable_edit`, `payable_pay`, `payable_undo`, `payable_cancel`, `recurring`, `recurring_create`, `recurring_edit`, `recurring_toggle`, `special`, `audit`, `cash_count`, `month_close`, `month_reopen`, `opinion`, `report`, `report_pdf`, `legacy`.

---

### Task 1: App, perfil Comissão de Contas e permissões

**Files:**
- Create: `tesouraria/{__init__,apps,permissions,urls}.py`, `tesouraria/tests/{__init__,helpers}.py`, `tesouraria/tests/test_permissions.py`
- Modify: `core/models.py` (Role), `config/settings.py` (INSTALLED_APPS), `config/urls.py`, `core/views.py` (`login_view`), nova migração em `core/migrations/`

**Interfaces:**
- Produces: `AccessProfile.Role.COMMITTEE = 'committee', 'Comissão de Contas'` (fora de `ADMIN_ROLES`, então `is_staff` fica falso).
- Produces em `tesouraria/permissions.py`: `can_edit_treasury(user) -> bool` (superusuário ou TREASURER), `can_view_treasury(user) -> bool` (editar, ou BOARD, ou COMMITTEE; vale para Caixa do Mês e Relatório), `can_view_details(user) -> bool` (editar ou COMMITTEE; vale para Lançamentos, Contas a pagar, Ofertas especiais, Histórico e Histórico anterior), `can_give_opinion(user) -> bool` (só COMMITTEE), `can_see_member_names(user) -> bool` (editar ou COMMITTEE), `landing_url(user) -> str`, decoradores `treasury_view_required`, `treasury_detail_required`, `treasury_edit_required`, `committee_required` (anônimo vai ao login; logado sem permissão recebe 403).
- Produces em `tesouraria/tests/helpers.py`: `make_user(username, role=None, *, is_staff=None, is_superuser=False) -> User` (`is_staff` padrão = `role in ADMIN_ROLES`), `configure(start=date(2026, 1, 1), cash='0.00', bank='0.00')` (cria `TreasurySettings`, definido na Task 2).

- [ ] **Step 1: Escrever os testes** em `test_permissions.py`: `test_matrix` com `subTest` por perfil e as asserções `can_edit_treasury`: tesoureiro e superusuário `True`, BOARD/COMMITTEE/DEACON/SECRETARY/PASTOR/MEMBER `False`; `can_view_treasury`: tesoureiro, BOARD, COMMITTEE, superusuário `True`, DEACON/SECRETARY/PASTOR/MEMBER `False`; `can_view_details`: tesoureiro, COMMITTEE, superusuário `True`, BOARD/DEACON/SECRETARY/PASTOR/MEMBER `False`; `can_see_member_names`: tesoureiro e COMMITTEE `True`, BOARD `False`. `test_committee_is_not_panel_user`: `core.permissions.is_panel_user(make_user('c', Role.COMMITTEE)) is False` e `user.is_staff is False`. `test_landing_url`: tesoureiro e comissão `reverse('tesouraria:home')`; BOARD `reverse('dashboard')`; membro `reverse('member_portal')`. `test_login_redirects_by_role`: POST no `login` com cada perfil leva ao `landing_url`.
- [ ] **Step 2: Rodar e ver falhar**: `DJANGO_DEBUG=True python manage.py test tesouraria.tests.test_permissions` → falha de importação.
- [ ] **Step 3: Implementar** o app (`urls.py` com `app_name = 'tesouraria'` e uma rota `home` provisória que devolve 200), o `Role.COMMITTEE` com `makemigrations core`, os predicados e decoradores acima baseados em `core.permissions.get_role`, e `landing_url`. Em `core/views.py`, `login_view` passa a redirecionar para `landing_url(user)` nos dois pontos. Incluir `path('tesouraria/', include('tesouraria.urls'))` antes de `core.urls`.
- [ ] **Step 4: Rodar a suíte** `DJANGO_DEBUG=True python manage.py test` → tudo passa (inclusive `core`).
- [ ] **Step 5: Commit** `feat(tesouraria): app, perfil Comissão de Contas e permissões`

### Task 2: Modelos, auditoria e categorias iniciais

**Files:**
- Create: `tesouraria/models.py`, `tesouraria/audit.py`, `tesouraria/visibility.py`, `tesouraria/migrations/0001_initial.py`, `0002_default_categories.py`, `tesouraria/tests/test_models.py`

**Interfaces:**
- Produces (enums em `models.py`): `Account{CASH='cash','Caixa'; BANK='bank','Banco'}`, `Method{CASH='cash','Dinheiro'; PIX='pix','Pix'; OTHER='other','Outra'}`, `Kind{INCOME='income','Entrada'; EXPENSE='expense','Saída'}`, `Status{PENDING='pending','A confirmar'; CONFIRMED='confirmed','Confirmado'; REJECTED='rejected','Recusado'}`, `Source{TREASURY='treasury','Tesouraria'; PORTAL='portal','Portal'}`.
- Produces modelos: `TreasurySettings(start_date, opening_cash, opening_bank)` com `@classmethod get() -> TreasurySettings | None` (registro único, `pk=1`); `Category(name max 80, kind, is_special, active)` com `unique(name, kind)` e `in_use() -> bool`; `Movement(date, kind, amount, category FK PROTECT, description max 180, account null, method, status, source, member FK null SET_NULL, destination max 120 blank, created_by FK null, rejection_reason blank, deleted_at null, created_at, updated_at)` com `Movement.objects.live()` e `.confirmed()`; `Transfer(date, from_account, to_account, amount, note, created_by, deleted_at)` com `clean()` (origem diferente de destino, valor maior que zero); `MonthClosing(month unique, counted_cash null, counted_by null, counted_at null, closed_at null, closed_by null, opening_cash null, opening_bank null, closing_cash null, closing_bank null, notes)` com `is_closed` (propriedade: `closed_at is not None`).
- Produces `audit.py`: constantes `CREATE, UPDATE, DELETE, CONFIRM, REJECT, PAY, UNDO_PAY, CANCEL, CLOSE, REOPEN, COUNT, OPINION, SETTINGS, ARCHIVE`; `snapshot(obj) -> dict` (valores seguros para JSON: `Decimal` e datas como texto); `record(user, action: str, obj, summary: str, before: dict | None = None, after: dict | None = None) -> AuditLog`. **`summary` nunca contém nome de membro nem descrição**: padrão `"Entrada de R$ 120,00 em Dízimos"`.
- Produces `visibility.py`: `description_for(movement, user) -> str`: devolve a descrição se `can_see_member_names(user)` ou se o movimento não tem `member`; senão `f"{category.name} (contribuição de membro)"`.

- [ ] **Step 1: Escrever os testes** em `test_models.py`: `test_settings_get_returns_none_until_configured`; `test_category_unique_per_kind` (mesmo nome em entrada e saída é permitido; duplicado no mesmo tipo levanta `IntegrityError`); `test_default_categories_exist` (migração criou Dízimos, Ofertas, "Ofertas especiais" com `is_special=True`, e saídas Água e luz, Manutenção, Missões, Ajuda social, Material, Outros); `test_movement_live_excludes_deleted`; `test_transfer_rejects_same_account_and_non_positive`; `test_audit_snapshot_serialises_decimal_and_date`; `test_description_for_masks_member_movements` (Diretoria recebe `"Dízimos (contribuição de membro)"`, Comissão e tesoureiro recebem a descrição, movimento sem membro mostra a descrição para todos).
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** os modelos e as duas migrações (a segunda é `RunPython` idempotente com `get_or_create`). `Category.in_use()` verifica `movement_set`; as Tasks 8 e 9 estendem para contas a pagar e recorrentes.
- [ ] **Step 4: Rodar** `test_models` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): modelos, auditoria e categorias iniciais`

### Task 3: Regras de data e função única de saldo

**Files:**
- Create: `tesouraria/rules.py`, `tesouraria/balances.py`, `tesouraria/tests/test_balances.py`

**Interfaces:**
- Consumes: modelos da Task 2.
- Produces em `rules.py`: `class TreasuryError(Exception)` (mensagem em português); `class MonthClosed(TreasuryError)`; `class BeforeStart(TreasuryError)`; `class NotConfigured(TreasuryError)`; `month_start(d: date) -> date`; `ensure_after_start(d: date) -> None`; `ensure_month_open(d: date) -> None`.
- Produces em `balances.py`: `account_balance(account: str, on: date) -> Decimal`; `opening_balance(account: str, month: date) -> Decimal`; `total_balance(on: date) -> Decimal`; `@dataclass(frozen=True) class MonthSummary` com `month`, `opening_cash`, `opening_bank`, `income_total`, `expense_total`, `income_by_category: list[tuple[Category, Decimal]]`, `expense_by_category`, `special_by_destination: list[tuple[str, Decimal]]`, `income_cash`, `income_pix`, `income_other`, `deposits_to_bank`, `withdrawals_to_cash`, `closing_cash`, `closing_bank`, `closing_total`, `payables_open_total`, `payables_paid_total`, `projected_total`, `counted_cash: Decimal | None`, `cash_difference: Decimal | None`, `is_closed: bool`; `month_summary(month: date) -> MonthSummary`.
- Regras: saldo = abertura + entradas confirmadas na conta − saídas da conta + transferências que entram − transferências que saem, só movimentos vivos com data entre `start_date` e `on`. `opening_balance` do mês de `start_date` é a abertura cadastrada; dos demais é `account_balance(account, month_start - 1 dia)`. `income_*` por forma somam só entradas confirmadas.

- [ ] **Step 1: Escrever os testes** em `test_balances.py` com `configure(start=date(2026,11,1), cash='1000', bank='5000')`: `test_opening_only` (saldo de caixa e banco no dia 1 = abertura); `test_income_cash_goes_to_cash_pix_to_bank` (entrada dinheiro 200 no caixa, Pix 300 no banco: caixa 1200, banco 5300); `test_expense_reduces_chosen_account`; `test_deposit_moves_without_income_or_expense` (depósito 400: caixa 800, banco 5400, `income_total` e `expense_total` inalterados, `deposits_to_bank == 400`); `test_withdrawal_banco_para_caixa`; `test_pending_rejected_deleted_do_not_count`; `test_before_start_date_ignored`; `test_total_is_cash_plus_bank`; `test_month_summary_splits_cash_and_pix_and_special_by_destination` (duas ofertas especiais em destinos "Missões" e "Obra", outra em "Missões": `special_by_destination == [('Missões', soma), ('Obra', x)]` ordenado por valor decrescente); `test_second_month_opening_is_previous_closing`; `test_ensure_month_open_and_after_start_raise`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** `rules.py` e `balances.py`. Uma única consulta agregada por conta; `month_summary` chama `account_balance`/`opening_balance`, nunca recalcula saldo por conta própria. Campos de contas a pagar e de conferência ficam `Decimal('0')` e `None`/`False` até as Tasks 8 e 10.
- [ ] **Step 4: Rodar** `test_balances` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): regras de data e saldo único`

### Task 4: Casca da Tesouraria e tela Caixa do Mês (leitura)

**Files:**
- Create: `tesouraria/{navigation,context_processors,views,forms}.py`, `tesouraria/templates/tesouraria/{home,not_configured}.html`, `tesouraria/tests/test_shell.py`
- Modify: `templates/core/admin_base.html` (parâmetros de `shell`), `config/settings.py` (registrar o processador), `tesouraria/urls.py`, `static/css/app.css`

**Interfaces:**
- Consumes: `can_view_treasury`, `can_edit_treasury`, `month_summary`, `TreasurySettings.get`.
- Produces: `build_treasury_nav(request) -> dict | None` com a mesma forma de `core.navigation.build_admin_nav` (`{'groups': [{'title', 'items': [{'label','icon','url','is_active','count','count_label'}]}]}`) e itens Caixa do Mês e Relatório (todos com `can_view_treasury`); A confirmar (contador = pendentes) e Configurações (só `can_edit_treasury`); Contas a pagar (contador = vencidas), Lançamentos, Ofertas especiais, Histórico e Histórico anterior (só `can_view_details`). Reutiliza `core.navigation.ICONS`.
- Produces: `tesouraria.context_processors.treasury_shell(request) -> dict`: para caminhos em `/tesouraria/` devolve `{'admin_nav': nav, 'shell': {'home_url', 'subtitle': 'Tesouraria', 'search': False, 'panel_url': url do painel ou None}}`; fora disso `{}`.
- Produces: `parse_month(value: str | None) -> date` (`'2026-11'` → `date(2026,11,1)`; inválido ou vazio → mês atual).

- [ ] **Step 1: Escrever os testes** em `test_shell.py`: `test_home_requires_view_permission` (anônimo 302 ao login; Secretário, Diácono, Pastor, membro 403); `test_not_configured_redirects_editor_to_settings_and_explains_to_readers` (tesoureiro 302 para `tesouraria:settings`; Diretoria 200 com "ainda não foi configurada"); `test_home_shows_summary_labels` (com `configure` e movimentos, o HTML contém "Caixa do Mês", "Saldo do Caixa", "Saldo do Banco", "Saldo total", "Em dinheiro", "Por Pix"); `test_month_query_parameter` (`?mes=2026-10` mostra outubro; `?mes=lixo` cai no mês atual); `test_shell_hides_panel_search_and_changes_brand` (HTML não contém `class="admin-search"`, contém "Tesouraria"); `test_nav_matches_role` (Diretoria vê só "Caixa do Mês" e "Relatório"; Comissão vê também "Lançamentos", "Histórico" e "Contas a pagar" mas não "A confirmar" nem "Configurações"; tesoureiro vê tudo); `test_panel_link_only_for_panel_users`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar**. Em `admin_base.html`, trocar o link da marca por `{{ shell.home_url|default:... }}`, o subtítulo, o formulário de busca (`{% if shell.search|default_if_none:True %}`) e acrescentar o atalho "Ir para o painel" quando `shell.panel_url`. A view `home` usa `treasury_view_required`, chama `ensure_recurring` só a partir da Task 9. Layout da tela: faixa `stat-row` com saldo anterior, entradas, saídas, Caixa, Banco e Total; blocos "Em dinheiro / Por Pix" e "Ofertas especiais por destino"; lista dos movimentos do mês.
- [ ] **Step 4: Rodar** `test_shell` e a suíte completa → passam (o painel `core` não pode mudar de aparência).
- [ ] **Step 5: Commit** `feat(tesouraria): casca da área e Caixa do Mês`

### Task 5: Configurações (abertura) e categorias

**Files:**
- Create: `tesouraria/templates/tesouraria/{settings,categories,category_form}.html`, `tesouraria/tests/test_settings_categories.py`
- Modify: `tesouraria/{forms,views,urls,models}.py`

**Interfaces:**
- Consumes: `treasury_edit_required`, `audit.record`, `Category`, `TreasurySettings`.
- Produces: `SettingsForm(start_date, opening_cash, opening_bank)`; `CategoryForm(name, kind, is_special)`; `Category.in_use()` já existe (Task 2).
- Regras: abertura só pode ser alterada enquanto não houver `MonthClosing` com `closed_at`. Excluir categoria sem uso apaga de verdade; com uso, a ação **arquiva** (`active=False`) e informa isso. Arquivada pode ser reativada. Nome único por tipo.

- [ ] **Step 1: Escrever os testes**: `test_editor_saves_opening_and_audits`; `test_opening_locked_after_a_month_is_closed`; `test_readers_get_403_on_settings_post`; `test_create_edit_category`; `test_duplicate_name_same_kind_is_rejected_with_message`; `test_delete_unused_category_removes_it`; `test_delete_used_category_archives_it_and_keeps_history` (movimento continua exibindo a categoria; ela some das escolhas do `MovementForm`); `test_reactivate_category`; `test_start_date_cannot_be_in_the_future_of_existing_movements` (se já existe movimento anterior à nova data, recusa).
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** os formulários e as views. A lista de categorias separa Entradas e Saídas, mostra "Arquivada" e a contagem de usos.
- [ ] **Step 4: Rodar** `test_settings_categories` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): configurações de abertura e categorias`

### Task 6: Lançamentos, depósitos e lista

**Files:**
- Create: `tesouraria/templates/tesouraria/{movements,movement_form,transfer_form}.html`, `tesouraria/tests/test_movements.py`
- Modify: `tesouraria/{forms,views,urls}.py`

**Interfaces:**
- Consumes: `ensure_after_start`, `ensure_month_open`, `audit.record`, `description_for`.
- Produces: `MovementForm(kind)` (campos: data, categoria do tipo, descrição, valor, conta, forma, membro opcional, destino só se a categoria for especial); `TransferForm(from_account, to_account, date, amount, note)`; `create_movement(user, **fields) -> Movement`, `update_movement(user, movement, **fields) -> Movement`, `delete_movement(user, movement) -> None`, `create_transfer(user, **fields) -> Transfer`, `delete_transfer(user, transfer) -> None` em `tesouraria/ledger.py` (cada uma chama as guardas, grava e registra auditoria, tudo em `transaction.atomic`).
- Regras: entrada em dinheiro sugere conta Caixa e Pix sugere Banco (a pessoa pode mudar); conta obrigatória ao salvar; valor maior que zero; destino obrigatório em oferta especial. Lançar em mês fechado ou antes do início é recusado com `TreasuryError`, mostrado como erro do formulário.

- [ ] **Step 1: Escrever os testes**: `test_create_income_cash_updates_cash_balance`; `test_create_expense_from_bank`; `test_special_offering_requires_destination`; `test_amount_must_be_positive`; `test_edit_records_before_and_after_in_audit`; `test_delete_is_logical_and_audited` (some da lista, `deleted_at` preenchido, linha em `AuditLog`); `test_closed_month_blocks_create_edit_delete` (criar `MonthClosing(closed_at=now)` direto no teste; os três caminhos, inclusive POST por URL adivinhada, recusam); `test_before_start_date_is_refused`; `test_transfer_deposit_updates_both_accounts_and_not_totals`; `test_movements_list_filters_by_type_category_account_method_and_month`; `test_home_list_masks_member_description_for_board_but_not_for_treasurer_or_committee`; `test_board_cannot_open_movements_list` (403), `test_committee_can_open_movements_list_read_only`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** `ledger.py`, formulários, views e telas, com os botões Nova entrada, Nova saída e Depósito no Caixa do Mês. A lista mostra `description_for(movement, request.user)`.
- [ ] **Step 4: Rodar** `test_movements` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): lançamentos e depósitos com auditoria`

### Task 7: Fila "A confirmar"

**Files:**
- Create: `tesouraria/pending.py`, `tesouraria/templates/tesouraria/pending.html`, `tesouraria/tests/test_pending.py`
- Modify: `tesouraria/{forms,views,urls}.py`

**Interfaces:**
- Consumes: `ensure_month_open`, `ensure_after_start`, `audit.record`.
- Produces em `pending.py`: `create_portal_contribution(member: Member, category_name: str, amount: Decimal, note: str) -> Movement` (entrada `PENDING`, `source=PORTAL`, sem conta, forma `PIX`, `created_by=member.user`, descrição `"{categoria sem o s final} via portal - {nome}"`); `confirm_pending(movement: Movement, *, user, account: str, method: str, date: date) -> Movement`; `reject_pending(movement: Movement, *, user, reason: str) -> Movement`.
- Regras: confirmar exige conta, forma e data em mês aberto e a partir do início; recusar exige motivo. Só `PENDING` pode ser confirmado ou recusado (repetir a ação é recusado). Fila vazia mostra convite claro.

- [ ] **Step 1: Escrever os testes**: `test_confirm_moves_money_into_chosen_account`; `test_pending_does_not_change_balances_until_confirmed`; `test_reject_requires_reason_and_never_counts`; `test_cannot_confirm_twice`; `test_confirm_into_closed_month_requires_open_date` (data em mês fechado é recusada com mensagem pedindo outra data); `test_confirm_before_start_is_refused`; `test_queue_shows_member_name_to_treasurer_only` (Diretoria nem acessa a fila: 403); `test_readers_cannot_post_confirm`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** as três funções (cada uma em `atomic`) e a tela com formulário de confirmar (conta, forma, data, padrão = data declarada) e de recusar (motivo).
- [ ] **Step 4: Rodar** `test_pending` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): fila a confirmar`

### Task 8: Contas a pagar

**Files:**
- Create: `tesouraria/payables.py`, `tesouraria/templates/tesouraria/{payables,payable_form,payable_pay}.html`, `tesouraria/tests/test_payables.py`, nova migração
- Modify: `tesouraria/{models,forms,views,urls,balances}.py`

**Interfaces:**
- Produces modelo `Payable(description max 180, payee max 120, category FK PROTECT, amount, due_date, status {OPEN='open','Em aberto'; PAID='paid','Paga'; CANCELED='canceled','Cancelada'}, recurring FK null, period date null, installment_number int null, installments_total int null, movement OneToOne null, paid_amount null, paid_date null, created_by)`; `Category.in_use()` passa a considerar `payable_set`.
- Produces em `payables.py`: `pay_payable(payable: Payable, *, user, paid_amount: Decimal, paid_date: date, account: str, method: str) -> Movement` (em `atomic`: guardas, cria saída `CONFIRMED` com a categoria da conta, marca `PAID`, grava `movement`, `paid_amount`, `paid_date`, auditoria); `undo_payment(payable: Payable, user) -> None` (só com o mês do pagamento aberto: exclui logicamente a saída, volta a `OPEN`, auditoria); `cancel_payable(payable: Payable, user) -> None` (só `OPEN`); `payables_overview(today: date) -> dict` com `overdue`, `upcoming`, `paid` (cada um `{'count', 'total'}`).
- Altera `month_summary`: `payables_open_total` = contas `OPEN` com vencimento no mês; `payables_paid_total` = soma de `paid_amount` das pagas no mês; `projected_total = closing_total - payables_open_total`.
- Regras: conta em aberto não altera saldo; vencida = `due_date < today`. Pagar só `OPEN`. Conta paga só se altera desfazendo o pagamento. Valor pago pode diferir do previsto.

- [ ] **Step 1: Escrever os testes**: `test_open_payable_does_not_change_balances`; `test_pay_creates_confirmed_expense_and_marks_paid`; `test_pay_with_different_amount_uses_paid_amount_in_balance`; `test_pay_is_atomic_when_closed_month` (força `MonthClosed` e confere que não sobrou saída nem mudança de situação); `test_undo_restores_open_and_removes_expense`; `test_undo_blocked_when_payment_month_is_closed`; `test_cancel_only_open`; `test_overview_splits_overdue_upcoming_paid` (três contas com vencimentos antes e depois de `today`); `test_summary_projected_total_subtracts_open_payables_of_the_month`; `test_tabs_screen_shows_Vencidas_A_vencer_Pagas_with_totals`; `test_readers_cannot_pay`; `test_board_cannot_open_payables_screen` (403) e `test_committee_can_read_payables`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** modelo, migração, `payables.py`, formulários e telas (abas, nova conta, editar, Pagar com valor padrão igual ao previsto, desfazer, cancelar). No Caixa do Mês acrescentar o bloco "Contas do mês" com vencimentos, pago, a pagar e "Saldo depois de pagar o que falta".
- [ ] **Step 4: Rodar** `test_payables` e `test_balances` → passam.
- [ ] **Step 5: Commit** `feat(tesouraria): contas a pagar`

### Task 9: Recorrentes e parceladas

**Files:**
- Create: `tesouraria/recurring.py`, `tesouraria/templates/tesouraria/{recurring,recurring_form}.html`, `tesouraria/tests/test_recurring.py`, nova migração
- Modify: `tesouraria/{models,forms,views,urls}.py`

**Interfaces:**
- Produces modelo `RecurringBill(description, payee, category FK PROTECT, amount, due_day 1..31, start_date, installments null, active, created_by)`; `Payable` ganha `UniqueConstraint(fields=['recurring','period'], condition=Q(recurring__isnull=False))`; `Category.in_use()` considera `recurringbill_set`.
- Produces em `recurring.py`: `due_date_for(month: date, due_day: int) -> date` (limita ao último dia do mês); `ensure_recurring(today: date) -> int` (cria, para o mês de `today` e o seguinte, uma `Payable` por recorrência ativa que já começou e ainda não esgotou as parcelas; devolve quantas criou; idempotente; numera `installment_number`/`installments_total` quando há parcelas; usa `get_or_create` e trata `IntegrityError` como "já existe").
- A view `home` e a lista de contas a pagar chamam `ensure_recurring(date.today())` ao abrir. Valor da conta nasce igual ao estimado.

- [ ] **Step 1: Escrever os testes**: `test_due_date_clamps_to_last_day` (31 em fevereiro de 2027 → 28; 30 em fevereiro de 2028 → 29; 31 em abril → 30); `test_creates_current_and_next_month`; `test_idempotent_when_called_twice`; `test_idempotent_under_integrity_error` (pré-cria a conta do período e chama de novo: devolve 0, sem exceção); `test_installments_stop_at_last_and_are_numbered` (3 parcelas começando em outubro: out 1/3, nov 2/3, dez 3/3, janeiro nada); `test_inactive_or_not_started_recurring_is_skipped`; `test_deactivating_stops_future_but_keeps_created`; `test_open_screen_triggers_generation`; `test_readers_cannot_create_recurring`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar**, mais a tela de recorrentes (listar, criar, editar, ativar/desativar; "3/10" visível nas contas geradas).
- [ ] **Step 4: Rodar** `test_recurring` e `test_payables` → passam.
- [ ] **Step 5: Commit** `feat(tesouraria): contas recorrentes e parceladas`

### Task 10: Conferência do caixa e fechamento do mês

**Files:**
- Create: `tesouraria/closing.py`, `tesouraria/templates/tesouraria/{cash_count,month_close}.html`, `tesouraria/tests/test_closing.py`
- Modify: `tesouraria/{forms,views,urls,balances}.py`, `tesouraria/templates/tesouraria/home.html`

**Interfaces:**
- Consumes: `month_summary`, `rules`.
- Produces em `closing.py`: `record_cash_count(month: date, counted: Decimal, user) -> MonthClosing` (`get_or_create` do mês; só em mês aberto); `close_month(month: date, user, notes: str = '') -> MonthClosing`; `reopen_month(month: date, user) -> MonthClosing`.
- Regras de `close_month`: bloqueia com `TreasuryError` se houver contribuição `PENDING` com data no mês; se o mês anterior (a partir do início) não estiver fechado; se o mês é futuro. Grava saldos inicial e final (devem coincidir com `month_summary`), `closed_at`, `closed_by`. `reopen_month` só reabre se o mês seguinte **não** estiver fechado; grava auditoria. `month_summary` preenche `counted_cash`, `cash_difference = counted_cash - closing_cash` e `is_closed`.

- [ ] **Step 1: Escrever os testes**: `test_cash_count_shows_difference`; `test_close_blocked_by_pending_contribution_in_month`; `test_close_requires_previous_month_closed`; `test_close_snapshots_balances_equal_to_summary`; `test_closed_month_is_read_only_via_every_mutation` (movimento, transferência, conta paga, confirmar, desfazer pagamento, contagem de caixa: todos recusados); `test_reopen_allows_edits_and_audits`; `test_cannot_reopen_when_next_month_closed`; `test_next_month_opening_equals_previous_closing`; `test_close_and_reopen_forbidden_for_readers`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar**, com botões "Conferir caixa" e "Fechar mês" no Caixa do Mês e selo "Mês fechado".
- [ ] **Step 4: Rodar** `test_closing` e a suíte do app → passam.
- [ ] **Step 5: Commit** `feat(tesouraria): conferência do caixa e fechamento do mês`

### Task 11: Ofertas especiais e Histórico

**Files:**
- Create: `tesouraria/templates/tesouraria/{special,audit}.html`, `tesouraria/tests/test_special_audit.py`
- Modify: `tesouraria/{views,urls}.py`

**Interfaces:**
- Consumes: `month_summary(...).special_by_destination`, `AuditLog`.
- Regras: a tela de ofertas especiais lista o total por destino e os lançamentos de cada um, no mês e no ano. O Histórico mostra data, quem, ação e `summary`, filtrável por mês e ação, e usa `treasury_detail_required`; o detalhe antes/depois só aparece para quem `can_see_member_names` (tesoureiro e Comissão, os únicos que chegam ali).

- [ ] **Step 1: Escrever os testes**: `test_special_groups_by_destination_for_month_and_year`; `test_special_ignores_pending_and_deleted`; `test_audit_lists_actions_newest_first`; `test_audit_summary_never_contains_member_name` (cria e confirma contribuição de "Ana Souza": nenhum `summary` contém "Ana"); `test_board_and_secretary_get_403_on_audit_and_special`; `test_audit_and_special_visible_to_committee_and_treasurer`; `test_audit_detail_before_after_shown_only_to_names_viewers` (tesoureiro e Comissão veem; confirma que o `summary` exibido não tem o nome).
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** as duas telas.
- [ ] **Step 4: Rodar** `test_special_audit` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): ofertas especiais e histórico de alterações`

### Task 12: Comissão de Contas, parecer e somente leitura

**Files:**
- Create: `tesouraria/templates/tesouraria/opinion.html`, `tesouraria/tests/test_committee.py`
- Modify: `tesouraria/{models,forms,views,urls}.py`, templates do Caixa do Mês e do relatório, nova migração

**Interfaces:**
- Produces modelo `CommitteeOpinion(month, author FK, result {APPROVED='approved','Aprovado'; RESERVATIONS='reservations','Aprovado com ressalvas'}, text, created_at, updated_at)` com `unique(month, author)`.
- Regras: só `committee_required` grava; só em mês **fechado**; refazer substitui e registra auditoria. Todos com acesso leem os pareceres no Caixa do Mês e no relatório. Toda view de escrita da Tesouraria rejeita Diretoria e Comissão com 403.

- [ ] **Step 1: Escrever os testes**: `test_committee_registers_opinion_on_closed_month_only`; `test_replacing_opinion_audits_the_change`; `test_treasurer_and_board_cannot_post_opinion`; `test_opinion_visible_on_home_and_report`; `test_every_write_url_returns_403_for_board_and_committee` (percorre `movement_create`, `movement_edit`, `movement_delete`, `transfer_create`, `pending_confirm`, `pending_reject`, `payable_create`, `payable_pay`, `payable_undo`, `payable_cancel`, `recurring_create`, `cash_count`, `month_close`, `month_reopen`, `settings`, `category_create`, `category_delete`, com POST); `test_committee_cannot_open_the_panel` (`dashboard` e `members` redirecionam ou dão 403); `test_committee_sees_member_names_in_movements_but_board_sees_masked_text_on_home`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar**, com o formulário de parecer no Caixa do Mês de um mês fechado, visível só para a Comissão.
- [ ] **Step 4: Rodar** `test_committee` e a suíte do app → passam.
- [ ] **Step 5: Commit** `feat(tesouraria): Comissão de Contas e parecer por mês`

### Task 13: Relatório mensal na tela e em PDF

**Files:**
- Create: `tesouraria/report.py`, `tesouraria/templates/tesouraria/report.html`, `tesouraria/tests/test_report.py`
- Modify: `tesouraria/{views,urls}.py`, `static/css/app.css` (impressão)

**Interfaces:**
- Produces: `build_report_context(month: date, *, user) -> dict` (resumo do mês, entradas e saídas por categoria, dinheiro contra Pix, ofertas especiais por destino, depósitos, saldos final, conferência, contas pagas e a pagar, pareceres, e a lista de movimentos com `description_for`); `render_report_pdf(month: date, *, user) -> bytes` (A4, `reportlab.platypus`, cabeçalho com o nome da igreja e o mês, mesmas seções, linhas de assinatura para Tesoureiro e Comissão, aviso "Mês em aberto" se não fechado).
- Rotas: `report` (tela, `?mes=`) e `report_pdf` (`application/pdf`, `Content-Disposition: inline; filename="relatorio-AAAA-MM.pdf"`). Resumo do ano: tabela mês a mês de entradas, saídas e saldo total, na tela.

- [ ] **Step 1: Escrever os testes**: `test_report_screen_numbers_match_month_summary` (compara o contexto com `month_summary`); `test_pdf_is_valid_and_contains_key_labels` (`pypdf.PdfReader` lê o texto e encontra "Saldo do Caixa", "Saldo do Banco", "Em dinheiro", "Por Pix"); `test_pdf_masks_member_names_for_board_and_shows_for_committee` (descrição de contribuição de "Ana Souza"); `test_open_month_is_marked_in_report_and_pdf`; `test_report_requires_view_permission`; `test_year_summary_matches_sum_of_months`; `test_pdf_with_no_movements_still_renders`.
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** o relatório; PDF a partir do mesmo `build_report_context`, sem recalcular saldo.
- [ ] **Step 4: Rodar** `test_report` → passa.
- [ ] **Step 5: Commit** `feat(tesouraria): relatório mensal em tela e PDF`

### Task 14: Virada: portal, fim do Financeiro antigo e Histórico anterior

**Files:**
- Create: `tesouraria/templates/tesouraria/legacy.html`, `tesouraria/tests/test_cutover.py`
- Modify: `core/views.py` (portal; remove `finance`, `transaction_form`, `show_finances` e saldo de `dashboard_context`), `core/urls.py`, `core/permissions.py` (remove `can_access_finance`, `financial_access_required`), `core/navigation.py` (remove o item Financeiro), `core/forms.py` (remove `TransactionForm`), `core/admin.py` (`TransactionAdmin` só leitura), `core/charts.py` (remove gráficos financeiros sem uso), `core/management/commands/seed_demo.py`, `templates/core/{dashboard,reports,member_portal}.html`, `templates/core/finance.html` (apagar), testes antigos em `core/tests.py` e `core/test_permissions.py`, `README.md`

**Interfaces:**
- Consumes: `create_portal_contribution` (Task 7), `Movement`, `Category`.
- Regras: o portal grava `create_portal_contribution` e mostra ao membro "aguardando confirmação" até virar `CONFIRMED`; recusada mostra o motivo; `contribution_total` conta só confirmadas. "Histórico anterior" lista `core.Transaction` em somente leitura, sem botões de escrita. O painel principal não mostra mais nenhum dado financeiro nem o item Financeiro, para nenhum perfil.

- [ ] **Step 1: Escrever os testes** em `test_cutover.py`: `test_portal_contribution_is_pending_and_does_not_touch_balances`; `test_portal_shows_waiting_then_confirmed_total`; `test_rejected_contribution_shows_reason_to_member`; `test_old_finance_urls_are_gone` (`reverse('finance')` e `reverse('transaction_create')` levantam `NoReverseMatch`); `test_panel_has_no_financial_data_or_menu_item` (dashboard, relatórios e sidebar de tesoureiro, Diretoria e superusuário sem "Financeiro" nem "Saldo"); `test_legacy_page_lists_old_transactions_read_only` (sem formulário nem botão de escrita; 200 para tesoureiro e Comissão; 403 para Diretoria e Secretário); `test_transaction_admin_is_read_only`; `test_seed_demo_creates_treasury_data` (categorias, configuração, movimentos, recorrente e usuários de teste dos perfis tesoureiro e comissão).
- [ ] **Step 2: Rodar e ver falhar**.
- [ ] **Step 3: Implementar** a troca, apagar os testes antigos do Financeiro (`test_pastor_cannot_access_or_see_financial_data`, `test_member_contribution_updates_finance_dashboard` e os de `test_permissions.py` sobre `can_access_finance`/`finance`) trocando por equivalentes novos nos arquivos da Tesouraria, atualizar `seed_demo` e documentar a Tesouraria no `README.md` (perfis, fluxo do mês, como abrir o primeiro mês).
- [ ] **Step 4: Rodar a suíte completa e as checagens**: `DJANGO_DEBUG=True python manage.py test` e `python manage.py check --deploy --fail-level WARNING` (com as variáveis de CI do workflow) → tudo passa, sem avisos.
- [ ] **Step 5: Commit** `feat(tesouraria): portal a confirmar e remoção do Financeiro antigo`

---

## Self-review

- **Cobertura do spec:** Caixa do Mês (4), abertura e categorias com arquivar/excluir (5), lançamentos, depósitos e edição com histórico (6, 2), fila a confirmar e mudança do portal (7, 14), contas a pagar com pagar/desfazer/cancelar e saldo depois de pagar (8), recorrentes e parceladas sem agendador (9), conferência e fechamento com bloqueios (10), ofertas especiais e histórico (11), Comissão com parecer e leitura (12, 1), relatório PDF e tela (13), remoção do menu e da página antiga, "Histórico anterior", sem migrar a tabela antiga (14). Lacuna conhecida e prevista no spec: comprovante anexado fica fora.
- **Consistência de nomes:** `Account`, `Method`, `Kind`, `Status`, `Source`, `Movement`, `Transfer`, `Payable`, `RecurringBill`, `MonthClosing`, `AuditLog`, `CommitteeOpinion`; funções `account_balance`, `opening_balance`, `month_summary`, `pay_payable`, `undo_payment`, `cancel_payable`, `ensure_recurring`, `due_date_for`, `create_portal_contribution`, `confirm_pending`, `reject_pending`, `record_cash_count`, `close_month`, `reopen_month`, `description_for`, `record`, `landing_url` definidas na tarefa que as produz e usadas só depois.
- **Proporção:** plano com cerca de duas vezes o tamanho do spec, sem corpos de função; os testes nomeiam as asserções que fixam os valores do spec.
