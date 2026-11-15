"""Automatic content hashes for all EZ Thing web assets.

No manual public version numbers or timestamp cache bumps. Build/source content
determines the URLs and the service-worker cache key, without a JS bundler or
additional third-party dependency. Business and API data are never cached here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fastapi.responses import HTMLResponse, Response


# This is intentionally attribute-scoped (not a broad replace of links
# embedded in script bodies). It catches both legacy ?v= and unversioned assets.
_ASSET_ATTRIBUTE = re.compile(
    r"""(?P<attribute>\b(?:src|href)\s*=\s*)(?P<quote>["'])(?P<url>/assets/[A-Za-z0-9_./-]+\.(?:js|css|svg|png|jpg|jpeg|gif|webp|ico|woff2?))(?P<old_query>\?[^"']*)?(?P=quote)""",
    re.IGNORECASE,
)
_ASSET_SUFFIXES = {".js", ".css", ".svg", ".png", ".jpg", ".jpeg",
                   ".gif", ".webp", ".ico", ".woff", ".woff2"}
_SHELL_ROUTES = ("/", "/app", "/menu/cafe", "/store/mart", "/store/online",
                 "/booking/wellness", "/reserve/cafe")


class AssetPipeline:
    """Immutable per-process fingerprint index, regenerated when code restarts."""

    def __init__(self, static_root: Path):
        self.root = static_root.resolve()
        assets = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _ASSET_SUFFIXES:
                continue
            relative = path.relative_to(self.root).as_posix()
            public_path = "/assets/" + relative
            assets[public_path] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        self.hashes = assets
        # Include static HTML and manifest sources in the shell revision.
        # A CSS/JS/HTML change updates the worker automatically. No "v8" key.
        digest = hashlib.sha256()
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in (
                _ASSET_SUFFIXES | {".html", ".webmanifest"}):
                continue
            relative = path.relative_to(self.root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        self.shell_hash = digest.hexdigest()[:16]

    def asset_url(self, original: str) -> str:
        """Ignore legacy query strings, use only the bytes being served."""
        public_path = original.split("?", 1)[0].split("#", 1)[0]
        content_hash = self.hashes.get(public_path)
        if content_hash is None:
            return original
        return public_path + "?h=" + content_hash

    def rewrite_html(self, html: str) -> str:
        def replace(match: re.Match) -> str:
            return (match.group("attribute") + match.group("quote")
                    + self.asset_url(match.group("url"))
                    + match.group("quote"))
        return _ASSET_ATTRIBUTE.sub(replace, html)

    def page(self, filename: str) -> HTMLResponse:
        # All callers use fixed filenames, never arbitrary user input.
        if filename not in {p.name for p in self.root.glob("*.html")}:
            raise FileNotFoundError(filename)
        html = (self.root / filename).read_text(encoding="utf-8")
        return HTMLResponse(
            self.rewrite_html(html),
            headers={"Cache-Control": "no-store, max-age=0",
                     "X-Content-Type-Options": "nosniff"},
        )

    def manifest(self) -> Response:
        data = json.loads((self.root / "manifest.webmanifest").read_text(encoding="utf-8"))
        for icon in data.get("icons", []):
            if isinstance(icon.get("src"), str):
                icon["src"] = self.asset_url(icon["src"])
        return Response(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            media_type="application/manifest+json",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )

    def service_worker(self) -> Response:
        template = (self.root / "sw.js").read_text(encoding="utf-8")
        precache = list(_SHELL_ROUTES)
        # Only static assets, never business-specific routes or API responses.
        precache += [self.asset_url(url) for url in sorted(self.hashes)
                     if url.endswith((".js", ".css", ".svg", ".png", ".webp"))]
        body = template.replace("__EZ_CONTENT_HASH__", self.shell_hash)
        body = body.replace("__EZ_PRECACHE_ASSETS__", json.dumps(precache))
        return Response(
            body,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                     "Service-Worker-Allowed": "/"},
        )


STATIC_ASSETS = AssetPipeline(Path(__file__).resolve().parent / "static")
