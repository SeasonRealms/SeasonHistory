/* 保留旧书签和下载锚点；目的地址只来自生成器验证过的站内链接。 */
(function () {
  'use strict';
  var link = document.querySelector('[data-redirect-target]');
  if (!link) return;
  var fragment = window.location.hash.slice(1);
  try { fragment = decodeURIComponent(fragment); } catch (_) { }
  var destination = link.getAttribute('href');
  var options = document.querySelectorAll('[data-old-fragment]');
  for (var i = 0; i < options.length; i++) {
    if (options[i].getAttribute('data-old-fragment') === fragment) {
      destination = options[i].getAttribute('href');
      break;
    }
  }
  if (link.getAttribute('data-preserve-fragment') === 'true' && window.location.hash) {
    destination += window.location.hash;
  }
  window.location.replace(destination);
}());
