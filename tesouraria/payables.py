"""Contas a pagar: uma conta em aberto não mexe em saldo; só o pagamento gera a saída."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from . import audit
from .ledger import _guard, money, validate_amount
from .models import Account, Kind, Method, Movement, Payable, Source, Status
from .rules import TreasuryError, ensure_month_open

ZERO = Decimal('0.00')
FIELDS = ('description', 'payee', 'category', 'amount', 'due_date')


def _summary(payable, verb) -> str:
    return f'{verb}: conta de {money(payable.amount)} em {payable.category.name}, vence em {payable.due_date:%d/%m/%Y}'


def _lock(payable) -> Payable:
    return Payable.objects.select_for_update().select_related('category').get(pk=payable.pk)


def _ensure_open(payable, action) -> None:
    if payable.status != Payable.Status.OPEN:
        raise TreasuryError(f'Só contas em aberto podem ser {action}; esta já está '
                            f'{payable.get_status_display().lower()}.')


def _clean(fields) -> dict:
    data = {k: v for k, v in fields.items() if k in FIELDS}
    data['amount'] = validate_amount(data.get('amount'))
    data['description'] = (data.get('description') or '').strip()
    if not data['description']:
        raise TreasuryError('Informe a descrição da conta.')
    data['payee'] = (data.get('payee') or '').strip()
    if data.get('category') is None or data['category'].kind != Kind.EXPENSE:
        raise TreasuryError('A categoria deve ser de saída.')
    if data.get('due_date') is None:
        raise TreasuryError('Informe o vencimento.')
    return data


@transaction.atomic
def create_payable(user, **fields) -> Payable:
    data = _clean(fields)
    payable = Payable.objects.create(created_by=user, **data)
    audit.record(user, audit.CREATE, payable, _summary(payable, 'Conta criada'), after=audit.snapshot(payable))
    return payable


@transaction.atomic
def update_payable(user, payable, **fields) -> Payable:
    payable = _lock(payable)
    before = audit.snapshot(payable)
    _ensure_open(payable, 'alteradas')
    for name, value in _clean(fields).items():
        setattr(payable, name, value)
    payable.save()
    audit.record(user, audit.UPDATE, payable, _summary(payable, 'Conta alterada'),
                 before=before, after=audit.snapshot(payable))
    return payable


@transaction.atomic
def pay_payable(payable: Payable, *, user, paid_amount: Decimal, paid_date: date, account: str,
                method: str) -> Movement:
    payable = _lock(payable)
    before = audit.snapshot(payable)
    _ensure_open(payable, 'pagas')
    paid_amount = validate_amount(paid_amount)
    if account not in Account.values:
        raise TreasuryError('Informe a conta (Caixa ou Banco) de onde saiu o dinheiro.')
    if method not in Method.values:
        raise TreasuryError('Informe a forma de pagamento.')
    if paid_date is None:
        raise TreasuryError('Informe a data do pagamento.')
    _guard(paid_date)
    movement = Movement.objects.create(
        date=paid_date, kind=Kind.EXPENSE, amount=paid_amount, category=payable.category,
        description=payable.description, account=account, method=method, status=Status.CONFIRMED,
        source=Source.TREASURY, created_by=user)
    payable.status = Payable.Status.PAID
    payable.movement, payable.paid_amount, payable.paid_date = movement, paid_amount, paid_date
    payable.save()
    audit.record(user, audit.PAY, payable, _summary(payable, f'Paga com {money(paid_amount)}'),
                 before=before, after=audit.snapshot(payable))
    return movement


@transaction.atomic
def undo_payment(payable: Payable, user) -> None:
    payable = _lock(payable)
    before = audit.snapshot(payable)
    if payable.status != Payable.Status.PAID or payable.movement_id is None:
        raise TreasuryError('Só contas pagas podem ter o pagamento desfeito.')
    movement = Movement.objects.select_for_update().get(pk=payable.movement_id)
    ensure_month_open(movement.date)
    movement.deleted_at = timezone.now()
    movement.save(update_fields=['deleted_at', 'updated_at'])
    payable.status = Payable.Status.OPEN
    payable.movement = payable.paid_amount = payable.paid_date = None
    payable.save()
    audit.record(user, audit.UNDO_PAY, payable, _summary(payable, 'Pagamento desfeito'),
                 before=before, after=audit.snapshot(payable))


@transaction.atomic
def cancel_payable(payable: Payable, user) -> None:
    payable = _lock(payable)
    before = audit.snapshot(payable)
    _ensure_open(payable, 'canceladas')
    payable.status = Payable.Status.CANCELED
    payable.save()
    audit.record(user, audit.CANCEL, payable, _summary(payable, 'Conta cancelada'),
                 before=before, after=audit.snapshot(payable))


def _bucket(qs, field) -> dict:
    row = qs.aggregate(count=Count('pk'), total=Sum(field))
    return {'count': row['count'] or 0, 'total': row['total'] or ZERO}


def payables_overview(today: date) -> dict:
    open_qs = Payable.objects.filter(status=Payable.Status.OPEN)
    return {
        'overdue': _bucket(open_qs.filter(due_date__lt=today), 'amount'),
        'upcoming': _bucket(open_qs.filter(due_date__gte=today), 'amount'),
        'paid': _bucket(Payable.objects.filter(status=Payable.Status.PAID), 'paid_amount'),
    }
