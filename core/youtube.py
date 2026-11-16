"""Vídeos do canal da igreja no YouTube: feed RSS, estado ao vivo e montagem da home.

Fontes estáveis, sem raspar HTML:
- feed RSS público da aba "Ao vivo" (Streams) do canal, a playlist automática
  `UULV<id do canal sem o UC>` (lista de transmissões e datas, sem precisar de chave);
- YouTube Data API `videos.list` (opcional, com chave) para saber o que está ao
  vivo e separar transmissões de uploads comuns.

A chave da API vai na URL da consulta. Por isso nenhuma exceção desta camada
carrega a URL: os erros são trocados por mensagens fixas e nada é registrado em log.
"""

import http.client
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import YoutubeSnapshot

FEED_URL = 'https://www.youtube.com/feeds/videos.xml'
API_VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'
TIMEOUT_SECONDS = 2
MAX_BODY_BYTES = 1024 * 1024
MAX_IDS_PER_REQUEST = 50
USER_AGENT = 'ibrcanaa-site/1.0'

ATOM = '{http://www.w3.org/2005/Atom}'
YT = '{http://www.youtube.com/xml/schemas/2015}'

REFRESH_SECONDS = 60
LIVE_MAX_AGE_SECONDS = 600
STACK_SIZE = 3
SNAPSHOT_KEY = 'channel'
CHANNEL_TITLE = 'Igreja Batista Regular Canaã'
UNDATED = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)  # vídeos sem data vão para o fim


class YoutubeError(Exception):
    """Falha ao consultar o YouTube. A mensagem nunca contém a URL nem a chave."""


def _read(url):
    request = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BODY_BYTES + 1)
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise YoutubeError(f'Falha ao consultar o YouTube ({type(error).__name__}).') from None
    if len(body) > MAX_BODY_BYTES:
        raise YoutubeError('Resposta do YouTube grande demais.')
    return body


def streams_playlist_id(channel_id):
    """Playlist automática com as transmissões do canal (a aba Streams)."""
    return 'UULV' + channel_id[2:] if channel_id.startswith('UC') else None


def fetch_feed_entries(channel_id):
    """Transmissões da aba Streams do canal (feed RSS), da mais nova à mais antiga, como
    `{'video_id', 'title', 'published'}` (`published` em ISO 8601)."""
    playlist_id = streams_playlist_id(channel_id)
    if not playlist_id:
        raise YoutubeError('ID de canal do YouTube inválido.')
    body = _read(f'{FEED_URL}?{urlencode({"playlist_id": playlist_id})}')
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise YoutubeError('Feed do YouTube inválido.') from None
    entries = []
    for entry in root.findall(f'{ATOM}entry'):
        video_id = (entry.findtext(f'{YT}videoId') or '').strip()
        title = (entry.findtext(f'{ATOM}title') or '').strip()
        if video_id and title:
            entries.append({
                'video_id': video_id,
                'title': title,
                'published': (entry.findtext(f'{ATOM}published') or '').strip(),
            })
    return entries


def fetch_video_details(video_ids, api_key):
    """Estado de cada vídeo segundo a API: `{video_id: {'live', 'transmission'}}`.

    `live`: está no ar agora. `transmission`: é (ou foi) uma transmissão ao vivo;
    agendadas que ainda não começaram não contam. Vídeos que a API não devolve
    (privados, apagados) ficam de fora.
    """
    ids = list(video_ids)[:MAX_IDS_PER_REQUEST]
    if not ids:
        return {}
    query = urlencode({
        'part': 'snippet,liveStreamingDetails',
        'id': ','.join(ids),
        'key': api_key,
    })
    body = _read(f'{API_VIDEOS_URL}?{query}')
    try:
        data = json.loads(body)
    except ValueError:
        raise YoutubeError('Resposta da API do YouTube inválida.') from None
    items = data.get('items') if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise YoutubeError('Resposta da API do YouTube inválida.')
    details = {}
    for item in items:
        if not isinstance(item, dict) or not item.get('id'):
            continue
        snippet = item.get('snippet')
        broadcast = snippet.get('liveBroadcastContent') if isinstance(snippet, dict) else None
        details[item['id']] = {
            'live': broadcast == 'live',
            'transmission': 'liveStreamingDetails' in item and broadcast != 'upcoming',
        }
    return details


def _claim_refresh(snapshot, now):
    """Decide se esta requisição deve atualizar o instantâneo.

    A atualização está vencida se a última tentativa tem 60 s ou mais. Quem
    vence a atualização condicional de `checked_at` faz a consulta; as demais
    requisições simultâneas seguem com os dados atuais. Como a tentativa é
    marcada antes da consulta, uma falha só é repetida após o intervalo.
    """
    if snapshot.checked_at is not None and now - snapshot.checked_at < timedelta(seconds=REFRESH_SECONDS):
        return False
    claimed = YoutubeSnapshot.objects.filter(
        pk=snapshot.pk, checked_at=snapshot.checked_at,
    ).update(checked_at=now)
    if claimed:
        snapshot.checked_at = now
    return bool(claimed)


def _has_recent_details(snapshot, now):
    """O instantâneo atual tem dados da API e é recente o bastante para ainda valer?"""
    if snapshot.updated_at is None or now - snapshot.updated_at > timedelta(seconds=LIVE_MAX_AGE_SECONDS):
        return False
    return bool((snapshot.payload or {}).get('live_state_known'))


def _refresh(snapshot, now):
    """Consulta o YouTube e grava o resultado. Em falha, mantém o instantâneo anterior."""
    try:
        entries = fetch_feed_entries(settings.YOUTUBE_CHANNEL_ID)
    except YoutubeError:
        return
    if not entries:
        return
    details = None
    if settings.YOUTUBE_API_KEY:
        try:
            details = fetch_video_details([entry['video_id'] for entry in entries], settings.YOUTUBE_API_KEY)
        except YoutubeError:
            # Falha passageira da API: não troca dados completos (com o estado ao
            # vivo) por dados só do RSS. Após 10 min sem sucesso, cai para o RSS.
            if _has_recent_details(snapshot, now):
                return
            details = None
    videos = []
    for entry in entries:
        detail = (details or {}).get(entry['video_id'])
        videos.append({
            **entry,
            'live': bool(detail and detail['live']),
            # Todo item da aba Streams é uma transmissão; a API só diz o que está no ar.
            'transmission': True,
        })
    snapshot.payload = {'videos': videos, 'live_state_known': details is not None}
    snapshot.updated_at = now
    snapshot.save(update_fields=['payload', 'updated_at'])


def load_videos(now=None):
    """Vídeos do canal, atualizando o instantâneo se estiver vencido.

    Cada item: `video_id`, `title`, `channel_title`, `published` (datetime ou None),
    `live` e `transmission` (`None` quando não há chave da API). O estado `live`
    é descartado se o último dado bom tiver mais de `LIVE_MAX_AGE_SECONDS`.
    """
    now = now or timezone.now()
    snapshot, _ = YoutubeSnapshot.objects.get_or_create(key=SNAPSHOT_KEY)
    if _claim_refresh(snapshot, now):
        _refresh(snapshot, now)
    live_is_trustworthy = (
        snapshot.updated_at is not None
        and now - snapshot.updated_at <= timedelta(seconds=LIVE_MAX_AGE_SECONDS)
    )
    videos = []
    for item in (snapshot.payload or {}).get('videos', []):
        videos.append({
            'video_id': item['video_id'],
            'title': item['title'],
            'channel_title': CHANNEL_TITLE,
            'published': parse_datetime(item.get('published') or ''),
            'live': bool(item.get('live')) and live_is_trustworthy,
            'transmission': item.get('transmission'),
        })
    return videos


def build_home_videos(videos, pinned):
    """Monta o destaque e a pilha da home. Função pura.

    Destaque: a live, se houver; senão o vídeo fixo; senão a transmissão mais
    recente. Pilha: as `STACK_SIZE` transmissões mais recentes, sem repetir o
    destaque nem o vídeo fixo. Sem dados da API (`transmission` sempre `None`),
    todos os vídeos do feed são candidatos.
    """
    live_video = next((item for item in videos if item['live']), None)
    has_details = any(item['transmission'] is not None for item in videos)
    candidates = [item for item in videos if item['transmission'] or not has_details]
    candidates.sort(key=lambda item: item['published'] or UNDATED, reverse=True)

    featured = live_video or pinned
    if featured is None and candidates:
        featured = candidates[0]
    excluded = {featured['video_id']} if featured else set()
    if pinned:
        excluded.add(pinned['video_id'])
    stack = [item for item in candidates if item['video_id'] not in excluded][:STACK_SIZE]
    return {
        'live': live_video is not None,
        'videos': ([featured] if featured else []) + stack,
    }


def home_videos(pinned=None, now=None):
    """Destaque e pilha da home. Sem tabelas do banco, mostra só o vídeo fixo."""
    try:
        videos = load_videos(now)
    except (OperationalError, ProgrammingError):
        videos = []
    return build_home_videos(videos, pinned)
