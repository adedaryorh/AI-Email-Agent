
from app.core.config import Settings


def get_chat_model(settings: Settings, **overrides):
    """settings.llm_model is 'provider:model', e.g. 'openai:gpt-4o-mini'."""
    if not settings.allow_cloud_processing:
        raise ValueError("Set ALLOW_CLOUD_PROCESSING=true after reviewing the data policy")
    from langchain.chat_models import init_chat_model

    options = {"temperature": 0, "timeout": 45, "max_retries": 2}
    options.update(overrides)
    return init_chat_model(settings.llm_model, **options)
