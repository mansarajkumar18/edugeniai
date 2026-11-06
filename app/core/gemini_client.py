import time
import concurrent.futures
from typing import Optional, List
import google.generativeai as genai
from google.generativeai.types import RequestOptions

from .config import settings, logger

# Cache to avoid re-configuring genai on every call if key hasn't changed
_configured_key: Optional[str] = None

def get_configured_client() -> bool:
    """Configures and returns status of Gemini API client."""
    global _configured_key
    current_key = settings.GEMINI_API_KEY
    if not current_key or current_key == "your_gemini_api_key_here":
        return False
    
    if _configured_key != current_key:
        try:
            genai.configure(api_key=current_key, transport="rest")
            _configured_key = current_key
        except Exception as exc:
            logger.error("Failed to configure Google Gemini API client: %s", type(exc).__name__)
            return False
    return True

def safe_extract_text(response) -> str:
    """Safely extracts text from a Gemini response without throwing ValueError on safety blocks."""
    if not response:
        return ""
    try:
        if hasattr(response, "text") and response.text:
            return response.text.strip()
    except (ValueError, AttributeError):
        pass
    try:
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and hasattr(candidate.content, "parts") and candidate.content.parts:
                part_texts = [getattr(p, "text", "") for p in candidate.content.parts if getattr(p, "text", None)]
                if part_texts:
                    return " ".join(part_texts).strip()
    except Exception:
        pass
    return ""

def _call_model_single(model_name: str, prompt: str, timeout: float) -> str:
    """Executes a single generate_content request with timeout."""
    model = genai.GenerativeModel(model_name=model_name)
    request_opts = RequestOptions(timeout=timeout)
    response = model.generate_content(prompt, request_options=request_opts)
    return safe_extract_text(response)

def call_gemini_with_retry(
    prompt: str,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    candidate_models: Optional[List[str]] = None
) -> str:
    """
    Calls Google Gemini API with strict timeout enforcement, bounded retries,
    and safe error logging. Returns empty string on failure or timeout.
    """
    if not get_configured_client():
        return ""

    if timeout is None:
        timeout = settings.AI_TIMEOUT_SECONDS
    if max_retries is None:
        max_retries = settings.AI_MAX_RETRIES
    if not candidate_models:
        preferred = getattr(settings, "GEMINI_MODEL", "") or "gemini-3.5-flash-lite"
        defaults = [
            preferred,
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
        ]
        # Deduplicate while preserving priority order
        candidate_models = list(dict.fromkeys(defaults))

    attempted_count = 0
    max_total_attempts = max(1, min(max_retries, 3))

    for model_name in candidate_models:
        if attempted_count >= max_total_attempts:
            break

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_model_single, model_name, prompt, timeout)
            try:
                result = future.result(timeout=timeout + 1.0)
                if result:
                    return result
                attempted_count += 1
            except concurrent.futures.TimeoutError:
                attempted_count += 1
                logger.warning(
                    "Gemini API call timed out after %.1fs for model %s (attempt %d/%d)",
                    timeout, model_name, attempted_count, max_total_attempts
                )
            except Exception as exc:
                err_str = str(exc)
                err_type = type(exc).__name__
                if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str:
                    logger.error("Gemini API authentication failed. Skipping remaining attempts.")
                    break
                elif "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    attempted_count += 1
                    logger.warning(
                        "Gemini API rate limit reached for model %s (attempt %d/%d)",
                        model_name, attempted_count, max_total_attempts
                    )
                elif "NOT_FOUND" in err_str or "404" in err_str or "no longer available" in err_str:
                    logger.warning(
                        "Gemini model %s not available or deprecated (%s), trying next candidate",
                        model_name, err_type
                    )
                else:
                    attempted_count += 1
                    logger.warning(
                        "Gemini API call failed for model %s with error %s (attempt %d/%d)",
                        model_name, err_type, attempted_count, max_total_attempts
                    )

        if attempted_count < max_total_attempts:
            time.sleep(0.2)

    return ""

def call_gemini_stream(
    prompt: str,
    timeout: Optional[float] = None,
    candidate_models: Optional[List[str]] = None
):
    """
    Calls Google Gemini API with streaming generation, yielding text chunks in real-time.
    Falls back gracefully to next candidate model if a stream encounters errors.
    """
    if not get_configured_client():
        return

    if timeout is None:
        timeout = settings.AI_TIMEOUT_SECONDS
    if not candidate_models:
        preferred = getattr(settings, "GEMINI_MODEL", "") or "gemini-3.5-flash-lite"
        defaults = [
            preferred,
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest",
        ]
        candidate_models = list(dict.fromkeys(defaults))

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name=model_name)
            request_opts = RequestOptions(timeout=timeout)
            response = model.generate_content(prompt, stream=True, request_options=request_opts)
            has_yielded = False
            for chunk in response:
                text_part = safe_extract_text(chunk)
                if text_part:
                    has_yielded = True
                    yield text_part
            if has_yielded:
                return
        except Exception as exc:
            logger.warning("Gemini streaming notice for model %s: %s", model_name, type(exc).__name__)
            continue

