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
    "SimplyTK": "https://simplytk.com/internship-tracker?programme=summer_internship%2Cindustrial_placement",
}


NOISE_PATTERNS = ["total views", "views today", "live uk openings"]

SIMPLYTK_PAGES = {"SimplyTK"}


def strip_posted_column(line):
    """Remove the last tab-separated field if it looks like a relative time (e.g. '4 hours ago')."""
    if "\t" not in line:
        return line
    parts = line.rsplit("\t", 1)
    if "ago" in parts[-1].lower():
        return parts[0]
    return line


def extract_lines(page, url, strip_posted=False):
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    # Scroll to bottom to trigger any lazy-loaded content
    prev_height = 0
    for _ in range(10):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
        curr_height = page.evaluate("document.body.scrollHeight")
        if curr_height == prev_height:
            break
        prev_height = curr_height

    text = page.inner_text("body")
    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if len(l) > 15]
    lines = [l for l in lines if not any(p in l.lower() for p in NOISE_PATTERNS)]
    if strip_posted:
        lines = [strip_posted_column(l) for l in lines]
    return lines


def format_listing(line, page_type="listing"):
    """Parse a tab-separated row into a readable Slack message block."""
    if "\t" not in line:
        return None
    parts = [p.strip() for p in line.split("\t")]
    company = parts[0] if len(parts) > 0 else ""
    name = parts[1] if len(parts) > 1 else ""

    if not company or not name:
        return None

    if page_type == "event":
        # Events: Company | Programme | Eligibility | Opening | Closing | Format | Event Date
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
    elif page_type == "simplytk":
        # SimplyTK: Company | Role | Programme | Location | Deadline (posted already stripped)
        programme = parts[2] if len(parts) > 2 else ""
        location = parts[3] if len(parts) > 3 else ""
        deadline = parts[4] if len(parts) > 4 else ""
        text = f"*{company}* — {name}"
        if programme:
            text += f" ({programme})"
        if location:
            text += f"\n    Location: {location}"
        if deadline and deadline != "·":
            text += f"  |  Deadline: {deadline}"
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

            is_simplytk = name in SIMPLYTK_PAGES
            current_lines = extract_lines(pg, url, strip_posted=is_simplytk)
            current_set = set(current_lines)

            old_lines = state.get(name, {}).get("lines", [])
            old_set = set(old_lines)

            if not old_set:
                print(f"  First run — saving baseline ({len(current_lines)} lines)")
            else:
                new_items = current_set - old_set

                # Only keep lines that look like actual listings (tab-separated)
                new_listings = [item for item in new_items if "\t" in item]

                if new_listings:
                    if name == "Events":
                        page_type = "event"
                    elif is_simplytk:
                        page_type = "simplytk"
                    else:
                        page_type = "listing"
                    formatted = [format_listing(l, page_type=page_type) for l in sorted(new_listings)]
                    formatted = [f for f in formatted if f]
                    items_text = "\n\n".join(f"• {f}" for f in formatted)
                    message = (
                        f"{SLACK_TAG} :new: *New listing(s) — {name}*\n"
                        f"<{url}|View page>\n\n"
                        f"{items_text}"
                    )
                    notify_slack(message)
                    print(f"  Notified Slack: {len(new_listings)} new listing(s)")
                else:
                    notify_slack(f":white_check_mark: *{name}* — no changes in the last 30 mins.")
                    print(f"  No changes")

            state[name] = {"lines": current_lines}

        browser.close()

    save_state(state)


if __name__ == "__main__":
    main()
