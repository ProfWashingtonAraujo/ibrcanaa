from django.contrib.auth.models import User
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from datetime import date, timedelta, datetime, timezone as dt_timezone
from io import BytesIO

from pypdf import PdfReader

from .bible import DAILY_VERSES, get_daily_verse
from .models import AccessProfile, BibleFavorite, BibleNote, Book, ChurchHistoryPage, ContactLead, Course, CourseEvaluation, Event, Lesson, LessonProgress, Member, MembershipApplication, Ministry, Transaction


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
        self.assertContains(response, 'Conheça a identidade da Canaã.')
        self.assertContains(response, '#nossa-igreja')
        self.assertContains(response, 'Desenvolvimento e criação por')
        self.assertContains(response, 'https://profwashingtonaraujo.github.io/carcara/')

    def test_home_and_bookstore_show_registered_books(self):
        Book.objects.create(
            title='Crescendo na Graça',
            subtitle='Um guia para a vida cristã',
            author_name='Pr. Washington Araujo',
            description='Livro de edificação para a igreja local.',
            cover_url='https://example.com/capa.jpg',
            preview_url='https://example.com/amostra',
            purchase_url='https://example.com/compra',
            price='39.90',
            is_featured=True,
        )

        home_response = self.client.get(reverse('home'))
        self.assertContains(home_response, 'Publicações')
        self.assertContains(home_response, 'Crescendo na Graça')
        self.assertContains(home_response, reverse('bookstore'))

        bookstore_response = self.client.get(reverse('bookstore'))
        self.assertEqual(bookstore_response.status_code, 200)
        self.assertContains(bookstore_response, 'Publicações pensadas para edificar a igreja.')
        self.assertContains(bookstore_response, 'Crescendo na Graça')
        self.assertContains(bookstore_response, 'R$ 39,90')

    def test_new_church_pages_load(self):
        history_response = self.client.get(reverse('church_history'))
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, 'A caminhada da Canaã ao longo do tempo.')

    def test_church_history_gallery_renders_photo_urls(self):
        ChurchHistoryPage.objects.create(
            photo_1_url='https://example.com/historia.jpg',
        )

        response = self.client.get(reverse('church_history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Foto 01')
        self.assertContains(response, 'https://example.com/historia.jpg')

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

    @patch('core.views.public_youtube_videos')
    def test_home_allows_referrer_identity_for_embedded_players(self, mocked_videos):
        mocked_videos.return_value = [
            {'video_id': 'AAAAAAAAAAA', 'title': 'Vídeo mais recente', 'channel_title': 'Igreja Batista Regular Canaã', 'published': datetime(2026, 8, 24, 12, 0, tzinfo=dt_timezone.utc)},
            {'video_id': 'BBBBBBBBBBB', 'title': 'Segundo vídeo', 'channel_title': 'Igreja Batista Regular Canaã', 'published': datetime(2026, 8, 23, 12, 0, tzinfo=dt_timezone.utc)},
            {'video_id': 'CCCCCCCCCCC', 'title': 'Terceiro vídeo', 'channel_title': 'Igreja Batista Regular Canaã', 'published': datetime(2026, 8, 22, 12, 0, tzinfo=dt_timezone.utc)},
            {'video_id': 'DDDDDDDDDDD', 'title': 'Quarto vídeo', 'channel_title': 'Igreja Batista Regular Canaã', 'published': datetime(2026, 8, 21, 12, 0, tzinfo=dt_timezone.utc)},
        ]
        response = self.client.get(reverse('home'))
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertContains(response, 'params="origin=http://testserver"', count=4)
        self.assertContains(response, 'videoid="AAAAAAAAAAA"')
        self.assertContains(response, 'videoid="BBBBBBBBBBB"')
        self.assertContains(response, 'videoid="CCCCCCCCCCC"')
        self.assertContains(response, 'videoid="DDDDDDDDDDD"')
        self.assertContains(response, 'MENSAGEM EM DESTAQUE · 24/08/2026')

    @patch('core.views.public_youtube_videos')
    def test_public_youtube_videos_feed_exposes_latest_videos(self, mocked_videos):
        mocked_videos.return_value = [
            {'video_id': 'AAAAAAAAAAA', 'title': 'Vídeo mais recente', 'channel_title': 'Igreja Batista Regular Canaã', 'published': datetime(2026, 8, 24, 12, 0, tzinfo=dt_timezone.utc)},
            {'video_id': 'BBBBBBBBBBB', 'title': 'Segundo vídeo', 'channel_title': 'Igreja Batista Regular Canaã', 'published': datetime(2026, 8, 23, 12, 0, tzinfo=dt_timezone.utc)},
        ]
        response = self.client.get(
            reverse('public_youtube_videos_feed'),
            HTTP_ORIGIN='https://profwashingtonaraujo.github.io',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://profwashingtonaraujo.github.io')
        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=300')
        self.assertEqual(response.json()['videos'][0]['video_id'], 'AAAAAAAAAAA')
        self.assertIn('2026-08-24', response.json()['videos'][0]['published'])
        self.assertEqual(response.json()['channel']['url'], 'https://www.youtube.com/@ibrcanaa')

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
            description='Cuidado prático para famílias da comunidade.',
            status=Ministry.Status.RECRUITING,
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Ação Social')
        self.assertContains(response, 'Cuidado prático para famílias da comunidade.')
        self.assertNotContains(response, 'Ana Liderança')
        self.assertContains(response, 'PRECISA DE VOLUNTÁRIOS')

    def test_public_ministry_feed_exposes_only_card_data(self):
        ministry = Ministry.objects.create(
            name='Louvor',
            leader_name='Líder Privado',
            description='Serviço da igreja por meio da música.',
        )
        member = Member.objects.create(
            name='Pessoa Privada',
            email='privado@example.com',
            phone='85999999999',
        )
        member.ministries.add(ministry)
        response = self.client.get(
            reverse('public_ministry_feed'),
            HTTP_ORIGIN='https://profwashingtonaraujo.github.io',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://profwashingtonaraujo.github.io')
        self.assertEqual(response.json(), [{
            'name': 'Louvor',
            'description': 'Serviço da igreja por meio da música.',
            'status': Ministry.Status.ACTIVE,
            'statusLabel': 'Ativo',
        }])
        self.assertNotContains(response, 'Líder Privado')
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
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="nav-symbol"><svg', count=10)
        self.assertContains(response, 'Publicações')
        self.assertContains(response, 'Conteúdo')
        self.assertContains(response, 'class="mobile-logout"')
        self.assertContains(response, 'aria-label="Sair do sistema"')

    def test_staff_can_access_book_admin(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('books'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Publicações')
        self.assertContains(response, 'Novo livro')

    def test_staff_can_access_institutional_content_admin(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('institutional_content'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Conteúdo institucional')
        self.assertContains(response, 'Nossa igreja')
        self.assertContains(response, 'Histórico')

    def test_staff_can_save_church_history_urls(self):
        self.client.login(username='staff', password='test-pass')

        response = self.client.post(reverse('church_history_edit'), {
            'eyebrow': 'Histórico da igreja',
            'heading': 'A caminhada da Canaã ao longo do tempo.',
            'intro': 'Uma linha do tempo para registrar a origem, o crescimento e a missão que continuam moldando a igreja até hoje.',
            'photo_1_url': 'https://example.com/historia-1.jpg',
            'photo_2_url': 'https://example.com/historia-2.jpg',
            'photo_3_url': 'https://example.com/historia-3.jpg',
            'milestone_1_title': 'Fundação',
            'milestone_1_text': 'Texto 1',
            'milestone_2_title': 'Crescimento',
            'milestone_2_text': 'Texto 2',
            'milestone_3_title': 'Hoje',
            'milestone_3_text': 'Texto 3',
        })

        self.assertRedirects(response, reverse('institutional_content'))
        page = ChurchHistoryPage.objects.get(site_key='history')
        self.assertEqual(page.photo_1_url, 'https://example.com/historia-1.jpg')
        self.assertEqual(page.photo_2_url, 'https://example.com/historia-2.jpg')
        self.assertEqual(page.photo_3_url, 'https://example.com/historia-3.jpg')

    def test_pastor_cannot_access_or_see_financial_data(self):
        pastor = User.objects.create_user('pastor.finance', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=pastor, role=AccessProfile.Role.PASTOR)
        Transaction.objects.create(
            date='2026-08-12', description='Valor confidencial', category='Dízimos',
            kind=Transaction.Kind.INCOME, amount='9876.54',
        )
        self.client.login(username='pastor.finance', password='test-pass')

        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertFalse(dashboard.context['show_finances'])
        self.assertNotIn('balance', dashboard.context)
        self.assertNotContains(dashboard, 'Financeiro')
        self.assertNotContains(dashboard, 'Movimentação atual')
        self.assertNotContains(dashboard, '9876,54')

        reports = self.client.get(reverse('reports'))
        self.assertEqual(reports.status_code, 200)
        self.assertNotContains(reports, 'Saldo financeiro')
        self.assertNotContains(reports, '9876,54')
        self.assertEqual(self.client.get(reverse('finance')).status_code, 403)
        self.assertEqual(self.client.get(reverse('transaction_create')).status_code, 403)

        self.client.logout()
        self.client.login(username='staff', password='test-pass')
        self.assertEqual(self.client.get(reverse('finance')).status_code, 200)

    def test_members_can_be_searched_and_filtered(self):
        ministry = Ministry.objects.create(name='Louvor', leader_name='Líder')
        member = Member.objects.create(
            name='Ana Oliveira',
            email='ana@example.com',
            phone='85999990000',
            status=Member.Status.LEADERSHIP,
            frequency=90,
        )
        member.ministries.add(ministry)
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
            'description': 'Acolhimento e cuidado da comunidade.',
            'status': Ministry.Status.RECRUITING,
        })
        self.assertRedirects(create_response, reverse('ministries'))
        ministry = Ministry.objects.get(name='Ação Social')
        self.assertEqual(ministry.description, 'Acolhimento e cuidado da comunidade.')

        list_response = self.client.get(reverse('ministries'), {'q': 'Social'})
        self.assertContains(list_response, 'Ação Social')
        self.assertContains(list_response, 'Líder Social')
        self.assertContains(list_response, '<strong>0</strong> participantes', html=True)

        form_response = self.client.get(reverse('ministry_edit', args=[ministry.pk]))
        self.assertNotIn('members', form_response.context['form'].fields)

        member = self.member_user.member_profile
        member.ministries.add(ministry)
        list_response = self.client.get(reverse('ministries'), {'q': 'Social'})
        self.assertContains(list_response, '<strong>1</strong> participante', html=True)

        edit_response = self.client.post(reverse('ministry_edit', args=[ministry.pk]), {
            'name': 'Ação e Cuidado',
            'leader_name': 'Nova Liderança',
            'description': 'Nova descrição pública.',
            'status': Ministry.Status.ACTIVE,
        })
        self.assertRedirects(edit_response, reverse('ministries'))
        ministry.refresh_from_db()
        self.assertEqual(ministry.name, 'Ação e Cuidado')
        self.assertEqual(ministry.leader_name, 'Nova Liderança')
        self.assertEqual(ministry.description, 'Nova descrição pública.')

        delete_response = self.client.post(reverse('ministry_delete', args=[ministry.pk]))
        self.assertRedirects(delete_response, reverse('ministries'))
        member.refresh_from_db()
        self.assertFalse(member.ministries.exists())

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
        ministry = Ministry.objects.create(name='Recepção', leader_name='Líder')
        response = self.client.post(reverse('member_create'), {
            'name': 'Nova Pessoa',
            'email': 'nova@example.com',
            'phone': '85999999999',
            'ministries': [ministry.pk],
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
        self.assertQuerySetEqual(member.ministries.all(), [ministry])
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

    def test_member_form_uses_ministry_checkboxes(self):
        self.client.login(username='staff', password='test-pass')
        Ministry.objects.create(name='Louvor', leader_name='Líder')
        response = self.client.get(reverse('member_create'))
        field = response.context['form'].fields['ministries']
        self.assertEqual(field.label, 'Ministérios')
        self.assertContains(response, 'type="checkbox"')

    def test_staff_registers_member_personal_and_family_information(self):
        self.client.login(username='staff', password='test-pass')
        form_page = self.client.get(reverse('member_create'))
        self.assertContains(form_page, 'Informações pessoais')
        self.assertContains(form_page, 'Família e estado civil')
        self.assertContains(form_page, 'Filhos')
        self.assertContains(form_page, 'type="date" name="birth_date"')
        self.assertContains(form_page, 'type="date" name="conversion_date"')
        self.assertContains(form_page, 'type="date" name="baptism_date"')
        self.assertContains(form_page, 'type="date" name="church_entry_date"')
        self.assertNotContains(form_page, 'name="frequency"')

        response = self.client.post(reverse('member_create'), {
            'name': 'Pessoa Completa',
            'birth_date': '1988-04-12',
            'address': 'Rua das Flores, 100',
            'email': 'completa@example.com',
            'home_phone': '8533334444',
            'phone': '85999998888',
            'work_phone': '8532221111',
            'profession': 'Professora',
            'education': 'Ensino superior',
            'married': 'True',
            'wedding_date': '2012-06-09',
            'widowed': 'False',
            'divorced': 'False',
            'married_to_divorced': 'False',
            'child_1_name': 'Filho Um',
            'child_1_birth_date': '2015-02-03',
            'ministries': [],
            'status': Member.Status.ACTIVE,
            'conversion_date': '2006-08-14',
            'baptism_date': '2007-01-20',
            'church_entry_date': '2016-02-14',
            'username': 'pessoa.completa',
            'password1': 'SenhaForte@2026',
            'password2': 'SenhaForte@2026',
        })

        self.assertRedirects(response, reverse('members'))
        member = Member.objects.get(email='completa@example.com')
        self.assertEqual(member.birth_date, date(1988, 4, 12))
        self.assertEqual(member.address, 'Rua das Flores, 100')
        self.assertEqual(member.home_phone, '8533334444')
        self.assertEqual(member.phone, '85999998888')
        self.assertEqual(member.profession, 'Professora')
        self.assertTrue(member.married)
        self.assertFalse(member.divorced)
        self.assertEqual(member.child_1_name, 'Filho Um')
        self.assertEqual(member.child_1_birth_date, date(2015, 2, 3))
        self.assertEqual(member.conversion_date, date(2006, 8, 14))
        self.assertEqual(member.baptism_date, date(2007, 1, 20))
        self.assertEqual(member.church_entry_date, date(2016, 2, 14))
        self.assertTrue(member.baptized)
        with patch('core.models.timezone.localdate', return_value=date(2026, 8, 14)):
            self.assertEqual(member.converted_duration, '20 anos')
            self.assertEqual(member.church_duration, '10 anos e 6 meses')

    def test_member_form_rejects_future_family_dates(self):
        self.client.login(username='staff', password='test-pass')
        future_date = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(reverse('member_create'), {
            'name': 'Data Inválida',
            'birth_date': future_date,
            'email': 'data.invalida@example.com',
            'status': Member.Status.ACTIVE,
            'frequency': 0,
            'username': 'data.invalida',
            'password1': 'SenhaForte@2026',
            'password2': 'SenhaForte@2026',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A data não pode estar no futuro.')
        self.assertFalse(Member.objects.filter(email='data.invalida@example.com').exists())

    def test_member_form_limits_ministries_to_three(self):
        self.client.login(username='staff', password='test-pass')
        ministries = [
            Ministry.objects.create(name=f'Ministério {index}', leader_name='Líder')
            for index in range(4)
        ]
        response = self.client.post(reverse('member_create'), {
            'name': 'Muitos Ministérios',
            'email': 'muitos@example.com',
            'ministries': [ministry.pk for ministry in ministries],
            'status': Member.Status.ACTIVE,
            'frequency': 50,
            'username': 'muitos.ministerios',
            'password1': 'SenhaForte@2026',
            'password2': 'SenhaForte@2026',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selecione no máximo 3 ministérios.')
        self.assertFalse(Member.objects.filter(email='muitos@example.com').exists())

    def test_staff_can_reset_member_password(self):
        self.client.login(username='staff', password='test-pass')
        member = self.member_user.member_profile
        response = self.client.post(reverse('member_edit', args=[member.pk]), {
            'name': member.name,
            'email': member.email,
            'phone': '',
            'ministries': [],
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
            'ministries': [],
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
            'ministries': [],
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
            'ministries': [],
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

    def test_staff_can_create_course_and_youtube_lesson(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('course_create'), {
            'title': 'Fundamentos da Fé',
            'description': 'Uma introdução às doutrinas cristãs.',
            'instructor': 'Pr. Teste',
            'cover_url': '',
            'published': 'on',
        })
        course = Course.objects.get(title='Fundamentos da Fé')
        self.assertRedirects(response, reverse('course_manage', args=[course.pk]))

        response = self.client.post(reverse('lesson_create', args=[course.pk]), {
            'title': 'A salvação',
            'youtube_url': 'https://youtu.be/jiIRdV-4rUE',
            'position': 1,
            'description': 'Graça e fé.',
        })
        self.assertRedirects(response, reverse('course_manage', args=[course.pk]))
        lesson = course.lessons.get()
        self.assertEqual(lesson.youtube_id, 'jiIRdV-4rUE')
        self.assertEqual(lesson.embed_url, 'https://www.youtube-nocookie.com/embed/jiIRdV-4rUE')
        self.assertEqual(course.cover_image_url, lesson.thumbnail_url)

        course.cover_url = 'https://youtu.be/MlocoEhWjAs'
        course.save(update_fields=['cover_url'])
        self.assertEqual(course.cover_image_url, 'https://i.ytimg.com/vi/MlocoEhWjAs/hqdefault.jpg')

    def test_lesson_rejects_invalid_youtube_url_and_duplicate_position(self):
        course = Course.objects.create(title='Curso', description='Descrição')
        Lesson.objects.create(
            course=course, title='Primeira', youtube_url='https://www.youtube.com/watch?v=jiIRdV-4rUE', position=1,
        )
        self.client.login(username='staff', password='test-pass')
        invalid = self.client.post(reverse('lesson_create', args=[course.pk]), {
            'title': 'Inválida', 'youtube_url': 'https://example.com/video', 'position': 2,
        })
        self.assertContains(invalid, 'Informe uma URL válida de vídeo do YouTube.')
        duplicate = self.client.post(reverse('lesson_create', args=[course.pk]), {
            'title': 'Duplicada', 'youtube_url': 'https://youtu.be/MlocoEhWjAs', 'position': 1,
        })
        self.assertContains(duplicate, 'Já existe uma aula nesta ordem.')
        self.assertEqual(course.lessons.count(), 1)

    def test_member_sees_only_published_courses_and_can_watch_lesson(self):
        published = Course.objects.create(title='Curso publicado', description='Disponível', published=True)
        lesson = Lesson.objects.create(
            course=published, title='Aula disponível', youtube_url='https://www.youtube.com/watch?v=jiIRdV-4rUE', position=1,
        )
        draft = Course.objects.create(title='Curso secreto', description='Rascunho', published=False)
        self.client.login(username='member', password='test-pass')
        catalog = self.client.get(reverse('member_courses'))
        self.assertContains(catalog, published.title)
        self.assertNotContains(catalog, draft.title)
        classroom = self.client.get(reverse('member_course_lesson', args=[published.pk, lesson.pk]))
        self.assertContains(classroom, 'youtube-nocookie.com/embed/jiIRdV-4rUE')
        self.assertContains(classroom, lesson.title)
        self.assertEqual(self.client.get(reverse('member_course_detail', args=[draft.pk])).status_code, 404)

    def test_course_areas_require_the_correct_access(self):
        self.assertRedirects(
            self.client.get(reverse('member_courses')),
            f"{reverse('login')}?next={reverse('member_courses')}",
        )
        self.client.login(username='member', password='test-pass')
        response = self.client.get(reverse('courses'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('login')}?next={reverse('courses')}")

    def test_member_course_progress_is_private_and_calculated(self):
        course = Course.objects.create(title='Curso progresso', description='Descrição', published=True)
        first = Lesson.objects.create(
            course=course, title='Primeira', youtube_url='https://youtu.be/jiIRdV-4rUE', position=1,
        )
        Lesson.objects.create(
            course=course, title='Segunda', youtube_url='https://youtu.be/MlocoEhWjAs', position=2,
        )
        self.client.login(username='member', password='test-pass')
        response = self.client.post(reverse('lesson_complete', args=[course.pk, first.pk]))
        self.assertRedirects(response, reverse('member_course_lesson', args=[course.pk, first.pk]))
        self.assertTrue(LessonProgress.objects.filter(user=self.member_user, lesson=first).exists())
        classroom = self.client.get(reverse('member_course_detail', args=[course.pk]))
        self.assertEqual(classroom.context['progress_percent'], 50)
        self.assertContains(classroom, '50%')
        self.assertContains(self.client.get(reverse('member_courses')), '50% concluído')

        other = User.objects.create_user('course.other', password='test-pass')
        self.client.logout()
        self.client.login(username=other.username, password='test-pass')
        self.assertEqual(
            self.client.get(reverse('member_course_detail', args=[course.pk])).context['progress_percent'],
            0,
        )

    def test_evaluation_requires_all_lessons_completed(self):
        course = Course.objects.create(title='Curso bloqueado', description='Descrição', published=True)
        Lesson.objects.create(
            course=course, title='Pendente', youtube_url='https://youtu.be/jiIRdV-4rUE', position=1,
        )
        self.client.login(username='member', password='test-pass')
        response = self.client.post(reverse('course_evaluation', args=[course.pk]), {
            'rating': 5, 'learning': 'Aprendizado', 'feedback': '',
        })
        self.assertRedirects(response, reverse('member_course_detail', args=[course.pk]))
        self.assertFalse(CourseEvaluation.objects.filter(user=self.member_user, course=course).exists())

    def test_completed_member_evaluates_and_downloads_own_certificate(self):
        course = Course.objects.create(
            title='Fundamentos Bíblicos', description='Descrição', instructor='Pr. Carlos', published=True,
        )
        lessons = [
            Lesson.objects.create(course=course, title=f'Aula {position}', youtube_url=url, position=position)
            for position, url in [(1, 'https://youtu.be/jiIRdV-4rUE'), (2, 'https://youtu.be/MlocoEhWjAs')]
        ]
        LessonProgress.objects.bulk_create([
            LessonProgress(user=self.member_user, lesson=lesson) for lesson in lessons
        ])
        self.client.login(username='member', password='test-pass')
        self.assertContains(
            self.client.get(reverse('course_evaluation', args=[course.pk])),
            'Enviar e gerar certificado',
        )
        response = self.client.post(reverse('course_evaluation', args=[course.pk]), {
            'rating': 5,
            'learning': 'A importância da doutrina bíblica.',
            'feedback': 'Excelente curso.',
        })
        evaluation = CourseEvaluation.objects.get(user=self.member_user, course=course)
        self.assertRedirects(response, reverse('course_certificate', args=[evaluation.certificate_id]))
        certificate = self.client.get(reverse('course_certificate', args=[evaluation.certificate_id]))
        self.assertEqual(certificate['Content-Type'], 'application/pdf')
        self.assertTrue(certificate.content.startswith(b'%PDF'))
        self.assertIn('attachment;', certificate['Content-Disposition'])
        certificate_text = PdfReader(BytesIO(certificate.content)).pages[0].extract_text()
        self.assertIn('CERTIFICADO DE CONCLUSÃO', certificate_text)
        self.assertIn('Membro Teste', certificate_text)
        self.assertIn('Fundamentos Bíblicos', certificate_text)
        self.assertIn(str(evaluation.certificate_id), certificate_text)

        other = User.objects.create_user('certificate.other', password='test-pass')
        self.client.logout()
        self.client.login(username=other.username, password='test-pass')
        self.assertEqual(
            self.client.get(reverse('course_certificate', args=[evaluation.certificate_id])).status_code,
            404,
        )

    def test_member_portal_shows_personal_summary(self):
        member = self.member_user.member_profile
        member.conversion_date = date(2006, 8, 14)
        member.baptism_date = date(2007, 1, 20)
        member.church_entry_date = date(2016, 2, 14)
        member.save(update_fields=['conversion_date', 'baptism_date', 'church_entry_date'])
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
        self.assertContains(response, 'Tempo de convertido')
        self.assertContains(response, 'Tempo de igreja')
        self.assertContains(response, '20/01/2007')
        self.assertNotContains(response, 'Minha frequência')
        self.assertContains(response, 'tesouraria_001.png')
        self.assertContains(response, 'Contribua também pelo QR Code')

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

    def test_only_pastor_can_access_membership_applications(self):
        pastor = User.objects.create_user('pastor', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=pastor, role=AccessProfile.Role.PASTOR)

        self.client.login(username='staff', password='test-pass')
        self.assertEqual(self.client.get(reverse('membership_applications')).status_code, 403)
        self.client.logout()

        self.client.login(username='member', password='test-pass')
        self.assertEqual(self.client.get(reverse('membership_applications')).status_code, 403)
        self.client.logout()

        self.client.login(username='pastor', password='test-pass')
        response = self.client.get(reverse('membership_applications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Conteúdo confidencial')

    def test_pastor_can_create_and_edit_membership_application(self):
        pastor = User.objects.create_user('pastor', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=pastor, role=AccessProfile.Role.PASTOR)
        self.client.login(username='pastor', password='test-pass')

        response = self.client.post(reverse('membership_application_create'), {
            'status': MembershipApplication.Status.REVIEW,
            'candidate_name': 'Candidato Teste',
            'candidate_email': 'candidato@example.com',
            'mobile_phone': '88999990000',
            'married': 'yes',
            'gospel_understanding': 'Cristo morreu e ressuscitou para salvar pecadores.',
            'recommended': 'yes',
            'received_as': 'assembly',
            'pastoral_notes': 'Entrevista inicial concluída.',
        })
        self.assertRedirects(response, reverse('membership_applications'))
        application = MembershipApplication.objects.get(candidate_email='candidato@example.com')
        self.assertEqual(application.created_by, pastor)
        self.assertEqual(application.responses['mobile_phone'], '88999990000')
        self.assertEqual(application.responses['gospel_understanding'], 'Cristo morreu e ressuscitou para salvar pecadores.')
        self.assertNotIn('recommended', application.responses)
        self.assertEqual(application.pastoral_review['recommended'], 'yes')
        self.assertEqual(application.pastoral_review['pastoral_notes'], 'Entrevista inicial concluída.')

        edit_response = self.client.get(reverse('membership_application_edit', args=[application.pk]))
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'Candidato Teste')
        self.assertContains(edit_response, 'Entrevista inicial concluída.')

    def test_candidate_link_excludes_pastoral_fields_and_requires_consent(self):
        pastor = User.objects.create_user('pastor', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=pastor, role=AccessProfile.Role.PASTOR)
        application = MembershipApplication.objects.create(
            candidate_name='Candidato Externo',
            candidate_email='externo@example.com',
            created_by=pastor,
        )
        url = reverse('membership_candidate_form', args=[application.access_token])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Candidato Externo')
        self.assertContains(response, 'name="consent"')
        self.assertNotContains(response, 'Preenchimento pastoral')
        self.assertNotContains(response, 'name="recommended"')
        self.assertNotContains(response, 'name="status"')

        response = self.client.post(url, {
            'candidate_name': 'Candidato Externo',
            'candidate_email': 'externo@example.com',
            'gospel_understanding': 'O Evangelho é a boa notícia de Cristo.',
            'recommended': 'yes',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo é obrigatório.')
        application.refresh_from_db()
        self.assertIsNone(application.submitted_at)

    def test_candidate_submission_is_stored_and_link_is_locked(self):
        pastor = User.objects.create_user('pastor', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=pastor, role=AccessProfile.Role.PASTOR)
        application = MembershipApplication.objects.create(
            candidate_name='Candidato Externo',
            candidate_email='externo@example.com',
            created_by=pastor,
            pastoral_review={'pastoral_notes': 'Preservar esta anotação.'},
        )
        url = reverse('membership_candidate_form', args=[application.access_token])
        response = self.client.post(url, {
            'candidate_name': 'Candidato Atualizado',
            'candidate_email': 'atualizado@example.com',
            'gospel_understanding': 'Cristo salva pecadores.',
            'recommended': 'yes',
            'consent': 'on',
        })
        self.assertRedirects(response, reverse('membership_candidate_thanks'))
        application.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.Status.REVIEW)
        self.assertIsNotNone(application.submitted_at)
        self.assertIsNotNone(application.consented_at)
        self.assertEqual(application.responses['gospel_understanding'], 'Cristo salva pecadores.')
        self.assertNotIn('recommended', application.responses)
        self.assertEqual(application.pastoral_review['pastoral_notes'], 'Preservar esta anotação.')

        second_response = self.client.get(url)
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, 'Questionário já enviado')
        self.assertNotContains(second_response, '<form method="post"')

    def test_expired_and_revoked_candidate_links_are_unavailable(self):
        pastor = User.objects.create_user('pastor', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=pastor, role=AccessProfile.Role.PASTOR)
        expired = MembershipApplication.objects.create(
            candidate_name='Link Expirado', candidate_email='expirado@example.com',
            created_by=pastor, link_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(
            self.client.get(reverse('membership_candidate_form', args=[expired.access_token])).status_code,
            410,
        )

        active = MembershipApplication.objects.create(
            candidate_name='Link Ativo', candidate_email='ativo@example.com', created_by=pastor,
        )
        self.client.login(username='pastor', password='test-pass')
        response = self.client.post(reverse('membership_application_link_action', args=[active.pk, 'revoke']))
        self.assertRedirects(response, reverse('membership_application_edit', args=[active.pk]))
        active.refresh_from_db()
        self.assertIsNotNone(active.link_revoked_at)
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse('membership_candidate_form', args=[active.access_token])).status_code,
            410,
        )

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
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertContains(response, '<option value="board">Admin</option>', html=True)
        self.assertNotContains(response, '<option value="board">Diretoria</option>', html=True)

    def test_editing_user_name_updates_linked_member_profile(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('user_account_edit', args=[self.member_user.pk]), {
            'first_name': 'Maria',
            'last_name': 'Oliveira',
            'email': 'member@example.com',
            'username': 'member',
            'is_active': 'on',
            'role': AccessProfile.Role.MEMBER,
            'member': self.member_user.member_profile.pk,
            'password1': '',
            'password2': '',
        })

        self.assertRedirects(response, reverse('user_accounts'))
        self.member_user.refresh_from_db()
        self.member_user.member_profile.refresh_from_db()
        self.assertEqual(self.member_user.get_full_name(), 'Maria Oliveira')
        self.assertEqual(self.member_user.member_profile.name, 'Maria Oliveira')

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
