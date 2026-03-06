import argparse

from gun_bot import run_forever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continuously scan GunsArizona for matching listings."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the JSON config file. Defaults to config.json.",
    )
    parser.add_argument(
        "--seen-file",
        default="seen_ads.json",
        help="Path to the JSON file used to track already-notified ads.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override the check interval in minutes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches instead of sending Telegram messages.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_forever(
            config_path=args.config,
            seen_path=args.seen_file,
            interval_override=args.interval,
            dry_run=args.dry_run,
        )
    )
