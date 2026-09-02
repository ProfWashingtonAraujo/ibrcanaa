import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import AccessProfile


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


class Command(BaseCommand):
    help = 'Cria ou atualiza um usuário inicial a partir de variáveis de ambiente.'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_BOOTSTRAP_USERNAME', '').strip()
        password = os.environ.get('DJANGO_BOOTSTRAP_PASSWORD', '').strip()
        if not username or not password:
            self.stdout.write(self.style.NOTICE('Bootstrap de usuário ignorado: variáveis não informadas.'))
            return

        user = User.objects.filter(username=username).first() or User(username=username)
        user.first_name = os.environ.get('DJANGO_BOOTSTRAP_FIRST_NAME', user.first_name).strip()
        user.last_name = os.environ.get('DJANGO_BOOTSTRAP_LAST_NAME', user.last_name).strip()
        email = os.environ.get('DJANGO_BOOTSTRAP_EMAIL', '').strip()
        if email:
            user.email = email
        user.is_staff = _env_bool('DJANGO_BOOTSTRAP_IS_STAFF', True)
        user.is_superuser = _env_bool('DJANGO_BOOTSTRAP_IS_SUPERUSER', False)
        user.set_password(password)
        user.save()

        role = os.environ.get('DJANGO_BOOTSTRAP_ROLE', AccessProfile.Role.BOARD).strip() or AccessProfile.Role.BOARD
        AccessProfile.objects.update_or_create(user=user, defaults={'role': role})

        self.stdout.write(self.style.SUCCESS(f'Usuário inicial pronto: {username}'))
