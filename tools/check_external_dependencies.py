#!/usr/bin/env python3
"""Check a static site's active browser resource references for external calls.

Ordinary anchor links (including attribution/license links) are intentionally
excluded: they navigate only when a visitor clicks them. Passive URL strings in
vendored libraries are also not treated as calls unless used as a resource,
request argument, layer data URL, or map/tile configuration.
"""
from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REMOTE = re.compile(r"^(?:https?:)?//", re.IGNORECASE)
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_IMPORT = re.compile(r"@import\s+(?:url\(\s*)?(['\"])(.*?)\1", re.IGNORECASE)
JS_STATIC_CALLS = {
    "fetch": re.compile(r"\bfetch\s*\(\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
    "XMLHttpRequest.open": re.compile(r"\.open\s*\(\s*['\"][A-Z]+['\"]\s*,\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
    "dynamic import": re.compile(r"\bimport\s*\(\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
    "importScripts": re.compile(r"\bimportScripts\s*\(\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
    "static import": re.compile(r"^\s*import\s+(?:[\s\S]*?\sfrom\s*)?(['\"])([^'\"]+)\1", re.MULTILINE),
    "Worker": re.compile(r"\bnew\s+(?:Shared)?Worker\s*\(\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
    "WebSocket/EventSource": re.compile(r"\bnew\s+(?:WebSocket|EventSource)\s*\(\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
    "sendBeacon": re.compile(r"\bsendBeacon\s*\(\s*(['\"`])([^'\"`]+)\1", re.IGNORECASE),
}
JS_RESOURCE_CONFIG = re.compile(
    r"\b(?:data|url|tiles|mapStyle|tileUrl|tileURL)\s*:\s*(['\"`])([^'\"`]+)\1",
    re.IGNORECASE,
)
JS_PROVIDER_CONFIG = re.compile(
    r"\b(mapProvider|mapboxApiAccessToken|basemap|tileServer)\s*:\s*(['\"`])([^'\"`]+)\2",
    re.IGNORECASE,
)
JS_DYNAMIC_SINKS = {
    "dynamic fetch URL": re.compile(r"\bfetch\s*\(\s*(?!['\"`])", re.IGNORECASE),
    "dynamic XHR URL": re.compile(r"\.open\s*\(\s*['\"][A-Z]+['\"]\s*,\s*(?!['\"`])", re.IGNORECASE),
    "dynamic import URL": re.compile(r"\bimport\s*\(\s*(?!['\"`])", re.IGNORECASE),
    "dynamic importScripts URL": re.compile(r"\bimportScripts\s*\(\s*(?!['\"`])", re.IGNORECASE),
    "dynamic Worker URL": re.compile(r"\bnew\s+(?:Shared)?Worker\s*\(\s*(?!['\"`])", re.IGNORECASE),
    "dynamic socket URL": re.compile(r"\bnew\s+(?:WebSocket|EventSource)\s*\(\s*(?!['\"`])", re.IGNORECASE),
    "dynamic sendBeacon URL": re.compile(r"\bsendBeacon\s*\(\s*(?!['\"`])", re.IGNORECASE),
}
RESOURCE_RELATIONS = {
    "stylesheet", "preload", "modulepreload", "prefetch", "preconnect",
    "dns-prefetch", "icon", "manifest", "mask-icon",
}
RESOURCE_TAGS = {
    "img": ("src",), "iframe": ("src",), "frame": ("src",),
    "source": ("src", "srcset"), "video": ("src", "poster"),
    "audio": ("src",), "track": ("src",), "embed": ("src",),
    "object": ("data",), "input": ("src",), "base": ("href",),
}


class DocumentParser(HTMLParser):
    def __init__(self, path: Path, site_dir: Path, findings: list[str], missing: list[str]):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.site_dir = site_dir
        self.findings = findings
        self.missing = missing
        self.inline_js: list[str] = []
        self.inline_css: list[str] = []
        self.capture: str | None = None
        self.buffer: list[str] = []

    def _reference(self, raw: str, context: str) -> None:
        value = html.unescape(raw.strip())
        if not value or value.startswith(("#", "data:", "blob:", "javascript:", "mailto:", "tel:")):
            return
        if REMOTE.match(value):
            self.findings.append(f"{context}: {value}")
            return
        parts = urlsplit(value)
        if parts.scheme or parts.netloc:
            return
        path = unquote(parts.path)
        if not path:
            return
        if path.startswith("/"):
            target = self.site_dir / path.lstrip("/")
        else:
            target = self.path.parent / path
        try:
            target.resolve().relative_to(self.site_dir.resolve())
        except ValueError:
            self.missing.append(f"site外を指す相対参照: {context}: {value}")
            return
        if not target.resolve().is_file():
            self.missing.append(f"ローカル参照先がありません: {context}: {value}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        if tag == "script":
            if values.get("src"):
                self._reference(values["src"], f"{self.path.name} <script src>")
            else:
                self.capture = "js"
                self.buffer = []
        elif tag == "link" and set(values.get("rel", "").lower().split()) & RESOURCE_RELATIONS:
            self._reference(values.get("href", ""), f"{self.path.name} <link href>")
        elif tag == "a" and values.get("href"):
            # External attribution links are inert until clicked; check local
            # notice links for missing targets without classifying them as calls.
            href = html.unescape(values["href"].strip())
            if not REMOTE.match(href) and not urlsplit(href).scheme:
                self._reference(href, f"{self.path.name} <a href>")
        elif tag in RESOURCE_TAGS:
            for attr in RESOURCE_TAGS[tag]:
                raw = values.get(attr, "")
                if attr == "srcset":
                    for item in raw.split(","):
                        self._reference(item.strip().split(" ")[0], f"{self.path.name} <{tag} srcset>")
                else:
                    self._reference(raw, f"{self.path.name} <{tag} {attr}>")
        elif tag == "style":
            self.capture = "css"
            self.buffer = []
        elif tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"\burl\s*=\s*(['\"]?)(.+?)\1\s*$", values.get("content", ""), re.IGNORECASE)
            if match:
                self._reference(match.group(2), f"{self.path.name} meta refresh")
        if values.get("style"):
            scan_css(values["style"], f"{self.path.name} inline style", self.site_dir, self.path.parent, self.findings, self.missing)

    def handle_endtag(self, tag: str) -> None:
        if (tag.lower() == "script" and self.capture == "js") or (tag.lower() == "style" and self.capture == "css"):
            content = "".join(self.buffer)
            (self.inline_js if self.capture == "js" else self.inline_css).append(content)
            self.capture = None
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)


def scan_css(source: str, context: str, site_dir: Path, base_dir: Path, findings: list[str], missing: list[str]) -> None:
    refs = [(match.group(2), "url()") for match in CSS_URL.finditer(source)]
    refs.extend((match.group(2), "@import") for match in CSS_IMPORT.finditer(source))
    for value, kind in refs:
        value = value.strip()
        if not value or value.startswith(("data:", "blob:", "#")):
            continue
        if REMOTE.match(value):
            findings.append(f"{context} {kind}: {value}")
            continue
        parts = urlsplit(value)
        if parts.scheme or parts.netloc:
            continue
        target = (site_dir / unquote(parts.path).lstrip("/")) if parts.path.startswith("/") else (base_dir / unquote(parts.path))
        try:
            target.resolve().relative_to(site_dir.resolve())
        except ValueError:
            missing.append(f"site外を指すCSS参照: {context}: {value}")
            continue
        if not target.resolve().is_file():
            missing.append(f"ローカルCSS参照先がありません: {context}: {value}")


def scan_javascript(source: str, context: str, site_dir: Path, base_dir: Path, findings: list[str], missing: list[str], strict_dynamic: bool = False) -> None:
    for kind, pattern in JS_STATIC_CALLS.items():
        for match in pattern.finditer(source):
            value = match.group(2).strip()
            # Generic bundled worker helpers interpolate a caller-supplied URL.
            # The literal `${...}` is not itself a network endpoint. Any
            # resulting off-origin script/fetch is also denied by the page CSP.
            if "${" in value and not REMOTE.match(value):
                continue
            _check_js_reference(value, f"{context} {kind}()", site_dir, base_dir, findings, missing)
    for match in JS_RESOURCE_CONFIG.finditer(source):
        value = match.group(2).strip()
        # Large vendor bundles contain generic `url`/`data` option names. Only
        # inspect values that are visibly resource-like, not arbitrary labels.
        if "${" in value or not (
            REMOTE.match(value)
            or value.startswith(("./", "../", "/", "data/", "assets/", "vendor/"))
            or re.search(r"\.(?:json|geojson|js|mjs|css|png|jpe?g|svg|woff2?)(?:[?#]|$)", value, re.IGNORECASE)
        ):
            continue
        _check_js_reference(value, f"{context} resource/layer/map configuration", site_dir, base_dir, findings, missing)
    for match in JS_PROVIDER_CONFIG.finditer(source):
        key, value = match.group(1), match.group(3).strip()
        if value.lower() not in {"none", "null", "false", ""}:
            findings.append(f"{context} external/provider configuration {key}: {value}")
    if strict_dynamic:
        for kind, pattern in JS_DYNAMIC_SINKS.items():
            if pattern.search(source):
                findings.append(f"{context} unresolved {kind}; inspect the runtime URL")


def _check_js_reference(value: str, context: str, site_dir: Path, base_dir: Path, findings: list[str], missing: list[str]) -> None:
    if not value or value.startswith(("data:", "blob:", "#", "javascript:")):
        return
    if REMOTE.match(value):
        findings.append(f"{context}: {value}")
        return
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return
    path = unquote(parts.path)
    if not path:
        return
    target = (site_dir / path.lstrip("/")) if path.startswith("/") else (base_dir / path)
    try:
        target.resolve().relative_to(site_dir.resolve())
    except ValueError:
        missing.append(f"site外を指すJS参照: {context}: {value}")
        return
    if not target.resolve().is_file():
        missing.append(f"ローカルJS参照先がありません: {context}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="静的サイトの外部実行時依存を検査します")
    parser.add_argument("--site", type=Path, default=ROOT / "site", help="公開用ディレクトリ (default: site/)")
    args = parser.parse_args()
    site_dir = args.site.resolve()
    index = site_dir / "index.html"
    if not index.is_file():
        print(f"検査できません: {index} がありません", file=sys.stderr)
        return 2

    findings: list[str] = []
    missing: list[str] = []
    parsed_html: list[str] = []
    html_source = index.read_text(encoding="utf-8-sig")
    document = DocumentParser(index, site_dir, findings, missing)
    document.feed(html_source)
    parsed_html.extend(document.inline_js)
    for style in document.inline_css:
        scan_css(style, "index.html inline CSS", site_dir, index.parent, findings, missing)

    for file_path in sorted(site_dir.rglob("*")):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix == ".html" and file_path != index:
            source = file_path.read_text(encoding="utf-8-sig")
            other = DocumentParser(file_path, site_dir, findings, missing)
            other.feed(source)
            parsed_html.extend(other.inline_js)
            for style in other.inline_css:
                scan_css(style, f"{file_path.relative_to(site_dir)} inline CSS", site_dir, file_path.parent, findings, missing)
        elif suffix in {".js", ".mjs"}:
            source = file_path.read_text(encoding="utf-8-sig", errors="replace")
            scan_javascript(source, file_path.relative_to(site_dir).as_posix(), site_dir, file_path.parent, findings, missing)
        elif suffix == ".css":
            scan_css(file_path.read_text(encoding="utf-8-sig", errors="replace"), file_path.relative_to(site_dir).as_posix(), site_dir, file_path.parent, findings, missing)
    for number, source in enumerate(parsed_html, start=1):
        scan_javascript(source, f"index.html inline script #{number}", site_dir, index.parent, findings, missing, strict_dynamic=True)

    csp = re.search(r"<meta\s+http-equiv\s*=\s*['\"]content-security-policy['\"][^>]*\bcontent\s*=\s*\"([^\"]+)\"", html_source, re.IGNORECASE)
    if not csp:
        missing.append("Content-Security-Policy meta がありません")
    else:
        directives = {key.lower(): value.split() for key, value in re.findall(r"([\w-]+)\s+([^;]+)", csp.group(1))}
        connect_sources = directives.get("connect-src", directives.get("default-src", []))
        if "'self'" not in connect_sources or any(source in {"*", "https:", "http:"} for source in connect_sources):
            missing.append("CSP connect-src が同一サイト限定ではありません")

    required_ui = ["year-slider", "play-button", "year-prev", "year-next", "prefecture-filter", "detail-panel", "detail-chart", "GeoJsonLayer", "ColumnLayer", "PostProcessEffect", "data/land_price.json", "data/prefectures.geojson"]
    for marker in required_ui:
        if marker not in html_source:
            missing.append(f"HTMLの機能マーカーがありません: {marker}")
    try:
        records = json.loads((site_dir / "data" / "land_price.json").read_text(encoding="utf-8"))
        boundaries = json.loads((site_dir / "data" / "prefectures.geojson").read_text(encoding="utf-8"))
        if not records:
            missing.append("land_price.json が空です")
        if len(boundaries.get("features", [])) != 47:
            missing.append(f"prefectures.geojson の都道府県数が47ではありません: {len(boundaries.get('features', []))}")
    except (OSError, json.JSONDecodeError) as error:
        missing.append(f"ローカルJSONを検証できません: {error}")

    if findings or missing:
        print("以下の外部依存または公開ファイルの問題が見つかりました")
        for item in findings:
            print(f"  外部通信: {item}")
        for item in missing:
            print(f"  要修正: {item}")
        return 1
    print("外部通信なし")
    print(f"検査対象: {site_dir}")
    print("HTML/CSS/JavaScriptの実行時参照は同梱ファイルまたは同一サイト内に限定されています。")
    print("出典への通常のリンクはクリック時だけ遷移するため、実行時依存には含めていません。")
    print(f"確認: 地価データ {len(records):,} 地点、都道府県境界 {len(boundaries['features'])} 件、CSP connect-src 'self'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
