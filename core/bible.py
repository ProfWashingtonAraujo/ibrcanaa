import json
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.core.cache import cache


BIBLE_BOOKS = (
    ('genesis', 'Gênesis', 50), ('exodo', 'Êxodo', 40), ('levitico', 'Levítico', 27),
    ('numeros', 'Números', 36), ('deuteronomio', 'Deuteronômio', 34), ('josue', 'Josué', 24),
    ('juizes', 'Juízes', 21), ('rute', 'Rute', 4), ('1-samuel', '1 Samuel', 31),
    ('2-samuel', '2 Samuel', 24), ('1-reis', '1 Reis', 22), ('2-reis', '2 Reis', 25),
    ('1-cronicas', '1 Crônicas', 29), ('2-cronicas', '2 Crônicas', 36), ('esdras', 'Esdras', 10),
    ('neemias', 'Neemias', 13), ('ester', 'Ester', 10), ('jo', 'Jó', 42), ('salmos', 'Salmos', 150),
    ('proverbios', 'Provérbios', 31), ('eclesiastes', 'Eclesiastes', 12), ('cantares', 'Cantares', 8),
    ('isaias', 'Isaías', 66), ('jeremias', 'Jeremias', 52), ('lamentacoes', 'Lamentações', 5),
    ('ezequiel', 'Ezequiel', 48), ('daniel', 'Daniel', 12), ('oseias', 'Oséias', 14), ('joel', 'Joel', 3),
    ('amos', 'Amós', 9), ('obadias', 'Obadias', 1), ('jonas', 'Jonas', 4), ('miqueias', 'Miquéias', 7),
    ('naum', 'Naum', 3), ('habacuque', 'Habacuque', 3), ('sofonias', 'Sofonias', 3),
    ('ageu', 'Ageu', 2), ('zacarias', 'Zacarias', 14), ('malaquias', 'Malaquias', 4),
    ('mateus', 'Mateus', 28), ('marcos', 'Marcos', 16), ('lucas', 'Lucas', 24), ('joao', 'João', 21),
    ('atos', 'Atos', 28), ('romanos', 'Romanos', 16), ('1-corintios', '1 Coríntios', 16),
    ('2-corintios', '2 Coríntios', 13), ('galatas', 'Gálatas', 6), ('efesios', 'Efésios', 6),
    ('filipenses', 'Filipenses', 4), ('colossenses', 'Colossenses', 4),
    ('1-tessalonicenses', '1 Tessalonicenses', 5), ('2-tessalonicenses', '2 Tessalonicenses', 3),
    ('1-timoteo', '1 Timóteo', 6), ('2-timoteo', '2 Timóteo', 4), ('tito', 'Tito', 3),
    ('filemom', 'Filemom', 1), ('hebreus', 'Hebreus', 13), ('tiago', 'Tiago', 5),
    ('1-pedro', '1 Pedro', 5), ('2-pedro', '2 Pedro', 3), ('1-joao', '1 João', 5),
    ('2-joao', '2 João', 1), ('3-joao', '3 João', 1), ('judas', 'Judas', 1), ('apocalipse', 'Apocalipse', 22),
)

DAILY_VERSES = (
    {'reference': 'João 3:16', 'book': 'joao', 'chapter': 3, 'verse': 16, 'text': 'Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito, para que todo aquele que nele crê não pereça, mas tenha a vida eterna.'},
    {'reference': 'Salmos 23:1', 'book': 'salmos', 'chapter': 23, 'verse': 1, 'text': 'O Senhor é o meu pastor; nada me faltará.'},
    {'reference': 'Filipenses 4:6', 'book': 'filipenses', 'chapter': 4, 'verse': 6, 'text': 'Não andeis ansiosos por coisa alguma; antes em tudo sejam os vossos pedidos conhecidos diante de Deus pela oração e súplica com ações de graças.'},
    {'reference': 'Provérbios 3:5', 'book': 'proverbios', 'chapter': 3, 'verse': 5, 'text': 'Confia no Senhor de todo o teu coração, e não te estribes no teu próprio entendimento.'},
    {'reference': 'Isaías 41:10', 'book': 'isaias', 'chapter': 41, 'verse': 10, 'text': 'Não temas, porque eu sou contigo; não te assombres, porque eu sou teu Deus; eu te fortaleço, e te ajudo, e te sustento com a destra da minha justiça.'},
    {'reference': 'Romanos 8:28', 'book': 'romanos', 'chapter': 8, 'verse': 28, 'text': 'E sabemos que todas as coisas concorrem para o bem daqueles que amam a Deus, daqueles que são chamados segundo o seu propósito.'},
    {'reference': 'Mateus 11:28', 'book': 'mateus', 'chapter': 11, 'verse': 28, 'text': 'Vinde a mim, todos os que estai cansados e oprimidos, e eu vos aliviarei.'},
)


def get_book(slug):
    return next((book for book in BIBLE_BOOKS if book[0] == slug), None)


def get_daily_verse(day=None):
    day = day or date.today()
    return {**DAILY_VERSES[(day.toordinal() - 1) % len(DAILY_VERSES)], 'date': day.isoformat()}


def fetch_chapter(book_name, chapter):
    cache_key = f'bible:almeida:{book_name}:{chapter}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    reference = quote(f'{book_name} {chapter}')
    request = Request(
        f'https://bible-api.com/{reference}?translation=almeida',
        headers={'User-Agent': 'IBR-Canaa-Portal/1.0'},
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    result = {
        'reference': payload.get('reference', f'{book_name} {chapter}'),
        'verses': payload.get('verses', []),
        'translation_name': payload.get('translation_name', 'João Ferreira de Almeida'),
        'translation_note': payload.get('translation_note', 'Public Domain'),
    }
    cache.set(cache_key, result, 60 * 60 * 24 * 30)
    return result
