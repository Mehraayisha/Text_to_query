"""Client for OpenAI-compatible hosted chat-completion APIs."""

import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """Call a configured OpenAI-compatible chat-completion endpoint."""

    def __init__(
        self,
        token: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.token = token or os.getenv("GEMINI_API_KEY", "") or os.getenv("HF_TOKEN", "")
        self.model = model or os.getenv(
            "LLM_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        )
        self.endpoint = endpoint or os.getenv(
            "LLM_ENDPOINT",
            os.getenv(
                "GEMINI_ENDPOINT",
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            ),
        )
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        if not self.token:
            raise ValueError("GEMINI_API_KEY must be configured in .env")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8")
        http_request = request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        body: Dict[str, Any]
        for attempt in range(self.max_retries + 1):
            try:
                with request.urlopen(http_request, timeout=120) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                transient = exc.code in {429, 500, 502, 503, 504}
                if not transient or attempt == self.max_retries:
                    raise RuntimeError(
                        f"{self.provider} request failed ({exc.code}): {details}"
                    ) from exc
                delay = min(2 ** attempt, 8)
                print(
                    f"{self.provider} is temporarily unavailable ({exc.code}); "
                    f"retrying in {delay} seconds..."
                )
                time.sleep(delay)
            except error.URLError as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Could not reach {self.provider}: {exc.reason}"
                    ) from exc
                delay = min(2 ** attempt, 8)
                print(
                    f"Could not reach {self.provider}; retrying in {delay} seconds..."
                )
                time.sleep(delay)

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected {self.provider} response: {body}") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"{self.provider} returned an empty response")
        return content.strip()


HuggingFaceClient = LLMClient
