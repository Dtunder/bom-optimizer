# Rate Limit Bypass Strategies for Distributor Scraping

This document outlines techniques used to maintain high throughput and avoid IP bans when querying distributor APIs (Mouser, DigiKey, etc.).

## 1. Request Header Mimicry
Always use realistic `User-Agent` strings. Rotate through a pool of common browser headers.

```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...",
    # ... more
]
```

## 2. IP Rotation (Proxy Pool)
For high-volume BOMs, use a rotating proxy service.
- **Residential Proxies:** Best for avoiding detection but expensive.
- **Datacenter Proxies:** Fast and cheap, but more easily blocked.

## 3. Session Management
Maintain cookies across requests within a single "session" to appear like a real user browsing the catalog. However, clear cookies periodically to avoid long-term tracking.

## 4. Request Jitter and Throttling
Avoid fixed intervals. Use a random delay (jitter) between requests.

```python
import time
import random

def random_delay():
    time.sleep(random.uniform(1.5, 4.0))
```

## 5. CAPTCHA Handling
If a CAPTCHA is triggered, the automated flow should:
1. Alert the operator.
2. Pause the specific proxy/session.
3. Optionally use a CAPTCHA solving service (e.g., 2Captcha, Anti-Captcha).

## 6. Headless Browser Optimization
Use `Playwright` or `Selenium` only when necessary (e.g., for heavy JS-rendered sites). For most distributors, `requests` or `httpx` with correct headers is sufficient and much faster.
