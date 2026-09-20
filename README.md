# TikTok Auto Uploader

Uploads the next pending video from a local folder to **TikTok Studio** automatically using
Playwright, with a saved browser session, hashtag/caption support, upload-progress monitoring,
and archiving of posted files. Built to run daily via cron.

## Features

- **Persistent login** — one-time interactive login saves a Chromium profile (`.tiktok_profile`);
  subsequent uploads run fully headless.
- **Oldest-first queue** — processes the oldest video in the source folder (sorted by mtime).
- **Robust upload** — polls for the hidden `input[type="file"]` across the page and iframes,
  then selects the clip on TikTok Studio.
- **Caption & hashtags** — type-ahead fills caption and hashtag with per-keypress delays to
  trigger TikTok's suggestion dropdown, then confirms with Enter.
- **Progress-aware posting** — watches upload progress indicators, waits for the *Post* button to
  become enabled (processing finished), then posts.
- **Automatic archiving** — moved the uploaded video to an archive folder; skipped/failed runs
  leave the file in place.

## Tech stack

| Layer      | Technology                         |
|------------|-------------------------------------|
| Language   | Python 3                           |
| Browser    | Playwright (Chromium, persistent context) |
| Target     | TikTok Studio web (headless)       |
| Environ    | Linux server, cron-driven          |

## Installation

```bash
git clone <your-repo-url> tiktok_uploader
cd tiktok_uploader

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

### 1. First-time login (interactive)

```bash
python3 tiktok_uploader.py --login
```

A visible browser opens; log in, accept any CAPTCHAs, then return to the terminal and press
Enter. The session is saved to `~/.tiktok_profile` for future headless runs.

### 2. Upload

```bash
python3 tiktok_uploader.py \
    --source /path/to/videos \
    --archive /path/to/archive \
    --hashtag "#your_tag" \
    --caption "Caption text" \
    --headless \
    --timeout 1800
```

Options:

| Flag          | Default           | Description                                    |
|---------------|-------------------|------------------------------------------------|
| `--login`     | off               | Launch headful browser to link a session       |
| `--source`    | `video_automation/final` | Folder containing pending videos       |
| `--archive`   | (storage mount)   | Folder to move uploaded videos into            |
| `--hashtag`   | `#your_tag`       | Hashtag(s) appended to the caption             |
| `--caption`   | _empty_           | Caption prefix                                 |
| `--headless`  | off               | Run Chromium headless during upload            |
| `--timeout`   | `1200`            | Max upload/processing wait in seconds          |

### 3. Schedule (cron)

```cron
0 10 * * * cd /path/to/tiktok_uploader && venv/bin/python tiktok_uploader.py --headless >> uploader.log 2>&1
```

If the session expires, the script exits with a message telling you to re-run `--login`.

## Repository details

- **Short description**: `Headless TikTok Studio uploader with saved sessions, captions, hashtags, progress monitoring and archiving.`
- **Suggested topics**: `tiktok`, `automation`, `playwright`, `python`, `uploader`, `headless`, `cron`, `social-media`
- **License recommendation**: [MIT](https://opensource.org/licenses/MIT).
- **Security note**: `.gitignore` excludes `.tiktok_profile/`, session data, and logs — the
  saved browser session is effectively a credential and must never be committed.