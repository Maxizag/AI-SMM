# Telegram Scraper Reliability Features

This document describes the reliability and error handling features in the Telegram scraper.

## Overview

The Telegram scraper includes robust error handling, retry mechanisms, timeout protection, and progress tracking to ensure reliable operation even under challenging conditions.

## Features

### 1. Automatic Retry with Exponential Backoff

All critical operations automatically retry on failures:

- **Network errors**: Retry with exponential backoff (1s, 2s, 4s)
- **Timeout errors**: Retry up to 3 times
- **Generic errors**: Retry without delay

```python
@retry_on_error(max_attempts=3, delay=1.0)
async def verify(self):
    # Automatically retries on failure
    pass
```

**Applied to:**
- `verify()` - Channel verification
- `scrape()` - Post scraping
- `_download_and_upload_photo()` - Photo downloads
- `_download_and_upload_video()` - Video downloads
- `_download_and_upload_document()` - Document downloads

### 2. FloodWaitError Handling

Telegram rate limits are handled gracefully:

```python
except FloodWaitError as e:
    wait_time = e.seconds
    if wait_time > 300:  # More than 5 minutes
        logger.warning(f"FloodWait too long ({wait_time}s), skipping")
        raise

    logger.info(f"FloodWait: waiting {wait_time}s")
    await asyncio.sleep(wait_time)
```

**Behavior:**
- Waits exactly as long as Telegram requires
- Skips operation if wait time exceeds 5 minutes
- Logs wait time for monitoring
- Automatically continues after wait

### 3. Timeout Protection

All network operations have timeouts to prevent hanging:

| Operation | Timeout | Reason |
|-----------|---------|--------|
| Client start | 30s | Initial connection |
| Get entity | 15s | Channel lookup |
| Get messages | 60s | Message fetching |
| Photo download | 120s (2 min) | Image files |
| Video download | 300s (5 min) | Large video files |
| Audio/voice download | 180s (3 min) | Audio files |
| Document download | 300s (5 min) | Large documents |

```python
await with_timeout(
    self.client.download_media(message.media, temp_file),
    timeout=120.0
)
```

### 4. Progress Tracking

Real-time progress updates during scraping:

```python
def progress_callback(current: int, total: int):
    percentage = (current / total) * 100
    print(f"Progress: {current}/{total} ({percentage:.1f}%)")

scraper = TelegramScraper(url, progress_callback=progress_callback)
posts = await scraper.scrape(limit=200)
```

**Features:**
- Called for each processed message
- Includes current and total counts
- Can be used for UI updates, progress bars, or logging
- Errors in callback don't stop scraping

### 5. Size Limits

File size limits prevent memory issues and long downloads:

| Media Type | Size Limit | Reason |
|------------|------------|--------|
| Videos | 50 MB | Large files take too long |
| Documents | 100 MB | Balance between size and utility |
| Audio/Voice | 20 MB | Typically smaller files |

```python
if file_size > 50 * 1024 * 1024:  # 50MB
    logger.warning(f"Video too large: {file_size} bytes, skipping")
    return None
```

### 6. Logging and Monitoring

Comprehensive logging for monitoring and debugging:

```python
# Progress logging every 50 messages
if i % 50 == 0:
    logger.info(f"Progress: {i}/{total_messages} messages processed")

# Error logging (security-safe)
logger.error(f"Download error: {get_safe_error_code(e)}")
```

**Log levels:**
- `INFO`: Normal operation, progress updates
- `WARNING`: Recoverable errors, skipped operations
- `ERROR`: Failed operations, exceptions

**Security:**
- No PII in logs
- No URLs with tokens
- Only error types logged (not full messages)

## Error Handling Strategies

### Network Errors

**Problem:** Intermittent network connectivity, temporary server issues

**Solution:**
- Retry up to 3 times with exponential backoff
- Log each retry attempt
- Fail gracefully after max attempts

### Rate Limiting (FloodWait)

**Problem:** Telegram enforces rate limits on API requests

**Solution:**
- Automatically wait exactly as long as required
- Continue seamlessly after wait
- Skip if wait time is excessive (>5 minutes)

### Timeouts

**Problem:** Operations hang indefinitely on slow networks

**Solution:**
- All network operations have timeouts
- Longer timeouts for larger files
- Retry after timeout (via retry mechanism)

### Large Files

**Problem:** Large media files consume memory and bandwidth

**Solution:**
- Size limits based on media type
- Skip files exceeding limits
- Log skipped files for monitoring

### Missing Media

**Problem:** Some messages have broken or unavailable media

**Solution:**
- Try to download, catch errors
- Log error (safe error code only)
- Continue with remaining messages
- Return partial results

## Usage Examples

### Basic Usage with Progress

```python
def show_progress(current, total):
    print(f"\rProcessing: {current}/{total}", end='', flush=True)

scraper = TelegramScraper(
    "https://t.me/channel",
    progress_callback=show_progress
)

try:
    posts = await scraper.scrape(limit=500)
    print(f"\n✅ Successfully scraped {len(posts)} posts")
except Exception as e:
    print(f"\n❌ Scraping failed: {e}")
```

### Handling Large Channels

```python
# For channels with 1000+ posts
scraper = TelegramScraper("https://t.me/largechannel")

# Scrape in batches
batch_size = 200
for offset in range(0, 1000, batch_size):
    try:
        posts = await scraper.scrape(limit=batch_size)
        # Process batch
        save_to_database(posts)
    except FloodWaitError as e:
        print(f"Rate limited, waiting {e.seconds}s...")
        await asyncio.sleep(e.seconds)
```

### With Timeout Protection

```python
import asyncio

scraper = TelegramScraper("https://t.me/channel")

try:
    # Overall timeout for entire scraping operation
    posts = await asyncio.wait_for(
        scraper.scrape(limit=100),
        timeout=600.0  # 10 minutes max
    )
except asyncio.TimeoutError:
    print("Scraping took too long, aborting")
```

## Best Practices

### 1. Use Progress Callbacks

Always provide a progress callback for long-running scrapes:
- Improves UX with visual feedback
- Helps diagnose stuck operations
- Allows for responsive UI updates

### 2. Handle FloodWait Gracefully

When scraping multiple channels:
```python
for channel in channels:
    try:
        posts = await scraper.scrape(channel)
    except FloodWaitError as e:
        if e.seconds < 300:
            await asyncio.sleep(e.seconds)
            # Retry after wait
        else:
            # Skip and move to next channel
            continue
```

### 3. Monitor Logs

Set up log monitoring to track:
- Retry attempts (may indicate network issues)
- FloodWait occurrences (may need to reduce rate)
- Skipped large files (adjust limits if needed)
- Timeout errors (may need longer timeouts)

### 4. Implement Graceful Degradation

Don't fail entire scrape on single errors:
```python
posts = await scraper.scrape(limit=100)
# Returns all successfully scraped posts
# Even if some failed or were skipped
```

### 5. Use Appropriate Timeouts

Adjust timeouts based on your environment:
- Fast networks: Use shorter timeouts
- Slow/mobile networks: Use longer timeouts
- Large files expected: Increase document/video timeouts

## Troubleshooting

### "FloodWait too long" Errors

**Cause:** Making too many requests too quickly

**Solutions:**
- Reduce scraping frequency
- Add delays between requests
- Use smaller batch sizes
- Spread scraping across multiple accounts

### Frequent Timeout Errors

**Cause:** Slow network, server issues, or too-short timeouts

**Solutions:**
- Check network connectivity
- Increase timeout values
- Reduce concurrent operations
- Try at different times

### Many Skipped Large Files

**Cause:** Channel has many videos/files exceeding limits

**Solutions:**
- Increase size limits if needed
- Download large files separately
- Use dedicated download sessions
- Filter by media type before downloading

### High Retry Counts

**Cause:** Unreliable network or server issues

**Solutions:**
- Check network stability
- Increase max retry attempts
- Add longer delays between retries
- Schedule scraping during off-peak hours

## Performance Tuning

### For Fast Scraping

```python
# Shorter timeouts, less retries
@retry_on_error(max_attempts=2, delay=0.5)
```

### For Reliability

```python
# Longer timeouts, more retries
@retry_on_error(max_attempts=5, delay=2.0)
```

### For Limited Bandwidth

```python
# Lower size limits
video_limit = 20 * 1024 * 1024  # 20MB instead of 50MB
document_limit = 50 * 1024 * 1024  # 50MB instead of 100MB
```

## Monitoring and Metrics

Key metrics to track:

1. **Success Rate**: Percentage of successful scrapes
2. **Retry Rate**: How often operations need retries
3. **FloodWait Frequency**: How often rate limited
4. **Average Scrape Time**: Duration of scraping operations
5. **Media Skip Rate**: Percentage of media files skipped

Example logging:
```python
logger.info(f"Scraped {len(posts)}/{limit} posts in {duration:.1f}s")
logger.info(f"Media: {photos} photos, {videos} videos, {skipped} skipped")
logger.info(f"Retries: {retry_count}, FloodWaits: {floodwait_count}")
```
