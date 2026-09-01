import json
import os
import sys
from playwright.sync_api import sync_playwright
import requests

SLACK_WEBHOOK = os.environ["SLACK_WEBHOOK"]
SLACK_TAG = "<@U0BDSG0NF7B>"
STATE_FILE = "state.json"

PAGES = {
    "Summer Internships": "https://app.the-trackr.com/uk-tech/summer-internships",
    "Industrial Placements": "https://app.the-trackr.com/uk-tech/industrial-placements",
}


def extract_lines(page, url):
    page.goto(url, wait_until="networkidle", timeout=60000)
    # Extra wait for JS to finish rendering
    page.wait_for_timeout(3000)

    text = page.inner_text("body")
    lines = [line.strip() for line in text.splitlines()]
    # Keep only meaningful lines (skip short/empty ones like nav items, icons, etc.)
    lines = [l for l in lines if len(l) > 15]
    return lines


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def notify_slack(message):
    resp = requests.post(SLACK_WEBHOOK, json={"text": message})
    resp.raise_for_status()


def main():
    state = load_state()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()

        for name, url in PAGES.items():
            print(f"Checking {name}...")

            current_lines = extract_lines(pg, url)
            current_set = set(current_lines)

            old_lines = state.get(name, {}).get("lines", [])
            old_set = set(old_lines)

            if not old_set:
                print(f"  First run — saving baseline ({len(current_lines)} lines)")
            else:
                new_items = current_set - old_set
                if new_items:
                    items_text = "\n".join(f"• {item}" for item in sorted(new_items))
                    message = (
                        f"{SLACK_TAG} :new: *New content on Trackr — {name}*\n"
                        f"<{url}|View listings>\n\n"
                        f"{items_text}"
                    )
                    notify_slack(message)
                    print(f"  Notified Slack: {len(new_items)} new item(s)")
                else:
                    notify_slack(f"{SLACK_TAG} :white_check_mark: *{name}* — no new listings in the last 15 mins.")
                    print(f"  No changes")

            state[name] = {"lines": current_lines}

        browser.close()

    save_state(state)


if __name__ == "__main__":
    main()
