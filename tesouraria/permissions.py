"""Permissões da Tesouraria, baseadas só no papel (não dependem de `is_staff`)."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.urls import reverse

from core.models import AccessProfile
from core.permissions import get_role, is_panel_user

Role = AccessProfile.Role


def _is_superuser(user):
    return getattr(user, 'is_authenticated', False) and user.is_superuser


def can_edit_treasury(user):
    return bool(_is_superuser(user) or get_role(user) == Role.TREASURER)


def can_view_treasury(user):
    return can_edit_treasury(user) or get_role(user) in (Role.BOARD, Role.COMMITTEE)


def can_view_details(user):
    return can_edit_treasury(user) or get_role(user) == Role.COMMITTEE


def can_see_member_names(user):
    return can_edit_treasury(user) or get_role(user) == Role.COMMITTEE


def can_give_opinion(user):
    return get_role(user) == Role.COMMITTEE


def landing_url(user):
    if get_role(user) in (Role.TREASURER, Role.COMMITTEE):
        return reverse('tesouraria:home')
    return reverse('dashboard' if is_panel_user(user) else 'member_portal')


def _required(predicate, message):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not predicate(request.user):
                return HttpResponseForbidden(message)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


treasury_view_required = _required(can_view_treasury, 'Sem acesso à Tesouraria.')
treasury_detail_required = _required(can_view_details, 'Sem acesso a esta página da Tesouraria.')
treasury_names_required = _required(can_see_member_names, 'Sem acesso aos nomes dos membros.')
treasury_edit_required = _required(can_edit_treasury, 'Apenas o Tesoureiro pode alterar a Tesouraria.')
committee_required = _required(can_give_opinion, 'Apenas a Comissão de Contas pode dar parecer.')
