"""Trilha de auditoria da Tesouraria."""

from datetime import date, datetime
from decimal import Decimal

CREATE = 'create'
UPDATE = 'update'
DELETE = 'delete'
CONFIRM = 'confirm'
REJECT = 'reject'
PAY = 'pay'
UNDO_PAY = 'undo_pay'
CANCEL = 'cancel'
CLOSE = 'close'
REOPEN = 'reopen'
COUNT = 'count'
OPINION = 'opinion'
SETTINGS = 'settings'
ARCHIVE = 'archive'

ACTION_CHOICES = [
    (CREATE, 'Criação'), (UPDATE, 'Alteração'), (DELETE, 'Exclusão'), (CONFIRM, 'Confirmação'),
    (REJECT, 'Recusa'), (PAY, 'Pagamento'), (UNDO_PAY, 'Pagamento desfeito'), (CANCEL, 'Cancelamento'),
    (CLOSE, 'Fechamento'), (REOPEN, 'Reabertura'), (COUNT, 'Contagem do caixa'), (OPINION, 'Parecer'),
    (SETTINGS, 'Configuração'), (ARCHIVE, 'Arquivamento'),
]


def _safe(value):
    if isinstance(value, (Decimal, date, datetime)):
        return str(value.isoformat() if isinstance(value, (date, datetime)) else value)
    return value


def snapshot(obj):
    """Valores do objeto seguros para JSON (Decimal e datas como texto; FKs pelo id)."""
    data = {}
    for field in obj._meta.concrete_fields:
        data[field.attname] = _safe(getattr(obj, field.attname))
    return data


def record(user, action, obj, summary, before=None, after=None):
    """Grava uma entrada de auditoria.

    `summary` nunca deve conter nome de membro nem descrição de movimento (a Diretoria
    lê o log): use o padrão ``"Entrada de R$ 120,00 em Dízimos"``. A função grava o que o
    chamador passar, então a regra é de quem chama.
    """
    from .models import AuditLog

    return AuditLog.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        action=action, model=type(obj).__name__, object_id=str(obj.pk),
        summary=summary, before=before, after=after,
    )
