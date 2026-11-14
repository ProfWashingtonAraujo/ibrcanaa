"""Fila "A confirmar": contribuições vindas do portal esperam a decisão do tesoureiro."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import audit
from .ledger import _guard, money
from .models import Account, Category, Kind, Method, Movement, Source, Status
from .rules import TreasuryError


def _summary(movement, verb) -> str:
    # Sem nome de membro nem descrição: a Diretoria lê o histórico.
    return f'{verb}: entrada de {money(movement.amount)} em {movement.category.name}'


@transaction.atomic
def create_portal_contribution(member, category_name: str, amount: Decimal, note: str = '') -> Movement:
    amount = Decimal(amount)
    if amount <= 0:
        raise TreasuryError('O valor deve ser maior que zero.')
    category = Category.objects.get(name=category_name, kind=Kind.INCOME)
    label = category.name[:-1] if category.name.endswith('s') else category.name
    movement = Movement.objects.create(
        date=timezone.localdate(), kind=Kind.INCOME, amount=amount, category=category,
        description=f'{label} via portal - {member.name}', account=None, method=Method.PIX,
        status=Status.PENDING, source=Source.PORTAL, member=member, created_by=member.user,
        destination=note or '')
    audit.record(member.user, audit.CREATE, movement, _summary(movement, 'Contribuição recebida pelo portal'),
                 after=audit.snapshot(movement))
    return movement


def _lock_pending(movement) -> Movement:
    movement = Movement.objects.select_for_update().select_related('category').get(pk=movement.pk)
    if movement.deleted_at is not None or movement.status != Status.PENDING:
        raise TreasuryError('Este lançamento já foi tratado (confirmado ou recusado) e não está mais na fila.')
    return movement


@transaction.atomic
def confirm_pending(movement, *, user, account: str, method: str, date: date) -> Movement:
    movement = _lock_pending(movement)
    before = audit.snapshot(movement)
    if account not in Account.values:
        raise TreasuryError('Informe a conta (Caixa ou Banco) onde o dinheiro entrou.')
    if method not in Method.values:
        raise TreasuryError('Informe a forma de pagamento.')
    if date is None:
        raise TreasuryError('Informe a data em que o dinheiro entrou.')
    _guard(date)
    movement.account, movement.method, movement.date = account, method, date
    movement.status = Status.CONFIRMED
    movement.save()
    audit.record(user, audit.CONFIRM, movement, _summary(movement, 'Confirmada'),
                 before=before, after=audit.snapshot(movement))
    return movement


@transaction.atomic
def reject_pending(movement, *, user, reason: str) -> Movement:
    movement = _lock_pending(movement)
    before = audit.snapshot(movement)
    reason = (reason or '').strip()
    if not reason:
        raise TreasuryError('Informe o motivo da recusa.')
    movement.status = Status.REJECTED
    movement.rejection_reason = reason
    movement.save()
    audit.record(user, audit.REJECT, movement, _summary(movement, 'Recusada'),
                 before=before, after=audit.snapshot(movement))
    return movement
