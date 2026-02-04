#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import difflib


ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "state.json"


def eprint(*a):
    print(*a, file=sys.stderr)


def load_config() -> dict:
    cfg_path = ROOT / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(
            "config.json not found. Copy config.example.json to config.json and edit it."
        )
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ValueError("config.json must be a JSON object.")
    if not cfg.get("target_url"):
        raise ValueError("config.json: target_url is required.")
    return cfg


def normalize_text(s: str) -> str:
    # collapse whitespace and trim
    return " ".join(s.split()).strip()


def fetch_page_text(url: str, user_agent: str) -> tuple[str, str]:
    headers = {"User-Agent": user_agent or "SiteChangeMonitorLite/1.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    html = r.text

    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts/styles/noscript
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""
    text = soup.get_text(" ", strip=True)
    text = normalize_text(text)

    return title, text


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def write_static_assets() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    css = """\
:root { color-scheme: dark; }
body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
       margin: 0; background: #0b0f17; color: #e7eefc; }
a { color: #8ab4ff; }
.container { max-width: 980px; margin: 0 auto; padding: 24px; }
.card { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10);
        border-radius: 16px; padding: 16px 18px; margin: 14px 0; }
.kv { display: grid; grid-template-columns: 180px 1fr; gap: 10px; }
code, pre { background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.10);
           border-radius: 12px; }
pre { padding: 12px; overflow: auto; }
.badge { display:inline-block; padding: 4px 10px; border-radius: 999px;
         background: rgba(138,180,255,0.18); border: 1px solid rgba(138,180,255,0.35); }
.badge.ok { background: rgba(80, 200, 120, 0.18); border-color: rgba(80, 200, 120, 0.35); }
.badge.changed { background: rgba(255, 120, 120, 0.18); border-color: rgba(255, 120, 120, 0.35); }
.small { opacity: 0.85; font-size: 0.95rem; }
"""
    (ASSETS_DIR / "style.css").write_text(css, encoding="utf-8")


def write_robots() -> None:
    (ROOT / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")


def write_sitemap() -> None:
    # Minimal sitemap with relative URL. GitHub Pages will still crawl it.
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>./index.html</loc></url>
</urlset>
"""
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def render_html(site_title: str, target_url: str, page_title: str, status: str, run_at: str,
                prev_hash: str, cur_hash: str, diff_text: str, snippet: str) -> str:
    badge_class = "ok" if status == "No change detected" else "changed"
    safe_diff = diff_text
    safe_snippet = snippet

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{site_title}</title>
  <link rel="stylesheet" href="assets/style.css" />
</head>
<body>
  <div class="container">
    <h1>{site_title}</h1>
    <p class="small">Target: <a href="{target_url}">{target_url}</a></p>

    <div class="card">
      <div class="kv">
        <div>Status</div>
        <div><span class="badge {badge_class}">{status}</span></div>
        <div>Checked at</div>
        <div>{run_at} (UTC)</div>
        <div>Page title</div>
        <div>{page_title or "(no title found)"}</div>
        <div>Previous hash</div>
        <div><code>{prev_hash or "-"}</code></div>
        <div>Current hash</div>
        <div><code>{cur_hash}</code></div>
      </div>
    </div>

    <div class="card">
      <h2>Current snippet</h2>
      <p class="small">First ~500 characters of the extracted text.</p>
      <pre>{safe_snippet}</pre>
    </div>

    <div class="card">
      <h2>Diff (previous → current)</h2>
      <p class="small">Unified diff of extracted text (limited). If this is empty and status is "No change",
      the content matched the previous run.</p>
      <pre>{safe_diff}</pre>
    </div>

    <p class="small">Generated by Site Change Monitor (Lite) via GitHub Actions.</p>
  </div>
</body>
</html>
"""


def build_diff(prev: str, cur: str, max_lines: int = 200) -> str:
    prev_lines = prev.splitlines()
    cur_lines = cur.splitlines()
    diff = difflib.unified_diff(prev_lines, cur_lines, fromfile="previous", tofile="current", lineterm="")
    out = []
    for i, line in enumerate(diff):
        if i >= max_lines:
            out.append("... (diff truncated)")
            break
        out.append(line)
    return "\n".join(out)


def selftest(cfg: dict) -> int:
    url = cfg.get("target_url", "")
    if not (url.startswith("http://") or url.startswith("https://")):
        eprint("Selftest failed: target_url must start with http:// or https://")
        return 1
    # create dirs
    try:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        eprint(f"Selftest failed: cannot create directories: {ex}")
        return 1
    print("Selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="Validate config and environment.")
    args = ap.parse_args()

    try:
        cfg = load_config()
    except Exception as ex:
        eprint(str(ex))
        return 1

    if args.selftest:
        return selftest(cfg)

    site_title = cfg.get("site_title", "Site Change Monitor (Lite)")
    target_url = cfg["target_url"]
    ua = cfg.get("user_agent", "SiteChangeMonitorLite/1.0")
    max_chars = int(cfg.get("max_text_chars", 20000))

    state = load_state()
    prev_text = state.get("last_text", "")
    prev_hash = state.get("last_hash", "")

    try:
        page_title, cur_text = fetch_page_text(target_url, ua)
    except Exception as ex:
        eprint(f"Fetch failed: {ex}")
        return 1

    cur_text = cur_text[:max_chars]
    cur_hash = sha256(cur_text)

    changed = (prev_hash != "" and cur_hash != prev_hash)
    status = "Change detected" if changed else "No change detected"
    run_at = datetime.datetime.utcnow().replace(microsecond=0).isoformat()

    # snippet & diff
    snippet = cur_text[:500]
    if prev_text:
        diff_text = build_diff(prev_text[:5000], cur_text[:5000], max_lines=220)
    else:
        diff_text = "(no previous snapshot yet — run once more to compare)"

    write_static_assets()
    write_robots()
    write_sitemap()

    html = render_html(
        site_title=site_title,
        target_url=target_url,
        page_title=page_title,
        status=status,
        run_at=run_at,
        prev_hash=prev_hash,
        cur_hash=cur_hash,
        diff_text=diff_text,
        snippet=snippet
    )
    (ROOT / "index.html").write_text(html, encoding="utf-8")

    # update state
    state_out = {
        "target_url": target_url,
        "last_checked_utc": run_at,
        "last_hash": cur_hash,
        "last_title": page_title,
        "last_text": cur_text,
    }
    save_state(state_out)

    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
