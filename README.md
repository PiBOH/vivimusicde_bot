# vivimusicde_bot
[![Upload Release to Telegram](https://github.com/PiBOH/vivimusicde_bot/actions/workflows/upload-release.yml/badge.svg)](https://github.com/PiBOH/vivimusicde_bot/actions/workflows/upload-release.yml)

Source code for the **@vivimusicde_bot** — the bot that posts VIVI Music DE
release assets to the [https://t.me/vivimusicde](https://t.me/vivimusicde)
channel. Its behaviour mirrors the original bot by vivizzz007: a GitHub
Actions workflow grabs the latest release from `PiBOH/vivi-music-de` (resolved
by publish date, not by comparing tag strings) and posts it to the channel
through the Telegram Bot API.

## What it does

- Fetches the latest release (or a specific tag) from `PiBOH/vivi-music-de`.
- Downloads every asset **except `*.log` and `*.install`** (the Inno Setup log
  and, defensively, the AUR hook — which no longer shows up in a release: the
  AUR files now ship together in `VIVIMusic-<version>-AUR.tar.gz`).
- Groups the download links by platform, including the native **Fedora/RHEL
  `.rpm`** and the Arch/AUR archive, next to the `.deb`, AppImage, Windows and
  macOS installers.
- Uploads the assets to `@vivimusicde` with a **single caption per release**
  (version, files, total size, link to the release), in the same style as the
  original bot.
- Deduplicates: each release tag is posted at most once (a cache marker per
  tag), so manual re-runs or overlapping triggers never double-post.

## Custom Android APK

The APKs are **not** release assets any more: `Build Android APK` publishes
`vivi-gms.apk`, `vivi-foss.apk` and a `version.json` to `.releases/apk/latest`
on the `apk-latest` branch. The bot does not post them by default; a **manual**
run can toggle `include_custom_apk` on and it appends the two fixed links
(sizes read from that `version.json` when reachable).

## How it is triggered

| Trigger | When |
|---|---|
| dispatch from `vivi-music-de` | The moment `Auto Release` publishes a release (`notify-bot` job → `gh workflow run`, with the tag). This is the normal path and it posts within seconds. |
| `schedule` | Hourly *poll*, a backstop only: it catches a release the dispatch missed (a token without access to this repo, a manual release, an outage). |
| `workflow_dispatch` | Manual run from the Actions tab (`release_tag`, `force_ignore_cache`, `include_custom_apk`) |

The poll asks for every hour but **must not be relied on for punctuality**. GitHub's
scheduler is best-effort and this repository was only getting roughly one run
every **3–5 hours** with `0 * * * *` (the top of the hour is the most congested
moment, and public repositories are the most affected). The cron was therefore
moved to an off-minute, but the real fix is the dispatch above: the release knows
it happened, so the bot does not have to poll to find out.

Every trigger is safe to repeat: the per-tag dedupe cache means a tag is posted
at most once, so a dispatch and a poll can never double-post the same release.

## Weekly code backup

`code-backup.yml` tags and publishes a patch release every Monday as a
**backup of this repository's source** — the same shape as the `code backup`
releases it already carried by hand (tag `1.0.x`, title `v1.0.x`, body
`code backup`). It is not a release of anything: nothing is built and no assets
are attached, so the release is purely a restorable snapshot
(`git checkout 1.0.7`). The patch number is derived from the highest existing
`1.x.y` tag, and a week with no new commits is skipped instead of tagging the
same commit twice.

## Setup

1. **Bot token**: create the bot with [@BotFather](https://t.me/BotFather),
   then add the bot as **administrator** of the `@vivimusicde` channel
   (Settings → Administrators → Add admin → pick the bot).
2. **Secrets** in the repository (Settings → Secrets and variables → Actions):
   - `TELEGRAM_BOT_TOKEN` — the token from BotFather (required).
   - `TELEGRAM_CHAT_ID` — the channel id. For a public channel you can use
     `@vivimusicde`; for a private channel use the numeric id (e.g.
     `-1001234567890`). If unset, the bot defaults to `@vivimusicde`.
   - `TELEGRAM_THREAD_ID` — optional, only if the channel uses forum topics.

## Run locally (test)

```bash
export TELEGRAM_BOT_TOKEN="<token>"
export TELEGRAM_CHAT_ID="@vivimusicde"
# optional: export RELEASE_TAG="v6.4.41_DE-1.41.15-nightly"
python3 bot.py
```

No third-party dependencies — only the Python standard library.

## Files

- `bot.py` — the bot logic (fetch release → download assets → upload).
- `.github/workflows/upload-release.yml` — the GitHub Actions workflow.
- `icon.png` / `logo.jpg` — channel artwork.
