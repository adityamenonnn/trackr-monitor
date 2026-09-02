import json
import os
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
    page.wait_for_timeout(3000)

    text = page.inner_text("body")
    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if len(l) > 15]
    return lines


def format_listing(line):
    """Parse a tab-separated listing row into a readable Slack message block."""
    if "\t" not in line:
        return None
    parts = [p.strip() for p in line.split("\t")]
    company = parts[0] if len(parts) > 0 else ""
    role = parts[1] if len(parts) > 1 else ""
    opening = parts[2] if len(parts) > 2 else ""
    closing = parts[3] if len(parts) > 3 else ""

    if not company or not role:
        return None

    text = f"*{company}* — {role}"
    if opening:
        text += f"\n    Opens: {opening}"
    if closing:
        text += f"  |  Closes: {closing}"
    return text


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

                # Only keep lines that look like listing rows (contain tabs)
                new_listings = [item for item in new_items if "\t" in item]

                if new_listings:
                    formatted = [format_listing(l) for l in sorted(new_listings)]
                    formatted = [f for f in formatted if f]
                    items_text = "\n\n".join(f"• {f}" for f in formatted)
                    message = (
                        f"{SLACK_TAG} :new: *New listing(s) on Trackr — {name}*\n"
                        f"<{url}|View listings>\n\n"
                        f"{items_text}"
                    )
                    notify_slack(message)
                    print(f"  Notified Slack: {len(new_listings)} new listing(s)")
                else:
                    notify_slack(f":white_check_mark: *{name}* — no new listings in the last 30 mins.")
                    print(f"  No changes")

            state[name] = {"lines": current_lines}

        browser.close()

    save_state(state)


if __name__ == "__main__":
    main()
