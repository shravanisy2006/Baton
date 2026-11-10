"""AI provider interface.

Every call asks for JSON that must validate against a Pydantic model. Invalid output is retried once
and then rejected loudly; it is never accepted silently. Responses are cached by a hash of the
prompt, so re-running the same evidence costs no quota and gives the same result.
"""
import hashlib
import json
import logging
import time
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import LLMCache

log = logging.getLogger("baton.llm")
T = TypeVar("T", bound=BaseModel)
PROMPT_VERSION = "v3"


class AIUnavailable(Exception):
    """No provider configured, or every provider failed."""


class InvalidAIOutput(Exception):
    pass


class Provider:
    name = "base"
    model = ""

    def generate(self, system: str, prompt: str, schema: type[BaseModel]) -> str:  # returns raw JSON text
        raise NotImplementedError


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        from google import genai  # imported lazily so tests don't need it
        from google.genai import types

        # Never wait forever on a busy model: give up after 90 s and let the backup model try.
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=90_000))
        self.model = model

    def generate(self, system: str, prompt: str, schema: type[BaseModel]) -> str:
        from google.genai import types

        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
        if not resp.text:
            raise InvalidAIOutput("Empty response from Gemini.")
        return resp.text


class FakeProvider(Provider):
    """Used only by automated tests: returns scripted JSON from a function."""
    name = "fake"
    model = "fake-model"

    def __init__(self, fn: Callable[[str, str, type[BaseModel]], str]):
        self.fn = fn

    def generate(self, system: str, prompt: str, schema: type[BaseModel]) -> str:
        return self.fn(system, prompt, schema)


_override: list[Provider] | None = None


def set_providers_for_tests(providers: list[Provider] | None) -> None:
    global _override
    _override = providers


def providers() -> list[Provider]:
    if _override is not None:
        return _override
    s = get_settings()
    chain: list[Provider] = []
    if s.ai_configured:
        chain.append(GeminiProvider(s.gemini_api_key, s.gemini_model))
        if s.backup_provider.startswith("gemini:"):
            chain.append(GeminiProvider(s.gemini_api_key, s.backup_provider.split(":", 1)[1]))
    return chain


def ai_status() -> dict:
    chain = providers()
    return {
        "configured": bool(chain),
        "chain": [f"{p.name}:{p.model}" for p in chain],
    }


def _cache_key(task: str, system: str, prompt: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}|{task}|{system}|{prompt}".encode()).hexdigest()


def call_json(db: Session, task: str, system: str, prompt: str, schema: type[T]) -> tuple[T, str]:
    """Return (validated result, provider label). Raises AIUnavailable or InvalidAIOutput."""
    key = _cache_key(task, system, prompt)
    cached = db.get(LLMCache, key)
    if cached:
        try:
            return schema.model_validate(cached.response), f"cache:{cached.model}"
        except ValidationError:
            db.delete(cached)
            db.commit()

    chain = providers()
    if not chain:
        raise AIUnavailable("AI is not configured. Add GEMINI_API_KEY to the backend environment.")

    errors: list[str] = []
    for provider in chain:
        for attempt in range(2):
            try:
                raw = provider.generate(system, prompt, schema)
                data = json.loads(raw)
                result = schema.model_validate(data)
            except (json.JSONDecodeError, ValidationError, InvalidAIOutput) as e:
                errors.append(f"{provider.model}: invalid output ({type(e).__name__})")
                log.warning("Invalid AI output from %s (attempt %d): %s", provider.model, attempt + 1, e)
                continue
            except Exception as e:  # noqa: BLE001 — network, quota, auth
                msg = str(e)
                errors.append(f"{provider.model}: {msg[:160]}")
                log.warning("AI call failed on %s: %s", provider.model, msg[:300])
                if ("429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg) and attempt == 0:
                    time.sleep(3)
                    continue  # one short retry on the same model, then the backup
                break  # try next provider
            db.merge(LLMCache(key=key, task=task, model=f"{provider.name}:{provider.model}",
                              response=result.model_dump()))
            db.commit()
            return result, f"{provider.name}:{provider.model}"
    if all("invalid output" in e for e in errors):
        raise InvalidAIOutput("; ".join(errors))
    raise AIUnavailable("; ".join(errors) or "All AI providers failed.")
