"""Camada de serviço dos lançamentos: guardas, gravação e auditoria em uma transação."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import audit
from .models import Account, Kind, Movement, Source, Status, Transfer
from .rules import TreasuryError, ensure_after_start, ensure_month_open

MOVEMENT_FIELDS = ('date', 'category', 'description', 'amount', 'account', 'method', 'member', 'destination')


def money(value) -> str:
    """12345.6 -> 'R$ 12.345,60' (sem depender do locale)."""
    text = f'{Decimal(value):,.2f}'
    return 'R$ ' + text.replace(',', '#').replace('.', ',').replace('#', '.')


def _summary(movement) -> str:
    label = 'Entrada' if movement.kind == Kind.INCOME else 'Saída'
    return f'{label} de {money(movement.amount)} em {movement.category.name}'


def _guard(*dates):
    for d in dates:
        ensure_after_start(d)
        ensure_month_open(d)


def _check(fields):
    amount = fields.get('amount')
    if amount is None or Decimal(amount) <= 0:
        raise TreasuryError('O valor deve ser maior que zero.')
    if Decimal(amount).as_tuple().exponent < -2:
        raise TreasuryError('O valor deve ter no máximo duas casas decimais.')
    if not fields.get('account'):
        raise TreasuryError('Informe a conta (Caixa ou Banco) do lançamento.')
    if fields['account'] not in Account.values:
        raise TreasuryError('Conta inválida.')
    category = fields['category']
    if not category.is_special:
        fields['destination'] = ''
    elif not (fields.get('destination') or '').strip():
        raise TreasuryError('Informe o destino da oferta especial.')


def ensure_editable(movement) -> None:
    """Só movimentos vivos e confirmados são alterados aqui; os demais vão pela fila (Task 7)."""
    if movement.deleted_at is not None:
        raise TreasuryError('Este lançamento já foi excluído.')
    if movement.status != Status.CONFIRMED:
        raise TreasuryError('Este lançamento ainda não foi confirmado (ou foi recusado); '
                            'trate-o na tela "A confirmar".')
    ensure_month_open(movement.date)


@transaction.atomic
def create_movement(user, **fields) -> Movement:
    fields = {k: v for k, v in fields.items() if k in MOVEMENT_FIELDS}
    category = fields['category']
    _check(fields)
    _guard(fields['date'])
    movement = Movement.objects.create(
        kind=category.kind, status=Status.CONFIRMED, source=Source.TREASURY, created_by=user, **fields)
    audit.record(user, audit.CREATE, movement, _summary(movement), after=audit.snapshot(movement))
    return movement


@transaction.atomic
def update_movement(user, movement, **fields) -> Movement:
    movement = Movement.objects.select_for_update().select_related('category').get(pk=movement.pk)
    before = audit.snapshot(movement)  # antes de qualquer alteração
    ensure_editable(movement)
    fields = {k: v for k, v in fields.items() if k in MOVEMENT_FIELDS}
    if not fields.get('member'):
        fields.pop('member', None)  # nunca apaga o membro já gravado; só trocar por outro
    merged = {name: getattr(movement, name) for name in MOVEMENT_FIELDS}
    merged.update(fields)
    if merged['category'].kind != movement.kind:
        raise TreasuryError('A categoria deve ser do mesmo tipo do lançamento.')
    _check(merged)
    _guard(movement.date, merged['date'])
    for name, value in merged.items():
        setattr(movement, name, value)
    movement.save()
    audit.record(user, audit.UPDATE, movement, _summary(movement), before=before, after=audit.snapshot(movement))
    return movement


@transaction.atomic
def delete_movement(user, movement) -> None:
    movement = Movement.objects.select_for_update().select_related('category').get(pk=movement.pk)
    before = audit.snapshot(movement)
    ensure_editable(movement)
    _guard(movement.date)
    movement.deleted_at = timezone.now()
    movement.save(update_fields=['deleted_at', 'updated_at'])
    audit.record(user, audit.DELETE, movement, _summary(movement), before=before, after=audit.snapshot(movement))


def _transfer_summary(transfer) -> str:
    names = dict(Account.choices)
    return (f'Transferência de {money(transfer.amount)} de {names[transfer.from_account]} '
            f'para {names[transfer.to_account]}')


@transaction.atomic
def create_transfer(user, **fields) -> Transfer:
    transfer = Transfer(created_by=user, note=fields.get('note', ''), date=fields['date'],
                        from_account=fields['from_account'], to_account=fields['to_account'],
                        amount=Decimal(fields['amount']))
    if transfer.from_account not in Account.values or transfer.to_account not in Account.values:
        raise TreasuryError('Conta inválida.')
    if transfer.from_account == transfer.to_account:
        raise TreasuryError('A conta de origem deve ser diferente da conta de destino.')
    if transfer.amount <= 0:
        raise TreasuryError('O valor deve ser maior que zero.')
    _guard(transfer.date)
    transfer.save()
    audit.record(user, audit.CREATE, transfer, _transfer_summary(transfer), after=audit.snapshot(transfer))
    return transfer


@transaction.atomic
def delete_transfer(user, transfer) -> None:
    transfer = Transfer.objects.select_for_update().get(pk=transfer.pk)
    before = audit.snapshot(transfer)
    if transfer.deleted_at is not None:
        raise TreasuryError('Esta transferência já foi excluída.')
    _guard(transfer.date)
    transfer.deleted_at = timezone.now()
    transfer.save(update_fields=['deleted_at'])
    audit.record(user, audit.DELETE, transfer, _transfer_summary(transfer), before=before,
                 after=audit.snapshot(transfer))
