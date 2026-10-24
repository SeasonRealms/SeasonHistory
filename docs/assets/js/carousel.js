/* 首页项目轮播：渐进增强，焦点和手动操作暂停自动播放，尊重减少动态效果偏好。 */
(function () {
  'use strict';
  var region = document.querySelector('[data-carousel]');
  if (!region) return;
  var track = region.querySelector('[data-carousel-track]');
  var viewport = region.querySelector('[data-carousel-viewport]');
  var slides = region.querySelectorAll('[data-slide]');
  var selectors = region.querySelectorAll('[data-carousel-to]');
  var controls = region.querySelector('[data-carousel-controls]');
  var play = region.querySelector('[data-carousel-play]');
  var previous = region.querySelector('[data-carousel-prev]');
  var next = region.querySelector('[data-carousel-next]');
  var status = region.querySelector('[data-carousel-status]');
  if (!track || !viewport || slides.length < 2 || selectors.length !== slides.length || !controls || !play || !previous || !next || !status) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var index = 0;
  var paused = reduced.matches;
  var hovered = false;
  var visible = true;
  var timer = null;
  var pointer = null;
  var playIntent = null;
  var interval = 7000;

  function stopTimer() {
    if (timer !== null) window.clearTimeout(timer);
    timer = null;
  }
  function schedule() {
    stopTimer();
    if (!paused && !reduced.matches && !hovered && visible && !document.hidden) {
      timer = window.setTimeout(function () { show(index + 1, false); }, interval);
    }
    play.disabled = reduced.matches;
    play.textContent = reduced.matches ? 'Reduced motion' : (paused ? 'Play slideshow' : 'Pause slideshow');
    play.setAttribute('aria-label', reduced.matches ? 'Automatic rotation disabled: reduced motion preference' :
      (paused ? 'Start automatic slide rotation' : 'Pause automatic slide rotation'));
  }
  function pause() {
    paused = true;
    schedule();
  }
  function show(target, manual) {
    var wrapped = target < 0 || target >= slides.length;
    var previousIndex = index;
    index = (target + slides.length) % slides.length;
    if (manual) paused = true;
    if (index !== previousIndex && slides[previousIndex].contains(document.activeElement)) {
      selectors[index].focus({ preventScroll: true });
    }
    // 首尾回绕不横穿中间三页；一般切换保留左右滑动。
    if (wrapped) track.classList.add('is-resetting');
    track.style.transform = 'translateX(' + (-index * 100) + '%)';
    if (wrapped) {
      void track.offsetWidth;
      track.classList.remove('is-resetting');
    }
    for (var i = 0; i < slides.length; i++) {
      var active = i === index;
      slides[i].classList.toggle('is-active', active);
      slides[i].setAttribute('aria-hidden', String(!active));
      if (active) slides[i].removeAttribute('inert');
      else slides[i].setAttribute('inert', '');
      // 不支持 inert 的浏览器仍不会把焦点送到画面外。
      var links = slides[i].querySelectorAll('a');
      for (var j = 0; j < links.length; j++) {
        if (active) links[j].removeAttribute('tabindex');
        else links[j].setAttribute('tabindex', '-1');
      }
      selectors[i].setAttribute('aria-pressed', String(active));
    }
    if (manual) status.textContent = slides[index].getAttribute('aria-label');
    schedule();
  }
  previous.addEventListener('click', function () { show(index - 1, true); });
  next.addEventListener('click', function () { show(index + 1, true); });
  for (var i = 0; i < selectors.length; i++) {
    selectors[i].addEventListener('click', function () {
      show(Number(this.getAttribute('data-carousel-to')), true);
    });
  }
  play.addEventListener('pointerdown', function () { playIntent = !paused; });
  play.addEventListener('pointercancel', function () { playIntent = null; });
  play.addEventListener('blur', function () { playIntent = null; });
  play.addEventListener('click', function () {
    if (reduced.matches) return;
    paused = playIntent === null ? !paused : playIntent;
    playIntent = null;
    schedule();
  });
  region.addEventListener('mouseenter', function () { hovered = true; schedule(); });
  region.addEventListener('mouseleave', function () { hovered = false; schedule(); });
  region.addEventListener('focusin', pause);
  region.addEventListener('keydown', function (event) {
    if (event.target === play || !event.target.closest('button')) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      show(index + (event.key === 'ArrowLeft' ? -1 : 1), true);
    }
  });
  viewport.addEventListener('pointerdown', function (event) {
    pointer = null;
    // 从链接或按钮起手时保留原操作，避免滑动后误触项目跳转。
    if (event.pointerType === 'touch' && event.isPrimary !== false &&
        !event.target.closest('a, button, input, select, textarea')) {
      pointer = { x: event.clientX, y: event.clientY, id: event.pointerId };
    }
  });
  viewport.addEventListener('pointerup', function (event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    var dx = event.clientX - pointer.x;
    var dy = event.clientY - pointer.y;
    pointer = null;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5) show(index + (dx < 0 ? 1 : -1), true);
  });
  viewport.addEventListener('pointercancel', function () { pointer = null; });
  document.addEventListener('visibilitychange', schedule);
  function motionChanged() {
    if (reduced.matches) paused = true;
    schedule();
  }
  if (reduced.addEventListener) reduced.addEventListener('change', motionChanged);
  else if (reduced.addListener) reduced.addListener(motionChanged);
  if (window.IntersectionObserver) {
    var observer = new window.IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
      schedule();
    });
    observer.observe(region);
  }
  // 在所有监听器就绪后隐藏非当前页，脚本未加载时四页与链接均可访问。
  region.classList.add('carousel-ready');
  controls.hidden = false;
  show(0, false);
}());
