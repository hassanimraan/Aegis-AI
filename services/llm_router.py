import time

from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI

from config.settings import (
    get_gemini_api_key,
    get_groq_api_key,
    get_openrouter_api_key,
)


GEMINI_MODEL = "gemini-3.5-flash"
GROQ_MODEL = "openai/gpt-oss-120b"
OPENROUTER_MODEL = "openrouter/free"

PROVIDER_TIMEOUT = 60

# Gemini SDK retry policy.
#
# The application itself controls provider fallback:
#
# Gemini -> Groq -> OpenRouter
#
# Therefore Gemini should not perform hidden retries that delay
# fallback to the next provider.
GEMINI_RETRY_ATTEMPTS = 1


class LLMProviderError(Exception):
    pass


class AllLLMProvidersFailed(Exception):

    def __init__(self, errors):

        self.errors = errors

        message = (
            "All configured LLM providers failed."
        )

        if errors:

            details = "\n".join(
                f"- {provider}: {error}"
                for provider, error in errors.items()
            )

            message = (
                f"{message}\n{details}"
            )

        super().__init__(message)


def _is_transient_error(error):

    error_text = str(error).lower()

    transient_markers = [
        "503",
        "service unavailable",
        "overloaded",
        "temporarily unavailable",
        "timeout",
        "timed out",
        "429",
        "rate limit",
        "resource exhausted",
        "internal server error",
        "502",
        "504",
    ]

    return any(
        marker in error_text
        for marker in transient_markers
    )


def _generate_with_gemini(prompt):

    api_key = get_gemini_api_key()

    if not api_key:

        raise LLMProviderError(
            "GEMINI_API_KEY is not configured."
        )

    try:

        http_options = types.HttpOptions(
            timeout=PROVIDER_TIMEOUT * 1000,
            retry_options=types.HttpRetryOptions(
                attempts=GEMINI_RETRY_ATTEMPTS
            ),
        )

        client = genai.Client(
            api_key=api_key,
            http_options=http_options,
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        if (
            not response
            or not response.text
        ):

            raise LLMProviderError(
                "Gemini returned an empty response."
            )

        return response.text

    except Exception as error:

        if _is_transient_error(error):

            raise LLMProviderError(
                f"Gemini transient/provider error: {error}"
            ) from error

        raise LLMProviderError(
            f"Gemini request failed: {error}"
        ) from error


def _generate_with_groq(prompt):

    api_key = get_groq_api_key()

    if not api_key:

        raise LLMProviderError(
            "GROQ_API_KEY is not configured."
        )

    try:

        client = Groq(
            api_key=api_key,
            timeout=PROVIDER_TIMEOUT,
            max_retries=0,
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        if (
            not response
            or not response.choices
            or not response.choices[0].message.content
        ):

            raise LLMProviderError(
                "Groq returned an empty response."
            )

        return response.choices[0].message.content

    except Exception as error:

        raise LLMProviderError(
            f"Groq request failed: {error}"
        ) from error


def _generate_with_openrouter(prompt):

    api_key = get_openrouter_api_key()

    if not api_key:

        raise LLMProviderError(
            "OPENROUTER_API_KEY is not configured."
        )

    try:

        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=PROVIDER_TIMEOUT,
            max_retries=0,
        )

        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        if (
            not response
            or not response.choices
            or not response.choices[0].message.content
        ):

            raise LLMProviderError(
                "OpenRouter returned an empty response."
            )

        return response.choices[0].message.content

    except Exception as error:

        raise LLMProviderError(
            f"OpenRouter request failed: {error}"
        ) from error


def generate_with_fallback(prompt):

    if not prompt or not str(prompt).strip():

        raise ValueError(
            "LLM prompt cannot be empty."
        )

    providers = [
        (
            "gemini",
            GEMINI_MODEL,
            _generate_with_gemini,
        ),
        (
            "groq",
            GROQ_MODEL,
            _generate_with_groq,
        ),
        (
            "openrouter",
            OPENROUTER_MODEL,
            _generate_with_openrouter,
        ),
    ]

    errors = {}

    for (
        provider_name,
        model_name,
        provider_function,
    ) in providers:

        started = time.time()

        try:

            text = provider_function(
                prompt
            )

            elapsed = round(
                time.time() - started,
                2,
            )

            return {
                "text": text,
                "provider": provider_name,
                "model": model_name,
                "elapsed_seconds": elapsed,
            }

        except Exception as error:

            errors[provider_name] = str(
                error
            )

            continue

    raise AllLLMProvidersFailed(
        errors
    )
