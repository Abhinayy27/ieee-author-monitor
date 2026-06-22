# IEEE Author Profile Monitor

An automated monitoring agent that tracks an IEEE Xplore author profile for new publications and sends an email notification when the publication count increases.

## Overview

This project uses GitHub Actions to automatically check the IEEE Xplore author profile twice daily (00:00 and 12:00 UTC). When a new publication is detected, it sends an email notification and updates its state to track the new count.

**Target Page:** https://ieeexplore.ieee.org/author/113479857928040

**Email Recipient:** babhinay27@gmail.com

## How It Works

1. **Scheduled Execution**: GitHub Actions runs the monitoring script twice daily at **00:00 UTC (midnight)** and **12:00 UTC (noon)**
2. **State Check**: The script loads `state.json` with the last known publication count and titles
3. **Page Fetching**: Uses **Playwright (headless browser)** to render JavaScript content and fetch the author profile. Falls back to `requests` if Playwright fails.
4. **Count Extraction**: Parses the **Publications** stat from the author profile page
5. **Detection**: Compares the current count to the stored count
6. **Notification**: If the count increased, sends an email via Gmail SMTP with the new publication title(s)
7. **State Update**: Updates `state.json` with the new count and commits it back to the repository

On the first run (or after a state reset), the script records the current count as a baseline without sending a notification.

## Setup Instructions

### 1. Clone or Fork This Repository

```bash
git clone <your-repo-url>
cd monitoring_agent
```

### 2. Set Up GitHub Secrets

Add two secrets to your GitHub repository:

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:

   - **Name:** `EMAIL_ADDRESS`
     - **Value:** Your Gmail address

   - **Name:** `EMAIL_APP_PASSWORD`
     - **Value:** Your Gmail App Password

### 3. Get Gmail App Password

1. Go to your Google Account settings: https://myaccount.google.com/
2. Navigate to **Security** → **2-Step Verification** (enable it if not already enabled)
3. Scroll down to **App passwords**
4. Generate a password for Mail
5. Use this as your `EMAIL_APP_PASSWORD` secret

### 4. Test the Workflow

1. Go to **Actions** tab in your repository
2. Select **IEEE Author Profile Monitor** workflow
3. Click **Run workflow** → **Run workflow**

## Configuration

### Changing the Schedule

Edit `.github/workflows/monitor.yml`:

```yaml
schedule:
  - cron: '0 */12 * * *'  # Twice daily at 00:00 and 12:00 UTC
```

### Modifying Target URL or Email Recipient

Edit `checker.py`:

```python
TARGET_URL = "https://ieeexplore.ieee.org/author/113479857928040"
RECIPIENT_EMAIL = "babhinay27@gmail.com"
```

## File Structure

```
monitoring_agent/
├── checker.py                 # Main monitoring script
├── requirements.txt           # Python dependencies
├── state.json                 # State tracking (git-tracked, auto-updated)
├── README.md                  # This file
└── .github/
    └── workflows/
        └── monitor.yml        # GitHub Actions workflow definition
```

## State Management

The `state.json` file tracks the last known publication count and titles:

```json
{
  "publication_count": 1,
  "publication_titles": [
    "Stacked Ensemble-Based Classification Model for Breast Cancer Diagnosis..."
  ]
}
```

When a new publication is detected, the count and titles are updated and committed back to the repository.

## Technical Details

### Dependencies
- **requests**: HTTP fallback
- **beautifulsoup4**: HTML parsing
- **lxml**: Parser backend for BeautifulSoup
- **playwright**: Headless browser for JavaScript rendering

### Detection Logic
The script reads the publication count from `div.publications.col-12 div.pub-citation-count` on the author profile page and compares it to the stored value. It also extracts publication titles from document links to include in the notification email.

## Troubleshooting

### Email Not Sending
- Verify `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` secrets are set correctly
- Check GitHub Actions logs for error messages

### Script Not Finding Publication Count
- IEEE Xplore pages are JavaScript-rendered; Playwright must be installed
- Check logs for "Could not find publications section on page"
- If the page structure changes, update the parsing logic in `checker.py`

### No Notification on First Run
- This is expected. The first run establishes a baseline count without notifying.
- You will be notified when the count increases above the baseline.

## License

This project is provided as-is for personal use. Please respect IEEE Xplore's terms of service and use responsibly.
