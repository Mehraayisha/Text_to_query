# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
OAuth2 Token Cache

Caches OAuth2 access tokens with TTL to reduce authentication overhead.
Reused from mongodb_structure_agent/utils/token_cache.py
"""

import time
import threading
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class TokenCache:
    """
    Thread-safe OAuth2 token cache with TTL

    Features:
    - Automatic token refresh before expiration
    - Thread-safe access
    - Configurable TTL
    """

    def __init__(self, token_url: str, client_id: str, client_secret: str, ttl_seconds: int = 3000):
        """
        Initialize token cache

        Args:
            token_url: OAuth2 token endpoint
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            ttl_seconds: Token TTL in seconds (default: 3000 = 50 minutes)
        """
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.ttl_seconds = ttl_seconds

        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._lock = threading.Lock()

        logger.info(f"[TokenCache] Initialized with TTL: {ttl_seconds}s")

    def get_token(self) -> str:
        """
        Get valid access token (from cache or fetch new)

        Returns:
            Valid access token
        """
        with self._lock:
            current_time = time.time()

            # Check if token is still valid
            if self._token and current_time < self._token_expiry:
                logger.debug("[TokenCache] Using cached token")
                return self._token

            # Token expired or not present, fetch new one
            logger.info("[TokenCache] Fetching new token...")
            self._token = self._fetch_token()
            self._token_expiry = current_time + self.ttl_seconds
            logger.info(f"[TokenCache] New token cached (expires in {self.ttl_seconds}s)")

            return self._token

    def _fetch_token(self) -> str:
        """Fetch new access token from OAuth2 server"""
        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")

                if not access_token:
                    raise ValueError("No access_token in response")

                logger.info("[TokenCache] Token fetched successfully")
                return access_token
            else:
                raise Exception(f"Token request failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"[TokenCache] Failed to fetch token: {e}")
            raise

    def invalidate(self):
        """Invalidate cached token (force refresh on next get_token)"""
        with self._lock:
            self._token = None
            self._token_expiry = 0
            logger.info("[TokenCache] Token cache invalidated")
