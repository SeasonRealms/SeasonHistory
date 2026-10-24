"""静态结构、资源、子路径、生成器与配色回归检查；不代替浏览器视觉验收。

运行：python -B tools/check_site.py
交互逻辑另用 tools/test-interactions.js 检查，无需安装 Node。
"""
from base64 import b64decode
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import PurePosixPath
import re
import unittest
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from build_site import (OUTPUT, SOURCE, NAVIGATION, PROJECT_ORDER, build_documents,
                        download_rows, normalize_base, render, split_project)

VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = set()
        self.errors = []
        self.stack = []
        self.feed(text)
        self.close()
        if self.stack:
            self.errors.append(f"未闭合标签：{self.stack}")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if identifier := attrs.get("id"):
            if identifier in self.ids:
                self.errors.append(f"重复 ID：{identifier}")
            self.ids.add(identifier)
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"闭合次序错误：{tag}")
        else:
            self.stack.pop()

    def select(self, tag):
        return [attrs for name, attrs in self.tags if name == tag]


def luminance(value):
    rgb = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * w
               for v, w in zip(rgb, (.2126, .7152, .0722)))


def contrast(a, b):
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)


class SiteChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((SOURCE / "site.json").read_text(encoding="utf-8"))
        cls.expected = build_documents(cls.config)
        cls.pages = {name: Page((OUTPUT / name).read_text(encoding="utf-8"))
                     for name in cls.expected if name.endswith(".html")}
        cls.css = (OUTPUT / "assets/css/history.css").read_text(encoding="utf-8")

    def test_generated_outputs_current(self):
        self.assertEqual({p.relative_to(OUTPUT).as_posix() for p in OUTPUT.rglob("*.html")
                          if not p.is_relative_to(OUTPUT / "zh")}, set(self.pages))
        for name, content in self.expected.items():
            with self.subTest(file=name):
                self.assertEqual((OUTPUT / name).read_text(encoding="utf-8"), content)
                self.assertNotIn("{{", content)

    def test_html_structure_metadata_and_accessibility(self):
        for name, page in self.pages.items():
            with self.subTest(file=name):
                self.assertEqual(page.errors, [])
                self.assertEqual(len(page.select("h1")), 1)
                self.assertEqual(len(page.select("main")), 1)
                self.assertEqual(len(page.select("title")), 1)
                self.assertEqual(page.select("html")[0]["lang"], "en")
                self.assertEqual(len([m for m in page.select("meta") if m.get("name") == "description"]), 1)
                for tag, attrs in page.tags:
                    for reference in (attrs.get("aria-controls", "") + " " + attrs.get("aria-labelledby", "")).split():
                        self.assertIn(reference, page.ids)
                    if tag == "nav":
                        self.assertTrue(attrs.get("aria-label"))
                    if tag == "button":
                        self.assertEqual(attrs.get("type"), "button")
                    if tag == "img":
                        self.assertIn("alt", attrs)
                        self.assertGreater(int(attrs["width"]), 0)
                        self.assertGreater(int(attrs["height"]), 0)

    def test_links_and_fragments_at_root_and_repository_path(self):
        for prefix in ("/", "/History/", "/nested/repository/"):
            base = "https://example.test" + prefix
            for name, page in self.pages.items():
                for tag, attrs in page.tags:
                    for attribute in ("href", "src", "poster"):
                        if attribute not in attrs:
                            continue
                        value = attrs[attribute]
                        with self.subTest(prefix=prefix, page=name, link=value[:120]):
                            self.assertTrue(value)
                            self.assertNotEqual(value, "#", "链接不得使用空占位地址")
                            self.assertNotIn("\\", value)
                            parsed = urlsplit(value)
                            if parsed.scheme == "data":
                                self.assertEqual(attribute, "src")
                                self.assert_inline_theme_icon(name, tag, attrs)
                                continue
                            if parsed.scheme or parsed.netloc:
                                self.assertEqual(parsed.scheme, "https")
                                self.assertTrue(tag == "a" or attrs.get("rel") == "canonical")
                                continue
                            self.assertFalse(value.startswith("/"), "站内地址不能绑定域名根路径")
                            resolved = urlsplit(urljoin(base + name, value))
                            self.assertTrue(resolved.path.startswith(prefix))
                            target = unquote(resolved.path[len(prefix):])
                            self.assertTrue((OUTPUT / target).is_file(), target)
                            if resolved.fragment and target in self.pages:
                                self.assertIn(unquote(resolved.fragment), self.pages[target].ids)

    def test_navigation_and_progressive_enhancement(self):
        self.assertEqual([label for _, label in NAVIGATION],
                         ["Home", "SanguoSeason", "Sanguo3D", "Creators", "Ming"])
        for name, text in self.expected.items():
            if not name.endswith(".html"):
                continue
            self.assertIn("Season Games", text)
            self.assertNotIn("Season Of Sanguo", text)
            if name != "404.html":
                navigation = re.search(r'<nav[^>]+id="site-navigation"[^>]*>(.*?)</nav>', text, re.S).group(1)
                self.assertEqual(re.findall(r'<a[^>]*>([^<]+)</a>', navigation), [label for _, label in NAVIGATION])
        for item in self.config["pages"]:
            page = self.pages[item["path"]]
            for link in page.select("a"):
                path = urlsplit(urljoin("https://example.test/" + item["path"], link["href"])).path.lstrip("/")
                self.assertNotIn(path, self.config["redirects"], "新内容不应继续指向兼容页")
            nav_links = [a for a in page.select("a") if a.get("aria-current")]
            expected = "page" if item["key"] == item["nav"] else "location"
            self.assertEqual(len(nav_links), 1 if item["nav"] else 0)
            if nav_links:
                self.assertEqual(nav_links[0]["aria-current"], expected)
            scripts = page.select("script")
            self.assertTrue(scripts[0]["src"].endswith("theme.js"))
            self.assertIn("defer", scripts[1])
            self.assertNotIn("hidden", next(n for n in page.select("nav") if n.get("id") == "site-navigation"))
            self.assertEqual(len([b for b in page.select("button") if "data-theme-toggle" in b]), 1)
        self.assertIn(".js .nav-links:not(.is-open)", self.css)
        self.assertIn("prefers-reduced-motion: no-preference", self.css)
        for width in (820, 560, 380):
            self.assertIn(f"max-width: {width}px", self.css)
        self.assertNotIn("autoplay", "".join(self.expected.values()))

    def test_family_website_links(self):
        destinations = {"SeasonEngine": "https://seasonrealms.github.io/SeasonEngine",
                        "SeasonStudio": "https://seasonrealms.github.io/SeasonStudio"}
        for name in self.pages:
            for text in (self.expected[name], (OUTPUT / name).read_text(encoding="utf-8")):
                with self.subTest(page=name):
                    family = [a["href"] for a in Page(text).select("a")
                              if "family-link" in a.get("class", "").split()]
                    self.assertEqual(family, [] if name == "404.html" else list(destinations.values()))
                    links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', text)
                    count = 0 if name == "404.html" else 2 if name == "about/index.html" else 1
                    for label, url in destinations.items():
                        self.assertEqual([href for href, title in links if title == label], [url] * count)

    def test_css_resources_and_image_manifest(self):
        for resource in re.findall(r'url\([\'"]?([^\)\'\"]+)', self.css):
            self.assertFalse(urlsplit(resource).scheme)
            target = (OUTPUT / "assets/css" / resource).resolve()
            self.assertTrue(target.is_relative_to(OUTPUT))
            self.assertTrue(target.is_file(), resource)
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        self.assertNotIn("@import", self.css)
        manifest = json.loads((OUTPUT / "assets/img/sources.json").read_text(encoding="utf-8"))
        images = {image["file"]: image for image in manifest}
        self.assertEqual(len(images), 18)
        for image in manifest:
            path = OUTPUT / "assets/img" / image["file"]
            self.assertEqual(path.stat().st_size, image["bytes"])
            if path.suffix == ".svg":
                svg = ET.fromstring(path.read_text(encoding="utf-8"))
                self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertEqual([int(v) for v in svg.attrib["viewBox"].split()], [0, 0, image["width"], image["height"]])
                for node in svg.iter():
                    if "d" in node.attrib:
                        self.assertRegex(node.attrib["d"], r"^[MmZzLlHhVvCcSsQqTtAaEe0-9+.,\s-]+$")
        for page in self.pages.values():
            for image in page.select("img"):
                if "theme-icon" in image.get("class", "").split():
                    self.assertEqual((image["width"], image["height"]), ("26", "26"))
                    continue
                source = images[PurePosixPath(image["src"]).name]
                self.assertAlmostEqual(int(image["width"]) / int(image["height"]),
                                       source["width"] / source["height"], places=2)

    def assert_inline_theme_icon(self, name, tag, attrs):
        self.assertEqual((name, tag), ("404.html", "img"))
        self.assertIn("theme-icon", attrs.get("class", "").split())
        source = attrs["src"]
        self.assertTrue(source.startswith("data:image/png;base64,"))
        icon = "Sun.png" if "theme-icon-day" in attrs["class"].split() else "Moon.png"
        self.assertEqual(b64decode(source.split(",", 1)[1], validate=True),
                         (OUTPUT / "assets/img" / icon).read_bytes())

    def test_default_dark_and_system_control(self):
        for name in self.pages:
            for text in (self.expected[name], (OUTPUT / name).read_text(encoding="utf-8")):
                with self.subTest(page=name):
                    page = Page(text)
                    self.assertEqual(page.select("html")[0]["data-theme"], "dark")
                    resets = [button for button in page.select("button") if "data-theme-reset" in button]
                    self.assertEqual(len(resets), 1)
                    self.assertRegex(text, r'<button[^>]*data-theme-reset[^>]*>Use device setting</button>')
                    if name == "404.html":
                        scripts = re.findall(r'<script>(.*?)</script>', text, re.S)
                        self.assertEqual(len(scripts), 2)
                        for inline, script in zip(scripts, ("theme.js", "history.js")):
                            self.assertEqual(inline.strip(), (OUTPUT / "assets/js" / script).read_text(encoding="utf-8").strip())

    def test_top_right_image_only_theme_button(self):
        for name, page in self.pages.items():
            with self.subTest(page=name):
                buttons = [a for a in page.select("button") if "data-theme-toggle" in a]
                self.assertEqual(len(buttons), 1)
                self.assertEqual(buttons[0]["class"], "theme-toggle")
                self.assertEqual(buttons[0]["aria-label"], "Switch to day theme")
                text = self.expected[name]
                button = re.search(r'<button[^>]*data-theme-toggle[^>]*>(.*?)</button>', text, re.S)
                self.assertEqual(re.sub(r"<[^>]+>", "", button.group(1)).strip(), "")
                self.assertNotIn("theme-label", text)
                self.assertLess(text.index('class="utility"'), button.start())
                self.assertLess(button.end(), text.index('<main'))
                if name != "404.html":
                    self.assertLess(button.end(), text.index('<header class="header">'))
                icons = [a for a in page.select("img") if "theme-icon" in a.get("class", "").split()]
                self.assertEqual(len(icons), 2)
                for icon, asset, variant in zip(icons, ("Sun.png", "Moon.png"), ("day", "night")):
                    self.assertEqual(icon["class"], "theme-icon theme-icon-" + variant)
                    self.assertEqual((icon["width"], icon["height"]), ("26", "26"))
                    self.assertEqual(icon["alt"], "")
                    self.assertEqual(icon["aria-hidden"], "true")
                    if name == "404.html":
                        self.assert_inline_theme_icon(name, "img", icon)
                    else:
                        self.assertTrue(icon["src"].endswith("assets/img/" + asset))
        error_css = re.search(r"<style>(.*?)</style>", self.expected["404.html"], re.S).group(1)
        for css in (self.css, error_css):
            block = re.search(r"\.theme-toggle\s*\{([^}]+)", css).group(1)
            for property_name, value in (("width", "26px"), ("height", "26px"), ("padding", "0"), ("border", "0")):
                self.assertRegex(block, r"\b" + property_name + r":\s*" + value + ";")
            bar = re.search(r"\.utility \.wrap\s*\{([^}]+)", css).group(1)
            for declaration in ("width: 100%;", "max-width: 1160px;", "padding-inline: 20px;", "height: 36px;"):
                self.assertIn(declaration, bar)
            self.assertIn('.theme-icon-night { display: none; }', css)
            self.assertIn('[data-theme="dark"] .theme-icon-day { display: none; }', css)
            self.assertIn('[data-theme="dark"] .theme-icon-night { display: block; }', css)
            self.assertEqual(len(re.findall(r"\.theme-toggle\s*\{", css)), 1,
                             "窄屏不可覆盖按钮尺寸")

    def test_language_links_before_theme_button(self):
        language = ('<span class="language"><a href="https://seasonrealms.github.io/SeasonHistory" lang="en">EN</a> '
                    '<span aria-hidden="true">/</span> <a href="https://seasont.com" lang="zh-CN">中文</a></span>')
        for name, page in self.pages.items():
            with self.subTest(page=name):
                text = self.expected[name]
                self.assertEqual(text.count(language), 1)
                self.assertEqual(text.count('class="language"'), 1)
                self.assertEqual((OUTPUT / name).read_text(encoding="utf-8").count(language), 1)
                self.assertFalse([a for a in page.select("a") if a.get("href") == "#"])
                self.assertLess(text.index('class="utility"'), text.index(language))
                self.assertRegex(text, re.escape(language) + r'\s*<button class="theme-toggle"')
                self.assertNotIn('<details class="language"', text)
                self.assertNotIn('Language information', text)
                css = re.search(r"<style>(.*?)</style>", text, re.S).group(1) if name == "404.html" else self.css
                self.assertNotIn('.language summary', css)
                self.assertNotIn('.language p', css)
                self.assertIn('white-space: nowrap;', re.search(r'\.language\s*\{([^}]+)', css).group(1))

    def test_brand_subtitle_closing_and_compact_footer(self):
        self.assertEqual(self.config["name"], "Season Games")
        introduction = ["Choose a world. Read its stories, and watch it grow.",
                        "Pasts to discover, new worlds for you to build.",
                        "Mountains, cities, and the everyday lives between."]
        verse = "Spring brings us together in the hills; wine and laughter brighten the autumn moon."
        ending = "Who can say what lies beyond sea and sky? In time, a brighter world will come."
        for name in self.pages:
            with self.subTest(page=name):
                text = self.expected[name]
                self.assertNotIn("Season History Games", text)
                self.assertIn("Season Games", re.search(r"<title>(.*?)</title>", text).group(1))
                if name == "404.html":
                    continue
                self.assertIn('<span class="brand-name">Season Games</span><span class="brand-note">Heroes’ lives, retold through strategy.</span>', text)
                closing = text.split('<div class="closing">', 1)[1].split('<footer class="footer">', 1)[0]
                self.assertEqual(re.findall(r"<p>(.*?)</p>", closing), introduction)
                footer = re.search(r'<footer class="footer">.*?</footer>', text, re.S).group(0)
                self.assertRegex(footer, r'<div class="footer-main">\s*<p class="footer-verse">' + re.escape(verse)
                                 + r'</p>\s*<nav class="footer-links"')
                self.assertRegex(footer, r'<div class="footer-bottom">\s*<span>' + re.escape(ending) + r'</span>')
                self.assertNotIn("Season Games", footer)
                self.assertNotIn('class="footer-title"', text)
                for line in introduction + [verse, ending]:
                    self.assertEqual(text.count(line), 1)
                self.assertEqual([a.get("href") for a in Page(footer).select("a")],
                                 ["../" * (len(PurePosixPath(name).parts) - 1) + target for target in
                                  ("about/index.html", "about/index.html#credits", "about/index.html#privacy", "index.html#zhsan")])
        for selector, declarations in {
            ".footer": ("padding-block: 20px 16px;", "font-size: .8rem;"),
            ".footer-main": ("display: flex;", "align-items: center;", "padding-bottom: 16px;"),
            ".footer .footer-verse": ("font: inherit;", "margin: 0;"),
            ".footer-links": ("font-size: inherit;",),
            ".footer-bottom": ("padding-top: 12px;", "font-size: inherit;"),
            ".footer-bottom > :last-child": ("font-size: .72rem;",),
            ".brand > span": ("display: block;", "text-align: left;"),
            ".brand-name": ("display: block;",),
            ".brand-note": ("display: block;", "font-size: .75rem;"),
        }.items():
            block = re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]+)", self.css).group(1)
            for declaration in declarations:
                self.assertIn(declaration, block)
        subtitle_sizes = []
        for block in re.findall(r"\.brand-note\s*\{([^}]+)", self.css):
            self.assertNotRegex(block, r"display:\s*none|visibility:\s*hidden")
            subtitle_sizes.extend(re.findall(r"font-size:\s*([.\d]+rem)", block))
        self.assertEqual(subtitle_sizes, [".75rem", ".72rem"])

    def test_project_codename_and_language_copy(self):
        self.assertEqual(self.config["projects"]["new-sanguo"]["name"], "Sanguo3D")
        self.assertEqual(self.config["projects"]["creators"]["name"], "Creators")
        for name, text in self.expected.items():
            with self.subTest(page=name):
                self.assertNotRegex(text, r"创世三国|创世春秋之三国|working Chinese title|Return to 三国春秋")
                self.assertNotRegex(text, r"English first, Chinese to follow|A Chinese edition is planned|language panel")
        for name in ("index.html", "sanguo3d/index.html", "sanguoseason/index.html", "about/index.html"):
            self.assertIn("development codename", self.expected[name].lower())
        self.assertIn("Return to SanguoSeason:", self.expected["sanguoseason/index.html"])
        self.assertIn("final title has not been decided", self.expected["sanguo3d/index.html"])
        self.assertIn("new Three Kingdoms world in 3D", self.config["projects"]["new-sanguo"]["summary"])
        self.assertIn('Creators / <span lang="zh-CN">创世春秋</span>', self.expected["about/index.html"])
        self.assertIn("Each game’s supported languages and platforms", self.expected["about/index.html"])
        self.assertIn('href="https://seasont.com/sanguo/docs/SanguoSeason.zip"',
                      self.expected["sanguoseason/index.html"])

    def test_theme_text_contrast(self):
        def palette(selector):
            match = re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]+)", self.css)
            return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})", match.group(1))) if match else {}
        for theme in ("day", "night"):
            for project in ("home", "classic", "sanguo3d", "creators", "ming", "zhsan"):
                colors = palette(":root")
                if theme == "night":
                    colors.update(palette('[data-theme="dark"]'))
                colors.update(palette(f'[data-project="{project}"]'))
                if theme == "night":
                    colors.update(palette(f'[data-theme="dark"] [data-project="{project}"]'))
                for ink in ("ink", "muted", "green", "gold", "seal"):
                    for paper in ("paper", "sheet", "paper-soft"):
                        with self.subTest(theme=theme, project=project, pair=(ink, paper)):
                            self.assertGreaterEqual(contrast(colors[ink], colors[paper]), 4.5)
                with self.subTest(theme=theme, project=project, pair="button"):
                    self.assertGreaterEqual(contrast(colors["button-ink"], colors["button"]), 4.5)
        # 此项检查纯色令牌；背景画面混合后的像素仍需人工视觉验收。

    def test_downloads_are_honest_and_escaped(self):
        by_key = {page["key"]: page for page in self.config["pages"]}
        for key, items in self.config["downloads"].items():
            rendered = self.expected[by_key[key]["path"]]
            with self.subTest(project=key):
                self.assertEqual(rendered.count('class="download-state"'), sum(item["url"] is None for item in items))
                self.assertEqual(rendered.count('class="download-row"'), len(items))
                self.assertIn(download_rows(items), rendered)
                self.assertNotIn('href="#"', download_rows(items))
        self.assertNotIn('class="download-row"', self.expected["downloads/index.html"])
        self.assertIn("legacy", self.expected[by_key["classic"]["path"]])
        sample = download_rows([{"platform": "<test>", "note": 'A & B', "label": '<not a button>', "url": None}])
        self.assertIn("&lt;test&gt;", sample)
        self.assertIn("A &amp; B", sample)
        self.assertNotIn("<a ", sample)
        with self.assertRaises(ValueError):
            download_rows([{"platform": "bad", "note": "", "label": "bad", "url": "javascript:alert(1)"}])

    def test_classic_direct_package_downloads(self):
        packages = {"windows": "https://seasont.com/sanguo/docs/SanguoSeason.zip",
                    "android": "https://seasont.com/sanguo/docs/com.season.sanguoseason.apk"}
        for name, first_href in (("index.html", "sanguoseason/index.html"),
                                 ("sanguoseason/index.html", "#overview")):
            with self.subTest(page=name):
                text = self.expected[name]
                actions = re.search(r'<div class="actions">(.*?)</div>', text, re.S).group(1)
                fragment = Page(actions)
                self.assertEqual(fragment.errors, [])
                links = fragment.select("a")
                self.assertEqual(len(links), 3)
                self.assertEqual(links[0]["href"], first_href)
                self.assertEqual(links[0]["class"], "button primary")
                self.assertEqual([a["data-download-platform"] for a in links[1:]], ["windows", "android"])
                self.assertIn("Legacy downloads:", actions)
                self.assertIn(">Windows ZIP</a>", actions)
                self.assertIn(">Android APK</a>", actions)
                self.assertNotIn("Availability", actions)
                self.assertFalse(fragment.select("img"))
                self.assertEqual(text.count('class="direct-downloads"'), 1)
                for link in links[1:]:
                    self.assertEqual(link["href"], packages[link["data-download-platform"]])
                    self.assertEqual(link["class"], "text-link")
                    self.assertNotIn("hidden", link)
                    self.assertNotIn("onclick", link)
                guarded = [a for a in self.pages[name].select("a") if "data-download-platform" in a]
                self.assertEqual(len(guarded), 2 if name == "index.html" else 4)
                for link in guarded:
                    self.assertEqual(link["href"], packages[link["data-download-platform"]])
        for name, page in self.pages.items():
            if name not in ("index.html", "sanguoseason/index.html"):
                self.assertFalse([a for a in page.select("a") if "data-download-platform" in a])
        for key in ("new-sanguo", "creators", "ming", "zhsan"):
            path = next(p["path"] for p in self.config["pages"] if p["key"] == key)
            actions = re.search(r'<div class="actions">(.*?)</div>', self.expected[path], re.S).group(1)
            self.assertIn('<a class="text-link" href="#downloads">Availability</a>', actions)
        block = re.search(r"\.direct-downloads\s*\{([^}]+)", self.css).group(1)
        self.assertIn("flex-wrap: wrap;", block)
        for bad in (None, "#", "javascript:alert(1)"):
            config = deepcopy(self.config)
            config["downloads"]["classic"][0]["url"] = bad
            with self.subTest(invalid_url=bad), self.assertRaises(ValueError):
                build_documents(config)
        config = deepcopy(self.config)
        config["downloads"]["classic"].append(deepcopy(config["downloads"]["classic"][0]))
        with self.assertRaises(ValueError):
            build_documents(config)
        config = deepcopy(self.config)
        config["downloads"]["classic"][0]["url"] = "https://example.test/updated.zip"
        documents = build_documents(config)
        self.assertEqual(documents["index.html"].count('href="https://example.test/updated.zip"'), 1)
        self.assertEqual(documents["sanguoseason/index.html"].count('href="https://example.test/updated.zip"'), 2)

    def test_home_project_order_and_carousel_fallback(self):
        home = self.pages["index.html"]
        slides = [a for a in home.select("article") if "data-slide" in a]
        self.assertEqual([a["data-project"] for a in slides], ["classic", "sanguo3d", "creators", "ming"])
        bands = [a for a in home.select("article") if a.get("class") == "project-band"]
        self.assertEqual([a["id"] for a in bands], ["sanguoseason", "sanguo3d", "creators", "ming", "zhsan"])
        selectors = [b for b in home.select("button") if "data-carousel-to" in b]
        self.assertEqual([b["data-carousel-to"] for b in selectors], ["0", "1", "2", "3"])
        self.assertEqual([b["aria-controls"] for b in selectors], [a["id"] for a in slides])
        for slide in slides:
            self.assertNotIn("hidden", slide)
            self.assertNotIn("inert", slide)
            self.assertNotIn("aria-hidden", slide)
        self.assertIn("hidden", next(a for _, a in home.tags if "data-carousel-controls" in a))
        self.assertIn(".carousel-ready .carousel-track.is-resetting { transition: none; }", self.css)
        for name, page in self.pages.items():
            scripts = [s.get("src", "") for s in page.select("script")]
            self.assertEqual(any(s.endswith("carousel.js") for s in scripts), name == "index.html")

    def test_shared_project_structure_and_reading_ownership(self):
        projects = [p for p in self.config["pages"] if p.get("kind") == "project"]
        self.assertEqual([p["key"] for p in projects], list(PROJECT_ORDER))
        for item in projects:
            page = self.pages[item["path"]]
            self.assertEqual([s["id"] for s in page.select("section") if "id" in s],
                             ["overview", "reading", "workshop", "downloads"])
            self.assertEqual(page.select("body")[0]["data-project"], item["theme"])
            self.assertEqual(len([n for n in page.select("nav") if n.get("class") == "project-nav jump-links"]), 1)
            self.assertEqual(tuple(split_project((SOURCE / "pages" / (item["key"] + ".html")).read_text(encoding="utf-8"))),
                             ("overview", "reading", "workshop", "downloads_note"))
        for path, project in (("sanguo3d/reading/three-kingdoms/index.html", "sanguo3d"),
                              ("sanguoseason/reading/a-painted-world/index.html", "classic")):
            self.assertEqual(self.pages[path].select("body")[0]["data-project"], project)
        self.assertTrue({"relationship", "platforms", "availability", "contributing"} <= self.pages["games/zhsan/index.html"].ids)
        for removed in ("games", "downloads", "journal"):
            self.assertFalse((SOURCE / "pages" / (removed + ".html")).exists())

    def test_legacy_routes_and_fragment_targets(self):
        self.assertEqual(len(self.config["redirects"]), 7)
        for path, item in self.config["redirects"].items():
            page = self.pages[path]
            resolve = lambda href: urljoin("https://example.test/" + path, href)
            target = next(a for a in page.select("a") if "data-redirect-target" in a)
            self.assertEqual(resolve(target["href"]), "https://example.test/" + item["target"])
            self.assertEqual(target.get("data-preserve-fragment") == "true", item.get("preserve_fragment", False))
            fragments = {a["data-old-fragment"]: resolve(a["href"]) for a in page.select("a") if "data-old-fragment" in a}
            self.assertEqual(fragments, {old: "https://example.test/" + new for old, new in item.get("fragments", {}).items()})
            self.assertIn({"name": "robots", "content": "noindex"}, page.select("meta"))
            self.assertTrue(any(s.get("src", "").endswith("redirect.js") for s in page.select("script")))

    def test_publish_urls_and_self_contained_404(self):
        for base in ("https://example.test/", "https://example.test/History/"):
            config = deepcopy(self.config)
            config["base_url"] = base
            documents = build_documents(config)
            sitemap = ET.fromstring(documents["sitemap.xml"])
            locations = [node.text for node in sitemap.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
            self.assertEqual(locations, [base + p["path"] for p in config["pages"]])
            for page in config["pages"]:
                self.assertIn(f'href="{base + page["path"]}"', documents[page["path"]])
            for old, item in config["redirects"].items():
                self.assertNotIn(base + old, locations)
                canonical = base + item["target"].split("#")[0]
                self.assertIn(f'rel="canonical" href="{canonical}"', documents[old])
            self.assertIn(f'href="{base}index.html"', documents["404.html"])
        error_page = self.pages["404.html"]
        self.assertFalse(error_page.select("link"))
        self.assertEqual(len(error_page.select("img")), 2)
        for image in error_page.select("img"):
            self.assert_inline_theme_icon("404.html", "img", image)
        self.assertTrue(all("src" not in s for s in error_page.select("script")))
        unconfigured = build_documents({**self.config, "base_url": ""})
        self.assertNotIn("sitemap.xml", unconfigured)
        self.assertNotIn('rel="canonical"', unconfigured["index.html"])
        self.assertIn("Back button", unconfigured["404.html"])

    def test_invalid_configuration_fails_before_writing(self):
        for path in ("../escape.html", "/absolute.html", "C:/escape.html", "404.html", "games/../../escape.html"):
            config = deepcopy(self.config)
            config["pages"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                build_documents(config)
        for url in ("//example.test/", "https://example.test/?query=1", "javascript:bad", "https://user:password@example.test/"):
            with self.assertRaises(ValueError):
                normalize_base(url)
        for target in ("https://outside.test/", "//outside.test/", "index.html?next=bad", "missing/index.html", "../index.html"):
            config = deepcopy(self.config)
            config["redirects"]["games/index.html"]["target"] = target
            with self.subTest(target=target), self.assertRaises(ValueError):
                build_documents(config)
        for body in ("<p>missing sections</p>", "<!-- section:reading -->wrong order"):
            with self.assertRaises(ValueError):
                split_project(body)
        with self.assertRaises(ValueError):
            render("{{unknown}}", {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
