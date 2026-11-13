/*
 * Atualiza o destaque de vídeo da home enquanto a página está aberta.
 *
 * A cada 60 s (com a aba visível) consulta o endpoint da própria home. Quando a
 * live começa ou termina, troca o destaque e a pilha lateral. Se o visitante já
 * apertou play no destaque, nada é trocado para não interromper a transmissão.
 */
(function (root) {
  'use strict';

  var POLL_MS = 60000;
  var STACK_SIZE = 3;

  function stackIdsOf(videos) {
    return videos.slice(1, 1 + STACK_SIZE).map(function (video) { return video && video.video_id; });
  }

  function sameList(a, b) {
    return a.length === b.length && a.every(function (value, index) { return value === b[index]; });
  }

  /*
   * Decide o que trocar. `current`: {live, videoId, activated, stackIds} lidos da
   * página; `payload`: resposta do endpoint. Função pura, testada no Node.
   */
  function nextFeaturedState(current, payload) {
    var none = { replaceFeatured: false, replaceStack: false };
    var videos = payload && Array.isArray(payload.videos) ? payload.videos : [];
    if (!videos.length || !videos[0] || !videos[0].video_id) return none;

    var featuredChanged = Boolean(payload.live) !== Boolean(current.live) || videos[0].video_id !== current.videoId;
    var stackChanged = !sameList(stackIdsOf(videos), current.stackIds || []);

    if (featuredChanged && current.activated) return none;
    return { replaceFeatured: featuredChanged, replaceStack: featuredChanged || stackChanged };
  }

  function formatDate(value) {
    if (!value) return '';
    var date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('pt-BR');
  }

  function createPlayer(video) {
    var player = document.createElement('lite-youtube');
    player.setAttribute('videoid', video.video_id);
    player.setAttribute('title', video.title);
    player.setAttribute('playlabel', 'Reproduzir ' + video.title);
    player.setAttribute('params', 'origin=' + location.origin);
    return player;
  }

  function createFeatured(video, live) {
    var article = document.createElement('article');
    article.className = 'video-featured reveal is-visible';
    article.dataset.live = live ? 'true' : 'false';
    article.dataset.videoId = video.video_id;
    var copy = document.createElement('div');
    var label = document.createElement('small');
    var date = live ? '' : formatDate(video.published);
    label.textContent = live ? '● AO VIVO AGORA' : 'EM DESTAQUE' + (date ? ' · ' + date : '');
    if (live) label.className = 'is-live';
    var title = document.createElement('h3');
    title.textContent = video.title;
    var channel = document.createElement('p');
    channel.textContent = video.channel_title || 'Igreja Batista Regular Canaã';
    copy.append(label, title, channel);
    article.append(createPlayer(video), copy);
    return article;
  }

  function createStackItem(video) {
    var article = document.createElement('article');
    article.className = 'reveal is-visible';
    var title = document.createElement('h3');
    title.textContent = video.title;
    var channel = document.createElement('p');
    channel.textContent = video.channel_title || 'Igreja Batista Regular Canaã';
    article.append(createPlayer(video), title, channel);
    var date = formatDate(video.published);
    if (date) {
      var published = document.createElement('small');
      published.textContent = date;
      article.append(published);
    }
    return article;
  }

  /*
   * Lê o estado atual da seção de vídeos. `activated` vale para qualquer player
   * em reprodução (destaque ou pilha): trocar o DOM interromperia quem assiste.
   */
  function readCurrent(section) {
    var featured = section.querySelector('.video-featured');
    if (!featured) return null;
    return {
      live: featured.dataset.live === 'true',
      videoId: featured.dataset.videoId,
      activated: Boolean(section.querySelector('lite-youtube.lyt-activated')),
      stackIds: Array.prototype.map.call(section.querySelectorAll('.video-list lite-youtube'), function (item) {
        return item.getAttribute('videoid');
      })
    };
  }

  function start() {
    var section = document.querySelector('#mensagens[data-feed-url]');
    if (!section || !root.fetch) return;

    function apply(payload) {
      var current = readCurrent(section);
      if (!current) return;
      var next = nextFeaturedState(current, payload);
      if (next.replaceFeatured) {
        section.querySelector('.video-featured').replaceWith(createFeatured(payload.videos[0], Boolean(payload.live)));
      }
      if (next.replaceStack) {
        var list = section.querySelector('.video-list');
        if (list) list.replaceChildren.apply(list, payload.videos.slice(1, 1 + STACK_SIZE).map(createStackItem));
      }
    }

    function check() {
      if (document.hidden) return;
      root.fetch(section.dataset.feedUrl, { headers: { Accept: 'application/json' }, cache: 'no-store' })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (payload) { if (payload) apply(payload); })
        .catch(function () { /* sem rede: mantém o que está na tela */ });
    }

    root.setInterval(check, POLL_MS);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) check(); });
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { nextFeaturedState: nextFeaturedState, readCurrent: readCurrent };
  } else if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }
})(typeof window !== 'undefined' ? window : globalThis);
