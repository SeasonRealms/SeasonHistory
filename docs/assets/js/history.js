/* 渐进增强：关闭脚本时，正文、导航、下载和资料折叠面板仍可使用。 */
(function () {
  'use strict';
  var root = document.documentElement;
  var toggle = document.querySelector('[data-theme-toggle]');
  var reset = document.querySelector('[data-theme-reset]');
  var preference = document.querySelector('[data-theme-preference]');
  var system = window.matchMedia('(prefers-color-scheme: dark)');
  var explicit = 'dark';
  try { explicit = localStorage.getItem('sos-theme'); } catch (_) { }
  if (explicit !== 'light' && explicit !== 'dark' && explicit !== 'system') explicit = 'dark';

  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    var dark = theme === 'dark';
    if (toggle) {
      toggle.setAttribute('aria-label', dark ? 'Switch to day theme' : 'Switch to night theme');
      toggle.hidden = false;
    }
    if (preference) preference.textContent = explicit === 'system' ? 'Appearance: device setting' : 'Appearance: your choice';
  }
  if (toggle) toggle.addEventListener('click', function () {
    explicit = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('sos-theme', explicit); } catch (_) { }
    applyTheme(explicit);
  });
  if (reset) {
    reset.hidden = false;
    reset.addEventListener('click', function () {
      explicit = 'system';
      try { localStorage.setItem('sos-theme', explicit); } catch (_) { }
      applyTheme(system.matches ? 'dark' : 'light');
    });
  }
  function watchMedia(query, listener) {
    if (query.addEventListener) query.addEventListener('change', listener);
    else if (query.addListener) query.addListener(listener);
  }
  watchMedia(system, function (event) {
    if (explicit === 'system') applyTheme(event.matches ? 'dark' : 'light');
  });
  window.addEventListener('storage', function (event) {
    if (event.key !== 'sos-theme' && event.key !== null) return;
    explicit = event.newValue === 'dark' || event.newValue === 'light' || event.newValue === 'system' ? event.newValue : 'dark';
    applyTheme(explicit === 'system' ? (system.matches ? 'dark' : 'light') : explicit);
  });
  applyTheme(explicit === 'system' ? (system.matches ? 'dark' : 'light') : explicit);

  function checkDownload(event) {
    // 保留新标签页、另存为等浏览器原生操作；普通点击和键盘激活才作提示。
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey
        || (typeof event.button === 'number' && event.button !== 0)) return;
    var target = this.getAttribute('data-download-platform');
    if (target !== 'windows' && target !== 'android') return;
    var browser = window.navigator || {};
    var ua = browser.userAgent || '';
    if (/MicroMessenger/i.test(ua)) {
      event.preventDefault();
      window.alert('WeChat may block package downloads. Choose Open in browser from the menu, or copy this page address into your system browser, then try again.');
      return;
    }
    // 平台判断只用于提示，不等于兼容性保证；Linux 不等同于 Android。
    var platform = (browser.userAgentData && browser.userAgentData.platform) || browser.platform || '';
    var phone = /Windows Phone|IEMobile/i.test(ua);
    var android = !phone && (/Android/i.test(ua) || /^Android$/i.test(platform));
    var windows = !phone && !android && (/Windows NT/i.test(ua) || /^(Windows|Win32|Win64)$/i.test(platform));
    var matches = target === 'windows' ? windows : android;
    var message = target === 'windows'
      ? 'This legacy ZIP is for Windows PCs. Your browser was not identified as Windows, so it may not run on this device. Save the package anyway?'
      : 'This legacy APK is for Android devices, not iPhone or iPad. Your browser was not identified as Android. Save the package anyway?';
    if (!matches && !window.confirm(message)) event.preventDefault();
  }
  var downloads = document.querySelectorAll('a[data-download-platform]');
  for (var i = 0; i < downloads.length; i++) downloads[i].addEventListener('click', checkDownload);

  var menu = document.querySelector('[data-menu-toggle]');
  var nav = document.getElementById('site-navigation');
  function closeMenu(restoreFocus) {
    if (!menu || !nav) return;
    nav.classList.remove('is-open');
    menu.setAttribute('aria-expanded', 'false');
    if (restoreFocus) menu.focus();
  }
  if (menu && nav) {
    menu.addEventListener('click', function () {
      var open = menu.getAttribute('aria-expanded') !== 'true';
      menu.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('is-open', open);
    });
    nav.addEventListener('click', function (event) {
      if (event.target.closest('a')) closeMenu(false);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && nav.classList.contains('is-open')) closeMenu(true);
    });
    document.addEventListener('click', function (event) {
      if (!event.target.closest('.header')) closeMenu(false);
    });
    watchMedia(window.matchMedia('(min-width: 821px)'), function () { closeMenu(false); });
    root.classList.add('js');
  }
}());
