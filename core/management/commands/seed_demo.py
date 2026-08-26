from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AccessProfile, Book, Event, Member, Ministry, Transaction


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

        for sort_order, book_data in enumerate([
            {
                'title': 'Crescendo na Graça',
                'subtitle': 'Um guia prático para a vida cristã',
                'description': 'Reflexões sobre discipulado, fé e maturidade espiritual para a igreja local.',
                'cover_url': 'https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=900&q=80',
                'purchase_url': 'https://wa.me/5585999999999',
                'preview_url': '',
                'price': Decimal('39.90'),
                'is_featured': True,
            },
            {
                'title': 'Família e Aliança',
                'subtitle': 'Cristo no centro do lar',
                'description': 'Um estudo devocional para fortalecer casamento, pais e filhos no cotidiano cristão.',
                'cover_url': 'https://images.unsplash.com/photo-1455885666463-83c5b4d7816b?auto=format&fit=crop&w=900&q=80',
                'purchase_url': 'https://wa.me/5585999999999',
                'preview_url': '',
                'price': Decimal('29.90'),
                'is_featured': False,
            },
            {
                'title': 'Fundamentos da Fé',
                'subtitle': 'Doutrina bíblica em linguagem simples',
                'description': 'Material introdutório para novos convertidos e para classes de ensino bíblico.',
                'cover_url': 'https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?auto=format&fit=crop&w=900&q=80',
                'purchase_url': 'https://wa.me/5585999999999',
                'preview_url': '',
                'price': Decimal('24.90'),
                'is_featured': False,
            },
        ], start=1):
            Book.objects.update_or_create(title=book_data['title'], defaults={**book_data, 'sort_order': sort_order})

        member_rows = [
            ('João Silva', 'joao.silva@email.com', 'Louvor e Adoração', Member.Status.ACTIVE, date(2005, 4, 10), date(2005, 9, 18), date(2014, 2, 2)),
            ('Maria Santos', 'maria.santos@email.com', 'Canaã Kids', Member.Status.LEADERSHIP, date(1998, 7, 12), date(1999, 1, 24), date(2008, 5, 11)),
            ('Pedro Oliveira', 'pedro.oliveira@email.com', 'Recepção', Member.Status.ACTIVE, date(2011, 3, 6), date(2011, 8, 21), date(2018, 10, 7)),
            ('Ana Costa', 'ana.costa@email.com', None, Member.Status.VISITOR, None, None, None),
            ('Lucas Souza', 'lucas.souza@email.com', 'Jovens', Member.Status.NEW, date(2025, 11, 9), None, date(2026, 1, 18)),
            ('Carla Dias', 'carla.dias@email.com', 'Intercessão', Member.Status.AWAY, date(2001, 6, 17), date(2002, 2, 10), date(2010, 8, 15)),
        ]
        members = {}
        for name, email, ministry, status, conversion_date, baptism_date, church_entry_date in member_rows:
            members[name], _ = Member.objects.update_or_create(email=email, defaults={
                'name': name,
                'status': status,
                'conversion_date': conversion_date,
                'baptism_date': baptism_date,
                'church_entry_date': church_entry_date,
                'baptized': bool(baptism_date),
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
