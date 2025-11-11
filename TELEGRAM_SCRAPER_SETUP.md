# Telegram Scraper Setup Guide

## Overview

The Telegram scraper uses **Telethon** (user-bot client) to scrape public channels and groups. It downloads media files and uploads them to S3 for storage.

## Prerequisites

1. **Telegram API credentials** from https://my.telegram.org/apps
2. **AWS S3 bucket** for media storage
3. **Telethon** and **boto3** installed (already in requirements.txt)

## Step 1: Get Telegram API Credentials

### 1.1 Go to https://my.telegram.org/apps

### 1.2 Login with your phone number

### 1.3 Create a new application:
- **App title**: AI-SMM Scraper
- **Short name**: aismm
- **Platform**: Other
- **Description**: Content scraper for AI-SMM

### 1.4 Copy your credentials:
- **api_id**: 12345678
- **api_hash**: abcdef1234567890abcdef1234567890

## Step 2: Configure Environment Variables

Add to `.env`:

```bash
# Telegram Scraper (Telethon)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_SESSION_NAME=aismm_scraper
```

## Step 3: Setup AWS S3

### 3.1 Create S3 Bucket

```bash
aws s3 mb s3://aismm-media --region us-east-1
```

### 3.2 Configure bucket policy for public access (optional):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::aismm-media/*"
    }
  ]
}
```

### 3.3 Add AWS credentials to `.env`:

```bash
# AWS S3 for Media Storage
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_S3_BUCKET=aismm-media
AWS_S3_REGION=us-east-1
```

## Step 4: First Run (Session Authentication)

On the first run, Telethon will create a session file and may ask for phone verification:

```bash
# Run in Docker or locally
python -c "from scrapers.telegram import TelegramScraper; import asyncio; asyncio.run(TelegramScraper('https://t.me/channel').verify())"
```

**You may be prompted to:**
1. Enter your phone number: `+1234567890`
2. Enter verification code: `12345`
3. Enter 2FA password (if enabled)

**Session file location:**
- The session will be saved as `aismm_scraper.session`
- This file contains authentication data and should NOT be committed to git
- Add `*.session` to `.gitignore`

## Step 5: Verify Setup

Test the scraper with a public channel:

```bash
curl -X POST http://localhost:8000/sources/verify \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "telegram",
    "url": "https://t.me/durov"
  }'
```

Expected response:
```json
{
  "handle": "@durov",
  "accessible": true,
  "private": false,
  "post_count": 150,
  "normalized_url": "https://t.me/durov",
  "message": "Channel verified: 150 posts",
  "recommendations": []
}
```

## Features

### ✅ Supported

- **Public channels** - scrape any public Telegram channel
- **Message text** - full post content
- **Photos** - download and upload to S3
- **Videos** - download (up to 50MB) and upload to S3
- **Metrics**:
  - Views count
  - Forwards count
  - Comments/replies count
- **URL formats**:
  - `https://t.me/channel`
  - `t.me/channel`
  - `@channel`
  - `channel`

### ❌ Not Supported (yet)

- Private channels (requires invitation/access)
- Groups (can be added easily)
- Stories
- Polls
- Large videos (>50MB) - skipped to avoid memory issues

## Architecture

```
┌──────────────────┐
│  TelegramScraper │
└────────┬─────────┘
         │
         ├─→ verify() ────→ Check channel accessibility
         │                  Get post count
         │                  Detect private status
         │
         └─→ scrape() ────→ Fetch last N messages (default: 200)
                            │
                            ├─→ Download photos ──→ Upload to S3
                            ├─→ Download videos ──→ Upload to S3
                            │
                            └─→ Return normalized posts
```

## Media Storage

Media files are stored in S3 with the following structure:

```
s3://aismm-media/
  └── telegram/
      └── channel_name/
          ├── abc123.jpg    (photo)
          ├── def456.jpg    (photo)
          └── xyz789.mp4    (video)
```

**File naming:**
- Random UUID to prevent collisions
- Original file extension preserved
- Content-Type detected automatically

## Rate Limits

Telegram has rate limits for API requests:

- **Verification**: ~30 requests/minute
- **Message fetching**: ~20 requests/minute
- **Media download**: Depends on file size

**Best practices:**
- Add delays between requests
- Use batch operations when possible
- Handle `FloodWaitError` with exponential backoff

## Error Handling

The scraper handles common errors:

| Error | Description | Action |
|-------|-------------|--------|
| `ChannelPrivateError` | Channel is private | Return `CLOSED` status |
| `ChannelInvalidError` | Channel doesn't exist | Return `INVALID_URL` status |
| `UsernameNotOccupiedError` | Username not found | Return `INVALID_URL` status |
| `FloodWaitError` | Rate limit exceeded | Wait and retry |

All errors are logged with only error type (security: no PII in logs).

## Security

### ✅ Safe

- **Logs**: Only error types, no URLs or content
- **Session file**: Encrypted by Telethon
- **S3 URLs**: Stored as `s3://...` not HTTPS
- **Raw field**: Empty `{}` (no full message data)

### ⚠️ Important

- **DO NOT** commit `.session` files
- **DO NOT** log full error messages (may contain URLs)
- **DO NOT** store user handles in logs (PII)

Add to `.gitignore`:
```
*.session
*.session-journal
```

## Troubleshooting

### Issue: "Telegram API credentials not configured"

**Solution**: Check `.env` file has `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`

### Issue: "Channel is private or unavailable"

**Solution**:
1. Check if channel is public
2. Verify you have access to the channel
3. Try with a different channel (e.g., `@durov`)

### Issue: "AWS credentials not configured"

**Solution**:
1. Create AWS IAM user with S3 access
2. Add credentials to `.env`
3. Test with: `aws s3 ls s3://aismm-media/`

### Issue: "FloodWaitError: A wait of X seconds is required"

**Solution**:
- Telegram is rate limiting your requests
- Wait X seconds before retrying
- Reduce scraping frequency

### Issue: "Session file permission denied"

**Solution**:
```bash
chmod 600 *.session
```

## Testing

### Test verification:

```python
from scrapers.telegram import TelegramScraper
import asyncio

async def test():
    scraper = TelegramScraper("https://t.me/durov")
    result = await scraper.verify()
    print(result)

asyncio.run(test())
```

### Test scraping:

```python
from scrapers.telegram import TelegramScraper
import asyncio

async def test():
    scraper = TelegramScraper("https://t.me/durov")
    posts = await scraper.scrape(limit=10)
    print(f"Scraped {len(posts)} posts")
    for post in posts[:3]:
        print(f"- {post['text'][:50]}...")

asyncio.run(test())
```

## Production Checklist

- [ ] Telegram API credentials configured
- [ ] AWS S3 bucket created and configured
- [ ] `.session` files in `.gitignore`
- [ ] Session file created (first run authentication)
- [ ] Tested with public channel
- [ ] Error handling verified
- [ ] Rate limits configured
- [ ] Monitoring/logging setup
- [ ] Backup session file (encrypted)

## Resources

- Telethon documentation: https://docs.telethon.dev/
- Telegram API: https://my.telegram.org/apps
- AWS S3 docs: https://docs.aws.amazon.com/s3/
