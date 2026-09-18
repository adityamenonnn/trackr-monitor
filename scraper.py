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
    "Events": "https://app.the-trackr.com/uk-tech/events",
}

NOISE_PATTERNS = ["total views", "views today"]


def extract_rows(page, url, debug=False):
    """Extract only tab-separated table rows from the page."""
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    text = page.inner_text("body")

    if debug:
        # Dump lines around any mention of BAE for debugging
        all_lines = text.splitlines()
        for i, l in enumerate(all_lines):
            if "bae" in l.lower():
                start = max(0, i - 2)
                end = min(len(all_lines), i + 5)
                for j in range(start, end):
                    print(f"  DEBUG [{j}]: {repr(all_lines[j])}")

    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if "\t" in l]
    lines = [l for l in lines if not any(p in l.lower() for p in NOISE_PATTERNS)]
    return lines


def format_listing(line, is_event=False):
    """Parse a tab-separated listing row into a readable Slack message block."""
    parts = [p.strip() for p in line.split("\t")]
    company = parts[0] if len(parts) > 0 else ""
    name = parts[1] if len(parts) > 1 else ""

    if not company or not name:
        return None

    if is_event:
        opening = parts[3] if len(parts) > 3 else ""
        closing = parts[4] if len(parts) > 4 else ""
        fmt = parts[5] if len(parts) > 5 else ""
        event_date = parts[6] if len(parts) > 6 else ""
        text = f"*{company}* — {name}"
        if event_date:
            text += f"\n    Event: {event_date}"
        if fmt:
            text += f" ({fmt})"
        if opening:
            text += f"\n    Apply: {opening}"
        if closing:
            text += f" to {closing}"
    else:
        opening = parts[2] if len(parts) > 2 else ""
        closing = parts[3] if len(parts) > 3 else ""
        text = f"*{company}* — {name}"
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

            current_lines = extract_rows(pg, url, debug=(name == "Industrial Placements"))
            current_set = set(current_lines)

            old_lines = state.get(name, {}).get("lines", [])
            old_set = set(old_lines)

            if not old_set:
                print(f"  First run — saving baseline ({len(current_lines)} rows)")
                for l in current_lines[:5]:
                    print(f"    SAMPLE: {repr(l)}")
            else:
                new_listings = current_set - old_set

                if new_listings:
                    is_event = name == "Events"
                    formatted = [format_listing(l, is_event=is_event) for l in sorted(new_listings)]
                    formatted = [f for f in formatted if f]
                    items_text = "\n\n".join(f"• {f}" for f in formatted)
                    message = (
                        f"{SLACK_TAG} :new: *New listing(s) on Trackr — {name}*\n"
                        f"<{url}|View page>\n\n"
                        f"{items_text}"
                    )
                    notify_slack(message)
                    print(f"  Notified Slack: {len(formatted)} new listing(s)")
                else:
                    notify_slack(f":white_check_mark: *{name}* — no new listings in the last 30 mins.")
                    print(f"  No changes")

            state[name] = {"lines": current_lines}

        browser.close()

    save_state(state)


if __name__ == "__main__":
    main()
