# Trackr Monitor

Watches the [Trackr](https://app.the-trackr.com) UK tech internship and placement listings every 15 minutes and sends you a Slack message when anything new appears.

**Monitors:**
- UK Tech → Summer Internships
- UK Tech → Industrial Placements

---

## How it works

- A cron service (cron-job.org) triggers a GitHub Actions workflow every 15 minutes
- The workflow uses a headless browser to load both Trackr pages
- It compares the current listings against the last saved state
- If anything new appears, it pings you on Slack with the details
- If nothing changed, it sends a quick confirmation message so you know it's still running

---

## Setup (takes ~10 minutes)

### 1. Fork this repo

Click **Fork** at the top right of this page. Keep it public (required for free unlimited GitHub Actions minutes).

### 2. Create a Slack Incoming Webhook

1. Go to your Slack workspace → **Apps** → search **Incoming Webhooks** → Add to Slack
2. Pick a channel → click **Add Incoming WebHooks Integration**
3. Copy the webhook URL (looks like `https://hooks.slack.com/services/...`)

### 3. Add your Slack webhook to GitHub

In your forked repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|---|---|
| `SLACK_WEBHOOK` | your webhook URL from step 2 |

### 4. Add your Slack user ID to the code

So the bot tags you in messages:

1. In Slack, click your profile picture → **Profile** → **three dots (...)** → **Copy member ID**
2. In your forked repo, edit `scraper.py` and replace `U0BDSG0NF7B` on this line with your own ID:
   ```python
   SLACK_TAG = "<@U0BDSG0NF7B>"
   ```

### 5. Create a GitHub Personal Access Token

1. Go to **github.com → Settings** (top right profile menu) → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **Generate new token (classic)**
3. Name it anything (e.g. `trackr-cron`)
4. Set expiration to **No expiration**
5. Tick only: `workflow`
6. Click **Generate token** and copy it — you won't see it again

### 6. Set up cron-job.org

1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. Click **Create cronjob** and fill in:

| Field | Value |
|---|---|
| Title | Trackr Monitor |
| URL | `https://api.github.com/repos/YOUR_GITHUB_USERNAME/trackr-monitor/actions/workflows/monitor.yml/dispatches` |
| Schedule | Every 15 minutes |
| Request method | `POST` |

3. Expand **Advanced** → **Headers** and add:

| Key | Value |
|---|---|
| `Authorization` | `Bearer YOUR_PAT_TOKEN` |
| `Accept` | `application/vnd.github+json` |

4. In **Request body** paste:
   ```json
   {"ref": "main"}
   ```

5. Make sure **Requires HTTP authentication** is toggled **off**

6. Save and enable the job

### 7. Run the baseline

In your forked repo → **Actions** → **Monitor Trackr** → **Run workflow**

This first run saves the current listings as a baseline (no Slack message sent). After this, every 15-minute run will compare against it and notify you of anything new.

---

## Testing

Hit **Run now** in cron-job.org. Within a minute you should get two Slack messages (one per page) confirming it's working.

---

## Security note

- Never commit your PAT token or Slack webhook URL to the repo
- Store them as GitHub Secrets and in cron-job.org only
- Rotate your PAT token periodically at GitHub → Settings → Developer settings → Tokens
