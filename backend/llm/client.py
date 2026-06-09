"""OpenAI client wiring for the AI Tailor feature.

Single place that reads the key + model from the environment so a provider swap
(or a model bump) is a one-file change. The key lives ONLY in the environment
(`backend/.env`, gitignored) and is never written to disk or committed.

This is the ONE part of the app that calls out to an LLM. The core /format flow
stays deterministic and never-invent; everything here is clearly the AI feature.
"""
import os

DEFAULT_MODEL = "gpt-4o-mini"


class LLMNotConfigured(RuntimeError):
    """Raised when no OPENAI_API_KEY is present, so callers can return a clean
    400/503 with setup guidance instead of a stack trace."""


def get_model() -> str:
    return (os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()


def is_configured() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def get_client():
    """Build an OpenAI client from the environment. Imported lazily so the rest
    of the app (and its tests) never need the `openai` package installed unless
    the Tailor feature is actually used."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise LLMNotConfigured(
            "The Tailor feature needs an OpenAI API key. Set OPENAI_API_KEY in "
            "backend/.env (it is gitignored — never commit it)."
        )
    from openai import OpenAI

    return OpenAI(api_key=api_key)
