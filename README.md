# vivimusicde_bot

Source code for the **@vivimusicde_bot** — the bot that posts VIVI Music DE
release assets to the [https://t.me/vivimusicde](https://t.me/vivimusicde)
channel. Its behaviour mirrors the original bot by vivizzz007: a GitHub
Actions workflow grabs the latest release from `PiBOH/vivi-music` and uploads
its assets to the channel through the Telegram Bot API.

## What it does

- Fetches the latest release (or a specific tag) from `PiBOH/vivi-music`.
- Downloads every asset **except `*.log` and `*.apk`** (the Inno Setup log and
  the mobile APK are skipped).
- Uploads the assets to `@vivimusicde` with a **single caption per release**
  (version, files, total size, link to the release), in the same style as the
  original bot.
- Deduplicates: each release tag is posted at most once (a cache marker per
  tag), so manual re-runs or overlapping triggers never double-post.

## How it is triggered

| Trigger | When |
|---|---|
| `repository_dispatch` | A `release-published` dispatch sent by `PiBOH/vivi-music`'s `auto-release.yml` right after a release is created (instant) |
| `schedule` | Hourly fallback poll in case the dispatch is not configured |
| `workflow_dispatch` | Manual run from the Actions tab (optional `release_tag` input) |

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
3. **Instant trigger (optional)**: in `PiBOH/vivi-music`, add the secret
   `BOT_DISPATCH_TOKEN` (a PAT with `repo` + `workflow` scope). The
   `auto-release.yml` there will send the dispatch automatically after each
   release. Without it, the hourly poll still covers everything (up to 60
   minutes delay).

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
