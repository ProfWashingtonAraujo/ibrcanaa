from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AccessProfile, Event, Member, Ministry, Transaction


class Command(BaseCommand):
    help = 'Cria dados locais para apresentação e desenvolvimento.'

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(username='diretoria', defaults={
            'first_name': 'Washington',
            'last_name': 'Araújo',
            'email': 'diretoria@ibrcanaa.local',
            'is_staff': True,
            'is_superuser': True,
        })
        admin.set_password('Canaa@2026')
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        AccessProfile.objects.update_or_create(user=admin, defaults={'role': AccessProfile.Role.BOARD})

        ministries = {}
        for name, leader, status in [
            ('Louvor e Adoração', 'João Batista', Ministry.Status.ACTIVE),
            ('Canaã Kids', 'Maria Santos', Ministry.Status.ACTIVE),
            ('Recepção', 'Pedro Oliveira', Ministry.Status.RECRUITING),
            ('Jovens', 'Lucas Souza', Ministry.Status.ACTIVE),
            ('Intercessão', 'Carla Dias', Ministry.Status.ACTIVE),
        ]:
            ministries[name], _ = Ministry.objects.update_or_create(name=name, defaults={'leader_name': leader, 'status': status})

        member_rows = [
            ('João Silva', 'joao.silva@email.com', 'Louvor e Adoração', Member.Status.ACTIVE, 95, True),
            ('Maria Santos', 'maria.santos@email.com', 'Canaã Kids', Member.Status.LEADERSHIP, 100, True),
            ('Pedro Oliveira', 'pedro.oliveira@email.com', 'Recepção', Member.Status.ACTIVE, 80, True),
            ('Ana Costa', 'ana.costa@email.com', None, Member.Status.VISITOR, 20, False),
            ('Lucas Souza', 'lucas.souza@email.com', 'Jovens', Member.Status.NEW, 50, False),
            ('Carla Dias', 'carla.dias@email.com', 'Intercessão', Member.Status.AWAY, 5, True),
        ]
        members = {}
        for name, email, ministry, status, frequency, baptized in member_rows:
            members[name], _ = Member.objects.update_or_create(email=email, defaults={
                'name': name,
                'status': status,
                'frequency': frequency,
                'baptized': baptized,
            })
            members[name].ministries.set([ministries[ministry]] if ministry else [])

        member_user, _ = User.objects.get_or_create(username='membro', defaults={'first_name': 'João', 'last_name': 'Silva', 'email': 'joao.silva@email.com'})
        member_user.set_password('Membro@2026')
        member_user.save()
        AccessProfile.objects.update_or_create(user=member_user, defaults={'role': AccessProfile.Role.MEMBER})
        members['João Silva'].user = member_user
        members['João Silva'].save(update_fields=['user'])

        Event.objects.all().delete()
        now = timezone.now()
        for days, hour, title, kind, location, expected in [
            (3, 18, 'Culto de Celebração', 'Culto', 'Templo principal', 350),
            (6, 19, 'Encontro de Jovens', 'Ministério', 'Salão anexo', 80),
            (10, 9, 'Escola Bíblica', 'Ensino', 'Salas de aula', 120),
            (14, 19, 'Culto de Oração', 'Culto', 'Templo principal', 150),
        ]:
            starts_at = (now + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
            Event.objects.create(title=title, starts_at=starts_at, kind=kind, location=location, expected_attendance=expected)

        Transaction.objects.all().delete()
        for days, description, category, kind, amount, member in [
            (1, 'Dízimo - Membro anônimo', 'Dízimos', Transaction.Kind.INCOME, '500.00', None),
            (2, 'Conta de luz', 'Manutenção', Transaction.Kind.EXPENSE, '350.00', None),
            (3, 'Oferta culto de domingo', 'Ofertas', Transaction.Kind.INCOME, '1250.50', None),
            (5, 'Material escola bíblica', 'Materiais', Transaction.Kind.EXPENSE, '120.00', None),
            (7, 'Dízimo - João Silva', 'Dízimos', Transaction.Kind.INCOME, '1000.00', members['João Silva']),
            (9, 'Ajuda missionária', 'Missões', Transaction.Kind.EXPENSE, '800.00', None),
        ]:
            Transaction.objects.create(date=date.today() - timedelta(days=days), description=description, category=category, kind=kind, amount=Decimal(amount), member=member)

        self.stdout.write(self.style.SUCCESS('Dados criados. Diretoria: diretoria / Canaa@2026 | Membro: membro / Membro@2026'))
