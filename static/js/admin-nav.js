/*
 * Painel: menu lateral como gaveta em telas até 1100px e atalho "/" para a busca.
 */
(function () {
  'use strict';
  var body = document.body;
  var button = document.querySelector('.menu-button');
  var sidebar = document.getElementById('admin-sidebar');
  var scrim = document.querySelector('.side-scrim');
  if (!button || !sidebar || !scrim) return;
  var wide = window.matchMedia('(min-width: 1101px)');

  function setOpen(open, returnFocus) {
    body.classList.toggle('nav-open', open);
    scrim.hidden = !open;
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    if (open) {
      var first = sidebar.querySelector('a');
      if (first) first.focus();
    } else if (returnFocus) {
      button.focus();
    }
  }

  button.addEventListener('click', function () { setOpen(!body.classList.contains('nav-open')); });
  scrim.addEventListener('click', function () { setOpen(false); });
  sidebar.addEventListener('click', function (event) {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && body.classList.contains('nav-open')) { setOpen(false, true); return; }
    if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey) {
      var target = event.target;
      var typing = target && (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable);
      var search = document.querySelector('.admin-search input');
      if (!typing && search) { event.preventDefault(); search.focus(); search.select(); }
    }
  });
  var onWide = function (event) { if (event.matches) setOpen(false); };
  if (wide.addEventListener) wide.addEventListener('change', onWide);
  else if (wide.addListener) wide.addListener(onWide);
})();
