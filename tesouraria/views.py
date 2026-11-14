from datetime import date

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import audit, ledger, payables as payables_service, pending as pending_service
from .balances import month_summary
from .forms import TITHE_HINT, CategoryForm, ConfirmPendingForm, MovementForm, PayableForm, PayForm, RejectPendingForm, SettingsForm, TransferForm
from .models import Account, Category, Kind, Method, Movement, Payable, Status, Transfer, TreasurySettings
from .permissions import (can_edit_treasury, treasury_detail_required, treasury_edit_required,
                          treasury_view_required)
from .rules import BeforeStart, MonthClosed, NotConfigured, TreasuryError, month_end, month_start, parse_month
from .visibility import description_for


@treasury_view_required
def home(request):
    month = parse_month(request.GET.get('mes'))
    try:
        summary = month_summary(month)
    except NotConfigured:
        if can_edit_treasury(request.user):
            return redirect('tesouraria:settings')
        return render(request, 'tesouraria/not_configured.html')
    except BeforeStart:
        start_month = month_start(TreasurySettings.get().start_date)
        return render(request, 'tesouraria/home.html', {
            'month': month, 'before_start': True,
            'start_month': start_month, 'start_month_param': f'{start_month:%Y-%m}',
        })
    movements = list(Movement.objects.counted()
                     .filter(date__gte=summary.month, date__lte=month_end(summary.month))
                     .select_related('category').order_by('-date', '-id'))
    for movement in movements:
        movement.shown_description = description_for(movement, request.user)
    return render(request, 'tesouraria/home.html', {
        'month': summary.month,
        'summary': summary,
        'movements': movements,
        'prev_param': f'{_shift(summary.month, -1):%Y-%m}',
        'next_param': f'{_shift(summary.month, 1):%Y-%m}',
        'can_edit': can_edit_treasury(request.user),
    })


def _shift(month: date, delta: int) -> date:
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


@treasury_edit_required
def settings(request):
    current = TreasurySettings.get()
    before = audit.snapshot(current) if current else None  # antes do form: is_valid() altera a instância
    form = SettingsForm(request.POST or None, instance=current)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        audit.record(request.user, audit.SETTINGS, saved, 'Abertura registrada',
                     before=before, after=audit.snapshot(saved))
        messages.success(request, 'Abertura da tesouraria salva.')
        return redirect('tesouraria:settings')
    return render(request, 'tesouraria/settings.html', {'form': form, 'locked': SettingsForm.is_locked()})


@treasury_edit_required
def categories(request):
    rows = Category.objects.annotate(uses=Count('movement')).order_by('name')
    return render(request, 'tesouraria/categories.html', {
        'groups': [('Entradas', rows.filter(kind=Kind.INCOME)), ('Saídas', rows.filter(kind=Kind.EXPENSE))],
    })


def _category_form(request, instance, title, verb):
    before = audit.snapshot(instance) if instance else None  # antes do form: is_valid() altera a instância
    form = CategoryForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        audit.record(request.user, audit.CREATE if instance is None else audit.UPDATE, saved,
                     f'Categoria {verb}: {saved.name}', before=before, after=audit.snapshot(saved))
        messages.success(request, f'Categoria {verb}.')
        return redirect('tesouraria:categories')
    return render(request, 'tesouraria/category_form.html', {'form': form, 'title': title})


@treasury_edit_required
def category_create(request):
    return _category_form(request, None, 'Nova categoria', 'criada')


@treasury_edit_required
def category_edit(request, pk):
    return _category_form(request, get_object_or_404(Category, pk=pk), 'Editar categoria', 'alterada')


@treasury_edit_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    before = audit.snapshot(category)
    if category.in_use():
        category.active = False
        category.save(update_fields=['active'])
        audit.record(request.user, audit.ARCHIVE, category, f'Categoria arquivada: {category.name}',
                     before=before, after=audit.snapshot(category))
        messages.success(request, f'A categoria "{category.name}" já tem lançamentos e foi arquivada, '
                                  'não excluída. Ela some das novas escolhas e o histórico continua intacto.')
    else:
        name = category.name
        audit.record(request.user, audit.DELETE, category, f'Categoria excluída: {name}', before=before)
        category.delete()
        messages.success(request, f'Categoria "{name}" excluída.')
    return redirect('tesouraria:categories')


@treasury_edit_required
@require_POST
def category_reactivate(request, pk):
    category = get_object_or_404(Category, pk=pk)
    before = audit.snapshot(category)
    category.active = True
    category.save(update_fields=['active'])
    audit.record(request.user, audit.UPDATE, category, f'Categoria reativada: {category.name}',
                 before=before, after=audit.snapshot(category))
    messages.success(request, f'Categoria "{category.name}" reativada.')
    return redirect('tesouraria:categories')


# --- Lançamentos, depósitos e lista ---------------------------------------------------------

def _tithe_hint(request, form):
    if form.tithe_without_member:
        messages.warning(request, TITHE_HINT + '.')


def _movement_form(request, movement, kind, title):
    initial = MovementForm.initial_from(movement) if movement else None
    form = MovementForm(request.POST or None, kind=kind, initial=initial,
                        current_category=movement.category if movement else None)
    if request.method == 'POST' and form.is_valid():
        fields = form.cleaned_data
        try:
            if movement is None:
                ledger.create_movement(request.user, **fields)
                messages.success(request, 'Lançamento registrado.')
            else:
                ledger.update_movement(request.user, movement, **fields)
                messages.success(request, 'Lançamento alterado.')
        except TreasuryError as error:
            form.add_error(None, str(error))
        else:
            _tithe_hint(request, form)
            return redirect('tesouraria:movements')
    return render(request, 'tesouraria/movement_form.html', {
        'form': form, 'title': title, 'kind': kind, 'cancel_url': reverse('tesouraria:movements')})


@treasury_edit_required
def movement_create(request):
    kind = Kind.EXPENSE if request.GET.get('tipo') == Kind.EXPENSE else Kind.INCOME
    return _movement_form(request, None, kind, 'Nova saída' if kind == Kind.EXPENSE else 'Nova entrada')


@treasury_edit_required
def movement_edit(request, pk):
    movement = get_object_or_404(Movement.objects.live().select_related('category'), pk=pk)
    if request.method != 'POST':
        try:
            ledger.ensure_editable(movement)
        except TreasuryError as error:
            messages.error(request, str(error))
            return redirect('tesouraria:movements')
    return _movement_form(request, movement, movement.kind, 'Editar lançamento')


@treasury_edit_required
@require_POST
def movement_delete(request, pk):
    movement = get_object_or_404(Movement.objects.live(), pk=pk)
    try:
        ledger.delete_movement(request.user, movement)
    except TreasuryError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Lançamento excluído.')
    return redirect(_back(request, movement.date))


@treasury_edit_required
def transfer_create(request):
    form = TransferForm(request.POST or None, initial={'date': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        try:
            ledger.create_transfer(request.user, **form.cleaned_data)
        except TreasuryError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, 'Depósito registrado.')
            return redirect('tesouraria:movements')
    return render(request, 'tesouraria/transfer_form.html', {
        'form': form, 'title': 'Depósito ou saque', 'cancel_url': reverse('tesouraria:movements')})


@treasury_edit_required
@require_POST
def transfer_delete(request, pk):
    transfer = get_object_or_404(Transfer.objects.filter(deleted_at__isnull=True), pk=pk)
    try:
        ledger.delete_transfer(request.user, transfer)
    except TreasuryError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Transferência excluída.')
    return redirect(_back(request, transfer.date))


def _back(request, when):
    return f"{reverse('tesouraria:movements')}?mes={when:%Y-%m}"


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@treasury_detail_required
def movements(request):
    month = parse_month(request.GET.get('mes'))
    kind = request.GET.get('tipo')
    kind = kind if kind in Kind.values else None
    account = request.GET.get('conta')
    account = account if account in Account.values else None
    method = request.GET.get('forma')
    method = method if method in Method.values else None
    category_id = _int_or_none(request.GET.get('categoria'))
    if category_id is not None and not Category.objects.filter(pk=category_id).exists():
        category_id = None

    rows = (Movement.objects.live().select_related('category', 'member')
            .filter(date__gte=month, date__lte=month_end(month)))
    if kind:
        rows = rows.filter(kind=kind)
    if category_id:
        rows = rows.filter(category_id=category_id)
    if account:
        rows = rows.filter(account=account)
    if method:
        rows = rows.filter(method=method)
    rows = list(rows.order_by('-date', '-id'))
    for movement in rows:
        movement.shown_description = description_for(movement, request.user)

    transfers = []
    if not (kind or category_id or method):
        found = Transfer.objects.filter(deleted_at__isnull=True, date__gte=month, date__lte=month_end(month))
        if account:
            found = found.filter(Q(from_account=account) | Q(to_account=account))
        transfers = list(found.order_by('-date', '-id'))

    return render(request, 'tesouraria/movements.html', {
        'movements': rows, 'transfers': transfers, 'month': month,
        'month_param': f'{month:%Y-%m}',
        'prev_param': f'{_shift(month, -1):%Y-%m}', 'next_param': f'{_shift(month, 1):%Y-%m}',
        'filters': {'tipo': kind or '', 'categoria': category_id or '', 'conta': account or '',
                    'forma': method or ''},
        'categories': Category.objects.order_by('kind', 'name'),
        'kinds': Kind.choices, 'accounts': Account.choices, 'methods': Method.choices,
        'can_edit': can_edit_treasury(request.user),
    })


# --- Fila "A confirmar" ---------------------------------------------------------------------

def _pending_page(request, bound=None):
    """`bound`: (pk, 'confirm'|'reject', form) com os erros a mostrar naquele item."""
    rows = list(Movement.objects.live().filter(status=Status.PENDING)
                .select_related('category', 'member').order_by('date', 'id'))
    for movement in rows:
        movement.confirm_form = ConfirmPendingForm(prefix=f'c{movement.pk}', initial={'date': movement.date})
        movement.reject_form = RejectPendingForm(prefix=f'r{movement.pk}')
        if bound and bound[0] == movement.pk:
            setattr(movement, f'{bound[1]}_form', bound[2])
    return render(request, 'tesouraria/pending.html', {'movements': rows})


@treasury_edit_required
def pending(request):
    return _pending_page(request)


def _pending_action(request, pk, kind, form_class, run):
    movement = get_object_or_404(Movement.objects.live(), pk=pk)
    form = form_class(request.POST, prefix=f'{"c" if kind == "confirm" else "r"}{pk}')
    if form.is_valid():
        try:
            run(movement, form.cleaned_data)
        except TreasuryError as error:
            form.add_error(None, str(error) + (' Escolha outra data, de um mês aberto.'
                                               if isinstance(error, MonthClosed) else ''))
            if movement.status != Status.PENDING:
                messages.error(request, str(error))
                return redirect('tesouraria:pending')
        else:
            messages.success(request, 'Contribuição confirmada.' if kind == 'confirm' else 'Contribuição recusada.')
            return redirect('tesouraria:pending')
    return _pending_page(request, (pk, kind, form))


@treasury_edit_required
@require_POST
def pending_confirm(request, pk):
    return _pending_action(request, pk, 'confirm', ConfirmPendingForm,
                           lambda m, d: pending_service.confirm_pending(
                               m, user=request.user, account=d['account'], method=d['method'], date=d['date']))


@treasury_edit_required
@require_POST
def pending_reject(request, pk):
    return _pending_action(request, pk, 'reject', RejectPendingForm,
                           lambda m, d: pending_service.reject_pending(m, user=request.user, reason=d['reason']))


# --- Contas a pagar -------------------------------------------------------------------------

PAYABLE_TABS = [('vencidas', 'Vencidas', 'overdue'), ('a-vencer', 'A vencer', 'upcoming'), ('pagas', 'Pagas', 'paid')]


@treasury_detail_required
def payables(request):
    today = timezone.localdate()
    tab = request.GET.get('aba')
    tab = tab if tab in {t[0] for t in PAYABLE_TABS} else 'vencidas'
    overview = payables_service.payables_overview(today)
    base = Payable.objects.select_related('category')
    open_rows = base.filter(status=Payable.Status.OPEN)
    if tab == 'vencidas':
        rows = open_rows.filter(due_date__lt=today).order_by('due_date', 'id')
    elif tab == 'a-vencer':
        rows = open_rows.filter(due_date__gte=today).order_by('due_date', 'id')
    else:
        rows = base.filter(status=Payable.Status.PAID).order_by('-paid_date', '-id')[:200]
    return render(request, 'tesouraria/payables.html', {
        'tabs': [{'key': key, 'label': label, 'active': key == tab, **overview[bucket]}
                 for key, label, bucket in PAYABLE_TABS],
        'tab': tab, 'rows': list(rows), 'today': today, 'can_edit': can_edit_treasury(request.user),
    })


def _payable_form(request, payable, title):
    before_ok = payable is None or payable.status == Payable.Status.OPEN
    if not before_ok:
        messages.error(request, 'Só contas em aberto podem ser alteradas; para mudar uma conta paga, '
                                'desfaça o pagamento.')
        return redirect('tesouraria:payables')
    initial = PayableForm.initial_from(payable) if payable else None
    form = PayableForm(request.POST or None, initial=initial,
                       current_category=payable.category if payable else None)
    if request.method == 'POST' and form.is_valid():
        try:
            if payable is None:
                payables_service.create_payable(request.user, **form.cleaned_data)
                messages.success(request, 'Conta registrada.')
            else:
                payables_service.update_payable(request.user, payable, **form.cleaned_data)
                messages.success(request, 'Conta alterada.')
        except TreasuryError as error:
            form.add_error(None, str(error))
        else:
            return redirect('tesouraria:payables')
    return render(request, 'tesouraria/payable_form.html', {
        'form': form, 'title': title, 'cancel_url': reverse('tesouraria:payables')})


@treasury_edit_required
def payable_create(request):
    return _payable_form(request, None, 'Nova conta a pagar')


@treasury_edit_required
def payable_edit(request, pk):
    return _payable_form(request, get_object_or_404(Payable.objects.select_related('category'), pk=pk),
                         'Editar conta a pagar')


@treasury_edit_required
def payable_pay(request, pk):
    payable = get_object_or_404(Payable.objects.select_related('category'), pk=pk)
    if payable.status != Payable.Status.OPEN:
        messages.error(request, 'Só contas em aberto podem ser pagas.')
        return redirect('tesouraria:payables')
    form = PayForm(request.POST or None, initial={'paid_amount': payable.amount, 'paid_date': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        try:
            payables_service.pay_payable(payable, user=request.user, **form.cleaned_data)
        except TreasuryError as error:
            form.add_error(None, str(error) + (' Escolha outra data, de um mês aberto.'
                                               if isinstance(error, MonthClosed) else ''))
            payable.refresh_from_db()
            if payable.status != Payable.Status.OPEN:
                messages.error(request, str(error))
                return redirect('tesouraria:payables')
        else:
            messages.success(request, 'Pagamento registrado.')
            return redirect('tesouraria:payables')
    return render(request, 'tesouraria/payable_pay.html', {
        'form': form, 'payable': payable, 'cancel_url': reverse('tesouraria:payables')})


def _payable_action(request, pk, run, ok_message):
    payable = get_object_or_404(Payable, pk=pk)
    try:
        run(payable, request.user)
    except TreasuryError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, ok_message)
    return redirect('tesouraria:payables')


@treasury_edit_required
@require_POST
def payable_undo(request, pk):
    return _payable_action(request, pk, payables_service.undo_payment, 'Pagamento desfeito; a conta voltou a ficar em aberto.')


@treasury_edit_required
@require_POST
def payable_cancel(request, pk):
    return _payable_action(request, pk, payables_service.cancel_payable, 'Conta cancelada.')
