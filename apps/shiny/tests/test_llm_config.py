import os
from pathlib import Path

from llm.config import bootstrap_environment, load_llm_config


def test_bootstrap_environment_loads_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=https://example.test\nLLM_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    bootstrap_environment(env_path, force=True, override=True)

    assert os.environ["LLM_BASE_URL"] == "https://example.test"
    assert os.environ["LLM_MODEL"] == "test-model"


def test_load_llm_config_requires_base_url():
    config, error = load_llm_config({"LLM_MODEL": "gpt-test"})
    assert config is None
    assert "LLM_BASE_URL" in error


def test_load_llm_config_accepts_optional_api_key():
    config, error = load_llm_config(
        {
            "LLM_BASE_URL": "https://example.test/",
            "LLM_CHAT_PATH": "smart",
            "LLM_MODEL": "gpt-test",
            "LLM_REASONING_EFFORT": "low",
            "LLM_TIMEOUT_SEC": "12.5",
            "LLM_MAX_TOKENS": "512",
            "LLM_TEMPERATURE": "0.4",
        }
    )
    assert error is None
    assert config is not None
    assert config.base_url == "https://example.test"
    assert config.chat_path == "/smart"
    assert config.api_key is None
    assert config.reasoning_effort == "low"
    assert config.timeout_sec == 12.5
    assert config.max_tokens == 512
    assert config.temperature == 0.4
