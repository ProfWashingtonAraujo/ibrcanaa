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
