"""Regras de acesso do painel e do portal, num único lugar.

A fonte de verdade é a classificação (`AccessProfile.role`). O flag `is_staff`
do Django é uma consequência dela: os formulários o gravam a partir do papel
(`role in ADMIN_ROLES`). Ele sozinho não basta, porque pode divergir do papel
quando o usuário é editado pelo Django admin ou pelo shell.

Regras:
- Painel: usuário autenticado com `is_staff` e papel administrativo.
  Superusuário sempre entra. Staff sem perfil de acesso continua entrando
  (contas antigas criadas por `createsuperuser`).
- Gestão de usuários: superusuário, Pastor ou Admin (Diretoria).
- Candidaturas e conteúdo confidencial: somente Pastor.
- Financeiro: painel, exceto Pastor.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden

from .models import AccessProfile

Role = AccessProfile.Role


def get_role(user):
    """Papel do usuário, ou None se anônimo ou sem perfil de acesso."""
    if not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.access_profile.role
    except AccessProfile.DoesNotExist:
        return None


def is_panel_user(user):
    if not getattr(user, 'is_authenticated', False) or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    role = get_role(user)
    return role is None or role in AccessProfile.ADMIN_ROLES


def is_pastor(user):
    return get_role(user) == Role.PASTOR


def can_manage_users(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return user.is_superuser or get_role(user) in AccessProfile.USER_MANAGER_ROLES


def can_access_finance(user):
    return is_panel_user(user) and not is_pastor(user)


def staff_required(view):
    return user_passes_test(is_panel_user, login_url='login')(view)


def user_manager_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not can_manage_users(request.user):
            return HttpResponseForbidden('Apenas Pastor e Diretoria podem gerenciar usuários.')
        return view(request, *args, **kwargs)

    return wrapped


def pastor_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not is_pastor(request.user):
            return HttpResponseForbidden('Conteúdo confidencial restrito ao perfil Pastor.')
        return view(request, *args, **kwargs)

    return wrapped


def financial_access_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not can_access_finance(request.user):
            return HttpResponseForbidden('O perfil Pastor não possui acesso à área financeira.')
        return view(request, *args, **kwargs)

    return wrapped
