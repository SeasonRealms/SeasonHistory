"""用标准库生成静态站；只编辑 site 内容与 docs/assets，再运行本脚本。

python tools/build_site.py             生成可直接托管的 docs
python tools/build_site.py --check     仅检查生成产物是否与源文件一致
正式域名确定后设置 site/site.json 的 base_url（含仓库路径，末尾斜杠）。
也可传 --base-url https://example.org/History/ 临时覆盖；不会修改配置。
未配置域名时不猜测 canonical、社交图片绝对地址或 sitemap。
"""
from __future__ import annotations

import argparse
from base64 import b64encode
from datetime import date
from html import escape
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site"
OUTPUT = ROOT / "docs"
TOKEN = re.compile(r"\{\{([a-z_:-]+)\}\}")
NAVIGATION = (("home", "Home"), ("classic", "SanguoSeason"), ("new-sanguo", "Sanguo3D"),
              ("creators", "Creators"), ("ming", "Ming"))
PROJECT_ORDER = tuple(key for key, _ in NAVIGATION[1:]) + ("zhsan",)
PROJECT_SECTIONS = ("overview", "reading", "workshop", "downloads_note")
PAGE_PATH = re.compile(r"(?:[a-z0-9-]+/)*[a-z0-9-]+\.html")


def render(template: str, values: dict[str, str]) -> str:
    """单轮替换：内容中的花括号不会被再次解释。"""
    def replace(match):
        key = match.group(1)
        if key not in values:
            raise ValueError(f"模板中有未知占位符：{key}")
        return values[key]
    result = TOKEN.sub(replace, template)
    if "{{" in result or "}}" in result:
        raise ValueError("生成结果仍含占位符")
    return result


def normalize_base(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value)
    if (parts.scheme not in ("https", "http") or not parts.netloc
            or parts.query or parts.fragment or parts.username or parts.password
            or re.search(r"[\s<>\"\\]", value)):
        raise ValueError("base_url 必须是无凭据、查询参数和片段的 HTTP(S) 站点地址")
    return value.rstrip("/") + "/"


def download_link(item: dict, label: str | None = None) -> str:
    """入口和下载栏目共用配置地址；真实 href 保证无脚本时仍可下载。"""
    url = item["url"]
    parts = urlsplit(url or "")
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise ValueError(f"下载地址必须使用无凭据的 HTTPS：{item['platform']}")
    platform = {"Windows": "windows", "Android": "android"}.get(item["platform"])
    guard = f' data-download-platform="{platform}"' if platform else ""
    return (f'<a class="text-link" href="{escape(url, quote=True)}"{guard}>'
            f'{escape(item["label"] if label is None else label)}</a>')


def download_action(config: dict, key: str, href: str) -> str:
    if key != "classic":
        return f'<a class="text-link" href="{escape(href, quote=True)}">Availability</a>'
    links = []
    for platform, label in (("Windows", "Windows ZIP"), ("Android", "Android APK")):
        items = [item for item in config["downloads"][key] if item["platform"] == platform]
        if len(items) != 1 or not items[0]["url"]:
            raise ValueError(f"三国春秋快捷下载需要唯一且有效的 {platform} 安装包地址")
        links.append(download_link(items[0], label))
    return ('<span class="direct-downloads" role="group" aria-label="SanguoSeason legacy package downloads">'
            '<span class="meta">Legacy downloads:</span>' + " ".join(links) + '</span>')


def download_rows(items: list[dict]) -> str:
    rows = []
    for item in items:
        action = (download_link(item) if item["url"]
                  else f'<span class="download-state">{escape(item["label"])}</span>')
        rows.append('<div class="download-row">'
                    f'<h3>{escape(item["platform"])}</h3>'
                    f'<p>{escape(item["note"])}</p>{action}</div>')
    return '<div class="download-rows">\n' + "\n".join(rows) + "\n</div>"


def split_project(source: str) -> dict[str, str]:
    """每个项目仅维护四段正文；页面结构全部由公共项目模板提供。"""
    chunks = re.split(r"<!-- section:([a-z_]+) -->", source)
    names = chunks[1::2]
    if chunks[0].strip() or tuple(names) != PROJECT_SECTIONS:
        raise ValueError("项目正文必须依次提供 overview、reading、workshop、downloads_note")
    return dict(zip(names, (part.strip() for part in chunks[2::2])))


def image_tag(project: dict, root: str, assets: dict, eager: bool = False) -> str:
    name = project["image"]
    if not re.fullmatch(r"[a-z0-9-]+\.(?:jpg|png|svg)", name):
        raise ValueError("项目图片必须引用本地 assets/img 中的文件")
    asset = assets[name]
    if not (OUTPUT / "assets/img" / name).is_file():
        raise ValueError(f"项目图片不存在：{name}")
    loading = 'loading="eager"' if eager else 'loading="lazy"'
    return (f'<img src="{root}assets/img/{name}" alt="{escape(project["image_alt"], quote=True)}" '
            f'width="{int(asset["width"])}" height="{int(asset["height"])}" {loading} decoding="async">')


def home_components(config: dict, by_key: dict, assets: dict, root: str) -> dict[str, str]:
    slides, buttons, rows = [], [], []
    for index, key in enumerate(PROJECT_ORDER):
        project = config["projects"][key]
        page = by_key[key]
        theme = page["theme"]
        name, summary, status, caption = (escape(project[field]) for field in ("name", "summary", "status", "caption"))
        url = root + page["path"]
        picture = image_tag(project, root, assets)
        if key != "zhsan":
            # 四个自有项目进入轮播，友情项目只进入下方列表。
            slide_id = f"slide-{key}"
            slides.append(f'<article class="carousel-slide" id="{slide_id}" data-slide data-project="{theme}" '
                          f'role="group" aria-roledescription="slide" aria-label="{index + 1} of 4: {name}">'
                          '<div class="wrap feature-inner"><div class="feature-copy">'
                          f'<p class="eyebrow">{status}</p><h2>{name}</h2>'
                          f'<p class="feature-tagline">{escape(project["tagline"])}</p><p class="lede">{summary}</p>'
                          f'<div class="actions"><a class="button primary" href="{url}">Explore {name} →</a>'
                          f'{download_action(config, key, url + "#downloads")}</div></div>'
                          f'<figure class="feature-art">{image_tag(project, root, assets, index == 0)}'
                          f'<figcaption>{caption}</figcaption></figure></div></article>')
            buttons.append(f'<button type="button" data-carousel-to="{index}" aria-controls="{slide_id}" '
                           f'aria-label="Show {name}" aria-pressed="{"true" if index == 0 else "false"}">{name}</button>')
        identifier = "zhsan" if key == "zhsan" else page["path"].split("/")[0]
        rows.append(f'<article class="project-band" data-project="{theme}" id="{identifier}">'
                    f'<figure>{picture}<figcaption>{caption}</figcaption></figure><div>'
                    f'<p class="eyebrow">{index + 1:02d} · {status}</p><h3><a href="{url}">{name}</a></h3>'
                    f'<p class="project-tagline">{escape(project["tagline"])}</p><p class="muted">{summary}</p>'
                    f'<a class="text-link" href="{url}">{"About the companion branch" if key == "zhsan" else "Explore the project"}</a>'
                    f'<div class="project-shortcuts"><a href="{url}#reading">Reading room</a>'
                    f'<a href="{url}#workshop">Workshop</a><a href="{url}#downloads">Downloads</a></div></div></article>')
    return {"slides": "\n".join(slides), "slide_buttons": "\n".join(buttons), "project_rows": "\n".join(rows)}


def relocation_content(item: dict, root: str, page_paths: set[str]) -> str:
    def link(target: str) -> str:
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or parts.query or parts.path not in page_paths:
            raise ValueError(f"旧地址必须转到实际生成的站内页面：{target}")
        return escape(root + target, quote=True)
    target = link(item["target"])
    links = [f'<li><a data-old-fragment="{escape(fragment, quote=True)}" href="{link(destination)}">'
             f'{escape(fragment)} → project section</a></li>'
             for fragment, destination in item.get("fragments", {}).items()]
    preserve = ' data-preserve-fragment="true"' if item.get("preserve_fragment") else ""
    return ('<div class="wrap section"><h1>This content now lives with its project.</h1>'
            '<p>Introductions, reading, workshop notes, and downloads are now organised by game.</p>'
            f'<p><a data-redirect-target{preserve} href="{target}">Continue to the current page →</a></p>'
            '<ul>' + "".join(links) + '</ul></div>')


def build_documents(config: dict) -> dict[str, str]:
    """先在内存完成全部渲染，任何内容错误均在落盘前报告。"""
    base = normalize_base(config.get("base_url", ""))
    language = config["language"]
    if language != "en":
        raise ValueError("目前仅有英文正文；新增语言需同时准备对应内容与导航")
    checked = date.fromisoformat(config["checked_on"])
    checked_label = f"{checked.day} {checked.strftime('%B')} {checked.year}"
    layout = (SOURCE / "layout.html").read_text(encoding="utf-8")
    pages = config["pages"]
    by_key = {page["key"]: page for page in pages}
    if len(by_key) != len(pages):
        raise ValueError("页面 key 不可重复")
    site_name = escape(config["name"], quote=True)
    assets = {asset["file"]: asset for asset in json.loads((OUTPUT / "assets/img/sources.json").read_text(encoding="utf-8"))}
    downloads = {key: download_rows(items) for key, items in config["downloads"].items()}
    if set(config["projects"]) != set(PROJECT_ORDER) or set(downloads) != set(PROJECT_ORDER):
        raise ValueError("项目配置与下载配置必须覆盖四个自有项目及 ZHSan")
    page_paths = {page["path"] for page in pages}
    if len(page_paths) != len(pages):
        raise ValueError("页面输出路径不可重复")
    for page in pages:
        if (not re.fullmatch(r"[a-z0-9-]+", page["key"]) or not PAGE_PATH.fullmatch(page["path"])
                or page["path"] == "404.html" or not re.fullmatch(r"[a-z0-9-]+", page["theme"])):
            raise ValueError(f"页面标识、主题或输出路径无效：{page['key']}")
    project_layout = (SOURCE / "project.html").read_text(encoding="utf-8")
    documents = {}
    for page in pages:
        key = page["key"]
        path = PurePosixPath(page["path"])
        root = "../" * (len(path.parts) - 1)
        links = []
        for nav_key, label in NAVIGATION:
            destination = by_key[nav_key]["path"]
            current = ""
            if page.get("nav") == nav_key:
                current = ' aria-current="page"' if key == nav_key else ' aria-current="location"'
            links.append(f'<a href="{root}{escape(destination, quote=True)}"{current}>{label}</a>')
        source = (SOURCE / "pages" / f"{key}.html").read_text(encoding="utf-8")
        if page.get("kind") == "project":
            project = config["projects"][key]
            sections = {name: render(text, {"root": root}) for name, text in split_project(source).items()}
            content = render(project_layout, {**{name: escape(value) for name, value in project.items()},
                             **sections, "project_name": escape(project["name"]), "root": root,
                             "image": image_tag(project, root, assets, True), "downloads": downloads[key],
                             "download_action": download_action(config, key, "#downloads"),
                             "checked_on": checked_label})
        else:
            components = home_components(config, by_key, assets, root) if key == "home" else {}
            content = render(source, {"root": root, "checked_on": checked_label, **components})
        social = ""
        if base:
            canonical = escape(base + str(path), quote=True)
            image = escape(base + "assets/img/social.jpg", quote=True)
            social = (f'<link rel="canonical" href="{canonical}">\n'
                      f'  <meta property="og:url" content="{canonical}">\n'
                      f'  <meta property="og:image" content="{image}">\n'
                      '  <meta property="og:image:alt" content="Blue-green mountains and rivers">')
        documents[str(path)] = render(layout, {
            "title": escape(page["title"]), "description": escape(page["description"], quote=True),
            "site_name": site_name, "project_theme": page["theme"],
            "page_scripts": f'<script src="{root}assets/js/carousel.js" defer></script>' if key == "home" else "",
            "language": escape(language, quote=True), "root": root,
            "navigation": "\n        ".join(links), "content": content,
            "og_type": "article" if key == "painted-world" else "website", "social_meta": social,
        })
    for path, item in config.get("redirects", {}).items():
        if not PAGE_PATH.fullmatch(path) or path in documents or path == "404.html":
            raise ValueError(f"兼容地址无效或与页面冲突：{path}")
        root = "../" * (len(PurePosixPath(path).parts) - 1)
        canonical = f'<link rel="canonical" href="{escape(base + item["target"].split("#")[0], quote=True)}">' if base else ""
        documents[path] = render(layout, {
            "title": "Content moved", "description": "Find this content in its project’s reading, workshop or download section.",
            "site_name": site_name, "language": language, "root": root, "project_theme": "home",
            "navigation": "\n".join(f'<a href="{root}{by_key[key]["path"]}">{label}</a>' for key, label in NAVIGATION),
            "content": relocation_content(item, root, page_paths), "og_type": "website",
            "social_meta": '<meta name="robots" content="noindex">' + canonical,
            "page_scripts": f'<script src="{root}assets/js/redirect.js" defer></script>',
        })
    recovery = (f'<p><a href="{escape(base, quote=True)}index.html">Return to {site_name} →</a></p>'
                if base else '<p>Use your browser’s Back button to return to the previous page, '
                'or check the address you entered.</p>')
    documents["404.html"] = render((SOURCE / "404.html").read_text(encoding="utf-8"), {
        "recovery": recovery, "site_name": site_name,
        "sun_image": "data:image/png;base64," + b64encode((OUTPUT / "assets/img/Sun.png").read_bytes()).decode("ascii"),
        "moon_image": "data:image/png;base64," + b64encode((OUTPUT / "assets/img/Moon.png").read_bytes()).decode("ascii"),
        "theme_script": (OUTPUT / "assets/js/theme.js").read_text(encoding="utf-8"),
        "interaction_script": (OUTPUT / "assets/js/history.js").read_text(encoding="utf-8"),
    })
    documents[".nojekyll"] = ""
    if base:
        urls = "\n".join(f'  <url><loc>{escape(base + page["path"])}</loc></url>' for page in pages)
        documents["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                    + urls + '\n</urlset>\n')
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    parser.add_argument("--base-url", help="发布站点完整地址，可含 GitHub Pages 仓库路径")
    args = parser.parse_args()
    try:
        config = json.loads((SOURCE / "site.json").read_text(encoding="utf-8"))
        if args.base_url is not None:
            config["base_url"] = args.base_url
        documents = build_documents(config)
        if "sitemap.xml" not in documents and (OUTPUT / "sitemap.xml").exists():
            raise ValueError("发现旧 sitemap.xml；请恢复正式 base_url，或手动移除旧发布地址清单")
        changed = []
        for name, content in documents.items():
            target = OUTPUT / name
            if target.exists() and target.read_text(encoding="utf-8") == content:
                continue
            changed.append(name)
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
        if args.check and changed:
            print("产物需要更新：" + ", ".join(changed))
            return 1
        print(f"{'检查通过' if args.check else '生成完成'}：{len(config['pages'])} 个内容页、{len(config.get('redirects', {}))} 个兼容页 + 自包含 404；"
              f"{len(changed)} 个文件{'待更新' if args.check else '已更新'}。")
        if not config.get("base_url"):
            print("尚未配置正式 base_url：已省略绝对分享地址及 sitemap，不影响本地和子路径访问。")
        return 0
    except (ValueError, KeyError, OSError) as error:
        print(f"生成失败：{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
