/*
 * Menu das páginas públicas em telas estreitas (até 1100px).
 * Botão .nav-toggle abre e fecha o painel <nav id="public-menu">.
 * Fecha com Esc, ao tocar num link, ao tocar fora ou ao alargar a janela.
 */
(function () {
  'use strict';
  var header = document.getElementById('public-nav');
  if (!header) return;
  var toggle = header.querySelector('.nav-toggle');
  var menu = document.getElementById('public-menu');
  if (!toggle || !menu) return;
  var wide = window.matchMedia('(min-width: 1101px)');

  function setOpen(open, returnFocus) {
    header.classList.toggle('menu-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    if (!open && returnFocus) toggle.focus();
  }

  toggle.addEventListener('click', function () {
    setOpen(!header.classList.contains('menu-open'));
  });
  menu.addEventListener('click', function (event) {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('click', function (event) {
    if (header.classList.contains('menu-open') && !header.contains(event.target)) setOpen(false);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && header.classList.contains('menu-open')) setOpen(false, true);
  });
  var onWide = function (event) { if (event.matches) setOpen(false); };
  if (wide.addEventListener) wide.addEventListener('change', onWide);
  else if (wide.addListener) wide.addListener(onWide);
})();
