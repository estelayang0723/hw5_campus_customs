"""Shared model, MCP transport, and usage-limit configuration."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import UsageLimits
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER = ROOT / "mcp_server" / "server.py"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"
MODEL_NAME = "gpt-6-luna"

# Keep local secrets out of source control; environment variables take precedence.
load_dotenv(ROOT / ".env")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
LOCAL_MOCK = os.getenv("CAMPUS_CUSTOMS_LOCAL_MOCK", "1").strip().lower() in {"1", "true", "yes", "on"}

# Each run is bounded; Boss delegation forwards the same usage object to specialists.
RUN_USAGE_LIMITS = UsageLimits(
    request_limit=10,
    tool_calls_limit=12,
    input_tokens_limit=8_000,
    output_tokens_limit=4_000,
    total_tokens_limit=12_000,
)


def make_model() -> OpenAIChatModel | FunctionModel:
    """Create the one permitted model, routed through Portkey's OpenAI-compatible gateway."""
    if LOCAL_MOCK:
        # Local execution never opens an LLM connection. This callable model returns
        # valid outputs while the Agent still executes its normal graph and MCP tools.
        from backend.local_mock import local_mock_model

        return FunctionModel(local_mock_model, model_name="campus-customs-local-mock")

    portkey_key = os.getenv("PORTKEY_API_KEY")
    if not portkey_key:
        raise RuntimeError("Set PORTKEY_API_KEY in the environment or in the project .env file.")

    # The gateway key is sent in Portkey's own header. Provider credentials/routing must
    # be configured on the Portkey side; PORTKEY_VIRTUAL_KEY may select that credential.
    headers = {
        "x-portkey-api-key": portkey_key,
        "x-portkey-provider": os.getenv("PORTKEY_PROVIDER", "openai"),
    }
    virtual_key = os.getenv("PORTKEY_VIRTUAL_KEY")
    if virtual_key:
        headers["x-portkey-virtual-key"] = virtual_key

    provider = OpenAIProvider(
        base_url=PORTKEY_BASE_URL,
        # OpenAI-compatible clients require a bearer token field. The Portkey gateway
        # authenticates via x-portkey-api-key above and resolves provider credentials.
        api_key="portkey-gateway",
    )
    # The model name is intentionally a constant: no request or environment variable can
    # switch agents to a different LLM.
    return OpenAIChatModel(MODEL_NAME, provider=provider)


def model_settings() -> dict[str, object]:
    if LOCAL_MOCK:
        return {}
    portkey_key = os.getenv("PORTKEY_API_KEY")
    if not portkey_key:
        raise RuntimeError("Set PORTKEY_API_KEY in the environment or in the project .env file.")
    headers = {
        "x-portkey-api-key": portkey_key,
        "x-portkey-provider": os.getenv("PORTKEY_PROVIDER", "openai"),
    }
    if virtual_key := os.getenv("PORTKEY_VIRTUAL_KEY"):
        headers["x-portkey-virtual-key"] = virtual_key
    return {"extra_headers": headers}
