"""OpenAI-compatible LLM client for infra-ingest."""

import os
import requests


def build_llm_config_from_env():
    """Load LLM settings from environment variables."""
    config = {
        "api_key": os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "timeout": int(os.getenv("LLM_TIMEOUT", "120")),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
    }
    fallback_api_key = os.getenv("LLM_FALLBACK_API_KEY") or os.getenv("OPENAI_FALLBACK_API_KEY")
    fallback_model = os.getenv("LLM_FALLBACK_MODEL")
    fallback_base_url = os.getenv("LLM_FALLBACK_BASE_URL")
    if fallback_api_key and fallback_model and fallback_base_url:
        config["fallback"] = {
            "api_key": fallback_api_key,
            "base_url": fallback_base_url,
            "model": fallback_model,
            "timeout": int(os.getenv("LLM_FALLBACK_TIMEOUT", str(config["timeout"]))),
            "temperature": float(os.getenv("LLM_FALLBACK_TEMPERATURE", str(config["temperature"]))),
        }
    return config


def validate_llm_config(config):
    """Raise a clear error when the OpenAI-compatible API config is incomplete."""
    if not config["api_key"]:
        raise RuntimeError(
            "未发现 LLM_API_KEY。请在 .env 中配置 LLM_API_KEY，"
            "或设置 OPENAI_API_KEY 作为兼容 fallback。"
        )
    if not config["base_url"].startswith(("http://", "https://")):
        raise RuntimeError("LLM_BASE_URL 必须是完整 URL，例如 https://api.deepseek.com/v1")
    if not config["model"]:
        raise RuntimeError("LLM_MODEL 不能为空，例如 deepseek-chat 或 gpt-4o-mini")


def call_llm_api(text_content, system_prompt, config):
    """Call an OpenAI-compatible chat completions endpoint."""
    try:
        return call_single_llm_api(text_content, system_prompt, config)
    except RuntimeError as exc:
        fallback = config.get("fallback")
        if not fallback:
            raise
        try:
            return call_single_llm_api(text_content, system_prompt, fallback)
        except RuntimeError as fallback_exc:
            raise RuntimeError(f"LLM 主模型和 fallback 均失败。主错误: {exc}; fallback 错误: {fallback_exc}") from fallback_exc


def call_single_llm_api(text_content, system_prompt, config):
    """Call one OpenAI-compatible chat completions endpoint."""
    validate_llm_config(config)

    user_prompt = f"以下是我们需要提炼的原始文本：\n---\n{text_content}\n---"
    url = f"{config['base_url'].rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": config["temperature"],
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config["timeout"],
        )
        response.raise_for_status()
        result_json = response.json()
        return result_json["choices"][0]["message"]["content"]
    except requests.HTTPError as exc:
        body = exc.response.text[:1000] if exc.response is not None else ""
        raise RuntimeError(f"LLM API HTTP 请求失败: {exc}. 响应片段: {body}") from exc
    except (KeyError, IndexError) as exc:
        raise RuntimeError("LLM API 响应格式不符合 OpenAI chat completions 规范") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"LLM API 网络请求失败: {exc}") from exc
