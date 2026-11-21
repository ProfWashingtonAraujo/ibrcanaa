"""Episódio mais recente de um programa do Spotify, sem chave de API.

A página pública de embed do programa (`/embed/show/<id>`) traz, no JSON
`__NEXT_DATA__`, o episódio mais recente. Como não é uma API documentada, tudo
aqui é defensivo: qualquer falha devolve o último resultado bom (ou `None`) e o
site cai no comportamento manual (embed do programa, título digitado no admin).
"""

import http.client
import json
import re
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

EMBED_URL = 'https://open.spotify.com/embed/show/{show_id}'
USER_AGENT = 'Mozilla/5.0 (compatible; ibrcanaa-site/1.0)'
TIMEOUT_SECONDS = 3
MAX_BODY_BYTES = 1024 * 1024
FRESH_SECONDS = 15 * 60
STALE_SECONDS = 7 * 24 * 3600
FAILURE_BACKOFF_SECONDS = 60

ID_RE = re.compile(r'[A-Za-z0-9]+')
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _fetch(show_id):
    request = Request(EMBED_URL.format(show_id=show_id), headers={'User-Agent': USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BODY_BYTES + 1)
    except (OSError, ValueError, http.client.HTTPException):
        return None
    if len(body) > MAX_BODY_BYTES:
        return None
    match = NEXT_DATA_RE.search(body.decode('utf-8', 'replace'))
    if not match:
        return None
    try:
        entity = json.loads(match.group(1))['props']['pageProps']['state']['data']['entity']
        episode_id = entity['id']
        title = entity['title']
        owner = entity.get('relatedEntityUri', '')
    except (ValueError, KeyError, TypeError):
        return None
    if entity.get('type') != 'episode' or owner != f'spotify:show:{show_id}':
        return None
    if not isinstance(episode_id, str) or not ID_RE.fullmatch(episode_id) or not isinstance(title, str) or not title.strip():
        return None
    release = entity.get('releaseDate')
    released = release.get('isoString', '') if isinstance(release, dict) else ''
    return {'id': episode_id, 'title': title.strip(), 'released': released}


def latest_episode(show_id):
    """`{'id', 'title', 'released'}` do episódio mais recente, ou `None` se nunca deu certo."""
    if not settings.SPOTIFY_LATEST_EPISODE or not ID_RE.fullmatch(show_id or ''):
        return None
    fresh_key, stale_key, fail_key = (f'spotify:{kind}:{show_id}' for kind in ('fresh', 'stale', 'fail'))
    episode = cache.get(fresh_key)
    if episode:
        return episode
    if cache.get(fail_key):
        return cache.get(stale_key)
    episode = _fetch(show_id)
    if episode:
        cache.set(fresh_key, episode, FRESH_SECONDS)
        cache.set(stale_key, episode, STALE_SECONDS)
        return episode
    cache.set(fail_key, True, FAILURE_BACKOFF_SECONDS)
    return cache.get(stale_key)
