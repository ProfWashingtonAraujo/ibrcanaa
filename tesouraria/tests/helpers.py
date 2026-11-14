from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import override_settings

from core.models import AccessProfile

# O backend do django-axes exige `request` em authenticate(); testes que fazem login
# pela view ou por client.login() usam o backend padrão do Django.
WITHOUT_AXES = override_settings(AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'])


def make_user(username, role=None, *, is_staff=None, is_superuser=False):
    if is_staff is None:
        is_staff = role in AccessProfile.ADMIN_ROLES
    user = User.objects.create_user(
        username, password='senha-forte-123', is_staff=is_staff, is_superuser=is_superuser,
    )
    if role is not None:
        AccessProfile.objects.create(user=user, role=role)
    return user


def configure(start=date(2026, 1, 1), cash='0.00', bank='0.00'):
    from tesouraria.models import TreasurySettings

    settings_obj, _ = TreasurySettings.objects.update_or_create(
        pk=1,
        defaults={'start_date': start, 'opening_cash': Decimal(cash), 'opening_bank': Decimal(bank)},
    )
    return settings_obj
