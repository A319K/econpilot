from app.config import get_settings


def test_settings_load_with_defaults():
    settings = get_settings()

    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_model == "z-ai/glm-5.2"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.notifier == "none"


def test_settings_is_cached():
    assert get_settings() is get_settings()
