# Destaque ao vivo e feed RSS do YouTube: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A home mostra a live no destaque grande quando houver uma, o vídeo fixo escolhido pela igreja quando não houver, e as 3 transmissões mais recentes na pilha, usando o feed RSS do canal e a YouTube Data API no lugar da raspagem de HTML.

**Architecture:** Um módulo novo `core/youtube.py` lê o RSS e (com chave) a API, guarda o resultado num instantâneo no banco compartilhado e monta a lista da home com uma função pura. As views só chamam `home_videos(pinned)`. O vídeo fixo vive em `ChurchAboutPage`, editável no painel. Um script pequeno na home consulta `/videos/youtube/` a cada 60 s.

**Tech Stack:** Django 6, Python 3.14, `urllib` e `xml.etree` da biblioteca padrão, JavaScript puro, lite-youtube-embed já usado.

**Spec:** `docs/superpowers/specs/2026-11-13-youtube-live-featured-design.md`

## Global Constraints

- ID do canal padrão: `UCnJeIwpnusCcbJa9nAInb8Q`. Variáveis de ambiente `YOUTUBE_CHANNEL_ID` (opcional) e `YOUTUBE_API_KEY` (opcional).
- Atualização no máximo a cada 60 s. "Ao vivo" expira se o último dado bom tiver mais de 600 s.
- Timeout de 2 s por chamada externa; leitura do RSS limitada a 1 MB.
- Pilha com 3 itens. Destaque inicial: `https://youtu.be/i7tGR33yy-o`, título `MARXISMO CULTURAL + Marcos Perin + Carlos A. Bezerra + Márcio Bastos. PodcastCanaã#01`.
- Rótulos: `● AO VIVO AGORA` (live) e `EM DESTAQUE` (vídeo fixo ou, sem ele, o mais recente).
- Nunca registrar em log nem propagar a URL da API (contém a chave).
- Sem raspagem de HTML do YouTube e sem lista de vídeos de reserva.
- O contrato do endpoint `/videos/youtube/` mantém `channel` e `videos` (destaque primeiro) e ganha `live` (booleano). `Cache-Control: public, max-age=30`.
- Testes rodam com `DJANGO_DEBUG=True python manage.py test`. Um commit por tarefa, com a linha `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- API com cota esgotada ou erro 403/5xx: a home continua abrindo com o último instantâneo, sem erro 500.
- "Ao vivo" preso depois de uma queda longa da API: some após 600 s sem atualização com sucesso.
- Vídeo fixo em branco ou inválido no painel: o destaque vira a transmissão mais recente, sem quebrar.
- RSS fora do ar ou XML inválido sem nenhum instantâneo: a home mostra só o vídeo fixo e o link do canal.
- O mesmo vídeo aparecer duas vezes (live igual ao vídeo fixo, ou o fixo também na pilha).

---

### Task 1: Vídeo fixo editável e modelo do instantâneo

**Files:**
- Modify: `core/models.py` (`ChurchAboutPage`, novo `YoutubeSnapshot`), `core/forms.py` (`ChurchAboutPageForm`)
- Create: `core/migrations/0024_*.py` (gerada por `makemigrations`)
- Test: `core/test_youtube.py` (novo; as próximas tarefas acrescentam a ele)

**Interfaces:**
- Produces: `core.models.DEFAULT_FEATURED_VIDEO_URL`, `DEFAULT_FEATURED_VIDEO_TITLE` (valores da seção Global Constraints); `ChurchAboutPage.featured_video_url` (`URLField`, `blank=True`, `validators=[validate_youtube_url]`), `ChurchAboutPage.featured_video_title` (`CharField(max_length=160, blank=True)`), propriedade `ChurchAboutPage.featured_video_id -> str | None`; `YoutubeSnapshot` com `key` (`CharField(max_length=20, unique=True, default='channel')`), `payload` (`JSONField(default=dict)`), `updated_at` e `checked_at` (`DateTimeField(null=True, blank=True)`).

- [ ] **Step 1: Escrever os testes que falham** em `core/test_youtube.py`, classe `FeaturedVideoFieldTests(TestCase)`:
  - `test_defaults_point_to_the_podcast`: `ChurchAboutPage.objects.create(site_key='about').featured_video_id == 'i7tGR33yy-o'` e o título padrão contém `PodcastCanaã#01`.
  - `test_form_accepts_valid_youtube_url`: `ChurchAboutPageForm` com os campos obrigatórios e `featured_video_url='https://youtu.be/AAAAAAAAAAA'` é válido.
  - `test_form_rejects_non_youtube_url`: `https://example.com/video` é inválido, com erro em `featured_video_url`.
  - `test_blank_url_is_allowed_and_has_no_video_id`: URL vazia é válida e `featured_video_id is None`.
  - `test_snapshot_key_is_unique`: criar dois `YoutubeSnapshot(key='channel')` levanta `IntegrityError`.
- [ ] **Step 2: Rodar e ver falhar** (`DJANGO_DEBUG=True python manage.py test core.test_youtube`). Esperado: `ImportError`/`AttributeError`.
- [ ] **Step 3: Implementar** os campos, a propriedade e o modelo em `core/models.py` (a propriedade usa `youtube_video_id` já existente); acrescentar `featured_video_title` e `featured_video_url` ao `Meta.fields` e a `full_width_fields` de `ChurchAboutPageForm`, com placeholder `https://youtu.be/...` no widget da URL; gerar a migration com `makemigrations core -n featured_video_and_youtube_snapshot`.
- [ ] **Step 4: Rodar a suíte inteira.** Esperado: tudo passa e `makemigrations --check` sem pendências.
- [ ] **Step 5: Commit** `feat: editable featured video and YouTube snapshot model`.

### Task 2: Leitura do RSS e da API

**Files:**
- Create: `core/youtube.py`
- Modify: `config/settings.py` (variáveis `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID`)
- Test: `core/test_youtube.py`

**Interfaces:**
- Produces: `class YoutubeError(Exception)`; `fetch_feed_entries(channel_id: str) -> list[dict]`, cada item `{'video_id': str, 'title': str, 'published': str}` (ISO 8601), na ordem do feed; `fetch_video_details(video_ids: list[str], api_key: str) -> dict[str, dict]`, no formato `{video_id: {'live': bool, 'transmission': bool}}`, omitindo ids que a API não devolver. Ambas chamam `urlopen` de `core.youtube` (testes fazem patch em `core.youtube.urlopen`).

- [ ] **Step 1: Escrever os testes que falham**, classes `FeedParsingTests` e `VideoDetailsTests`:
  - `test_feed_entries_are_parsed_in_order`: XML com 2 `<entry>` (ids `AAAAAAAAAAA`, `BBBBBBBBBBB`, `yt:videoId`, `title`, `published`) devolve os dois, com o `published` original.
  - `test_feed_requests_the_channel_feed_url`: a URL pedida é `https://www.youtube.com/feeds/videos.xml?channel_id=UC...`.
  - `test_feed_rejects_malformed_xml`, `test_feed_rejects_oversized_body` (> 1 MB), `test_feed_network_error_becomes_youtube_error`: todos levantam `YoutubeError`.
  - `test_details_flags_live_and_transmissions`: resposta JSON com um item `liveBroadcastContent: 'live'` e `liveStreamingDetails`, um `none` com `liveStreamingDetails`, um `none` sem ele e um `upcoming` com ele. Esperado: ao vivo = `live True, transmission True`; encerrada = `live False, transmission True`; upload comum = ambos `False`; agendada = ambos `False`.
  - `test_details_http_error_hides_the_api_key`: `HTTPError` 403 vira `YoutubeError` e `'SEGREDO123'` (a chave usada) não aparece em `str(error)` nem em `caplog.text`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** as funções em `core/youtube.py`: `xml.etree.ElementTree` com os namespaces Atom e `yt`; ler no máximo 1 MB + 1 byte e recusar se passar; `videos.list` com `part=snippet,liveStreamingDetails` e `id` separado por vírgula (até 50). Capturar `OSError`, `ValueError`, `ParseError` e relançar `YoutubeError` com mensagem fixa (nome do tipo da exceção, sem URL). Em `settings.py`, ler as duas variáveis com `.strip()`; `YOUTUBE_CHANNEL_ID` padrão `UCnJeIwpnusCcbJa9nAInb8Q`.
- [ ] **Step 4: Rodar a suíte inteira.** Esperado: passa.
- [ ] **Step 5: Commit** `feat: read the channel RSS feed and YouTube video details`.

### Task 3: Instantâneo compartilhado e montagem da lista

**Files:**
- Modify: `core/youtube.py`
- Test: `core/test_youtube.py`

**Interfaces:**
- Consumes: `fetch_feed_entries`, `fetch_video_details`, `YoutubeError`, `YoutubeSnapshot`, `settings.YOUTUBE_API_KEY`, `settings.YOUTUBE_CHANNEL_ID`.
- Produces: constantes `REFRESH_SECONDS = 60`, `LIVE_MAX_AGE_SECONDS = 600`, `STACK_SIZE = 3`; `load_videos(now: datetime | None = None) -> list[dict]` (atualiza se vencido; cada item `{'video_id', 'title', 'channel_title', 'published': datetime | None, 'live': bool, 'transmission': bool | None}`; `transmission` é `None` sem chave; lista vazia se nunca houve dado; `live` já zerado se o dado tiver mais de 600 s); `build_home_videos(videos: list[dict], pinned: dict | None) -> dict` (pura; devolve `{'live': bool, 'videos': list[dict]}`); `home_videos(pinned: dict | None = None, now: datetime | None = None) -> dict` (`build_home_videos(load_videos(now), pinned)`). `pinned` tem o formato `{'video_id', 'title', 'channel_title', 'published': None}`.

- [ ] **Step 1: Escrever os testes que falham.** Para `build_home_videos` (sem rede), classe `BuildHomeVideosTests(SimpleTestCase)`, com vídeos `V1..V5` do mais novo ao mais velho:
  - `test_live_takes_the_featured_slot_and_pinned_is_hidden`: com `V1` ao vivo e `P` fixo, `videos[0]` é `V1`, `live is True`, `P` não aparece e a pilha é `V2, V3, V4`.
  - `test_pinned_is_featured_when_nothing_is_live`: `videos[0]` é `P` e a pilha é `V1, V2, V3`.
  - `test_ended_live_goes_to_the_stack`: `V1` com `live False, transmission True` fica em `videos[1]`.
  - `test_stack_only_has_transmissions_when_details_exist`: um upload comum (`transmission False`) entre os vídeos não entra.
  - `test_without_details_the_stack_uses_the_latest_entries`: com `transmission None`, a pilha usa os 3 mais recentes.
  - `test_no_pinned_uses_latest_transmission_as_featured`: sem `pinned` e sem live, `videos[0]` é `V1` e a pilha tem 3 itens seguintes.
  - `test_pinned_never_repeats_in_the_stack`: se `P` for o mesmo id de `V2`, ele aparece só uma vez.
  - `test_live_equal_to_pinned_appears_once`.
  - `test_nothing_available_returns_only_pinned` e `test_nothing_at_all_returns_empty`.
  - Para `load_videos`, classe `LoadVideosTests(TestCase)` com `urlopen` e a API simulados por patch em `core.youtube.fetch_feed_entries` e `core.youtube.fetch_video_details`:
  - `test_first_call_fetches_and_stores_a_snapshot`: grava `YoutubeSnapshot` e devolve os vídeos.
  - `test_fresh_snapshot_does_not_refetch`: segunda chamada em até 60 s não chama as funções de rede.
  - `test_stale_snapshot_refetches`: após 61 s chama de novo.
  - `test_failed_refresh_keeps_the_last_good_snapshot`: o RSS falha e a lista antiga é devolvida.
  - `test_failed_refresh_is_retried_only_after_the_interval`: após a falha, uma nova chamada em até 60 s não tenta de novo.
  - `test_api_failure_keeps_feed_entries_without_live_flags`: o RSS funciona e a API levanta `YoutubeError`; os vídeos vêm com `transmission None` e `live False`.
  - `test_live_flag_expires_after_ten_minutes_without_success`: dado com 601 s e falha na atualização devolve `live False`.
  - `test_without_api_key_the_api_is_never_called` (`override_settings(YOUTUBE_API_KEY='')`).
  - `test_only_one_request_claims_a_due_refresh`: duas chamadas seguidas com o mesmo `now` vencido resultam em uma só ida à rede.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** em `core/youtube.py`. Regras de `build_home_videos`: destaque = primeiro `live`, senão `pinned`, senão o primeiro candidato; candidatos = vídeos com `transmission is True` se algum vídeo tiver `transmission` diferente de `None`, senão todos; excluir da pilha o id do destaque e o id de `pinned`; ordenar por `published` decrescente; pilha = `STACK_SIZE` itens. Regras de `load_videos`: usar `YoutubeSnapshot.objects.get_or_create(key='channel')`; "reivindicar" a atualização com `filter(pk=..., checked_at=<valor lido>).update(checked_at=now)` e só ir à rede se `update` devolver 1; em sucesso gravar `payload` e `updated_at`; `published` convertido com `django.utils.dateparse.parse_datetime`; `channel_title` fixo `'Igreja Batista Regular Canaã'`.
- [ ] **Step 4: Rodar a suíte inteira.** Esperado: passa.
- [ ] **Step 5: Commit** `feat: shared YouTube snapshot and home video selection`.

### Task 4: Views, template e endpoint

**Files:**
- Modify: `core/views.py`, `templates/core/home.html`, `core/tests.py` (substituir os 3 testes do YouTube nas linhas ~141-205)
- Test: `core/tests.py`, `core/test_youtube.py`

**Interfaces:**
- Consumes: `home_videos(pinned)` de `core.youtube`, `ChurchAboutPage.featured_video_id/.featured_video_title`, `DEFAULT_FEATURED_VIDEO_URL/TITLE`.
- Produces: `core.views._pinned_video() -> dict | None` (lê `ChurchAboutPage`; com erro de banco usa os padrões; URL vazia ou inválida devolve `None`); contexto da home com `youtube_videos` (lista, destaque primeiro) e `youtube_live` (bool); resposta de `/videos/youtube/` com `live`.

- [ ] **Step 1: Escrever os testes que falham** (patch em `core.views.home_videos`), classe `HomeYoutubeTests(TestCase)` em `core/test_youtube.py`:
  - `test_home_labels_the_live_and_marks_it_in_the_page`: com `live True`, a home contém `● AO VIVO AGORA`, `data-live="true"` e `data-video-id` do destaque.
  - `test_home_labels_the_pinned_video`: com `live False`, contém `EM DESTAQUE` e `data-live="false"`; a home não contém `TRANSMISSÃO EM DESTAQUE`.
  - `test_home_renders_featured_and_three_stack_items_with_origin_param`: reaproveita a verificação de `params="origin=http://testserver"` com 4 players e a de `Referrer-Policy`.
  - `test_home_exposes_the_feed_url_for_polling`: o HTML tem `data-feed-url="/videos/youtube/"` na seção de vídeos.
  - `test_home_still_loads_when_the_snapshot_is_empty`: com `home_videos` devolvendo só o vídeo fixo, a home abre (200) com um player.
  - `test_feed_endpoint_exposes_live_and_keeps_contract`: JSON com `live`, `videos[0].video_id`, `channel.url`, CORS para `https://profwashingtonaraujo.github.io` e `Cache-Control: public, max-age=30`.
  - `test_pinned_video_comes_from_the_about_page`: `_pinned_video()` devolve o id salvo; com URL vazia devolve `None`; com `'https://example.com'` devolve `None`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar.** Em `views.py` remover `_get_youtube_videos_from_page`, `public_youtube_videos`, `YOUTUBE_FALLBACK_VIDEOS`, `YOUTUBE_VIDEOS_URL`, `YOUTUBE_CACHE_KEY`, `YOUTUBE_CACHE_TTL` e os imports que ficarem sem uso (conferir com `pyflakes`). `home` e `_build_youtube_response` chamam `home_videos(_pinned_video())`; o endpoint passa a `max-age=30`. No template: rótulo conforme `youtube_live`, `data-live` e `data-video-id` no `article.video-featured`, `data-feed-url="{% url 'public_youtube_videos_feed' %}"` na seção `#mensagens`. Apagar os 3 testes antigos de YouTube em `core/tests.py` (incluindo o da raspagem), já cobertos pelos novos.
- [ ] **Step 4: Rodar a suíte inteira e `pyflakes core/views.py`.** Esperado: tudo passa, sem imports soltos novos.
- [ ] **Step 5: Commit** `feat: show live video in the home highlight and drop HTML scraping`.

### Task 5: Atualização automática na home e na página do GitHub Pages

**Files:**
- Create: `static/js/home-live.js`
- Modify: `templates/core/home.html` (incluir o script), `static/css/app.css`, `pages/index.html`, `pages/assets/app.css`
- Test: `core/test_youtube.py`

**Interfaces:**
- Produces: em `home-live.js`, função pura `nextFeaturedState(current: {live: boolean, videoId: string, activated: boolean}, payload: {live: boolean, videos: Array}) -> {replace: boolean}` (troca só se `payload.videos[0]` existir, o par `live`/`videoId` mudou e `activated` for falso); consulta a cada 60 s com a aba visível; ao trocar, reconstrói destaque e pilha com o mesmo HTML da home. Classe CSS `.is-live` no rótulo do destaque.

- [ ] **Step 1: Escrever o teste que falha**, em `core/test_youtube.py`: `test_home_includes_the_live_polling_script` confirma `js/home-live.js` no HTML da home; `test_pages_index_label_follows_the_payload` abre `pages/index.html` e confirma que o texto fixo `TRANSMISSÃO EM DESTAQUE` não existe mais e que há `AO VIVO AGORA` e `EM DESTAQUE`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** `home-live.js` (JavaScript puro, sem dependências; `activated` = o `lite-youtube` do destaque tem a classe `lyt-activated`); rótulo com `.is-live` em vermelho e ponto; em `pages/index.html` o `createVideoCard` usa `payload.live` para escolher `● AO VIVO AGORA` ou `EM DESTAQUE`, e o conteúdo fixo antes do JS passa a ser o vídeo `i7tGR33yy-o` com a lista lateral vazia (sem os vídeos de setembro).
- [ ] **Step 4: Verificar a função pura com Node** (`node -e` importando `nextFeaturedState`): troca quando a live começa, não troca se o visitante já deu play, não troca se nada mudou, não troca com `videos` vazio. Rodar a suíte inteira. Esperado: tudo passa.
- [ ] **Step 5: Commit** `feat: refresh the home video highlight while a live is running`.

### Task 6: Documentação e verificação final

**Files:**
- Modify: `README.md`, `.env.example`

- [ ] **Step 1:** Acrescentar ao README a seção "YouTube ao vivo": o que o destaque faz; as variáveis `YOUTUBE_API_KEY` e `YOUTUBE_CHANNEL_ID`; o passo a passo para criar a chave (projeto no Google Cloud, ativar "YouTube Data API v3", criar chave de API, restringi-la a essa API); a nota de que sem a chave o destaque ao vivo e o filtro de transmissões ficam desativados; como trocar o vídeo fixo em "Conteúdo > Nossa igreja". Acrescentar as duas variáveis, vazias, ao `.env.example`.
- [ ] **Step 2: Verificar.** `DJANGO_DEBUG=True python manage.py test` passa; `check --deploy --fail-level WARNING` com variáveis de produção simuladas passa; `makemigrations --check` sem pendências; `pyflakes` sem novos avisos nos arquivos tocados.
- [ ] **Step 3: Commit** `docs: document YouTube live highlight setup`.
