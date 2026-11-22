import json
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from datetime import date, timedelta
from io import BytesIO, StringIO

from cloudinary.exceptions import AuthorizationRequired
from pypdf import PdfReader

from .bible import DAILY_VERSES, get_daily_verse
from .models import AccessProfile, BibleFavorite, BibleNote, Book, ChurchAboutPage, ChurchHistoryPage, ContactLead, Course, CourseEvaluation, Event, Lesson, LessonProgress, Member, MembershipApplication, Ministry, Transaction
from tesouraria.models import Category, Kind, Movement, Status

# Estas classes testam autorização, não o limite de login. O backend do django-axes exige
# `request` em authenticate(), que client.login() não envia. O limite de login é coberto
# em core/test_throttling.py, com o backend do axes ativo.
WITHOUT_AXES = override_settings(AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'])



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
        self.assertContains(response, 'Horários')
        self.assertContains(response, 'Uma igreja fundamentada nas Escrituras')
        self.assertContains(response, 'Ensino fiel da Palavra de Deus')
        self.assertContains(response, 'Conheça a identidade da Canaã.')
        self.assertContains(response, '#nossa-igreja')
        self.assertContains(response, 'Desenvolvimento e criação por')
        self.assertContains(response, 'https://carcaratech.com.br')

    def test_home_uses_fallback_when_database_is_unavailable(self):
        with patch.object(ChurchAboutPage.objects, 'get_or_create', side_effect=OperationalError('db offline')):
            response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Conteúdo temporariamente indisponível.')
        self.assertContains(response, 'Estamos restaurando as informações desta seção.')
        self.assertContains(response, 'Em breve, novas oportunidades para servir.')

    def test_home_embeds_configured_spotify_playlist(self):
        ChurchAboutPage.objects.create(
            spotify_playlist_title='Louvores da Canaã',
            spotify_playlist_text='Canções selecionadas pela nossa igreja.',
            spotify_playlist_url='https://open.spotify.com/playlist/abc123XYZ?si=tracking',
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'id="playlist"')
        self.assertContains(response, 'Louvores da Canaã')
        self.assertContains(response, 'https://open.spotify.com/embed/playlist/abc123XYZ?utm_source=generator&amp;theme=0')
        self.assertContains(response, 'Abrir no Spotify')

    @patch('core.models.latest_episode', return_value=None)
    def test_home_embeds_configured_spotify_show_when_spotify_is_unavailable(self, _latest):
        ChurchAboutPage.objects.create(
            spotify_playlist_title='Série em Atos dos Apóstolos - Episódio 23',
            spotify_playlist_url='https://open.spotify.com/show/7cIt85QzUPeO10vOLYDsAp?si=tracking',
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Série em Atos dos Apóstolos - Episódio 23')
        self.assertContains(response, 'https://open.spotify.com/embed/show/7cIt85QzUPeO10vOLYDsAp?utm_source=generator&amp;theme=0')

    @patch('core.models.latest_episode', return_value={'id': 'EP123abc', 'title': 'Quando a Ira de Deus se Manifesta', 'released': ''})
    def test_home_follows_latest_episode_of_spotify_show(self, latest):
        ChurchAboutPage.objects.create(
            spotify_playlist_title='Título manual',
            spotify_playlist_url='https://open.spotify.com/show/7cIt85QzUPeO10vOLYDsAp?si=tracking',
        )

        response = self.client.get(reverse('home'))

        latest.assert_called_once_with('7cIt85QzUPeO10vOLYDsAp')
        self.assertContains(response, 'Quando a Ira de Deus se Manifesta')
        self.assertNotContains(response, 'Título manual')
        self.assertContains(response, 'https://open.spotify.com/embed/episode/EP123abc?utm_source=generator&amp;theme=0')
        self.assertContains(response, 'href="https://open.spotify.com/episode/EP123abc"')

    def test_home_hides_invalid_spotify_playlist(self):
        ChurchAboutPage.objects.create(spotify_playlist_url='https://example.com/playlist/abc123')

        response = self.client.get(reverse('home'))

        self.assertNotContains(response, 'class="spotify-section"')

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
        self.assertContains(history_response, 'Uma história guiada pela fidelidade de Deus.')

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

    def test_home_service_board_lists_schedule_and_marks_today(self):
        from datetime import datetime
        from unittest import mock
        from django.utils import timezone

        sunday = timezone.make_aware(datetime(2026, 11, 15, 10, 0))
        with mock.patch('core.views.timezone.localdate', return_value=sunday.date()):
            response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="horarios"')
        self.assertContains(response, '<span class="horarios-name">EBD <span class="horarios-today">Hoje</span>')
        self.assertContains(response, '<span class="horarios-name">Culto <span class="horarios-today">Hoje</span>')
        self.assertContains(response, '<span class="horarios-name">EBEC</span>')

    def test_public_pages_have_mobile_menu(self):
        for name in ('home', 'bookstore', 'church_history'):
            response = self.client.get(reverse(name))
            self.assertContains(response, 'class="nav-toggle"', msg_prefix=name)
            self.assertContains(response, 'aria-controls="public-menu"', msg_prefix=name)
            self.assertContains(response, 'id="public-menu"', msg_prefix=name)
            self.assertContains(response, 'js/public-nav.js', msg_prefix=name)

    def test_home_service_board_hides_live_badge_when_offline(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'data-live-badge hidden')

    def test_home_shows_church_location_and_service_times(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'R. Delmiro Gouvêia, 1074')
        self.assertContains(response, 'Culto de oração, 19h')
        self.assertContains(response, 'EBEC, 19h')
        self.assertContains(response, 'Mocidade, 19h')
        self.assertContains(response, 'EBD, 9h')
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
        self.assertEqual(payload['backgroundColor'], '#2752b3')
        self.assertEqual(payload['borderColor'], '#2752b3')
        self.assertEqual(payload['extendedProps']['location'], 'Templo principal')
        self.assertNotIn('churchEventId', payload['extendedProps'])
        self.assertNotIn('expectedAttendance', payload['extendedProps'])


@WITHOUT_AXES
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
        self.assertContains(response, 'class="nav-symbol"><svg', count=9)
        self.assertContains(response, 'Publicações')
        self.assertContains(response, 'Conteúdo')
        self.assertContains(response, 'class="side-logout"')
        self.assertContains(response, 'class="menu-button"')
        self.assertContains(response, 'href="#conteudo"')

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

    def test_church_about_form_rejects_non_spotify_playlist(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.post(reverse('church_about_edit'), {
            'eyebrow': 'Nossa igreja',
            'heading': 'Conheça a identidade da Canaã.',
            'intro': 'Introdução',
            'highlight_1_title': 'Destaque 1',
            'highlight_1_text': 'Texto 1',
            'highlight_2_title': 'Destaque 2',
            'highlight_2_text': 'Texto 2',
            'highlight_3_title': 'Destaque 3',
            'highlight_3_text': 'Texto 3',
            'spotify_playlist_title': 'Playlist',
            'spotify_playlist_text': 'Descrição',
            'spotify_playlist_url': 'https://example.com/playlist/invalida',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe o link público de uma playlist, programa ou episódio do Spotify.')

    def test_staff_can_save_church_history_urls(self):
        self.client.login(username='staff', password='test-pass')

        response = self.client.post(reverse('church_history_edit'), {
            'eyebrow': 'Histórico da igreja',
            'heading': 'Uma história guiada pela fidelidade de Deus.',
            'intro': 'Conheça a origem, o crescimento e a missão que Deus tem sustentado na Canaã ao longo dos anos.',
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
        self.assertContains(response, 'Não foi possível salvar. Corrija')
        self.assertContains(response, 'As senhas não coincidem')
        self.assertFalse(Member.objects.filter(email='divergente@example.com').exists())

    def test_member_form_uses_ministry_checkboxes(self):
        self.client.login(username='staff', password='test-pass')
        Ministry.objects.create(name='Louvor', leader_name='Líder')
        response = self.client.get(reverse('member_create'))
        field = response.context['form'].fields['ministries']
        self.assertEqual(field.label, 'Ministérios')
        self.assertContains(response, 'type="checkbox"')

    def test_member_form_has_password_visibility_and_match_feedback(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('member_create'))
        self.assertContains(response, "document.getElementById('id_password1')")
        self.assertContains(response, "document.getElementById('id_password2')")
        self.assertContains(response, 'password-toggle')
        self.assertContains(response, 'As senhas não coincidem.')
        self.assertContains(response, 'As senhas coincidem.')

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

    def test_member_edit_loads_personal_family_and_church_fields(self):
        ministry = Ministry.objects.create(name='Ensino', leader_name='Líder')
        member = self.member_user.member_profile
        member.birth_date = date(1988, 4, 12)
        member.address = 'Rua das Flores, 100'
        member.home_phone = '8533334444'
        member.work_phone = '8532221111'
        member.profession = 'Professora'
        member.education = 'Ensino superior'
        member.married = True
        member.wedding_date = date(2012, 6, 9)
        member.child_1_name = 'Filho Um'
        member.child_1_birth_date = date(2015, 2, 3)
        member.status = Member.Status.LEADERSHIP
        member.conversion_date = date(2006, 8, 14)
        member.baptism_date = date(2007, 1, 20)
        member.church_entry_date = date(2016, 2, 14)
        member.save()
        member.ministries.add(ministry)
        self.client.login(username='staff', password='test-pass')

        response = self.client.get(reverse('member_edit', args=[member.pk]))
        form = response.context['form']

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="1988-04-12"')
        self.assertContains(response, 'value="2012-06-09"')
        self.assertContains(response, 'value="2015-02-03"')
        self.assertContains(response, 'value="2006-08-14"')
        self.assertContains(response, 'value="2007-01-20"')
        self.assertContains(response, 'value="2016-02-14"')
        self.assertEqual(form['profession'].value(), 'Professora')
        self.assertEqual(form['education'].value(), 'Ensino superior')
        self.assertEqual(form['home_phone'].value(), '8533334444')
        self.assertEqual(form['work_phone'].value(), '8532221111')
        self.assertEqual(form['married'].value(), True)
        self.assertEqual(form['status'].value(), Member.Status.LEADERSHIP)
        self.assertEqual(form['ministries'].value(), [ministry.pk])

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

    def test_member_photo_storage_error_does_not_create_partial_account(self):
        import base64

        photo = SimpleUploadedFile(
            'membro.png',
            base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='),
            content_type='image/png',
        )
        photo_storage = AccessProfile._meta.get_field('photo').storage
        self.client.login(username='staff', password='test-pass')

        with patch.object(photo_storage, 'save', side_effect=AuthorizationRequired('Invalid api_key')):
            response = self.client.post(reverse('member_create'), {
                'name': 'Falha no Upload',
                'email': 'falha.upload@example.com',
                'status': Member.Status.ACTIVE,
                'username': 'falha.upload',
                'password1': 'SenhaForte@2026',
                'password2': 'SenhaForte@2026',
                'photo': photo,
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não foi possível salvar. Corrija')
        self.assertContains(response, 'Não foi possível enviar a foto.')
        self.assertFalse(User.objects.filter(username='falha.upload').exists())
        self.assertFalse(Member.objects.filter(email='falha.upload@example.com').exists())

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
        self.assertEqual(feed.json()[0]['backgroundColor'], '#2752b3')
        self.assertEqual(feed.json()[0]['extendedProps']['location'], 'Templo principal')

    def test_event_form_offers_fixed_classifications(self):
        self.client.login(username='staff', password='test-pass')

        response = self.client.get(reverse('event_create'))

        self.assertEqual(response.status_code, 200)
        choices = list(response.context['form'].fields['kind'].choices)
        self.assertEqual(choices[0], ('', '---------'))
        self.assertEqual(
            choices[1:],
            list(Event.Classification.choices),
        )

    def test_event_form_preserves_legacy_classification_on_edit(self):
        event = Event.objects.create(
            title='Evento antigo',
            starts_at='2026-08-15T19:00:00-03:00',
            kind='Ensino',
            location='Sala',
        )
        self.client.login(username='staff', password='test-pass')

        response = self.client.get(reverse('event_edit', args=[event.pk]))

        self.assertContains(response, 'Ensino (classificação anterior)')

    def test_event_feeds_use_classification_colors(self):
        from core.views import sync_calendar_event

        expected_colors = {
            Event.Classification.SERVICE: '#2752b3',
            Event.Classification.SUNDAY_SCHOOL: '#e67e22',
            Event.Classification.CONFERENCE: '#8b5e3c',
            Event.Classification.SMALL_GROUP: '#9b72cf',
        }
        for index, classification in enumerate(Event.Classification.values, start=1):
            event = Event.objects.create(
                title=f'Evento {classification}',
                starts_at=f'2026-08-{index + 10:02}T19:00:00-03:00',
                kind=classification,
                location='Templo',
            )
            sync_calendar_event(event)

        response = self.client.get(reverse('public_event_feed'), {
            'start': '2026-08-01T00:00:00-03:00',
            'end': '2026-09-01T00:00:00-03:00',
        })

        colors_by_kind = {
            event['extendedProps']['kind']: event['backgroundColor']
            for event in response.json()
        }
        self.assertEqual(colors_by_kind, expected_colors)

    def test_events_page_loads_fullcalendar(self):
        self.client.login(username='staff', password='test-pass')
        response = self.client.get(reverse('events'))
        self.assertContains(response, 'fullcalendar@6.1.19')
        self.assertContains(response, reverse('event_feed'))
        self.assertContains(response, 'class="event-color-key"')

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
            'kind': Event.Classification.SUNDAY_SCHOOL,
            'location': 'Sala de aula',
            'expected_attendance': 50,
            'description': 'Novo conteúdo.',
        })
        self.assertRedirects(response, reverse('events'))
        event.refresh_from_db()
        occurrence = Occurrence.objects.get(event_id=calendar_event_id)
        self.assertEqual(event.title, 'Encontro Atualizado')
        self.assertEqual(event.kind, Event.Classification.SUNDAY_SCHOOL)
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
        Movement.objects.create(
            date=date(2026, 8, 1),
            description='Contribuição mensal',
            category=Category.objects.get(name='Dízimos', kind=Kind.INCOME),
            kind=Kind.INCOME,
            amount='150.00',
            account='bank',
            status=Status.CONFIRMED,
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

    def test_invalid_member_contribution_is_not_recorded(self):
        self.client.login(username='member', password='test-pass')
        response = self.client.post(reverse('member_portal'), {
            'category': 'Ofertas',
            'amount': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Certifique-se que este valor seja maior ou igual a 1.00')
        self.assertFalse(Movement.objects.exists())
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

class BootstrapUserTests(TestCase):
    @patch.dict('os.environ', {
        'DJANGO_BOOTSTRAP_USERNAME': 'diretoria',
        'DJANGO_BOOTSTRAP_PASSWORD': 'Canaa@2026',
        'DJANGO_BOOTSTRAP_EMAIL': 'diretoria@ibrcanaa.local',
        'DJANGO_BOOTSTRAP_FIRST_NAME': 'Washington',
        'DJANGO_BOOTSTRAP_LAST_NAME': 'Araújo',
        'DJANGO_BOOTSTRAP_ROLE': AccessProfile.Role.BOARD,
        'DJANGO_BOOTSTRAP_IS_STAFF': 'true',
        'DJANGO_BOOTSTRAP_IS_SUPERUSER': 'true',
    }, clear=False)
    def test_bootstrap_user_command_creates_initial_account(self):
        call_command('bootstrap_user', verbosity=0)
        user = User.objects.get(username='diretoria')
        self.assertTrue(user.check_password('Canaa@2026'))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.access_profile.role, AccessProfile.Role.BOARD)


class SeedDemoSafetyTests(TestCase):
    def test_seed_demo_is_blocked_when_debug_is_off(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command('seed_demo')
        self.assertFalse(User.objects.filter(username='diretoria').exists())

    def test_seed_demo_runs_when_debug_is_on(self):
        with override_settings(DEBUG=True):
            call_command('seed_demo', stdout=StringIO())
        self.assertTrue(User.objects.filter(username='diretoria').exists())


class ProductionSettingsTests(SimpleTestCase):
    def _run_settings(self, env, code='import config.settings'):
        import os
        import subprocess
        import sys
        from pathlib import Path

        base = Path(__file__).resolve().parent.parent
        clean = {
            k: v for k, v in os.environ.items()
            if not k.startswith(('DJANGO_', 'VERCEL_', 'RENDER_'))
        }
        clean.update(env)
        return subprocess.run(
            [sys.executable, '-c', code],
            cwd=base, env=clean, capture_output=True, text=True,
        )

    def _setting(self, env, name):
        result = self._run_settings(
            {'DJANGO_DEBUG': 'True', **env},
            f'import json, config.settings as s; print(json.dumps(s.{name}))',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_no_vercel_wildcards_in_hosts_or_csrf(self):
        hosts = self._setting({}, 'ALLOWED_HOSTS')
        origins = self._setting({}, 'CSRF_TRUSTED_ORIGINS')
        self.assertEqual(hosts, ['127.0.0.1', 'localhost'])
        self.assertEqual(origins, [])

    def test_platform_hosts_are_trusted_for_hosts_and_csrf(self):
        env = {
            'VERCEL_URL': 'ibrcanaa-abc123.vercel.app',
            'VERCEL_BRANCH_URL': 'ibrcanaa-git-feature.vercel.app',
            'VERCEL_PROJECT_PRODUCTION_URL': 'ibrcanaa.vercel.app',
            'RENDER_EXTERNAL_HOSTNAME': 'ibrcanaa.onrender.com',
        }
        expected = list(env.values())
        hosts = self._setting(env, 'ALLOWED_HOSTS')
        origins = self._setting(env, 'CSRF_TRUSTED_ORIGINS')
        for host in expected:
            self.assertIn(host, hosts)
            self.assertIn(f'https://{host}', origins)
        self.assertFalse([h for h in hosts if '*' in h or h.startswith('.')])
        self.assertFalse([o for o in origins if '*' in o])

    def test_custom_domains_come_from_environment(self):
        env = {
            'DJANGO_ALLOWED_HOSTS': 'igreja.example.org, www.igreja.example.org',
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://igreja.example.org',
        }
        self.assertEqual(
            self._setting(env, 'ALLOWED_HOSTS'),
            ['igreja.example.org', 'www.igreja.example.org'],
        )
        self.assertEqual(self._setting(env, 'CSRF_TRUSTED_ORIGINS'), ['https://igreja.example.org'])

    def test_missing_debug_defaults_to_off_and_requires_secret(self):
        result = self._run_settings({'DATABASE_URL': 'sqlite:///x.db'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_placeholder_secret_is_rejected(self):
        result = self._run_settings({'DJANGO_SECRET_KEY': 'change-me-in-production', 'DATABASE_URL': 'sqlite:///x.db'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_django_insecure_prefix_is_rejected(self):
        result = self._run_settings({'DJANGO_SECRET_KEY': 'django-insecure-abc', 'DATABASE_URL': 'sqlite:///x.db'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_debug_on_imports_without_secret_or_database(self):
        result = self._run_settings({'DJANGO_DEBUG': 'True'})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_true_debug_values_keep_debug_off(self):
        result = self._run_settings({'DJANGO_DEBUG': '1', 'DATABASE_URL': 'sqlite:///x.db'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_real_secret_is_accepted(self):
        result = self._run_settings({'DJANGO_SECRET_KEY': 'x' * 50, 'DATABASE_URL': 'sqlite:///x.db'})
        self.assertEqual(result.returncode, 0, result.stderr)


@WITHOUT_AXES
class AdminWeekAndNavigationTests(TestCase):
    def setUp(self):
        self.board = User.objects.create_user('board', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.board, role=AccessProfile.Role.BOARD)
        self.pastor = User.objects.create_user('pastor', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.pastor, role=AccessProfile.Role.PASTOR)

    def _lead(self, **kwargs):
        data = dict(name='Maria Visitante', email='maria@example.com', whatsapp='(88) 99999-1234',
                    interest=ContactLead.Interest.VISIT, message='Quero conhecer a igreja no domingo.')
        data.update(kwargs)
        return ContactLead.objects.create(**data)

    def test_sidebar_is_grouped_and_hides_pastoral_items_from_board(self):
        self.client.login(username='board', password='test-pass')
        response = self.client.get(reverse('dashboard'))
        for title in ('Pessoas', 'Ensino', 'Agenda e site', 'Gestão'):
            self.assertContains(response, f'>{title}</h2>')
        self.assertNotContains(response, 'Candidaturas')
        self.assertNotContains(response, 'Financeiro')
        self.assertContains(response, 'aria-current="page"')

    def test_pastor_sees_applications_and_no_financial_menu(self):
        self.client.login(username='pastor', password='test-pass')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Candidaturas')
        self.assertNotContains(response, '>Financeiro<')

    def test_sidebar_counts_pending_contacts_and_reviews(self):
        self._lead()
        self._lead(name='João')
        MembershipApplication.objects.create(
            candidate_name='Pedro', candidate_email='p@example.com',
            status=MembershipApplication.Status.REVIEW, created_by=self.pastor,
        )
        self.client.login(username='pastor', password='test-pass')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '2 pendentes')
        self.assertContains(response, '1 pendente')
        self.assertContains(response, 'Candidaturas em avaliação')
        self.assertContains(response, 'Pedro')

    def test_dashboard_lists_pending_contact_with_whatsapp_link(self):
        lead = self._lead()
        self.client.login(username='board', password='test-pass')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Maria Visitante')
        self.assertContains(response, 'https://wa.me/5588999991234')
        self.assertContains(response, reverse('contact_mark_done', args=[lead.pk]))

    def test_dashboard_empty_states_invite_action(self):
        self.client.login(username='board', password='test-pass')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Nenhuma mensagem aguardando resposta')
        self.assertContains(response, 'Nenhum aniversário nos próximos 7 dias')

    def test_mark_contact_done_requires_post_and_login(self):
        lead = self._lead()
        url = reverse('contact_mark_done', args=[lead.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        lead.refresh_from_db()
        self.assertFalse(lead.contacted)
        self.client.login(username='board', password='test-pass')
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        lead.refresh_from_db()
        self.assertTrue(lead.contacted)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Maria Visitante')

    def test_search_requires_login_and_finds_members(self):
        Member.objects.create(name='Ana Beatriz', email='ana@example.com')
        self.assertEqual(self.client.get(reverse('admin_search'), {'q': 'ana'}).status_code, 302)
        self.client.login(username='board', password='test-pass')
        response = self.client.get(reverse('admin_search'), {'q': 'beatriz'})
        self.assertContains(response, 'Ana Beatriz')
        self.assertContains(response, 'Pessoas')
        self.assertContains(self.client.get(reverse('admin_search'), {'q': 'zzzzzz'}), 'Nada encontrado')
        self.assertContains(self.client.get(reverse('admin_search'), {'q': 'a'}), 'pelo menos 2 letras')


class AdminHelpersTests(SimpleTestCase):
    def test_whatsapp_url_adds_country_code_and_rejects_short_numbers(self):
        from .views import _whatsapp_url
        self.assertEqual(_whatsapp_url('(88) 99999-1234'), 'https://wa.me/5588999991234')
        self.assertEqual(_whatsapp_url('+55 88 3571-0000'), 'https://wa.me/558835710000')
        self.assertEqual(_whatsapp_url('1234'), '')
        self.assertEqual(_whatsapp_url(''), '')


class UpcomingBirthdaysTests(TestCase):
    def test_window_and_ordering_including_leap_day_and_year_end(self):
        from .views import upcoming_birthdays
        Member.objects.create(name='Hoje', email='a@x.com', birth_date=date(1990, 12, 29))
        Member.objects.create(name='Virada', email='b@x.com', birth_date=date(2000, 1, 2))
        Member.objects.create(name='Longe', email='c@x.com', birth_date=date(1985, 6, 1))
        Member.objects.create(name='Bissexto', email='d@x.com', birth_date=date(2004, 2, 29))
        found = upcoming_birthdays(today=date(2026, 12, 29), days=7)
        self.assertEqual([item['member'].name for item in found], ['Hoje', 'Virada'])
        self.assertEqual([item['days'] for item in found], [0, 4])
        self.assertEqual(found[1]['age'], 27)
        feb = upcoming_birthdays(today=date(2027, 2, 27), days=3)
        self.assertEqual([item['member'].name for item in feb], ['Bissexto'])


@WITHOUT_AXES
class MembersDirectoryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff2', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.staff, role=AccessProfile.Role.BOARD)
        self.ministry = Ministry.objects.create(name='Louvor', leader_name='Líder')
        self.ana = Member.objects.create(
            name='Ana Oliveira', email='ana@example.com', phone='(88) 99999-1234',
            status=Member.Status.LEADERSHIP, birth_date=date(1990, 5, 20),
            church_entry_date=date(2020, 1, 10), baptism_date=date(2019, 6, 2),
        )
        self.ana.ministries.add(self.ministry)
        Member.objects.create(name='Bruno Lima', email='bruno@example.com', status=Member.Status.VISITOR)
        self.client.login(username='staff2', password='test-pass')

    def test_tabs_show_counts_and_filter_by_status(self):
        response = self.client.get(reverse('members'))
        tabs = {tab['label']: tab['count'] for tab in response.context['tabs']}
        self.assertEqual(tabs['Todos'], 2)
        self.assertEqual(tabs['Liderança'], 1)
        self.assertEqual(tabs['Visitantes'], 1)
        self.assertEqual(tabs['Afastados'], 0)
        filtered = self.client.get(reverse('members'), {'status': Member.Status.VISITOR})
        self.assertContains(filtered, 'Bruno Lima')
        self.assertNotContains(filtered, 'Ana Oliveira')
        self.assertContains(filtered, 'aria-current="page"')

    def test_singular_count_is_not_pluralized(self):
        response = self.client.get(reverse('members'), {'q': 'Ana'})
        self.assertContains(response, '<strong>1</strong> pessoa encontrada')
        self.assertNotContains(response, '1 pessoas')

    def test_cards_link_to_profile_and_offer_whatsapp_only_with_phone(self):
        response = self.client.get(reverse('members'))
        self.assertContains(response, reverse('member_detail', args=[self.ana.pk]))
        self.assertContains(response, 'https://wa.me/5588999991234', count=1)
        self.assertContains(response, 'mailto:bruno@example.com')

    def test_pagination_keeps_filters(self):
        Member.objects.bulk_create([
            Member(name=f'Visitante {i:02}', email=f'v{i}@example.com', status=Member.Status.VISITOR) for i in range(13)
        ])
        response = self.client.get(reverse('members'), {'status': Member.Status.VISITOR})
        self.assertContains(response, 'status=visitor&page=2')

    def test_member_profile_shows_contact_journey_and_ministries(self):
        response = self.client.get(reverse('member_detail', args=[self.ana.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Oliveira')
        self.assertContains(response, 'Louvor')
        self.assertContains(response, 'ana@example.com')
        self.assertContains(response, '02/06/2019')
        self.assertContains(response, reverse('member_edit', args=[self.ana.pk]))
        self.assertContains(response, 'https://wa.me/5588999991234')

    def test_member_profile_handles_missing_data_and_unknown_id(self):
        bare = Member.objects.get(name='Bruno Lima')
        response = self.client.get(reverse('member_detail', args=[bare.pk]))
        self.assertContains(response, 'Sem ministério')
        self.assertIsNone(response.context['age'])
        self.assertContains(response, '<dt>Idade</dt><dd>Não informada</dd>')
        self.assertNotContains(response, 'wa.me')
        self.assertEqual(self.client.get(reverse('member_detail', args=[99999])).status_code, 404)

    def test_member_profile_requires_panel_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('member_detail', args=[self.ana.pk])).status_code, 302)
        plain = User.objects.create_user('plain', password='test-pass')
        AccessProfile.objects.create(user=plain, role=AccessProfile.Role.MEMBER)
        self.client.login(username='plain', password='test-pass')
        self.assertEqual(self.client.get(reverse('member_detail', args=[self.ana.pk])).status_code, 302)

    def test_global_search_opens_the_profile(self):
        response = self.client.get(reverse('admin_search'), {'q': 'Oliveira'})
        self.assertContains(response, reverse('member_detail', args=[self.ana.pk]))

    def test_sidebar_marks_members_active_on_profile(self):
        response = self.client.get(reverse('member_detail', args=[self.ana.pk]))
        self.assertContains(response, 'class="side-link active"')


@WITHOUT_AXES
class MinistryDetailTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff3', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.staff, role=AccessProfile.Role.BOARD)
        self.louvor = Ministry.objects.create(name='Louvor', leader_name='Marta', description='Adoração em comunhão.')
        self.kids = Ministry.objects.create(name='Kids', leader_name='Paulo', status=Ministry.Status.RECRUITING)
        self.ana = Member.objects.create(name='Ana', email='ana@x.com', phone='(88) 99999-1234', status=Member.Status.ACTIVE)
        self.bia = Member.objects.create(name='Bia', email='bia@x.com', status=Member.Status.NEW)
        self.cris = Member.objects.create(name='Cris', email='cris@x.com')
        self.louvor.members.add(self.ana, self.bia)
        self.client.login(username='staff3', password='test-pass')

    def test_tabs_count_and_filter_ministries(self):
        response = self.client.get(reverse('ministries'))
        tabs = {tab['label']: tab['count'] for tab in response.context['tabs']}
        self.assertEqual(tabs, {'Todos': 2, 'Ativos': 1, 'Precisam de voluntários': 1})
        filtered = self.client.get(reverse('ministries'), {'status': Ministry.Status.RECRUITING})
        self.assertContains(filtered, 'Kids')
        self.assertNotContains(filtered, 'Louvor')

    def test_cards_link_to_detail_and_singular_count(self):
        response = self.client.get(reverse('ministries'), {'q': 'Kids'})
        self.assertContains(response, reverse('ministry_detail', args=[self.kids.pk]))
        self.assertContains(response, '<strong>1</strong> ministério encontrado')

    def test_detail_shows_team_breakdown_and_public_label(self):
        response = self.client.get(reverse('ministry_detail', args=[self.louvor.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adoração em comunhão.')
        self.assertContains(response, reverse('member_detail', args=[self.ana.pk]))
        self.assertContains(response, 'https://wa.me/5588999991234')
        self.assertContains(response, 'width:50%')
        self.assertContains(response, 'Conhecer')
        self.assertEqual((response.context['total'], response.context['active_total'], response.context['newcomers_total']), (2, 1, 1))
        self.assertEqual([m.name for m in response.context['available_members']], ['Cris'])
        kids = self.client.get(reverse('ministry_detail', args=[self.kids.pk]))
        self.assertContains(kids, 'Quero servir')
        self.assertContains(kids, 'Nenhuma pessoa neste ministério')

    def test_add_and_remove_member(self):
        add_url = reverse('ministry_member_add', args=[self.louvor.pk])
        response = self.client.post(add_url, {'member_id': self.cris.pk})
        self.assertRedirects(response, reverse('ministry_detail', args=[self.louvor.pk]))
        self.assertIn(self.cris, self.louvor.members.all())
        remove_url = reverse('ministry_member_remove', args=[self.louvor.pk, self.cris.pk])
        self.assertRedirects(self.client.post(remove_url), reverse('ministry_detail', args=[self.louvor.pk]))
        self.assertNotIn(self.cris, self.louvor.members.all())

    def test_add_member_rejects_invalid_choice_and_get(self):
        add_url = reverse('ministry_member_add', args=[self.louvor.pk])
        self.client.post(add_url, {'member_id': ''})
        self.client.post(add_url, {'member_id': '99999'})
        self.assertEqual(self.louvor.members.count(), 2)
        self.assertEqual(self.client.get(add_url).status_code, 405)
        self.assertEqual(self.client.get(reverse('ministry_member_remove', args=[self.louvor.pk, self.ana.pk])).status_code, 405)

    def test_detail_actions_require_panel_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('ministry_detail', args=[self.louvor.pk])).status_code, 302)
        self.assertEqual(self.client.post(reverse('ministry_member_add', args=[self.louvor.pk]), {'member_id': self.cris.pk}).status_code, 302)
        self.assertNotIn(self.cris, self.louvor.members.all())
        self.client.login(username='staff3', password='test-pass')
        self.assertEqual(self.client.get(reverse('ministry_detail', args=[99999])).status_code, 404)

    def test_global_search_opens_ministry_detail(self):
        response = self.client.get(reverse('admin_search'), {'q': 'Louv'})
        self.assertContains(response, reverse('ministry_detail', args=[self.louvor.pk]))


@WITHOUT_AXES
class EntityFormTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff4', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.staff, role=AccessProfile.Role.BOARD)
        self.client.login(username='staff4', password='test-pass')

    def test_form_shows_back_link_required_legend_and_sticky_actions(self):
        response = self.client.get(reverse('ministry_create'))
        self.assertContains(response, 'Voltar sem salvar')
        self.assertContains(response, reverse('ministries'))
        self.assertContains(response, 'Campo obrigatório')
        self.assertContains(response, 'class="form-actions"')

    def test_invalid_submit_summarises_errors_with_links_to_fields(self):
        response = self.client.post(reverse('ministry_create'), {'name': '', 'leader_name': '', 'status': Ministry.Status.ACTIVE})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não foi possível salvar. Corrija 2 campos:')
        self.assertContains(response, 'href="#id_name"')
        self.assertContains(response, 'role="alert"')
        self.assertFalse(Ministry.objects.exists())

    def test_valid_form_has_no_error_summary(self):
        response = self.client.get(reverse('ministry_create'))
        self.assertNotContains(response, 'Não foi possível salvar')


@WITHOUT_AXES
class MinistryFormScreenTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff5', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.staff, role=AccessProfile.Role.BOARD)
        self.ministry = Ministry.objects.create(name='Louvor', leader_name='Marta', description='Adoração.')
        self.ministry.members.add(Member.objects.create(name='Ana', email='ana@x.com'))
        self.client.login(username='staff5', password='test-pass')

    def test_edit_shows_header_context_preview_and_returns_to_profile(self):
        response = self.client.get(reverse('ministry_edit', args=[self.ministry.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 participante.')
        self.assertContains(response, 'Líder atual: Marta')
        self.assertContains(response, 'Ver ficha e equipe')
        self.assertContains(response, 'Como aparece no site')
        self.assertContains(response, 'data-preview-name')
        self.assertContains(response, f'href="{reverse("ministry_detail", args=[self.ministry.pk])}">Cancelar')

    def test_create_has_preview_but_no_profile_header_and_returns_to_list(self):
        response = self.client.get(reverse('ministry_create'))
        self.assertContains(response, 'Como aparece no site')
        self.assertNotContains(response, 'Ver ficha e equipe')
        self.assertContains(response, f'href="{reverse("ministries")}">Cancelar')

    def test_status_is_a_radio_choice_without_empty_option(self):
        response = self.client.get(reverse('ministry_create'))
        self.assertContains(response, 'type="radio"', count=2)
        self.assertContains(response, 'Precisa de voluntários')
        self.assertNotContains(response, '---------')

    def test_saving_still_works_and_redirects_to_list(self):
        response = self.client.post(reverse('ministry_edit', args=[self.ministry.pk]), {
            'name': 'Louvor e Adoração', 'leader_name': 'Marta', 'description': 'Novo texto.',
            'status': Ministry.Status.RECRUITING,
        })
        self.assertRedirects(response, reverse('ministries'))
        self.ministry.refresh_from_db()
        self.assertEqual((self.ministry.name, self.ministry.status), ('Louvor e Adoração', Ministry.Status.RECRUITING))


@WITHOUT_AXES
class FormScreensTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff6', password='test-pass', is_staff=True)
        AccessProfile.objects.create(user=self.staff, role=AccessProfile.Role.BOARD)
        self.client.login(username='staff6', password='test-pass')

    def test_member_detail_header_has_summary_and_actions(self):
        member = Member.objects.create(
            name='Ana', email='ana@x.com', phone='(88) 99999-1234', birth_date=date(1990, 5, 20),
            baptism_date=date(2019, 6, 2), church_entry_date=date(2020, 1, 10),
        )
        response = self.client.get(reverse('member_detail', args=[member.pk]))
        self.assertContains(response, 'class="panel profile-head"')
        self.assertContains(response, '<dt>Na igreja há</dt>')
        self.assertContains(response, '<dd>02/06/2019</dd>')
        self.assertContains(response, 'Editar ficha')
        self.assertContains(response, '20/05/1990')
        self.assertContains(response, '10/01/2020')
        self.assertNotContains(response, 'stat-row')

    def test_member_form_has_section_index_without_numbers_and_required_marks(self):
        response = self.client.get(reverse('member_create'))
        self.assertContains(response, 'class="mf-index"')
        self.assertContains(response, 'href="#secao-5"')
        self.assertContains(response, 'id="secao-1"')
        self.assertContains(response, 'Campo obrigatório')
        self.assertContains(response, 'class="req"')
        self.assertNotContains(response, 'Ver ficha')
        self.assertContains(response, f'href="{reverse("members")}">Cancelar')

    def test_member_form_edit_shows_context_and_returns_to_profile(self):
        member = Member.objects.create(name='Bia', email='bia@x.com')
        response = self.client.get(reverse('member_edit', args=[member.pk]))
        self.assertContains(response, 'Ver ficha')
        self.assertContains(response, 'profile-head-compact')
        self.assertContains(response, f'href="{reverse("member_detail", args=[member.pk])}">Cancelar')

    def test_book_form_has_live_preview(self):
        response = self.client.get(reverse('book_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="book-preview"')
        self.assertContains(response, 'data-bp-title')
        self.assertContains(response, 'Como aparece no site')
        self.assertContains(response, f'href="{reverse("books")}">Cancelar')

    def test_event_form_has_live_preview_and_still_saves(self):
        response = self.client.get(reverse('event_create'))
        self.assertContains(response, 'class="event-preview"')
        self.assertContains(response, 'Como aparece na agenda')
        saved = self.client.post(reverse('event_create'), {
            'title': 'Culto de Ação de Graças', 'starts_at': '2027-01-10T19:00', 'kind': 'Culto',
            'location': 'Templo', 'expected_attendance': 120, 'description': 'Gratidão.',
        })
        self.assertRedirects(saved, reverse('events'))
        self.assertTrue(Event.objects.filter(title='Culto de Ação de Graças').exists())


class BookAmazonTests(TestCase):
    def test_is_amazon_detects_amazon_links_only(self):
        for url in ('https://www.amazon.com.br/dp/B0TEST', 'https://amzn.to/abc', 'https://a.co/d/xyz'):
            self.assertTrue(Book(title='L', purchase_url=url).is_amazon, url)
        for url in ('', 'https://wa.me/5511999999999', 'https://evilamazon.com.br/x', 'https://amazon.com.br.evil.com/x'):
            self.assertFalse(Book(title='L', purchase_url=url).is_amazon, url)

    def test_amazon_book_hides_price_on_bookstore(self):
        Book.objects.create(title='Livro Amazon', price='39.90', purchase_url='https://www.amazon.com.br/dp/B0TEST')
        Book.objects.create(title='Livro Direto', price='25.00', purchase_url='https://wa.me/5511999999999')
        html = self.client.get('/').content.decode()
        self.assertIn('Ver preço na Amazon', html)
        self.assertNotIn('39,90', html)
        self.assertIn('25,00', html)
