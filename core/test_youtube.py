import http.client
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone as dt_timezone
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.db.utils import OperationalError
from unittest import skipUnless

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.forms import ChurchAboutPageForm
from core.models import ChurchAboutPage, YoutubeSnapshot
from core.views import _pinned_video
from core.youtube import (
    YoutubeError,
    _claim_refresh,
    build_home_videos,
    fetch_feed_entries,
    fetch_video_details,
    home_videos,
    load_videos,
)

CHANNEL_ID = 'UCnJeIwpnusCcbJa9nAInb8Q'
FEED_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <entry><id>yt:video:AAAAAAAAAAA</id><yt:videoId>AAAAAAAAAAA</yt:videoId>
  <title>Culto de Louvor - 08/11/2026</title><published>2026-11-09T11:44:52+00:00</published></entry>
 <entry><id>yt:video:BBBBBBBBBBB</id><yt:videoId>BBBBBBBBBBB</yt:videoId>
  <title>Escola Bíblica - 08/11/2026</title><published>2026-11-09T02:36:23+00:00</published></entry>
</feed>'''


def respond_with(mocked_urlopen, body):
    data = body.encode() if isinstance(body, str) else body
    mocked_urlopen.return_value.__enter__.return_value = BytesIO(data)


class FeaturedVideoFieldTests(TestCase):
    def form(self, **overrides):
        page = ChurchAboutPage.objects.create(site_key='about')
        data = model_to_dict(page)
        data.update(overrides)
        return ChurchAboutPageForm(data, instance=page)

    def test_no_pinned_video_by_default(self):
        page = ChurchAboutPage.objects.create(site_key='about')
        self.assertIsNone(page.featured_video_id)
        self.assertEqual(page.featured_video_title, '')
        self.assertIsNone(_pinned_video())

    def test_form_accepts_valid_youtube_url(self):
        form = self.form(featured_video_url='https://youtu.be/AAAAAAAAAAA')
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_non_youtube_url(self):
        form = self.form(featured_video_url='https://example.com/video')
        self.assertFalse(form.is_valid())
        self.assertIn('featured_video_url', form.errors)

    def test_blank_url_is_allowed_and_has_no_video_id(self):
        form = self.form(featured_video_url='')
        self.assertTrue(form.is_valid(), form.errors)
        page = form.save()
        self.assertIsNone(page.featured_video_id)

    def test_snapshot_key_is_unique(self):
        YoutubeSnapshot.objects.create(key='channel')
        with self.assertRaises(IntegrityError), transaction.atomic():
            YoutubeSnapshot.objects.create(key='channel')


@patch('core.youtube.urlopen')
class FeedParsingTests(SimpleTestCase):
    def test_feed_entries_are_parsed_in_order(self, mocked_urlopen):
        respond_with(mocked_urlopen, FEED_XML)
        entries = fetch_feed_entries(CHANNEL_ID)
        self.assertEqual([entry['video_id'] for entry in entries], ['AAAAAAAAAAA', 'BBBBBBBBBBB'])
        self.assertEqual(entries[0]['title'], 'Culto de Louvor - 08/11/2026')
        self.assertEqual(entries[0]['published'], '2026-11-09T11:44:52+00:00')

    def test_feed_requests_the_streams_playlist_feed_url(self, mocked_urlopen):
        respond_with(mocked_urlopen, FEED_XML)
        fetch_feed_entries(CHANNEL_ID)
        request = mocked_urlopen.call_args.args[0]
        url = request.full_url if hasattr(request, 'full_url') else request
        self.assertEqual(url, f'https://www.youtube.com/feeds/videos.xml?playlist_id=UULV{CHANNEL_ID[2:]}')
        self.assertEqual(mocked_urlopen.call_args.kwargs['timeout'], 2)

    def test_feed_rejects_malformed_xml(self, mocked_urlopen):
        respond_with(mocked_urlopen, '<feed><entry>')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)

    def test_feed_rejects_oversized_body(self, mocked_urlopen):
        respond_with(mocked_urlopen, b'<feed>' + b'x' * (1024 * 1024 + 10) + b'</feed>')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)

    def test_feed_truncated_or_malformed_http_becomes_youtube_error(self, mocked_urlopen):
        for error in (http.client.IncompleteRead(b'abc'), http.client.BadStatusLine('lixo')):
            with self.subTest(error=type(error).__name__):
                mocked_urlopen.side_effect = error
                with self.assertRaises(YoutubeError):
                    fetch_feed_entries(CHANNEL_ID)

    def test_feed_network_error_becomes_youtube_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = URLError('sem rede')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)


@patch('core.youtube.urlopen')
class VideoDetailsTests(SimpleTestCase):
    def test_details_flags_live_and_transmissions(self, mocked_urlopen):
        respond_with(mocked_urlopen, json.dumps({'items': [
            {'id': 'LIVE0000001', 'snippet': {'liveBroadcastContent': 'live'}, 'liveStreamingDetails': {}},
            {'id': 'ENDED000001', 'snippet': {'liveBroadcastContent': 'none'}, 'liveStreamingDetails': {}},
            {'id': 'UPLOAD00001', 'snippet': {'liveBroadcastContent': 'none'}},
            {'id': 'SOON0000001', 'snippet': {'liveBroadcastContent': 'upcoming'}, 'liveStreamingDetails': {}},
        ]}))
        details = fetch_video_details(['LIVE0000001', 'ENDED000001', 'UPLOAD00001', 'SOON0000001'], 'chave')
        self.assertEqual(details['LIVE0000001'], {'live': True, 'transmission': True})
        self.assertEqual(details['ENDED000001'], {'live': False, 'transmission': True})
        self.assertEqual(details['UPLOAD00001'], {'live': False, 'transmission': False})
        self.assertEqual(details['SOON0000001'], {'live': False, 'transmission': False})

    def test_details_request_asks_for_snippet_and_live_streaming_details(self, mocked_urlopen):
        respond_with(mocked_urlopen, json.dumps({'items': []}))
        fetch_video_details(['AAAAAAAAAAA', 'BBBBBBBBBBB'], 'chave')
        request = mocked_urlopen.call_args.args[0]
        url = request.full_url if hasattr(request, 'full_url') else request
        query = parse_qs(urlparse(url).query)
        self.assertEqual(urlparse(url).path, '/youtube/v3/videos')
        self.assertEqual(query['part'], ['snippet,liveStreamingDetails'])
        self.assertEqual(query['id'], ['AAAAAAAAAAA,BBBBBBBBBBB'])
        self.assertEqual(query['key'], ['chave'])

    def test_videos_missing_from_the_response_are_omitted(self, mocked_urlopen):
        respond_with(mocked_urlopen, json.dumps({'items': []}))
        self.assertEqual(fetch_video_details(['AAAAAAAAAAA'], 'chave'), {})

    def test_no_ids_means_no_request(self, mocked_urlopen):
        self.assertEqual(fetch_video_details([], 'chave'), {})
        mocked_urlopen.assert_not_called()

    def test_details_http_error_hides_the_api_key(self, mocked_urlopen):
        url = 'https://www.googleapis.com/youtube/v3/videos?key=SEGREDO123'
        mocked_urlopen.side_effect = HTTPError(url, 403, 'Forbidden', {}, None)
        with self.assertRaises(YoutubeError) as raised, self.assertNoLogs(level='DEBUG'):
            fetch_video_details(['AAAAAAAAAAA'], 'SEGREDO123')
        self.assertNotIn('SEGREDO123', str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertTrue(raised.exception.__suppress_context__)

    def test_details_invalid_json_becomes_youtube_error(self, mocked_urlopen):
        respond_with(mocked_urlopen, 'não é json')
        with self.assertRaises(YoutubeError):
            fetch_video_details(['AAAAAAAAAAA'], 'chave')


NEWEST = datetime(2026, 11, 10, 12, 0, tzinfo=dt_timezone.utc)
PINNED = {'video_id': 'PPPPPPPPPPP', 'title': 'Podcast', 'channel_title': 'Igreja Batista Regular Canaã', 'published': None}


def video(index, live=False, transmission=True):
    """V1 é o mais novo; cada índice seguinte é um dia mais velho."""
    return {
        'video_id': f'V{index:010d}',
        'title': f'Vídeo {index}',
        'channel_title': 'Igreja Batista Regular Canaã',
        'published': NEWEST - timedelta(days=index - 1),
        'live': live,
        'transmission': transmission,
    }


def ids(result):
    return [item['video_id'] for item in result['videos']]


def vid(index):
    return f'V{index:010d}'


class BuildHomeVideosTests(SimpleTestCase):
    def test_live_takes_the_featured_slot_and_pinned_is_hidden(self):
        result = build_home_videos([video(1, live=True), video(2), video(3), video(4), video(5)], PINNED)
        self.assertTrue(result['live'])
        self.assertEqual(ids(result), [vid(1), vid(2), vid(3), vid(4)])

    def test_pinned_is_featured_when_nothing_is_live(self):
        result = build_home_videos([video(1), video(2), video(3), video(4), video(5)], PINNED)
        self.assertFalse(result['live'])
        self.assertEqual(ids(result), ['PPPPPPPPPPP', vid(1), vid(2), vid(3)])

    def test_ended_live_goes_to_the_top_of_the_stack(self):
        result = build_home_videos([video(1, live=False, transmission=True), video(2), video(3)], PINNED)
        self.assertEqual(ids(result)[:2], ['PPPPPPPPPPP', vid(1)])

    def test_stack_only_has_transmissions_when_details_exist(self):
        result = build_home_videos([video(1), video(2, transmission=False), video(3), video(4)], PINNED)
        self.assertEqual(ids(result), ['PPPPPPPPPPP', vid(1), vid(3), vid(4)])

    def test_without_details_the_stack_uses_the_latest_entries(self):
        videos = [video(index, transmission=None) for index in range(1, 6)]
        self.assertEqual(ids(build_home_videos(videos, PINNED)), ['PPPPPPPPPPP', vid(1), vid(2), vid(3)])

    def test_no_pinned_uses_latest_transmission_as_featured(self):
        result = build_home_videos([video(index) for index in range(1, 6)], None)
        self.assertEqual(ids(result), [vid(1), vid(2), vid(3), vid(4)])

    def test_pinned_never_repeats_in_the_stack(self):
        pinned = {**PINNED, 'video_id': vid(2)}
        result = build_home_videos([video(1), video(2), video(3), video(4)], pinned)
        self.assertEqual(ids(result), [vid(2), vid(1), vid(3), vid(4)])

    def test_live_equal_to_pinned_appears_once(self):
        pinned = {**PINNED, 'video_id': vid(1)}
        result = build_home_videos([video(1, live=True), video(2), video(3), video(4)], pinned)
        self.assertEqual(ids(result), [vid(1), vid(2), vid(3), vid(4)])

    def test_stack_is_ordered_by_publication_date_newest_first(self):
        result = build_home_videos([video(3), video(1), video(2)], PINNED)
        self.assertEqual(ids(result), ['PPPPPPPPPPP', vid(1), vid(2), vid(3)])

    def test_entries_without_a_date_go_last(self):
        undated = {**video(1), 'published': None}
        result = build_home_videos([undated, video(2), video(3), video(4)], PINNED)
        self.assertEqual(ids(result), ['PPPPPPPPPPP', vid(2), vid(3), vid(4)])

    def test_nothing_available_returns_only_pinned(self):
        result = build_home_videos([], PINNED)
        self.assertFalse(result['live'])
        self.assertEqual(ids(result), ['PPPPPPPPPPP'])

    def test_nothing_at_all_returns_empty(self):
        self.assertEqual(build_home_videos([], None), {'live': False, 'videos': []})


NOW = datetime(2026, 11, 13, 12, 0, tzinfo=dt_timezone.utc)
ENTRIES = [
    {'video_id': 'AAAAAAAAAAA', 'title': 'Culto A', 'published': '2026-11-09T11:44:52+00:00'},
    {'video_id': 'BBBBBBBBBBB', 'title': 'Culto B', 'published': '2026-11-02T11:44:33+00:00'},
]
DETAILS = {
    'AAAAAAAAAAA': {'live': True, 'transmission': True},
    'BBBBBBBBBBB': {'live': False, 'transmission': True},
}


@override_settings(YOUTUBE_API_KEY='chave', YOUTUBE_CHANNEL_ID=CHANNEL_ID)
class LoadVideosTests(TestCase):
    def setUp(self):
        feed = patch('core.youtube.fetch_feed_entries', return_value=ENTRIES)
        details = patch('core.youtube.fetch_video_details', return_value=DETAILS)
        self.feed = feed.start()
        self.details = details.start()
        self.addCleanup(feed.stop)
        self.addCleanup(details.stop)
        live_page = patch('core.youtube.fetch_live_without_key', return_value=None)
        self.live_page = live_page.start()
        self.addCleanup(live_page.stop)

    def at(self, seconds):
        return NOW + timedelta(seconds=seconds)

    def test_first_call_fetches_and_stores_a_snapshot(self):
        videos = load_videos(NOW)
        self.assertEqual([item['video_id'] for item in videos], ['AAAAAAAAAAA', 'BBBBBBBBBBB'])
        self.assertTrue(videos[0]['live'])
        self.assertEqual(videos[0]['published'], datetime(2026, 11, 9, 11, 44, 52, tzinfo=dt_timezone.utc))
        self.assertEqual(videos[0]['channel_title'], 'Igreja Batista Regular Canaã')
        self.assertEqual(YoutubeSnapshot.objects.count(), 1)
        self.feed.assert_called_once_with(CHANNEL_ID)
        self.details.assert_called_once_with(['AAAAAAAAAAA', 'BBBBBBBBBBB'], 'chave')

    def test_fresh_snapshot_does_not_refetch(self):
        load_videos(NOW)
        load_videos(self.at(20))
        self.assertEqual(self.feed.call_count, 1)
        self.assertEqual(self.details.call_count, 1)

    def test_stale_snapshot_refetches(self):
        load_videos(NOW)
        load_videos(self.at(61))
        self.assertEqual(self.feed.call_count, 2)

    def test_failed_refresh_keeps_the_last_good_snapshot(self):
        load_videos(NOW)
        self.feed.side_effect = YoutubeError('fora do ar')
        videos = load_videos(self.at(61))
        self.assertEqual([item['video_id'] for item in videos], ['AAAAAAAAAAA', 'BBBBBBBBBBB'])
        self.assertTrue(videos[0]['live'])

    def test_failed_refresh_is_retried_only_after_the_interval(self):
        load_videos(NOW)
        self.feed.side_effect = YoutubeError('fora do ar')
        load_videos(self.at(61))
        attempts = self.feed.call_count
        load_videos(self.at(70))
        self.assertEqual(self.feed.call_count, attempts)
        load_videos(self.at(125))
        self.assertEqual(self.feed.call_count, attempts + 1)

    def test_api_failure_keeps_feed_entries_without_live_flags(self):
        self.details.side_effect = YoutubeError('cota esgotada')
        videos = load_videos(NOW)
        self.assertEqual(len(videos), 2)
        self.assertFalse(any(item['live'] for item in videos))
        self.assertTrue(all(item['transmission'] is True for item in videos))

    def test_api_failure_keeps_the_previous_snapshot_while_it_is_recent(self):
        load_videos(NOW)
        self.details.side_effect = YoutubeError('cota esgotada')
        self.feed.return_value = [*ENTRIES, {'video_id': 'CCCCCCCCCCC', 'title': 'Novo', 'published': '2026-11-13T11:00:00+00:00'}]
        videos = load_videos(self.at(61))
        self.assertEqual([item['video_id'] for item in videos], ['AAAAAAAAAAA', 'BBBBBBBBBBB'])
        self.assertTrue(videos[0]['live'])
        self.assertTrue(videos[0]['transmission'])

    def test_long_api_outage_falls_back_to_the_feed_only(self):
        load_videos(NOW)
        self.details.side_effect = YoutubeError('cota esgotada')
        videos = load_videos(self.at(700))
        self.assertEqual(len(videos), 2)
        self.assertFalse(any(item['live'] for item in videos))
        self.assertTrue(all(item['transmission'] is True for item in videos))

    def test_live_flag_expires_after_ten_minutes_without_success(self):
        load_videos(NOW)
        self.feed.side_effect = YoutubeError('fora do ar')
        videos = load_videos(self.at(601))
        self.assertEqual(len(videos), 2)
        self.assertFalse(any(item['live'] for item in videos))

    def test_live_flag_survives_while_the_data_is_recent(self):
        load_videos(NOW)
        self.feed.side_effect = YoutubeError('fora do ar')
        self.assertTrue(load_videos(self.at(599))[0]['live'])

    def test_empty_feed_is_treated_as_a_failure_and_keeps_the_snapshot(self):
        load_videos(NOW)
        self.feed.return_value = []
        self.assertEqual(len(load_videos(self.at(61))), 2)

    @override_settings(YOUTUBE_API_KEY='')
    def test_without_api_key_the_api_is_never_called(self):
        videos = load_videos(NOW)
        self.details.assert_not_called()
        self.assertTrue(all(item['transmission'] is True for item in videos))
        self.assertFalse(any(item['live'] for item in videos))

    def test_nothing_fetched_ever_returns_an_empty_list(self):
        self.feed.side_effect = YoutubeError('fora do ar')
        self.assertEqual(load_videos(NOW), [])

    def test_only_one_request_claims_a_due_refresh(self):
        first = YoutubeSnapshot.objects.create(key='channel', checked_at=NOW - timedelta(seconds=300))
        second = YoutubeSnapshot.objects.get(pk=first.pk)
        self.assertTrue(_claim_refresh(first, NOW))
        self.assertFalse(_claim_refresh(second, NOW))

    def test_home_videos_combines_snapshot_and_pinned(self):
        result = home_videos(PINNED, NOW)
        self.assertTrue(result['live'])
        self.assertEqual(ids(result), ['AAAAAAAAAAA', 'BBBBBBBBBBB'])

    def test_home_videos_survives_database_errors(self):
        with patch('core.youtube.load_videos', side_effect=OperationalError('sem tabela')):
            result = home_videos(PINNED, NOW)
        self.assertEqual(result, {'live': False, 'videos': [PINNED]})


def listed(video_id, title, day, live=False):
    return {
        'video_id': video_id, 'title': title, 'channel_title': 'Igreja Batista Regular Canaã',
        'published': datetime(2026, 11, day, 12, 0, tzinfo=dt_timezone.utc), 'live': live, 'transmission': True,
    }


LIVE_RESULT = {'live': True, 'videos': [
    listed('LIVE0000001', 'Culto ao vivo', 15, live=True),
    listed('AAAAAAAAAAA', 'Culto A', 8), listed('BBBBBBBBBBB', 'Culto B', 1), listed('CCCCCCCCCCC', 'Culto C', 25),
]}
PINNED_RESULT = {'live': False, 'videos': [
    {**PINNED, 'video_id': 'i7tGR33yy-o', 'title': 'Podcast Canaã #01'},
    listed('AAAAAAAAAAA', 'Culto A', 8), listed('BBBBBBBBBBB', 'Culto B', 1), listed('CCCCCCCCCCC', 'Culto C', 25),
]}


@patch('core.views.home_videos')
class HomeYoutubeTests(TestCase):
    def test_home_labels_the_live_and_marks_it_in_the_page(self, mocked):
        mocked.return_value = LIVE_RESULT
        response = self.client.get(reverse('home'))
        self.assertContains(response, '● AO VIVO AGORA')
        self.assertContains(response, 'data-live="true"')
        self.assertContains(response, 'data-video-id="LIVE0000001"')
        self.assertNotContains(response, 'EM DESTAQUE')

    def test_home_turns_the_section_into_the_live_stage(self, mocked):
        mocked.return_value = LIVE_RESULT
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'video-section is-live')
        self.assertContains(response, 'O culto está acontecendo agora')
        self.assertContains(response, '&autoplay=1&mute=1')
        self.assertContains(response, ' autoload')

    def test_home_without_live_keeps_the_regular_section(self, mocked):
        mocked.return_value = PINNED_RESULT
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'video-section is-live')
        self.assertContains(response, 'Transmissões mais recentes')
        self.assertNotContains(response, 'autoplay=1')

    def test_home_labels_the_pinned_video(self, mocked):
        mocked.return_value = PINNED_RESULT
        ChurchAboutPage.objects.update_or_create(site_key='about', defaults={'featured_video_url': 'https://youtu.be/i7tGR33yy-o', 'featured_video_title': 'Podcast Canaã #01'})
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'EM DESTAQUE')
        self.assertContains(response, 'data-live="false"')
        self.assertContains(response, 'data-video-id="i7tGR33yy-o"')
        self.assertNotContains(response, 'TRANSMISSÃO EM DESTAQUE')
        self.assertNotContains(response, 'AO VIVO AGORA')

    def test_home_renders_featured_and_three_stack_items_with_origin_param(self, mocked):
        mocked.return_value = PINNED_RESULT
        response = self.client.get(reverse('home'))
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertContains(response, 'params="origin=http://testserver"', count=4)
        for video_id in ('i7tGR33yy-o', 'AAAAAAAAAAA', 'BBBBBBBBBBB', 'CCCCCCCCCCC'):
            self.assertContains(response, f'videoid="{video_id}"')

    def test_home_exposes_the_feed_url_for_polling(self, mocked):
        mocked.return_value = PINNED_RESULT
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'data-feed-url="{reverse("public_youtube_videos_feed")}"')

    def test_home_still_loads_when_only_the_pinned_video_exists(self, mocked):
        mocked.return_value = {'live': False, 'videos': [PINNED_RESULT['videos'][0]]}
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'params="origin=http://testserver"', count=1)

    def test_home_still_loads_when_there_is_no_video_at_all(self, mocked):
        mocked.return_value = {'live': False, 'videos': []}
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'video-featured')

    def test_home_passes_the_pinned_video_to_home_videos(self, mocked):
        mocked.return_value = PINNED_RESULT
        ChurchAboutPage.objects.update_or_create(site_key='about', defaults={'featured_video_url': 'https://youtu.be/i7tGR33yy-o', 'featured_video_title': 'Podcast Canaã #01'})
        self.client.get(reverse('home'))
        pinned = mocked.call_args.args[0]
        self.assertEqual(pinned['video_id'], 'i7tGR33yy-o')

    def test_feed_endpoint_exposes_live_and_keeps_contract(self, mocked):
        mocked.return_value = LIVE_RESULT
        response = self.client.get(reverse('public_youtube_videos_feed'), HTTP_ORIGIN='https://profwashingtonaraujo.github.io')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://profwashingtonaraujo.github.io')
        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=30')
        payload = response.json()
        self.assertTrue(payload['live'])
        self.assertEqual(payload['videos'][0]['video_id'], 'LIVE0000001')
        self.assertIn('2026-11-15', payload['videos'][0]['published'])
        self.assertEqual(payload['channel']['url'], 'https://www.youtube.com/@ibrcanaa')


class PinnedVideoTests(TestCase):
    def test_pinned_video_comes_from_the_about_page(self):
        ChurchAboutPage.objects.update_or_create(site_key='about', defaults={'featured_video_url': 'https://youtu.be/i7tGR33yy-o', 'featured_video_title': 'Podcast Canaã #01'})
        pinned = _pinned_video()
        self.assertEqual(pinned['video_id'], 'i7tGR33yy-o')
        self.assertEqual(pinned['title'], 'Podcast Canaã #01')
        self.assertIsNone(pinned['published'])

    def test_blank_or_invalid_url_means_no_pinned_video(self):
        page = ChurchAboutPage.objects.create(site_key='about')
        for url in ('', 'https://example.com/video'):
            with self.subTest(url=url):
                ChurchAboutPage.objects.filter(pk=page.pk).update(featured_video_url=url)
                self.assertIsNone(_pinned_video())

    def test_blank_title_gets_a_generic_title(self):
        page = ChurchAboutPage.objects.create(site_key='about', featured_video_url='https://youtu.be/i7tGR33yy-o')
        self.assertEqual(_pinned_video()['title'], 'Vídeo em destaque')

    def test_no_pinned_video_when_the_database_fails(self):
        with patch('core.views.ChurchAboutPage.objects.get_or_create', side_effect=OperationalError('sem tabela')):
            self.assertIsNone(_pinned_video())


SCRIPT = Path(settings.BASE_DIR) / 'static' / 'js' / 'home-live.js'


def decide(current, payload):
    """Roda `nextFeaturedState` do script da home no Node e devolve o resultado."""
    code = (
        "const {nextFeaturedState} = require(process.argv[1]);"
        "const [current, payload] = JSON.parse(process.argv[2]);"
        "console.log(JSON.stringify(nextFeaturedState(current, payload)));"
    )
    done = subprocess.run(
        ['node', '-e', code, str(SCRIPT), json.dumps([current, payload])],
        capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout)


def payload_for(live, *video_ids):
    return {'live': live, 'videos': [{'video_id': video_id, 'title': video_id} for video_id in video_ids]}


class LivePollingPageTests(TestCase):
    @patch('core.views.home_videos', return_value=PINNED_RESULT)
    def test_home_includes_the_live_polling_script(self, _mocked):
        self.assertContains(self.client.get(reverse('home')), 'js/home-live')

    def test_script_uses_the_visibility_class_the_site_css_defines(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'app.css').read_text(encoding='utf-8')
        script = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('.reveal.is-visible', css)
        self.assertNotIn('reveal visible', script)
        self.assertEqual(script.count('reveal is-visible'), 2)

    def test_live_style_exists(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'app.css').read_text(encoding='utf-8')
        self.assertIn('.is-live', css)


class StaticPageTests(SimpleTestCase):
    def test_pages_index_label_follows_the_payload(self):
        html = (Path(settings.BASE_DIR) / 'pages' / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('TRANSMISSÃO EM DESTAQUE', html)
        self.assertIn('AO VIVO AGORA', html)
        self.assertIn('EM DESTAQUE', html)
        self.assertIn('i7tGR33yy-o', html)
        self.assertNotIn('yDlicSLiB4s', html)

    def test_pages_css_has_the_live_style(self):
        css = (Path(settings.BASE_DIR) / 'pages' / 'assets' / 'app.css').read_text(encoding='utf-8')
        self.assertIn('.is-live', css)


@skipUnless(shutil.which('node'), 'Node não está instalado')
class NextFeaturedStateTests(SimpleTestCase):
    idle = {'live': False, 'videoId': 'PIN', 'activated': False, 'stackIds': ['A', 'B', 'C']}

    def test_live_starting_replaces_the_featured_video_and_the_stack(self):
        result = decide(self.idle, payload_for(True, 'LIVE', 'A', 'B', 'C'))
        self.assertEqual(result, {'replaceFeatured': True, 'replaceStack': True})

    def test_live_ending_brings_the_pinned_video_back(self):
        current = {'live': True, 'videoId': 'LIVE', 'activated': False, 'stackIds': ['A', 'B', 'C']}
        result = decide(current, payload_for(False, 'PIN', 'LIVE', 'A', 'B'))
        self.assertEqual(result, {'replaceFeatured': True, 'replaceStack': True})

    def test_nothing_changed_replaces_nothing(self):
        self.assertEqual(decide(self.idle, payload_for(False, 'PIN', 'A', 'B', 'C')),
                         {'replaceFeatured': False, 'replaceStack': False})

    def test_new_transmission_updates_only_the_stack(self):
        result = decide(self.idle, payload_for(False, 'PIN', 'NEW', 'A', 'B'))
        self.assertEqual(result, {'replaceFeatured': False, 'replaceStack': True})

    def test_visitor_already_watching_keeps_everything(self):
        current = {**self.idle, 'activated': True}
        result = decide(current, payload_for(True, 'LIVE', 'A', 'B', 'C'))
        self.assertEqual(result, {'replaceFeatured': False, 'replaceStack': False})

    def test_empty_or_malformed_payload_changes_nothing(self):
        nothing = {'replaceFeatured': False, 'replaceStack': False}
        self.assertEqual(decide(self.idle, {'live': False, 'videos': []}), nothing)
        self.assertEqual(decide(self.idle, {}), nothing)
        self.assertEqual(decide(self.idle, {'videos': [{'title': 'sem id'}]}), nothing)


def read_current(featured_present=True, active_in=None):
    """Roda `readCurrent` do script com uma seção falsa (sem navegador)."""
    code = (
        "const {readCurrent} = require(process.argv[1]);"
        "const {present, activeIn} = JSON.parse(process.argv[2]);"
        "const stack = ['A','B','C'].map((id) => ({getAttribute: () => id}));"
        "const featured = present ? {dataset: {live: 'false', videoId: 'PIN'}} : null;"
        "const section = {"
        "  querySelector(sel) {"
        "    if (sel === '.video-featured') return featured;"
        "    if (sel === 'lite-youtube.lyt-activated') return activeIn ? {} : null;"
        "    return null;"
        "  },"
        "  querySelectorAll(sel) { return sel === '.video-list lite-youtube' ? stack : []; },"
        "};"
        "console.log(JSON.stringify(readCurrent(section)));"
    )
    done = subprocess.run(
        ['node', '-e', code, str(SCRIPT), json.dumps({'present': featured_present, 'activeIn': active_in})],
        capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout)


@skipUnless(shutil.which('node'), 'Node não está instalado')
class ReadCurrentStateTests(SimpleTestCase):
    def test_reads_the_page_state(self):
        self.assertEqual(
            read_current(),
            {'live': False, 'videoId': 'PIN', 'activated': False, 'stackIds': ['A', 'B', 'C']},
        )

    def test_a_playing_video_anywhere_in_the_section_counts_as_activated(self):
        self.assertTrue(read_current(active_in='stack')['activated'])

    def test_no_featured_element_means_no_state(self):
        self.assertIsNone(read_current(featured_present=False))


class LiveWithoutKeyTests(TestCase):
    """Sem chave da API, a transmissão no ar é detectada pela página /live do canal."""

    PAGE_LIVE = (
        '<meta property="og:title" content="Culto de Louvor &amp; Adoração - 16/11/2026">'
        '<link rel="canonical" href="https://www.youtube.com/watch?v=LIVE0000001">'
        '..."isLiveNow":true...'
    )
    PAGE_OFFLINE = '<link rel="canonical" href="https://www.youtube.com/channel/UCnJeIwpnusCcbJa9nAInb8Q">'

    def test_parses_a_live_page(self):
        from core.youtube import parse_channel_live_page
        self.assertEqual(parse_channel_live_page(self.PAGE_LIVE),
                         {'video_id': 'LIVE0000001', 'title': 'Culto de Louvor & Adoração - 16/11/2026'})

    def test_offline_or_unconfirmed_pages_are_not_live(self):
        from core.youtube import parse_channel_live_page
        self.assertIsNone(parse_channel_live_page(self.PAGE_OFFLINE))
        self.assertIsNone(parse_channel_live_page(self.PAGE_LIVE.replace('"isLiveNow":true', '"isLiveNow":false')))

    @override_settings(YOUTUBE_API_KEY='', YOUTUBE_CHANNEL_ID=CHANNEL_ID, YOUTUBE_LIVE_PAGE_CHECK=True)
    def test_live_is_detected_even_when_the_streams_feed_is_down(self):
        live = {'video_id': 'LIVE0000001', 'title': 'Culto ao vivo'}
        with patch('core.youtube.fetch_feed_entries', side_effect=YoutubeError('fora do ar')), \
                patch('core.youtube.fetch_live_without_key', return_value=live):
            videos = load_videos(NOW)
        self.assertEqual([item['video_id'] for item in videos], ['LIVE0000001'])
        self.assertTrue(videos[0]['live'])

    @override_settings(YOUTUBE_API_KEY='', YOUTUBE_CHANNEL_ID=CHANNEL_ID, YOUTUBE_LIVE_PAGE_CHECK=True)
    def test_live_detected_without_key_is_featured_even_if_not_in_the_streams_feed(self):
        live = {'video_id': 'LIVE0000001', 'title': 'Culto ao vivo'}
        with patch('core.youtube.fetch_feed_entries', return_value=ENTRIES), \
                patch('core.youtube.fetch_live_without_key', return_value=live):
            videos = load_videos(NOW)
        self.assertEqual(videos[0]['video_id'], 'LIVE0000001')
        self.assertTrue(videos[0]['live'])
        self.assertTrue(build_home_videos(videos, None)['live'])
