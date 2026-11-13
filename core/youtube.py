"""Vídeos do canal da igreja no YouTube: feed RSS, estado ao vivo e montagem da home.

Fontes estáveis, sem raspar HTML:
- feed RSS público do canal (lista de vídeos e datas);
- YouTube Data API `videos.list` (opcional, com chave) para saber o que está ao
  vivo e separar transmissões de uploads comuns.

A chave da API vai na URL da consulta. Por isso nenhuma exceção desta camada
carrega a URL: os erros são trocados por mensagens fixas e nada é registrado em log.
"""

import json
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FEED_URL = 'https://www.youtube.com/feeds/videos.xml'
API_VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'
TIMEOUT_SECONDS = 2
MAX_BODY_BYTES = 1024 * 1024
MAX_IDS_PER_REQUEST = 50
USER_AGENT = 'ibrcanaa-site/1.0'

ATOM = '{http://www.w3.org/2005/Atom}'
YT = '{http://www.youtube.com/xml/schemas/2015}'


class YoutubeError(Exception):
    """Falha ao consultar o YouTube. A mensagem nunca contém a URL nem a chave."""


def _read(url):
    request = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BODY_BYTES + 1)
    except (OSError, ValueError) as error:
        raise YoutubeError(f'Falha ao consultar o YouTube ({type(error).__name__}).') from None
    if len(body) > MAX_BODY_BYTES:
        raise YoutubeError('Resposta do YouTube grande demais.')
    return body


def fetch_feed_entries(channel_id):
    """Vídeos do feed RSS do canal, do mais novo ao mais antigo, como
    `{'video_id', 'title', 'published'}` (`published` em ISO 8601)."""
    body = _read(f'{FEED_URL}?{urlencode({"channel_id": channel_id})}')
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
