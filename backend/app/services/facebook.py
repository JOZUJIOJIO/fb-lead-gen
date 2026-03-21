"""Facebook Graph API integration (experimental).

NOTE: Facebook has severely restricted Graph API access since 2018-2019.
- Group member lists are no longer available
- Page fan lists are not available
- Comment author data may be limited to name and profile link

This module is provided for the technical spike (Week 1) to test
what data is actually available. The MVP should not depend on this
module — CSV import is the primary data source.
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def fetch_page_posts(page_id: str, limit: int = 25) -> list[dict[str, Any]]:
    """Fetch public posts from a Facebook Page.

    Requires a valid Facebook access token with pages_read_engagement permission.
    Endpoint: GET /{page-id}/feed
    """
    if not settings.facebook_access_token:
        raise ValueError("Facebook access token not configured")

    url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
    params = {
        "access_token": settings.facebook_access_token,
        "fields": "id,message,created_time,from,shares,comments.summary(true),likes.summary(true)",
        "limit": limit,
    }

    with httpx.Client(timeout=30) as client:
        response = client.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Facebook API error: {response.status_code} {response.text}")
            raise Exception(f"Facebook API error: {response.status_code}")
        data = response.json()
        return data.get("data", [])


def fetch_post_comments(post_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch comments on a specific post.

    Endpoint: GET /{post-id}/comments
    Returns commenter name and profile link (phone/email NOT available).
    """
    if not settings.facebook_access_token:
        raise ValueError("Facebook access token not configured")

    url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
    params = {
        "access_token": settings.facebook_access_token,
        "fields": "id,message,from,created_time",
        "limit": limit,
    }

    with httpx.Client(timeout=30) as client:
        response = client.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Facebook API error: {response.status_code} {response.text}")
            raise Exception(f"Facebook API error: {response.status_code}")
        data = response.json()
        comments = data.get("data", [])

        leads = []
        for comment in comments:
            commenter = comment.get("from", {})
            leads.append({
                "name": commenter.get("name", ""),
                "facebook_id": commenter.get("id", ""),
                "comment_text": comment.get("message", ""),
                "comment_time": comment.get("created_time", ""),
                "source_post_id": post_id,
            })
        return leads
