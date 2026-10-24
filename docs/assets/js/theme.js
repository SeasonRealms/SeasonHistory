/* 在样式表之前读取偏好，避免页面先亮后暗；存储被禁用时仍可浏览。 */
(function () {
  'use strict';
  var theme = 'dark';
  try {
    var saved = localStorage.getItem('sos-theme');
    if (saved === 'light' || saved === 'dark') theme = saved;
    else if (saved === 'system' && window.matchMedia) {
      theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
  } catch (_) { }
  document.documentElement.setAttribute('data-theme', theme);
}());
