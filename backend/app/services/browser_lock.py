"""Global browser lock to prevent concurrent browser access."""

import asyncio

# Single lock shared between campaign_runner and reply_service
browser_lock = asyncio.Lock()
