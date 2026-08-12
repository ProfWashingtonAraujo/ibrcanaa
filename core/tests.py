from django.contrib.auth.models import User
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch
from datetime import date

from .bible import DAILY_VERSES, get_daily_verse
from .models import AccessProfile, BibleFavorite, BibleNote, ContactLead, Event, Member, Ministry, Transaction


class PublicViewsTests(TestCase):
    def test_daily_verse_changes_with_the_date(self):
        first = get_daily_verse(date(2026, 8, 12))
        second = get_daily_verse(date(2026, 8, 13))
        self.assertNotEqual(first['reference'], second['reference'])
        self.assertIn(first['reference'], {verse['reference'] for verse in DAILY_VERSES})
        self.assertEqual(first['date'], '2026-08-12')

    def test_home_loads(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Doutrina, comunhão e serviço')
        self.assertContains(response, 'Uma igreja fundamentada nas Escrituras')
        self.assertContains(response, 'Ensino fiel da Palavra de Deus')
        self.assertContains(response, 'Fidelidade à Palavra, fé em Cristo e comunhão verdadeira.')
        self.assertContains(response, 'Desenvolvimento e criação por')
        self.assertContains(response, 'https://profwashingtonaraujo.github.io/carcara/')

    def test_contact_form_saves(self):
        response = self.client.post(reverse('home'), {
            'name': 'Visitante',
            'email': 'visitante@example.com',
            'whatsapp': '85999999999',
            'interest': 'visit',
            'message': 'Quero planejar uma visita.',
        })
        self.assertRedirects(response, reverse('contact_thanks'))
        self.assertEqual(ContactLead.objects.count(), 1)

    def test_home_has_public_calendar(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'id="public-calendar"')
        self.assertContains(response, reverse('public_event_feed'))

    def test_home_allows_referrer_identity_for_embedded_players(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertContains(response, 'params="origin=https://ibrcanaa.onrender.com"', count=4)
        self.assertContains(response, 'videoid="jiIRdV-4rUE"')
        self.assertContains(response, 'videoid="MlocoEhWjAs"')
        self.assertContains(response, 'videoid="pkkm0wvwgHY"')

    def test_home_shows_church_location_and_service_times(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'R. Delmiro Gouvêia, 1074')
        self.assertContains(response, 'Culto de oração · 19h')
        self.assertContains(response, 'EBEC · 19h')
        self.assertContains(response, 'Mocidade · 19h')
        self.assertContains(response, 'EBD · 9h')
        self.assertContains(response, 'churchLocation = [-7.2132769, -39.32141]')

    def test_home_reflects_registered_ministries(self):
        Ministry.objects.create(
            name='Ação Social',
            leader_name='Ana Liderança',
            status=Ministry.Status.RECRUITING,
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Ação Social')
        self.assertContains(response, 'Liderança: Ana Liderança')
        self.assertContains(response, 'PRECISA DE VOLUNTÁRIOS')

    def test_public_ministry_feed_exposes_only_card_data(self):
        ministry = Ministry.objects.create(name='Louvor', leader_name='Líder Público')
        Member.objects.create(
            name='Pessoa Privada',
            email='privado@example.com',
            phone='85999999999',
            ministry=ministry,
        )
        response = self.client.get(
            reverse('public_ministry_feed'),
            HTTP_ORIGIN='https://profwashingtonaraujo.github.io',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://profwashingtonaraujo.github.io')
        self.assertEqual(response.json(), [{
            'name': 'Louvor',
            'leader': 'Líder Público',
            'status': Ministry.Status.ACTIVE,
            'statusLabel': 'Ativo',
        }])
        self.assertNotContains(response, 'Pessoa Privada')
        self.assertNotContains(response, 'privado@example.com')

    def test_public_ministry_feed_rejects_unknown_cors_origin(self):
        response = self.client.get(
            reverse('public_ministry_feed'),
            HTTP_ORIGIN='https://example.com',
        )
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

    def test_home_and_public_feed_show_daily_verse(self):
        home_response = self.client.get(reverse('home'))
        verse = get_daily_verse()
        self.assertContains(home_response, 'Versículo do dia')
        self.assertContains(home_response, verse['text'])
        self.assertContains(home_response, verse['reference'])

        feed_response = self.client.get(
            reverse('public_daily_verse'),
            HTTP_ORIGIN='https://profwashingtonaraujo.github.io',
        )
        self.assertEqual(feed_response.json(), verse)
        self.assertEqual(feed_response.headers['Access-Control-Allow-Origin'], 'https://profwashingtonaraujo.github.io')
        self.assertEqual(feed_response.headers['Cache-Control'], 'public, max-age=3600')

    def test_public_calendar_feed_exposes_only_public_event_details(self):
        from core.views import sync_calendar_event

        event = Event.objects.create(
            title='Culto Público',
            starts_at='2026-08-15T19:00:00-03:00',
            kind='Culto',
            location='Templo principal',
            expected_attendance=100,
            description='Celebração aberta.',
        )
        sync_calendar_event(event)

        response = self.client.get(reverse('public_event_feed'), {
            'start': '2026-08-01T00:00:00-03:00',
            'end': '2026-09-01T00:00:00-03:00',
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()[0]
        self.assertEqual(payload['title'], 'Culto Público')
        self.assertEqual(payload['extendedProps']['location'], 'Templo principal')
        self.assertNotIn('churchEventId', payload['extendedProps'])
        self.assertNotIn('expectedAttendance', payload['extendedProps'])


class AccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.staff, role=AccessProfile.Role.BOARD)
        self.member_user = User.objects.create_user('member', password='test-pass')
        AccessProfile.objects.create(user=self.member_user, role=AccessProfile.Role.MEMBER)
        Member.objects.create(user=self.member_user, name='Membro Teste', email='member@example.com')

    def test_admin_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_staff_can_access_dashboard(self):
        self.client.login(username='staff', password='test-pass')
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_members_can_be_searched_and_filtered(self):
        ministry = Ministry.objects.create(name='Louvor', leader_name='Líder')
        Member.objects.create(
            name='Ana Oliveira',
            email='ana@example.com',
            phone='85999990000',
            ministry=ministry,
            status=Member.Status.LEADERSHIP,
            frequency=90,
        )
        Member.objects.create(name='Bruno Lima', email='bruno@example.com', status=Member.Status.AWAY)
        self.client.login(username='staff', password='test-pass')

        response = self.client.get(reverse('members'), {
            'q': 'Ana',
            'status': Member.Status.LEADERSHIP,
            'ministry': ministry.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Oliveira')
        self.assertNotContains(response, 'Bruno Lima')
        self.assertEqual(response.context['filtered_count'], 1)

    def test_members_page_paginates_results(self):
        Member.objects.bulk_create([
            Member(name=f'Pessoa {index:02}', email=f'pessoa{index}@example.com')
            for index in range(13)
        ])
        self.client.login(username='staff', password='test-pass')

        response = self.client.get(reverse('members'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['members']), 12)
        self.assertTrue(response.context['members'].has_next())

    def test_staff_can_manage_ministries(self):
        self.client.login(username='staff', password='test-pass')
        create_response = self.client.post(reverse('ministry_create'), {
            'name': 'Ação Social',
            'leader_name': 'Líder Social',
            'status': Ministry.Status.RECRUITING,
        })
        self.assertRedirects(create_response, reverse('ministries'))
        ministry = Ministry.objects.get(name='Ação Social')

        list_response = self.client.get(reverse('ministries'), {'q': 'Social'})
        self.assertContains(list_response, 'Ação Social')
        self.assertContains(list_response, 'Líder Social')

        edit_response = self.client.post(reverse('ministry_edit', args=[ministry.pk]), {
            'name': 'Ação e Cuidado',
            'leader_name': 'Nova Liderança',
            'status': Ministry.Status.ACTIVE,
        })
        self.assertRedirects(edit_response, reverse('ministries'))
        ministry.refresh_from_db()
        self.assertEqual(ministry.name, 'Ação e Cuidado')
        self.assertEqual(ministry.leader_name, 'Nova Liderança')

        member = self.member_user.member_profile
        member.ministry = ministry
        member.save(update_fields=['ministry'])
        delete_response = self.client.post(reverse('ministry_delete', args=[ministry.pk]))
        self.assertRedirects(delete_response, reverse('ministries'))
        member.refresh_from_db()
        self.assertIsNone(member.ministry)

    def test_ministry_delete_rejects_get(self):
        ministry = Ministry.objects.create(name='Protegido', leader_name='Líder')
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('ministry_delete', args=[ministry.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Ministry.objects.filter(pk=ministry.pk).exists())

    def test_member_cannot_access_ministry_management(self):
        self.client.login(username='member', password='test-pass')
        response = self.client.get(reverse('ministries'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('ministries')}")

    def test_staff_creates_member_with_individual_login(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('member_create'), {
            'name': 'Nova Pessoa',
            'email': 'nova@example.com',
            'phone': '85999999999',
            'ministry': '',
            'status': Member.Status.ACTIVE,
            'frequency': 70,
            'baptized': '',
            'avatar_url': '',
            'username': 'nova.pessoa',
            'password1': 'SenhaForte@2026',
            'password2': 'SenhaForte@2026',
        })

        self.assertRedirects(response, reverse('members'))
        member = Member.objects.get(email='nova@example.com')
        self.assertEqual(member.user.username, 'nova.pessoa')
        self.client.logout()
        login_response = self.client.post(reverse('login'), {
            'username': 'nova.pessoa',
            'password': 'SenhaForte@2026',
        })
        self.assertRedirects(login_response, reverse('member_portal'))

    def test_member_password_confirmation_is_required(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('member_create'), {
            'name': 'Senha Divergente',
            'email': 'divergente@example.com',
            'status': Member.Status.ACTIVE,
            'frequency': 0,
            'username': 'divergente',
            'password1': 'SenhaForte@2026',
            'password2': 'OutraSenha@2026',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'As senhas não coincidem')
        self.assertFalse(Member.objects.filter(email='divergente@example.com').exists())

    def test_staff_can_reset_member_password(self):
        self.client.login(username='staff', password='test-pass')
        member = self.member_user.member_profile
        response = self.client.post(reverse('member_edit', args=[member.pk]), {
            'name': member.name,
            'email': member.email,
            'phone': '',
            'ministry': '',
            'status': member.status,
            'frequency': member.frequency,
            'baptized': '',
            'avatar_url': '',
            'username': self.member_user.username,
            'password1': 'NovaSenha@2026',
            'password2': 'NovaSenha@2026',
        })
        self.assertRedirects(response, reverse('members'))
        self.member_user.refresh_from_db()
        self.assertTrue(self.member_user.check_password('NovaSenha@2026'))

    def test_editing_member_without_password_keeps_current_password(self):
        original_password = self.member_user.password
        member = self.member_user.member_profile
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('member_edit', args=[member.pk]), {
            'name': member.name,
            'email': member.email,
            'phone': '85999990000',
            'ministry': '',
            'status': member.status,
            'frequency': member.frequency,
            'baptized': '',
            'avatar_url': '',
            'username': self.member_user.username,
            'password1': '',
            'password2': '',
        })
        self.assertRedirects(response, reverse('members'))
        self.member_user.refresh_from_db()
        self.assertEqual(self.member_user.password, original_password)

    def test_member_form_uploads_photo_to_access_profile(self):
        import base64

        photo = SimpleUploadedFile(
            'membro.png',
            base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='),
            content_type='image/png',
        )
        member = self.member_user.member_profile
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('member_edit', args=[member.pk]), {
            'name': member.name,
            'email': member.email,
            'phone': '',
            'ministry': '',
            'status': member.status,
            'frequency': member.frequency,
            'baptized': '',
            'username': self.member_user.username,
            'photo': photo,
            'password1': '',
            'password2': '',
        })
        self.assertRedirects(response, reverse('members'))
        self.member_user.access_profile.refresh_from_db()
        photo_name = self.member_user.access_profile.photo.name
        self.assertTrue(photo_name.startswith('usuarios/'))

        response = self.client.post(reverse('member_edit', args=[member.pk]), {
            'name': member.name,
            'email': member.email,
            'phone': '',
            'ministry': '',
            'status': member.status,
            'frequency': member.frequency,
            'baptized': '',
            'username': self.member_user.username,
            'password1': '',
            'password2': '',
        })
        self.assertRedirects(response, reverse('members'))
        self.member_user.access_profile.refresh_from_db()
        self.assertEqual(self.member_user.access_profile.photo.name, photo_name)

    def test_event_creation_syncs_swingtime_and_feeds_calendar(self):
        from swingtime.models import Occurrence

        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('event_create'), {
            'title': 'Culto de Teste',
            'starts_at': '2026-08-15T19:00',
            'kind': 'Culto',
            'location': 'Templo principal',
            'expected_attendance': 120,
            'description': 'Celebração da comunidade.',
        })

        self.assertRedirects(response, reverse('events'))
        event = Event.objects.get(title='Culto de Teste')
        self.assertIsNotNone(event.calendar_event_id)
        self.assertEqual(Occurrence.objects.filter(event=event.calendar_event).count(), 1)

        feed = self.client.get(reverse('event_feed'), {
            'start': '2026-08-01T00:00:00-03:00',
            'end': '2026-09-01T00:00:00-03:00',
            'kind': 'Culto',
        })
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.json()[0]['title'], 'Culto de Teste')
        self.assertEqual(feed.json()[0]['extendedProps']['location'], 'Templo principal')

    def test_events_page_loads_fullcalendar(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('events'))
        self.assertContains(response, 'fullcalendar@6.1.19')
        self.assertContains(response, reverse('event_feed'))

    def test_staff_can_edit_and_delete_event_with_swingtime(self):
        from swingtime.models import Occurrence

        self.client.login(username='staff', password='test-pass')
        self.client.post(reverse('event_create'), {
            'title': 'Encontro Inicial',
            'starts_at': '2026-08-15T19:00',
            'kind': 'Culto',
            'location': 'Templo',
            'expected_attendance': 80,
            'description': '',
        })
        event = Event.objects.get(title='Encontro Inicial')
        calendar_event_id = event.calendar_event_id

        response = self.client.post(reverse('event_edit', args=[event.pk]), {
            'title': 'Encontro Atualizado',
            'starts_at': '2026-08-16T20:00',
            'kind': 'Ensino',
            'location': 'Sala de aula',
            'expected_attendance': 50,
            'description': 'Novo conteúdo.',
        })
        self.assertRedirects(response, reverse('events'))
        event.refresh_from_db()
        occurrence = Occurrence.objects.get(event_id=calendar_event_id)
        self.assertEqual(event.title, 'Encontro Atualizado')
        self.assertEqual(occurrence.start_time, event.starts_at)

        response = self.client.post(reverse('event_delete', args=[event.pk]))
        self.assertRedirects(response, reverse('events'))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
        self.assertFalse(Occurrence.objects.filter(event_id=calendar_event_id).exists())

    def test_event_delete_rejects_get(self):
        self.client.login(username='staff', password='test-pass')
        event = Event.objects.create(
            title='Protegido',
            starts_at='2026-08-15T19:00:00-03:00',
            kind='Culto',
            location='Templo',
        )
        self.assertEqual(self.client.get(reverse('event_delete', args=[event.pk])).status_code, 403)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_member_can_access_portal(self):
        self.client.login(username='member', password='test-pass')
        response = self.client.get(reverse('member_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Membro Teste')

    def test_member_portal_shows_personal_summary(self):
        Transaction.objects.create(
            date='2026-08-01',
            description='Contribuição mensal',
            category='Dízimos',
            kind=Transaction.Kind.INCOME,
            amount='150.00',
            member=self.member_user.member_profile,
        )
        self.client.login(username='member', password='test-pass')

        response = self.client.get(reverse('member_portal'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Olá, Membro.')
        self.assertContains(response, 'R$ 150,00')
        self.assertContains(response, 'Minha frequência')

    def test_member_contribution_updates_finance_dashboard(self):
        member = self.member_user.member_profile
        self.client.login(username='member', password='test-pass')

        response = self.client.post(reverse('member_portal'), {
            'category': 'Dízimos',
            'amount': '250.50',
            'note': 'Contribuição de agosto',
            'member': '999',
            'kind': Transaction.Kind.EXPENSE,
        })

        self.assertRedirects(response, reverse('member_portal'))
        contribution = Transaction.objects.get(member=member, amount='250.50')
        self.assertEqual(contribution.kind, Transaction.Kind.INCOME)
        self.assertEqual(contribution.category, 'Dízimos')

        portal = self.client.get(reverse('member_portal'))
        self.assertContains(portal, 'R$ 250,50')
        self.client.logout()
        self.client.login(username='staff', password='test-pass')
        finance = self.client.get(reverse('finance'))
        self.assertEqual(finance.context['income'], contribution.amount)
        self.assertContains(finance, 'Contribuição de agosto')

    def test_invalid_member_contribution_is_not_recorded(self):
        self.client.login(username='member', password='test-pass')
        response = self.client.post(reverse('member_portal'), {
            'category': 'Ofertas',
            'amount': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Certifique-se que este valor seja maior ou igual a 1.00')
        self.assertEqual(Transaction.objects.count(), 0)

    @patch('core.views.fetch_chapter')
    def test_member_can_read_bible_and_save_private_note(self, fetch_chapter):
        fetch_chapter.return_value = {
            'reference': 'João 3',
            'translation_name': 'João Ferreira de Almeida',
            'translation_note': 'Public Domain',
            'verses': [{'verse': 16, 'text': 'Porque Deus amou o mundo.'}],
        }
        self.client.login(username='member', password='test-pass')
        reader = self.client.get(reverse('bible_reader'), {'livro': 'joao', 'capitulo': 3})
        self.assertEqual(reader.status_code, 200)
        self.assertContains(reader, 'Porque Deus amou o mundo.')

        response = self.client.post(reverse('bible_note_save'), {
            'book': 'joao',
            'chapter': 3,
            'content': 'Deus demonstrou seu amor em Cristo.',
        })
        self.assertRedirects(response, f"{reverse('bible_reader')}?livro=joao&capitulo=3#anotacao")
        note = BibleNote.objects.get(user=self.member_user)
        self.assertEqual(note.reference, 'João 3')

        other_user = User.objects.create_user('other', password='test-pass')
        self.assertFalse(BibleNote.objects.filter(user=other_user).exists())

    @patch('core.views.fetch_chapter')
    def test_favorite_text_is_loaded_from_server_not_post(self, fetch_chapter):
        fetch_chapter.return_value = {
            'verses': [{'verse': 16, 'text': 'Texto bíblico validado.'}],
        }
        self.client.login(username='member', password='test-pass')
        response = self.client.post(reverse('bible_favorite_toggle'), {
            'book': 'joao',
            'chapter': 3,
            'verse': 16,
            'text': '<script>texto forjado</script>',
        })
        self.assertRedirects(response, f"{reverse('bible_reader')}?livro=joao&capitulo=3#v16")
        favorite = BibleFavorite.objects.get(user=self.member_user)
        self.assertEqual(favorite.text, 'Texto bíblico validado.')

        self.client.post(reverse('bible_favorite_toggle'), {
            'book': 'joao', 'chapter': 3, 'verse': 16,
        })
        self.assertFalse(BibleFavorite.objects.filter(pk=favorite.pk).exists())

    def test_bible_area_requires_login(self):
        response = self.client.get(reverse('bible_reader'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('bible_reader')}")

    def test_board_can_create_classified_user(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('user_account_create'), {
            'first_name': 'Paulo',
            'last_name': 'Pastor',
            'email': 'pastor@example.com',
            'username': 'pastor.paulo',
            'is_active': 'on',
            'role': AccessProfile.Role.PASTOR,
            'member': '',
            'password1': 'SenhaForte@2026',
            'password2': 'SenhaForte@2026',
        })
        self.assertRedirects(response, reverse('user_accounts'))
        user = User.objects.get(username='pastor.paulo')
        self.assertTrue(user.is_staff)
        self.assertEqual(user.access_profile.role, AccessProfile.Role.PASTOR)

    def test_treasurer_cannot_manage_users(self):
        treasurer = User.objects.create_user('tesoureiro', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=treasurer, role=AccessProfile.Role.TREASURER)
        self.client.login(username='tesoureiro', password='test-pass')
        response = self.client.get(reverse('user_accounts'))
        self.assertEqual(response.status_code, 403)

    def test_board_cannot_delete_or_demote_self(self):
        self.client.login(username='staff', password='test-pass')
        delete_response = self.client.post(reverse('user_account_delete', args=[self.staff.pk]))
        self.assertRedirects(delete_response, reverse('user_accounts'))
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())

        edit_response = self.client.post(reverse('user_account_edit', args=[self.staff.pk]), {
            'first_name': 'Staff',
            'last_name': '',
            'email': 'staff@example.com',
            'username': 'staff',
            'is_active': 'on',
            'role': AccessProfile.Role.MEMBER,
            'member': '',
            'password1': '',
            'password2': '',
        })
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'Você não pode remover sua própria permissão de gestão')
        self.staff.access_profile.refresh_from_db()
        self.assertEqual(self.staff.access_profile.role, AccessProfile.Role.BOARD)

    def test_member_autocomplete_is_restricted_to_user_managers(self):
        available = Member.objects.create(name='Ana Disponível', email='ana.disponivel@example.com')
        self.client.login(username='member', password='test-pass')
        denied = self.client.get(reverse('member_autocomplete'), {'q': 'Ana'})
        self.assertEqual(denied.status_code, 200)
        self.assertEqual(denied.json()['results'], [])

        self.client.logout()
        self.client.login(username='staff', password='test-pass')
        allowed = self.client.get(reverse('member_autocomplete'), {'q': 'Ana'})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()['results'][0]['id'], str(available.pk))

    def test_user_form_loads_dal_select2_assets(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('user_account_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-autocomplete-light-function="select2"')
        self.assertContains(response, reverse('member_autocomplete'))

    def test_user_photo_upload_is_saved_and_preserved(self):
        import base64

        photo = SimpleUploadedFile(
            'perfil.png',
            base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='),
            content_type='image/png',
        )
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('user_account_edit', args=[self.member_user.pk]), {
            'first_name': 'Membro',
            'last_name': 'Teste',
            'email': 'member@example.com',
            'username': 'member',
            'is_active': 'on',
            'role': AccessProfile.Role.MEMBER,
            'member': self.member_user.member_profile.pk,
            'photo': photo,
            'password1': '',
            'password2': '',
        })
        self.assertRedirects(response, reverse('user_accounts'))
        self.member_user.access_profile.refresh_from_db()
        photo_name = self.member_user.access_profile.photo.name
        self.assertTrue(photo_name.startswith('usuarios/'))

        response = self.client.post(reverse('user_account_edit', args=[self.member_user.pk]), {
            'first_name': 'Membro',
            'last_name': 'Teste',
            'email': 'member@example.com',
            'username': 'member',
            'is_active': 'on',
            'role': AccessProfile.Role.MEMBER,
            'member': self.member_user.member_profile.pk,
            'password1': '',
            'password2': '',
        })
        self.assertRedirects(response, reverse('user_accounts'))
        self.member_user.access_profile.refresh_from_db()
        self.assertEqual(self.member_user.access_profile.photo.name, photo_name)

# Create your tests here.
