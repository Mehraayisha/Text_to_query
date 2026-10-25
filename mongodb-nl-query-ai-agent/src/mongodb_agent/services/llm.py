# SPDX-License-Identifier: MIT
"""
LLM Service Abstraction for MongoDB Agent.

Supports:
- OpenAI & OpenRouter (with built-in HTTP fallback)
- Azure OpenAI
- Anthropic Claude
"""

import logging
import os
import requests
from typing import Optional, Dict, Any

from mongodb_agent.config import Config

logger = logging.getLogger(__name__)
llm = None


class RequestsChatOpenAI:
    """Lightweight HTTP fallback for OpenAI / OpenRouter when langchain_openai is not installed."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        default_headers: Optional[Dict[str, str]] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.default_headers = default_headers or {}

    def invoke(self, input_data: Any):
        from langchain_core.messages import AIMessage, BaseMessage

        messages = []
        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        elif isinstance(input_data, list):
            for m in input_data:
                if isinstance(m, BaseMessage):
                    role = "user" if m.type == "human" else ("assistant" if m.type == "ai" else "system")
                    messages.append({"role": role, "content": m.content})
                elif isinstance(m, dict):
                    messages.append(m)
                else:
                    messages.append({"role": "user", "content": str(m)})
        else:
            messages.append({"role": "user", "content": str(input_data)})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.default_headers,
        }
        site_url = os.getenv("OPENROUTER_SITE_URL")
        app_name = os.getenv("OPENROUTER_APP_NAME")
        if site_url and "HTTP-Referer" not in headers:
            headers["HTTP-Referer"] = site_url
        if app_name and "X-Title" not in headers:
            headers["X-Title"] = app_name

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        data = res.json()

        reply = None
        if data.get("choices") and len(data["choices"]) > 0:
            msg = data["choices"][0].get("message", {})
            reply = msg.get("content")
            # If content is None or empty, check reasoning fields (used by some OpenRouter free models like DeepSeek)
            if not reply:
                reply = msg.get("reasoning") or msg.get("reasoning_content") or ""

        if reply is None:
            logger.warning(f"LLM returned empty/None content. Raw response: {data}")
            reply = ""

        return AIMessage(content=str(reply))

    def stream(self, input_data: Any):
        yield self.invoke(input_data)


def get_llm(config: Config):
    """
    Get LLM instance based on configuration.
    """
    global llm

    if config.llm_provider == "openai":
        if not config.openai_api_key:
            raise ValueError("OpenAI/OpenRouter provider requires OPENAI_API_KEY in .env")

        base_url = getattr(config, "openai_base_url", None) or os.getenv("OPENAI_BASE_URL")
        logger.info(
            f"Initializing OpenAI/OpenRouter: {config.openai_model} (base_url={base_url or 'default'})"
        )

        headers = {}
        if base_url == "https://openrouter.ai/api/v1":
            headers = {
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "MongoDB NL Query AI Agent"),
            }

        try:
            from langchain_openai import ChatOpenAI

            llm_kwargs = {
                "api_key": config.openai_api_key,
                "model": config.openai_model,
                "temperature": 0,
                "streaming": True,
            }
            if base_url:
                llm_kwargs["base_url"] = base_url
            if headers:
                llm_kwargs["default_headers"] = headers
            llm = ChatOpenAI(**llm_kwargs)
            logger.info("Using langchain_openai.ChatOpenAI")
        except ImportError:
            logger.info("langchain_openai not installed; using built-in RequestsChatOpenAI")
            llm = RequestsChatOpenAI(
                api_key=config.openai_api_key,
                model=config.openai_model,
                base_url=base_url,
                default_headers=headers,
            )

    elif config.llm_provider == "azure":
        from langchain_openai import AzureChatOpenAI

        logger.info(f"Initializing Azure OpenAI: {config.azure_deployment_name}")
        llm = AzureChatOpenAI(
            azure_endpoint=config.azure_endpoint,
            api_key=config.azure_api_key,
            deployment_name=config.azure_deployment_name,
            api_version=config.azure_api_version,
            temperature=0,
            streaming=True,
        )

    elif config.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        logger.info("Initializing Anthropic Claude")
        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            temperature=0,
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")

    return llm
