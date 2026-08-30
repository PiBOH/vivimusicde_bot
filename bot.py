#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upload VIVI Music DE release assets to the Telegram channel.

Mirrors the behaviour of the original Vivi Music bot (vivizzz007): a
GitHub Actions workflow downloads the release and posts it to the channel
through the Bot API, with one HTML caption per release (not per asset).

Excluded assets: *.log and *.apk (the setup log and the mobile APK).

Environment variables:
  TELEGRAM_BOT_TOKEN  Bot token from @BotFather (required)
  TELEGRAM_CHAT_ID    Channel to post to (default: @vivimusicde)
  TELEGRAM_THREAD_ID  Optional message_thread_id for forum topics
  SOURCE_REPO         GitHub repo whose releases we post (default: PiBOH/vivi-music)
  RELEASE_TAG         Optional: a specific tag to post (default: latest)

Exit code is 0 only if every asset was posted successfully.
"""

import os
import re
import sys
import json
import time
import uuid
import urllib.parse
import urllib.request
import urllib.error

SOURCE_REPO = os.environ.get("SOURCE_REPO", "PiBOH/vivi-music")
RELEASE_TAG = (os.environ.get("RELEASE_TAG") or "").strip()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "@vivimusicde"
THREAD_ID = (os.environ.get("TELEGRAM_THREAD_ID") or "").strip()

EXCLUDED_SUFFIXES = (".log", ".apk")
API_BASE = "https://api.github.com/repos/" + SOURCE_REPO
TG_BASE = "https://api.telegram.org/bot" + BOT_TOKEN

MIME_BY_EXT = {
    ".exe": "application/x-msdownload",
    ".msi": "application/x-msdownload",
    ".deb": "application/vnd.debian.binary-package",
    ".appimage": "application/x-elf",
    ".dmg": "application/x-apple-diskimage",
    ".pkg": "application/x-newton-compatible-pkg",
    ".zip": "application/zip",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".b64": "text/plain",
    ".json": "application/json",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
}


def github_json(url, timeout=60):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "vivimusicde_bot"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def version_parts(tag):
    match = re.findall(r"\d+(?:\.\d+)*", str(tag or ""))
    if not match:
        return []
    return [int(n) for n in ".".join(match).split(".")]


def by_version_desc(a, b):
    pa, pb = version_parts(a.get("tag_name")), version_parts(b.get("tag_name"))
    length = max(len(pa), len(pb))
    for i in range(length):
        av = pa[i] if i < len(pa) else 0
        bv = pb[i] if i < len(pb) else 0
        if av != bv:
            return bv - av
    return 0


def get_release():
    if RELEASE_TAG:
        return github_json(API_BASE + "/releases/tags/" + urllib.parse.quote(RELEASE_TAG))
    # /releases/latest only resolves non-prerelease releases, but every VIVI
    # Music DE release carries a channel suffix (e.g. -nightly) and is a
    # pre-release. So we list all releases and pick the one with the highest
    # version in its tag, exactly like the website does.
    releases = github_json(API_BASE + "/releases?per_page=30")
    released = [r for r in releases if not r.get("draft")]
    if not released:
        raise RuntimeError("No published releases found in " + SOURCE_REPO)
    released.sort(key=lambda r: version_parts(r.get("tag_name")))
    return released[-1]


def is_excluded(name):
    lowered = name.lower()
    return lowered.endswith(EXCLUDED_SUFFIXES)


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"


def build_caption(release, assets):
    tag = release.get("tag_name") or ""
    name = release.get("name") or tag
    release_url = release.get("html_url") or (API_BASE + "/releases/tag/" + tag)
    total_bytes = sum(a.get("size", 0) for a in assets)
    formats = ", ".join(sorted({a["name"].rsplit(".", 1)[-1].lower() for a in assets}))

    lines = [
        "🎧 <b>ViviMusic DE — New Release</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "💻 <b>Version:</b> <code>{}</code>".format(tag or name),
        "📦 <b>Files:</b> {} ({})".format(len(assets), formats),
        "📁 <b>Total size:</b> {}".format(human_size(total_bytes)),
        "🔗 <b>Release:</b> <a href=\"{}\">{}</a>".format(release_url, tag or name),
        "━━━━━━━━━━━━━━━━━━━━",
        "🚀 <i>Compiled automatically with the latest updates!</i>",
    ]
    return "\n".join(lines)


def tg_api(method, fields):
    payload = []
    boundary = "------------------------" + uuid.uuid4().hex
    files = []

    def add_field(name, value):
        payload.append(
            "--{}\r\nContent-Disposition: form-data; name=\"{}\"\r\n\r\n{}\r\n".format(
                boundary, name, value
            ).encode("utf-8")
        )

    for key, value in fields.items():
        if isinstance(value, dict):  # file upload
            files.append((key, value))
        else:
            add_field(key, value)

    for key, file_info in files:
        file_header = (
            "--{}\r\n"
            'Content-Disposition: form-data; name="{}"; filename="{}"\r\n'
            "Content-Type: {}\r\n\r\n"
        ).format(boundary, key, file_info["filename"], file_info["content_type"]).encode("utf-8")
        payload.append(file_header + file_info["data"] + b"\r\n")
    payload.append(("--{}--\r\n".format(boundary)).encode("utf-8"))

    body = b"".join(payload)
    req = urllib.request.Request(
        TG_BASE + "/" + method,
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_document(file_bytes, filename, content_type, caption=None):
    fields = {"chat_id": CHAT_ID, "parse_mode": "HTML"}
    if THREAD_ID:
        fields["message_thread_id"] = THREAD_ID
    if caption:
        fields["caption"] = caption
    fields["document"] = {
        "filename": filename,
        "content_type": content_type,
        "data": file_bytes,
    }
    return tg_api("sendDocument", fields)


MAX_DOCUMENT_BYTES = 50 * 1024 * 1024  # Telegram Bot API upload limit per document

# Only these assets are attached as files; every other asset is posted as a
# download link (the bot API caps uploads, and the installers are huge).
ATTACHED_NAMES = {"INSTALL-GUIDE.md"}


def send_message(text):
    fields = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if THREAD_ID:
        fields["message_thread_id"] = THREAD_ID
    return tg_api("sendMessage", fields)


def os_for_asset(name):
    """Return the target OS label for a release asset based on its format."""
    lowered = (name or "").lower()
    if lowered.endswith(".exe") or lowered.endswith(".msi"):
        return "Windows 10+"
    if lowered.endswith(".deb"):
        return "Debian/Ubuntu"
    if lowered.endswith(".appimage"):
        return "Linux (AppImage)"
    if "pkgbuild" in lowered:
        return "Arch Linux (AUR)"
    if "srcinfo" in lowered:
        return "Arch Linux (AUR)"
    if lowered.endswith(".dmg") or lowered.endswith(".pkg"):
        return "macOS"
    if lowered.endswith(".md") or lowered.endswith(".txt"):
        return "Guide"
    return ""


def post_assets(release, assets):
    failures = 0
    to_attach = [
        a for a in assets
        if a["name"] in ATTACHED_NAMES and a.get("size", 0) <= MAX_DOCUMENT_BYTES
    ]
    to_link = [a for a in assets if a not in to_attach]
    caption = build_caption(release, assets) if assets else None

    for asset in to_attach:
        filename = asset["name"]
        url = asset["browser_download_url"]
        ext = "." + (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
        content_type = MIME_BY_EXT.get(ext, "application/octet-stream")

        print("Downloading {} ({} bytes)...".format(filename, asset.get("size", "?")))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vivimusicde_bot"})
            with urllib.request.urlopen(req, timeout=900) as resp:
                data = resp.read()
        except Exception as e:
            print("ERROR downloading {}: {}".format(filename, e))
            failures += 1
            continue

        posted = False
        for attempt in (1, 2):
            try:
                print("Uploading {} ({} bytes)...".format(filename, len(data)))
                result = send_document(data, filename, content_type, caption)
                if result.get("ok"):
                    print("OK: {}".format(filename))
                    posted = True
                    break
                raise RuntimeError(result.get("description", "unknown error"))
            except Exception as e:
                print("Attempt {} failed for {}: {}".format(attempt, filename, e))
        if not posted:
            failures += 1
        time.sleep(1)

    if to_link:
        lines = ["📦 <b>Download links</b> (attached as files: {} only):".format(", ".join(sorted(ATTACHED_NAMES)))]
        for a in to_link:
            name = a["name"]
            size = human_size(a.get("size", 0))
            os_label = os_for_asset(name)
            suffix = "  ({})".format(os_label) if os_label else ""
            lines.append('• <a href="{}">{}</a> ({}){}'.format(
                a.get("browser_download_url", ""), name, size, suffix))
        print("Posting {} download links...".format(len(to_link)))
        try:
            result = send_message("\n".join(lines))
            if result.get("ok"):
                print("OK: posted {} download links".format(len(to_link)))
            else:
                print("ERROR posting download links: {}".format(result.get("description")))
                failures += 1
        except Exception as e:
            print("ERROR posting download links: {}".format(e))
            failures += 1

    if failures:
        print("DONE with {} failure(s)".format(failures))
        sys.exit(1)
    print("DONE: {} attached + {} link(s) posted".format(len(to_attach), len(to_link)))


def resolve_latest_tag():
    releases = github_json(API_BASE + "/releases?per_page=30")
    released = [r for r in releases if not r.get("draft")]
    if not released:
        raise RuntimeError("No published releases found in " + SOURCE_REPO)
    released.sort(key=lambda r: version_parts(r.get("tag_name")))
    return released[-1]["tag_name"]


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--resolve-tag":
        # Used by the workflow to pin the exact tag BEFORE the dedupe cache
        # check, so the cache key is never empty.
        print(resolve_latest_tag())
        sys.exit(0)
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is required")
        sys.exit(1)
    print("Fetching release (repo={}, tag={})...".format(SOURCE_REPO, RELEASE_TAG or "latest"))
    release = get_release()
    tag = release.get("tag_name") or "?"
    assets = [a for a in release.get("assets", []) if not is_excluded(a.get("name", ""))]
    excluded = [a["name"] for a in release.get("assets", []) if is_excluded(a.get("name", ""))]

    print("Release: {}".format(tag))
    print("Assets to post: {}".format([a["name"] for a in assets]))
    if excluded:
        print("Excluded: {}".format(excluded))
    if not assets:
        print("Nothing to post")
        sys.exit(0)

    post_assets(release, assets)


if __name__ == "__main__":
    main()
