import json
from datetime import datetime, timedelta, timezone as dt_timezone
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings

from core.forms import ChurchAboutPageForm
from core.models import ChurchAboutPage, YoutubeSnapshot
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

    def test_defaults_point_to_the_podcast(self):
        page = ChurchAboutPage.objects.create(site_key='about')
        self.assertEqual(page.featured_video_id, 'i7tGR33yy-o')
        self.assertIn('PodcastCanaã#01', page.featured_video_title)

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

    def test_feed_requests_the_channel_feed_url(self, mocked_urlopen):
        respond_with(mocked_urlopen, FEED_XML)
        fetch_feed_entries(CHANNEL_ID)
        request = mocked_urlopen.call_args.args[0]
        url = request.full_url if hasattr(request, 'full_url') else request
        self.assertEqual(url, f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}')
        self.assertEqual(mocked_urlopen.call_args.kwargs['timeout'], 2)

    def test_feed_rejects_malformed_xml(self, mocked_urlopen):
        respond_with(mocked_urlopen, '<feed><entry>')
        with self.assertRaises(YoutubeError):
            fetch_feed_entries(CHANNEL_ID)

    def test_feed_rejects_oversized_body(self, mocked_urlopen):
        respond_with(mocked_urlopen, b'<feed>' + b'x' * (1024 * 1024 + 10) + b'</feed>')
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
        load_videos(self.at(30))
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
        self.assertTrue(all(item['transmission'] is None for item in videos))

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
        self.assertTrue(all(item['transmission'] is None for item in videos))
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
