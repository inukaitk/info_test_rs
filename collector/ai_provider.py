"""AI provider（要約・タグ付けのためのモデル呼び出し）。

実装している provider は Anthropic（Claude API）の1つだけ。テストでは MockProvider を使い、実際のAPIは呼ばない。
LLM には道具（tools）や権限を一切渡さない。1回の呼び出しで JSON を1つ返させるだけ。
APIキーは環境変数 ANTHROPIC_API_KEY からだけ読み、ログ・ファイル・画面には書かない。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

API_KEY_ENV = "ANTHROPIC_API_KEY"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class MissingApiKey(Exception):
    """APIキーが設定されていない。"""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderResult:
    """1回の呼び出しの結果。kind は ok / refusal / truncated / api_error / retryable_error。"""

    kind: str
    text: str | None = None
    usage: Usage = field(default_factory=Usage)
    error: str | None = None
    model: str | None = None


class Provider(Protocol):
    name: str
    model: str

    def count_tokens(self, system: str, user: str) -> int: ...

    def complete(self, system: str, user: str, schema: dict, max_tokens: int) -> ProviderResult: ...


# ---------------------------------------------------------------- Anthropic（Claude API）


class AnthropicProvider:
    """Claude API の Messages API を、構造化出力（output_config.format の json_schema）で1回呼ぶ。"""

    name = "anthropic"

    def __init__(self, model: str, effort: str = "medium", fallbacks: bool = True, client: Any | None = None,
                 environ: dict[str, str] | None = None):
        environ = os.environ if environ is None else environ
        if client is None:
            if not environ.get(API_KEY_ENV):
                raise MissingApiKey(f"環境変数 {API_KEY_ENV} が設定されていません")
            import anthropic

            # 再試行は呼び出し側（summarize）で回数を数えて行うため、SDK の自動再試行は使わない
            client = anthropic.Anthropic(api_key=environ[API_KEY_ENV], max_retries=0, timeout=300.0)
        self.client = client
        self.model = model
        self.effort = effort
        self.fallbacks = fallbacks

    def _request(self, system: str, user: str) -> dict:
        return {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

    def count_tokens(self, system: str, user: str) -> int:
        """入力トークン数を API で数える（課金されない）。"""
        return self.client.messages.count_tokens(**self._request(system, user)).input_tokens

    def complete(self, system: str, user: str, schema: dict, max_tokens: int) -> ProviderResult:
        import anthropic

        params: dict[str, Any] = {
            **self._request(system, user),
            "max_tokens": max_tokens,
            "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        }
        try:
            if self.fallbacks:
                # 安全上の理由で拒否されたときに、API 側で既定の別モデルに切り替える
                response = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
            else:
                response = self.client.messages.create(**params)
        except anthropic.RateLimitError as e:
            return ProviderResult("retryable_error", error=f"API の利用制限（HTTP 429）：{_message(e)}")
        except anthropic.APIStatusError as e:
            kind = "retryable_error" if e.status_code >= 500 else "api_error"
            return ProviderResult(kind, error=f"API エラー（HTTP {e.status_code}）：{_message(e)}")
        except anthropic.APIConnectionError as e:
            return ProviderResult("retryable_error", error=f"API に接続できません（{type(e).__name__}）。ネットワーク設定を確認してください")

        usage = Usage(response.usage.input_tokens or 0, response.usage.output_tokens or 0)
        served = getattr(response, "model", self.model)
        if response.stop_reason == "refusal":
            return ProviderResult("refusal", usage=usage, error="モデルが応答を拒否しました", model=served)
        if response.stop_reason == "max_tokens":
            return ProviderResult("truncated", usage=usage, error="出力が上限で途切れました", model=served)
        text = next((b.text for b in response.content if b.type == "text"), None)
        return ProviderResult("ok", text=text, usage=usage, model=served)


def _message(e: Exception) -> str:
    return str(getattr(e, "message", "") or type(e).__name__)[:200]


# ---------------------------------------------------------------- テスト用


@dataclass
class MockProvider:
    """テスト用。決められた応答を順に返す（ネットワークに出ない）。

    responses の要素は ProviderResult、または dict（JSON にして ok として返す）、または
    (system, user) を受け取って ProviderResult/dict を返す関数。
    """

    responses: list[Any]
    model: str = "mock-model"
    name: str = "mock"
    calls: list[dict] = field(default_factory=list)
    tokens_per_char: float = 1.0

    def count_tokens(self, system: str, user: str) -> int:
        return int((len(system) + len(user)) * self.tokens_per_char)

    def complete(self, system: str, user: str, schema: dict, max_tokens: int) -> ProviderResult:
        self.calls.append({"system": system, "user": user, "schema": schema, "max_tokens": max_tokens})
        if not self.responses:
            raise AssertionError("MockProvider の応答が足りません")
        item = self.responses.pop(0)
        if callable(item):
            item = item(system, user)
        if isinstance(item, ProviderResult):
            return item
        return ProviderResult("ok", text=json.dumps(item, ensure_ascii=False),
                              usage=Usage(self.count_tokens(system, user), 300), model=self.model)


def build_provider(ai_config: dict, environ: dict[str, str] | None = None,
                   factory: Callable[..., Provider] | None = None) -> Provider:
    """設定から provider を作る。APIキーがなければ MissingApiKey。"""
    if ai_config["provider"] != "anthropic":
        raise ValueError(f"未対応の provider: {ai_config['provider']}")
    factory = factory or AnthropicProvider
    return factory(model=ai_config["model"], effort=ai_config["effort"], fallbacks=ai_config["fallbacks"], environ=environ)
