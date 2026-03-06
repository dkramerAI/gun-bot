# GunsArizona Bot

This bot scans GunsArizona firearm listings, filters them by your keywords, and sends Telegram alerts for new matches.

## What changed

The old GitHub Actions path depended on Selenium, Chrome, and `webdriver-manager` every run. The site currently serves the listing HTML directly, so the bot now uses a single shared scraper based on `urllib` + BeautifulSoup. That removes the browser dependency and makes local runs and Actions runs much less brittle.

## Files

- `run_once.py`: run a single scan
- `main.py`: run continuously with a sleep loop between scans
- `config.example.json`: sample config you can copy to `config.json`
- `seen_ads.json`: list of ad IDs that have already triggered alerts

## GitHub Actions setup

1. Push this repo to GitHub.
2. Add these repository secrets:

| Name | Value |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Telegram chat ID |

3. Optional: copy `config.example.json` to `config.json`, change the keywords or interval, and commit it.
4. Enable Actions in the repo.
5. The workflow runs every 5 minutes and commits `seen_ads.json` back when new alerts are sent.

`PAT_TOKEN` is no longer required. The workflow uses the default `GITHUB_TOKEN` with `contents: write`.

## Local usage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
python run_once.py --dry-run
```

The `--dry-run` flag prints matches instead of sending Telegram messages or updating `seen_ads.json`.

To run continuously:

```bash
python main.py
```

Useful flags:

- `python run_once.py --config config.json --seen-file seen_ads.json`
- `python main.py --interval 10`
- `python run_once.py --dry-run`

## Config

`config.json` supports:

```json
{
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "check_interval_minutes": 5,
  "keywords": [
    "Daniel Defense",
    "Glock 19",
    "Glock 43X",
    "Sig P365"
  ]
}
```

Environment variables override the file:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GUN_BOT_KEYWORDS` as a comma-separated list
- `CHECK_INTERVAL_MINUTES`

## Notes

- Alerts are only marked as seen after a Telegram message is sent successfully.
- If Telegram is not configured, matches are printed to stdout and left unseen.
- `run_once.py` and `main.py` now use the same scraper logic, so local runs and GitHub Actions behave the same way.
