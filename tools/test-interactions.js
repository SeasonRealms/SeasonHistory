/* Windows 自带 JScript 执行真实站点脚本，模拟 DOM / 媒体查询 / 存储。
   仅验证状态转换，不声称覆盖浏览器排版、可访问性树或视觉效果。
   运行：cscript //nologo //E:JScript tools/test-interactions.js */
(function () {
  var fso = new ActiveXObject('Scripting.FileSystemObject');
  var rootPath = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName));
  function readSource(name) {
    var stream = new ActiveXObject('ADODB.Stream');
    stream.Type = 2;
    stream.Charset = 'utf-8';
    stream.Open();
    stream.LoadFromFile(fso.BuildPath(rootPath, 'docs\\assets\\js\\' + name));
    var text = stream.ReadText();
    stream.Close();
    return text;
  }
  var earlySource = readSource('theme.js');
  var mainSource = readSource('history.js');
  var carouselSource = readSource('carousel.js');
  var redirectSource = readSource('redirect.js');
  var count = 0;
  function equal(actual, expected, label) {
    count++;
    if (actual !== expected) throw new Error(label + ': expected ' + expected + ', got ' + actual);
  }
  function EventTarget() { this.listeners = {}; }
  EventTarget.prototype.addEventListener = function (name, listener) {
    if (!this.listeners[name]) this.listeners[name] = [];
    this.listeners[name].push(listener);
  };
  EventTarget.prototype.emit = function (name, event) {
    var listeners = this.listeners[name] || [];
    event = event || {};
    if (!event.target) event.target = this;
    for (var i = 0; i < listeners.length; i++) listeners[i].call(this, event);
  };
  function Classes() { this.values = {}; }
  Classes.prototype.add = function (name) { this.values[name] = true; };
  Classes.prototype.remove = function (name) { this.values[name] = false; };
  Classes.prototype.contains = function (name) { return !!this.values[name]; };
  Classes.prototype.toggle = function (name, enabled) { this.values[name] = enabled; };
  function Element() {
    this.listeners = {};
    this.attrs = {};
    this.classList = new Classes();
    this.hidden = true;
    this.textContent = '';
    this.children = {};
    this.focused = false;
    this.tagName = 'div';
    this.parentNode = null;
    this.style = {};
    this.offsetWidth = 1200;
  }
  Element.prototype = new EventTarget();
  Element.prototype.setAttribute = function (name, value) { this.attrs[name] = value; };
  Element.prototype.getAttribute = function (name) { return name in this.attrs ? this.attrs[name] : null; };
  Element.prototype.removeAttribute = function (name) { delete this.attrs[name]; };
  Element.prototype.querySelector = function (name) { return this.children[name] || null; };
  Element.prototype.querySelectorAll = function (name) { return this.children[name] || []; };
  Element.prototype.contains = function (target) {
    for (var node = target; node; node = node.parentNode) if (node === this) return true;
    return false;
  };
  Element.prototype.closest = function (selector) {
    var tags = selector.replace(/\s/g, '').split(',');
    for (var node = this; node; node = node.parentNode) {
      for (var i = 0; i < tags.length; i++) if (node.tagName === tags[i]) return node;
    }
    return null;
  };
  Element.prototype.focus = function () {
    this.focused = true;
    if (this.ownerDocument) {
      this.ownerDocument.activeElement = this;
      if (this.focusRegion) this.focusRegion.emit('focusin', { target: this });
    }
  };
  function Environment(saved, dark, blocked, oldMedia, withoutMenu) {
    var self = this;
    this.root = new Element();
    this.toggle = new Element();
    this.reset = new Element();
    this.preference = new Element();
    this.menu = new Element();
    this.nav = new Element();
    this.menu.setAttribute('aria-expanded', 'false');
    this.saved = saved;
    this.system = new EventTarget();
    this.system.matches = dark;
    this.desktop = new EventTarget();
    this.desktop.matches = false;
    if (oldMedia) {
      this.system.addEventListener = null;
      this.desktop.addEventListener = null;
      this.system.addListener = this.desktop.addListener = function (listener) {
        EventTarget.prototype.addEventListener.call(this, 'change', listener);
      };
    }
    this.window = new EventTarget();
    this.window.matchMedia = function (query) {
      return query === '(prefers-color-scheme: dark)' ? self.system : self.desktop;
    };
    this.document = new EventTarget();
    this.document.documentElement = this.root;
    this.document.querySelectorAll = function (query) {
      return query === 'a[data-download-platform]' ? (self.downloads || []) : [];
    };
    this.document.getElementById = function () { return withoutMenu ? null : self.nav; };
    this.document.querySelector = function (query) {
      if (query === '[data-theme-toggle]') return self.toggle;
      if (query === '[data-theme-reset]') return self.reset;
      if (query === '[data-theme-preference]') return self.preference;
      if (query === '[data-menu-toggle]') return withoutMenu ? null : self.menu;
      return null;
    };
    this.storage = {
      getItem: function () { if (blocked) throw new Error('Storage blocked'); return self.saved; },
      setItem: function (key, value) { if (blocked) throw new Error('Storage blocked'); self.saved = value; },
      removeItem: function () { if (blocked) throw new Error('Storage blocked'); self.saved = null; }
    };
  }
  Environment.prototype.run = function (source) {
    new Function('document', 'window', 'localStorage', source)(this.document, this.window, this.storage);
  };
  Environment.prototype.start = function () { this.run(earlySource); this.run(mainSource); };
  Environment.prototype.theme = function () { return this.root.getAttribute('data-theme'); };
  Environment.prototype.systemChange = function (dark) { this.system.matches = dark; this.system.emit('change', { matches: dark }); };

  var deviceDay = new Environment(null, false, false, false, false);
  deviceDay.run(earlySource);
  equal(deviceDay.theme(), 'dark', '日间系统首次访问也默认黑夜');
  deviceDay.run(mainSource);
  equal(deviceDay.theme(), 'dark', '交互脚本不覆盖默认黑夜');
  equal(deviceDay.preference.textContent, 'Appearance: your choice', '默认固定主题文案');
  equal(deviceDay.reset.hidden, false, '默认保留跟随系统按钮');
  equal(deviceDay.saved, null, '初始化不写入用户偏好');
  deviceDay.systemChange(true);
  deviceDay.systemChange(false);
  equal(deviceDay.theme(), 'dark', '默认不随系统变化');
  deviceDay.reset.emit('click');
  equal(deviceDay.theme(), 'light', '点击后立即采用日间系统');
  equal(deviceDay.saved, 'system', '显式保存跟随系统');
  var systemPage = new Environment(deviceDay.saved, false, false, false, false);
  systemPage.run(earlySource);
  equal(systemPage.theme(), 'light', '刷新首帧保留跟随系统');
  systemPage.run(mainSource);
  equal(systemPage.theme(), 'light', '跨页继续跟随系统');
  systemPage.systemChange(true);
  equal(systemPage.theme(), 'dark', '跟随系统响应夜间变化');
  systemPage.toggle.emit('click');
  equal(systemPage.saved, 'light', '手动切换退出跟随系统');
  systemPage.systemChange(true);
  equal(systemPage.theme(), 'light', '手动主题优先于系统');
  var deviceNight = new Environment(null, true, false, false, false);
  deviceNight.run(earlySource);
  equal(deviceNight.theme(), 'dark', 'Initial device night');
  var invalid = new Environment('invalid-theme', false, false, false, false);
  invalid.run(earlySource);
  equal(invalid.theme(), 'dark', '无效偏好首帧回退黑夜');
  invalid.run(mainSource);
  equal(invalid.theme(), 'dark', '无效偏好交互回退黑夜');
  var stored = new Environment('light', true, false, false, false);
  stored.run(earlySource);
  equal(stored.theme(), 'light', '已有日间偏好首帧继续生效');
  stored.run(mainSource);
  equal(stored.theme(), 'light', 'Stored choice wins over system');
  equal(stored.toggle.hidden, false, 'Theme control enabled');
  equal(stored.reset.hidden, false, 'Reset control enabled');
  equal(stored.toggle.getAttribute('aria-label'), 'Switch to night theme', 'Day action label');
  stored.systemChange(true);
  equal(stored.theme(), 'light', 'Explicit preference ignores system change');
  stored.toggle.emit('click');
  equal(stored.theme(), 'dark', 'Switch to night');
  equal(stored.saved, 'dark', 'Night persisted');
  equal(stored.toggle.getAttribute('aria-label'), 'Switch to day theme', 'Night action label');
  equal(stored.toggle.textContent, '', 'Image-only button has no visible label');
  var nextPage = new Environment(stored.saved, false, false, false, false);
  nextPage.start();
  equal(nextPage.theme(), 'dark', 'Preference retained across pages');
  stored.reset.emit('click');
  equal(stored.saved, 'system', '跟随系统选择持久化');
  equal(stored.theme(), 'dark', 'Reset follows device');
  stored.systemChange(false);
  equal(stored.theme(), 'light', 'System changes after reset');
  equal(stored.preference.textContent, 'Appearance: device setting', 'Device setting label');

  var denied = new Environment(null, false, true, false, false);
  denied.run(earlySource);
  equal(denied.theme(), 'dark', '存储不可用时首帧默认黑夜');
  denied.run(mainSource);
  equal(denied.theme(), 'dark', '存储不可用时仍默认黑夜');
  denied.toggle.emit('click');
  equal(denied.theme(), 'light', 'Blocked storage permits local toggle');
  denied.systemChange(true);
  equal(denied.theme(), 'light', 'In-memory preference remains explicit');
  denied.reset.emit('click');
  equal(denied.theme(), 'dark', 'Blocked storage permits reset');
  denied.systemChange(false);
  equal(denied.theme(), 'light', '存储不可用时仍可在当前页跟随系统');
  equal(denied.root.classList.contains('js'), true, 'Blocked storage does not prevent navigation');

  stored.window.emit('storage', { key: 'unrelated', newValue: 'dark' });
  equal(stored.theme(), 'light', 'Unrelated storage changes ignored');
  stored.window.emit('storage', { key: 'sos-theme', newValue: 'dark' });
  equal(stored.theme(), 'dark', 'Cross-tab preference applied');
  stored.window.emit('storage', { key: 'sos-theme', newValue: null });
  equal(stored.theme(), 'dark', '跨标签页删除偏好恢复默认黑夜');
  stored.window.emit('storage', { key: 'sos-theme', newValue: 'system' });
  equal(stored.theme(), 'light', '跨标签页采用跟随系统');
  equal(stored.preference.textContent, 'Appearance: device setting', '跨标签页更新系统偏好文案');
  stored.systemChange(true);
  equal(stored.theme(), 'dark', '跨标签页系统模式响应变化');
  stored.systemChange(false);
  stored.window.emit('storage', { key: null, newValue: null });
  equal(stored.theme(), 'dark', '清空存储恢复默认黑夜');
  stored.systemChange(false);
  equal(stored.theme(), 'dark', '清空后不再跟随系统');
  stored.window.emit('storage', { key: 'sos-theme', newValue: 'invalid-theme' });
  equal(stored.theme(), 'dark', '跨标签页无效偏好回退黑夜');

  equal(stored.menu.getAttribute('aria-expanded'), 'false', 'Menu initially closed');
  stored.menu.emit('click');
  equal(stored.menu.getAttribute('aria-expanded'), 'true', 'Menu expands');
  equal(stored.nav.classList.contains('is-open'), true, 'Menu expansion class');
  stored.document.emit('keydown', { key: 'Escape' });
  equal(stored.menu.getAttribute('aria-expanded'), 'false', 'Escape closes menu');
  equal(stored.menu.focused, true, 'Escape restores focus');
  stored.menu.emit('click');
  stored.document.emit('click', { target: { closest: function () { return null; } } });
  equal(stored.nav.classList.contains('is-open'), false, 'Outside click closes menu');
  stored.menu.emit('click');
  stored.document.emit('click', { target: { closest: function () { return {}; } } });
  equal(stored.nav.classList.contains('is-open'), true, 'Inside header keeps menu open');
  stored.nav.emit('click', { target: { closest: function () { return {}; } } });
  equal(stored.nav.classList.contains('is-open'), false, 'Navigation click closes menu');
  stored.menu.emit('click');
  stored.desktop.emit('change', { matches: true });
  equal(stored.menu.getAttribute('aria-expanded'), 'false', 'Breakpoint change closes menu');
  stored.menu.emit('click');
  stored.menu.emit('click');
  equal(stored.menu.getAttribute('aria-expanded'), 'false', 'Second toggle closes menu');

  var oldBrowser = new Environment(null, false, false, true, false);
  oldBrowser.start();
  oldBrowser.reset.emit('click');
  equal(oldBrowser.theme(), 'light', '旧媒体接口可显式采用日间系统');
  oldBrowser.systemChange(true);
  equal(oldBrowser.theme(), 'dark', 'Legacy media listener follows device');
  oldBrowser.menu.emit('click');
  oldBrowser.desktop.emit('change', {});
  equal(oldBrowser.nav.classList.contains('is-open'), false, 'Legacy breakpoint listener closes menu');
  var errorPage = new Environment(null, false, false, false, true);
  errorPage.start();
  equal(errorPage.theme(), 'dark', '错误页默认黑夜');
  errorPage.reset.emit('click');
  equal(errorPage.theme(), 'light', '错误页支持跟随系统');
  errorPage.systemChange(true);
  errorPage.toggle.emit('click');
  equal(errorPage.theme(), 'light', 'Self-contained error page supports themes without menu');

  function downloadAttempt(browser, target, answer, allowed, mode, options) {
    var env = new Environment(null, false, false, false, true);
    var link = new Element();
    link.setAttribute('data-download-platform', target);
    link.setAttribute('href', 'https://example.test/package.' + (target === 'windows' ? 'zip' : 'apk'));
    var original = link.getAttribute('href');
    env.downloads = [link];
    env.window.navigator = browser;
    env.window.location = { href: 'https://example.test/index.html' };
    var alerts = [], prompts = [];
    env.window.alert = function (message) { alerts.push(message); };
    env.window.confirm = function (message) { prompts.push(message); return answer; };
    env.start();
    equal(alerts.length + prompts.length, 0, 'No download prompt on page load');
    var event = options || {};
    event.defaultPrevented = !!event.defaultPrevented;
    event.preventDefault = function () { this.defaultPrevented = true; };
    link.emit('click', event);
    equal(!event.defaultPrevented, allowed, 'Download default action: ' + target);
    equal(alerts.length, mode === 'wechat' ? 1 : 0, 'WeChat alert count');
    equal(prompts.length, mode === 'mismatch' ? 1 : 0, 'Platform confirmation count');
    equal(link.getAttribute('href'), original, 'Keep real package href');
    equal(env.window.location.href, 'https://example.test/index.html', 'No scripted redirect or automatic download');
    if (alerts.length) equal(alerts[0].indexOf('WeChat') >= 0, true, 'Localized external-browser instruction');
    if (prompts.length) {
      equal(prompts[0].indexOf(target === 'windows' ? 'Windows' : 'Android') >= 0, true, 'Correct platform warning');
      equal(prompts[0].indexOf('legacy') >= 0, true, 'Legacy package warning');
    }
  }
  var platforms = [
    [{ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }, 'windows'],
    [{ userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8)' }, 'android'],
    [{ userAgent: '', userAgentData: { platform: 'Windows' } }, 'windows'],
    [{ userAgent: '', userAgentData: { platform: 'Android' } }, 'android'],
    [{ platform: 'Win32' }, 'windows'],
    [{ userAgent: 'Mozilla/5.0 (X11; Linux x86_64)', platform: 'Linux x86_64' }, ''],
    [{ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X)', platform: 'MacIntel' }, ''],
    [{ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)' }, ''],
    [{ userAgent: 'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)' }, ''],
    [{ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X)', platform: 'MacIntel', maxTouchPoints: 5 }, ''],
    [{ userAgent: 'Windows Phone 10.0; Android 6.0; Windows NT 10.0' }, ''],
    [{}, ''],
    [null, '']
  ];
  var targets = ['windows', 'android'];
  for (var p = 0; p < platforms.length; p++) {
    for (var t = 0; t < targets.length; t++) {
      var matches = targets[t] === platforms[p][1];
      downloadAttempt(platforms[p][0], targets[t], false, matches, matches ? '' : 'mismatch');
      if (!matches) downloadAttempt(platforms[p][0], targets[t], true, true, 'mismatch');
    }
  }
  for (var w = 0; w < 3; w++) {
    var wechat = { userAgent: ['Android 14 MicroMessenger/8.0', 'iPhone micromessenger/8.0', 'Windows NT 10.0 MicroMessenger/4.0'][w] };
    for (var d = 0; d < targets.length; d++) downloadAttempt(wechat, targets[d], true, false, 'wechat');
  }
  var nativeClicks = [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }];
  for (var c = 0; c < nativeClicks.length; c++) downloadAttempt({}, 'windows', false, true, '', nativeClicks[c]);
  downloadAttempt({}, 'windows', false, false, '', { defaultPrevented: true });
  downloadAttempt({ userAgent: 'Windows NT 10.0' }, 'windows', false, true, '', { button: 0 });
  downloadAttempt({ userAgent: 'Android 14' }, 'android', false, true, '', { detail: 0 });
  downloadAttempt({}, 'unknown', false, true, '');
  var noScript = new Element();
  noScript.setAttribute('href', 'https://example.test/package.zip');
  var nativeEvent = { prevented: false, preventDefault: function () { this.prevented = true; } };
  noScript.emit('click', nativeEvent);
  equal(nativeEvent.prevented, false, 'Without script native download remains available');

  function CarouselEnvironment(reduced, legacy, noObserver) {
    var self = this;
    this.document = new EventTarget();
    this.document.hidden = false;
    this.document.activeElement = null;
    this.region = new Element();
    this.document.querySelector = function (query) { return query === '[data-carousel]' ? self.region : null; };
    function element(tag, parent) {
      var node = new Element();
      node.tagName = tag;
      node.parentNode = parent || self.region;
      node.ownerDocument = self.document;
      node.focusRegion = self.region;
      return node;
    }
    this.track = element('div');
    this.viewport = element('div');
    this.controls = element('div');
    this.play = element('button');
    this.previous = element('button');
    this.next = element('button');
    this.status = element('p');
    this.slides = [];
    this.selectors = [];
    var names = ['SanguoSeason', 'Sanguo3D', 'Creators', 'Ming'];
    for (var i = 0; i < 4; i++) {
      var slide = element('article', this.track);
      slide.setAttribute('aria-label', (i + 1) + ' of 4: ' + names[i]);
      slide.children.a = [element('a', slide), element('a', slide)];
      this.slides.push(slide);
      var selector = element('button');
      selector.setAttribute('data-carousel-to', String(i));
      this.selectors.push(selector);
    }
    this.region.children = {
      '[data-carousel-track]': this.track, '[data-carousel-viewport]': this.viewport,
      '[data-carousel-controls]': this.controls, '[data-carousel-play]': this.play,
      '[data-carousel-prev]': this.previous, '[data-carousel-next]': this.next,
      '[data-carousel-status]': this.status, '[data-slide]': this.slides,
      '[data-carousel-to]': this.selectors
    };
    this.motion = new EventTarget();
    this.motion.matches = reduced;
    if (legacy) {
      this.motion.addEventListener = null;
      this.motion.addListener = function (listener) {
        EventTarget.prototype.addEventListener.call(this, 'change', listener);
      };
    }
    this.timers = {};
    this.lastTimer = 0;
    this.window = new EventTarget();
    this.window.matchMedia = function () { return self.motion; };
    this.window.setTimeout = function (callback, delay) {
      self.delay = delay;
      self.timers[++self.lastTimer] = callback;
      return self.lastTimer;
    };
    this.window.clearTimeout = function (id) { delete self.timers[id]; };
    if (!noObserver) this.window.IntersectionObserver = function (callback) {
      self.intersect = callback;
      this.observe = function (target) { self.observed = target; };
    };
  }
  CarouselEnvironment.prototype.run = function () {
    new Function('document', 'window', carouselSource)(this.document, this.window);
  };
  CarouselEnvironment.prototype.pending = function () {
    var total = 0;
    for (var id in this.timers) if (this.timers.hasOwnProperty(id)) total++;
    return total;
  };
  CarouselEnvironment.prototype.tick = function () {
    for (var id in this.timers) if (this.timers.hasOwnProperty(id)) {
      var callback = this.timers[id];
      delete this.timers[id];
      callback();
      return;
    }
    throw new Error('No active carousel timer');
  };
  CarouselEnvironment.prototype.swipe = function (dx, dy, target, pointerType, cancel) {
    this.viewport.emit('pointerdown', { pointerType: pointerType || 'touch', pointerId: 7,
      clientX: 200, clientY: 100, target: target || this.viewport });
    if (cancel) this.viewport.emit('pointercancel');
    this.viewport.emit('pointerup', { pointerId: 7, clientX: 200 + dx, clientY: 100 + dy });
  };
  var carousel = new CarouselEnvironment(false, false, false);
  carousel.run();
  equal(carousel.controls.hidden, false, 'Carousel controls enabled');
  equal(carousel.region.classList.contains('carousel-ready'), true, 'Carousel enhanced after setup');
  equal(carousel.track.style.transform, 'translateX(0%)', 'First slide initially visible');
  equal(carousel.pending(), 1, 'One automatic rotation timer');
  equal(carousel.delay, 7000, 'Seven-second reading interval');
  equal(carousel.observed, carousel.region, 'Carousel visibility observed');
  for (var s = 0; s < 4; s++) {
    equal(carousel.slides[s].getAttribute('aria-hidden'), String(s !== 0), 'Slide accessibility ' + s);
    equal(carousel.slides[s].getAttribute('inert'), s === 0 ? null : '', 'Slide inert state ' + s);
    equal(carousel.slides[s].children.a[0].getAttribute('tabindex'), s === 0 ? null : '-1', 'Slide tab order ' + s);
  }
  carousel.tick();
  equal(carousel.track.style.transform, 'translateX(-100%)', 'Automatic next slide');
  equal(carousel.status.textContent, '', 'Automatic rotation does not announce');
  equal(carousel.pending(), 1, 'Automatic timer rescheduled without duplicates');
  carousel.region.emit('mouseenter');
  equal(carousel.pending(), 0, 'Hover suspends rotation');
  carousel.region.emit('mouseleave');
  equal(carousel.pending(), 1, 'Leaving hover resumes rotation');
  carousel.next.focus();
  equal(carousel.pending(), 0, 'Keyboard focus pauses rotation');
  carousel.region.emit('mouseleave');
  equal(carousel.pending(), 0, 'Leaving hover does not undo focus pause');
  carousel.play.emit('click');
  equal(carousel.pending(), 1, 'Explicit play resumes rotation');
  carousel.document.hidden = true;
  carousel.document.emit('visibilitychange');
  equal(carousel.pending(), 0, 'Hidden page stops rotation');
  carousel.document.hidden = false;
  carousel.document.emit('visibilitychange');
  equal(carousel.pending(), 1, 'Visible page resumes rotation');
  carousel.intersect([{ isIntersecting: false }]);
  equal(carousel.pending(), 0, 'Offscreen carousel stops rotation');
  carousel.intersect([{ isIntersecting: true }]);
  equal(carousel.pending(), 1, 'Onscreen carousel resumes rotation');
  carousel.play.emit('pointerdown');
  carousel.play.focus();
  carousel.play.emit('click');
  equal(carousel.pending(), 0, 'Pointer pause survives intervening focus event');
  carousel.play.emit('pointerdown');
  carousel.play.emit('click');
  equal(carousel.pending(), 1, 'Pointer play resumes after pause');
  carousel.next.emit('click');
  equal(carousel.track.style.transform, 'translateX(-200%)', 'Next project control');
  equal(carousel.status.textContent, '3 of 4: Creators', 'Manual change announced');
  equal(carousel.pending(), 0, 'Manual change pauses rotation');
  carousel.selectors[3].emit('click');
  equal(carousel.track.style.transform, 'translateX(-300%)', 'Named project selector');
  equal(carousel.selectors[3].getAttribute('aria-pressed'), 'true', 'Selected project state');
  carousel.next.emit('click');
  equal(carousel.track.style.transform, 'translateX(0%)', 'Next wraps to first slide');
  equal(carousel.track.classList.contains('is-resetting'), false, 'Wrap clears reset state');
  carousel.previous.emit('click');
  equal(carousel.track.style.transform, 'translateX(-300%)', 'Previous wraps to last slide');
  var prevented = false;
  carousel.region.emit('keydown', { key: 'ArrowLeft', target: carousel.previous,
    preventDefault: function () { prevented = true; } });
  equal(carousel.track.style.transform, 'translateX(-200%)', 'Left arrow keyboard control');
  equal(prevented, true, 'Arrow control prevents default scrolling');
  carousel.region.emit('keydown', { key: 'ArrowRight', target: carousel.next, preventDefault: function () {} });
  equal(carousel.track.style.transform, 'translateX(-300%)', 'Right arrow keyboard control');
  carousel.region.emit('keydown', { key: 'ArrowLeft', target: carousel.play });
  equal(carousel.track.style.transform, 'translateX(-300%)', 'Playback control ignores slide arrows');
  carousel.selectors[0].emit('click');
  carousel.slides[0].children.a[0].focus();
  carousel.swipe(-100, 5);
  equal(carousel.track.style.transform, 'translateX(-100%)', 'Touch swipe advances');
  equal(carousel.document.activeElement, carousel.selectors[1], 'Focus leaves slide before it becomes inert');
  equal(carousel.slides[1].children.a[0].getAttribute('tabindex'), null, 'Active slide links restored');
  carousel.swipe(100, 5);
  equal(carousel.track.style.transform, 'translateX(0%)', 'Right swipe returns');
  carousel.swipe(-30, 0);
  equal(carousel.track.style.transform, 'translateX(0%)', 'Small touch movement ignored');
  carousel.swipe(-90, 180);
  equal(carousel.track.style.transform, 'translateX(0%)', 'Vertical gesture keeps page scrolling');
  carousel.swipe(-100, 0, carousel.slides[0].children.a[0]);
  equal(carousel.track.style.transform, 'translateX(0%)', 'Link-origin gesture does not change slide');
  carousel.swipe(-100, 0, null, 'mouse');
  equal(carousel.track.style.transform, 'translateX(0%)', 'Mouse selection is not a touch swipe');
  carousel.swipe(-100, 0, null, 'touch', true);
  equal(carousel.track.style.transform, 'translateX(0%)', 'Cancelled gesture ignored');
  carousel.motion.matches = true;
  carousel.motion.emit('change');
  equal(carousel.play.disabled, true, 'Reduced-motion disables automatic play control');
  equal(carousel.pending(), 0, 'Reduced-motion removes timer');
  carousel.play.emit('click');
  equal(carousel.pending(), 0, 'Reduced-motion cannot accidentally restart rotation');
  carousel.next.emit('click');
  equal(carousel.track.style.transform, 'translateX(-100%)', 'Reduced-motion permits manual navigation');
  carousel.motion.matches = false;
  carousel.motion.emit('change');
  equal(carousel.play.disabled, false, 'Play control restored when preference changes');
  equal(carousel.pending(), 0, 'Preference change does not force restart');
  carousel.play.emit('click');
  equal(carousel.pending(), 1, 'Explicit play after preference change');
  carousel.tick(); carousel.tick(); carousel.tick();
  equal(carousel.track.style.transform, 'translateX(0%)', 'Automatic wrap to first slide');
  var reducedCarousel = new CarouselEnvironment(true, true, true);
  reducedCarousel.run();
  equal(reducedCarousel.pending(), 0, 'Initial reduced-motion is static');
  equal(reducedCarousel.play.textContent, 'Reduced motion', 'Reduced-motion control explanation');
  reducedCarousel.motion.matches = false;
  reducedCarousel.motion.emit('change');
  reducedCarousel.play.emit('click');
  equal(reducedCarousel.pending(), 1, 'Legacy media listener and no visibility observer supported');
  var missingCarousel = new CarouselEnvironment(false, false, false);
  missingCarousel.document.querySelector = function () { return null; };
  missingCarousel.run();
  equal(missingCarousel.pending(), 0, 'Pages without carousel exit safely');
  var incompleteCarousel = new CarouselEnvironment(false, false, false);
  incompleteCarousel.region.children['[data-carousel-track]'] = null;
  incompleteCarousel.run();
  equal(incompleteCarousel.controls.hidden, true, 'Incomplete markup retains readable fallback');

  function redirect(hash, preserve, mappings, noLink) {
    var target = new Element();
    target.setAttribute('href', '../sanguo3d/reading/three-kingdoms/index.html');
    if (preserve) target.setAttribute('data-preserve-fragment', 'true');
    var choices = [];
    for (var key in mappings) if (mappings.hasOwnProperty(key)) {
      var choice = new Element();
      choice.setAttribute('data-old-fragment', key);
      choice.setAttribute('href', mappings[key]);
      choices.push(choice);
    }
    var destination = null;
    var document = { querySelector: function () { return noLink ? null : target; },
      querySelectorAll: function () { return choices; } };
    var window = { location: { hash: hash, search: '?next=https://outside.test/',
      replace: function (value) { destination = value; } } };
    new Function('document', 'window', redirectSource)(document, window);
    return destination;
  }
  var fallback = '../sanguo3d/reading/three-kingdoms/index.html';
  var mapping = { classic: '../sanguoseason/index.html#downloads', 'new-sanguo': '../sanguo3d/index.html#downloads' };
  equal(redirect('', false, mapping), fallback, 'Legacy route default ignores query destination');
  equal(redirect('#classic', false, mapping), mapping.classic, 'Legacy download fragment');
  equal(redirect('#new-sanguo', false, mapping), mapping['new-sanguo'], 'Second legacy download fragment');
  equal(redirect('#%63lassic', false, mapping), mapping.classic, 'Encoded legacy fragment');
  equal(redirect('#unknown', false, mapping), fallback, 'Unknown old fragment uses safe fallback');
  equal(redirect('#%E0%A4%A', false, mapping), fallback, 'Malformed fragment encoding does not break redirect');
  equal(redirect('#history-stories', true, {}), fallback + '#history-stories', 'Reading fragment preserved');
  equal(redirect('#https://outside.test/', true, {}), fallback + '#https://outside.test/', 'Fragment cannot become an external destination');
  equal(redirect('', false, {}, true), null, 'Pages without relocation link exit safely');

  WScript.Echo('PASS: ' + count + ' interaction assertions; real scripts with mocked DOM (no rendering test).');
}());
