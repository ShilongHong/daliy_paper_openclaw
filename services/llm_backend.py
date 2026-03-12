import json
import subprocess
from collections.abc import Sequence
from typing import Any, cast

import httpx
from openai import OpenAI


Message = dict[str, str]


class OpenAICompatibleBackend:
    def __init__(self, config: dict[str, object]):
        http_client = httpx.Client(timeout=60.0, follow_redirects=True)
        client_kwargs: dict[str, Any] = {"http_client": http_client}

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        if isinstance(api_key, str) and api_key:
            client_kwargs["api_key"] = api_key
        if isinstance(base_url, str) and base_url:
            client_kwargs["base_url"] = base_url

        self.client: Any = OpenAI(**cast(Any, client_kwargs))

    def generate(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = cast(Any, self.client.chat.completions.create)(
            model=model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class OpenClawBackend:
    def __init__(
        self,
        config: dict[str, object],
        purpose: str = "filter",
        runner=subprocess.run,
    ):
        openclaw_config = config.get("openclaw")
        openclaw_map = openclaw_config if isinstance(openclaw_config, dict) else {}
        self.binary_path = str(openclaw_map.get("binary_path", "openclaw"))
        self.agent_id = self._resolve_agent_id(openclaw_map, purpose)
        self.timeout_seconds = int(openclaw_map.get("timeout_seconds", 120))
        self.use_local = bool(openclaw_map.get("use_local", False))
        self.runner = runner

    def _resolve_agent_id(self, openclaw_map: dict[str, object], purpose: str) -> str:
        purpose_key_map = {
            "translation": "translation_agent_id",
            "filter": "filter_agent_id",
            "review": "review_agent_id",
        }
        key = purpose_key_map.get(purpose, "agent_id")
        fallback_map = {
            "translation": "translation",
            "filter": "filter",
            "review": "graduate-student",
        }
        return str(
            openclaw_map.get(
                key,
                openclaw_map.get("agent_id", fallback_map.get(purpose, "paper2data-llm")),
            )
        )

    def _build_prompt(self, messages: Sequence[Message]) -> str:
        sections = []
        for message in messages:
            role = message.get("role", "user").upper()
            content = message.get("content", "")
            sections.append(f"[{role}]\n{content}")
        sections.append("[OUTPUT]\n只返回最终答案内容，不要补充解释。")
        return "\n\n".join(sections)

    def _build_command(self, prompt: str) -> list[str]:
        command = [
            self.binary_path,
            "agent",
            "--agent",
            self.agent_id,
            "--json",
            "--message",
            prompt,
            "--timeout",
            str(self.timeout_seconds),
        ]
        if self.use_local:
            command.insert(2, "--local")
        return command

    def _extract_text(self, stdout: str) -> str:
        payload = json.loads(stdout)
        top_level_payloads = payload.get("payloads", [])
        if isinstance(top_level_payloads, list):
            for item in top_level_payloads:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        return text

        result = payload.get("result", {})
        if isinstance(result, dict):
            output_payloads = result.get("payloads", [])
            if isinstance(output_payloads, list):
                for item in output_payloads:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text:
                            return text

        messages = payload.get("messages", [])
        if isinstance(messages, list):
            for item in reversed(messages):
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, str) and content:
                    return content

        raise ValueError("OpenClaw 未返回可解析的文本内容")

    def generate(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        temperature: float,
        max_tokens: int,
    ) -> str:
        _ = model
        _ = temperature
        _ = max_tokens
        prompt = self._build_prompt(messages)
        result = self.runner(
            self._build_command(prompt),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if getattr(result, "returncode", 1) != 0:
            stderr = getattr(result, "stderr", "") or getattr(result, "stdout", "")
            raise RuntimeError(f"OpenClaw 调用失败: {stderr.strip()}")
        return self._extract_text(getattr(result, "stdout", "") or "")


def create_llm_backend(config: dict[str, object], purpose: str = "filter"):
    backend = str(config.get("backend", "openai_compatible"))
    if backend == "openclaw":
        return OpenClawBackend(config, purpose=purpose)
    return OpenAICompatibleBackend(config)
