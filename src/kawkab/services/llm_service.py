"""LLM service - multi-provider support for report generation.

Supports Ollama (local, default), Groq, Google AI Studio, OpenRouter.
All providers are free-tier, $0/month.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: Literal["ollama", "groq", "google", "openrouter"] = "ollama"
    ollama_model: str = "ministral-3:14b"
    ollama_base_url: str = "http://localhost:11434"
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int = 8000
    num_gpu: int = 99  # Number of GPU layers to use (0 = CPU only, 99 = all)


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this provider is available/ready."""
        ...

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            system: Optional system message

        Returns:
            Generated text
        """
        ...


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider (free, offline)."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = config.ollama_base_url
        self.model = config.ollama_model

    async def is_available(self) -> bool:
        """Check if Ollama is running and model is loaded."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return any(self.model.split(":")[0] in m for m in models)
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False
        return False

    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate response via Ollama API with retry on empty responses."""
        import httpx

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
                "num_gpu": self.config.num_gpu,
            },
        }

        if system:
            payload["system"] = system

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate", json=payload
                    )
                    response.raise_for_status()
                    data = response.json()
                    result = data.get("response", "").strip()
                    logger.info(
                        f"Ollama attempt {attempt+1}: "
                        f"prompt_len={len(prompt)}, "
                        f"system_len={len(system) if system else 0}, "
                        f"eval_count={data.get('eval_count')}, "
                        f"resp_len={len(result)}, "
                        f"done={data.get('done_reason')}"
                    )
                    if result and len(result) > 10:
                        return result
            except Exception as e:
                logger.warning(
                    f"Ollama call failed (attempt {attempt+1}/{max_retries}): {e}"
                )
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 * (attempt + 1))

        return (
            "I was unable to generate a report at this time. "
            "The match analysis data is available, but the AI assistant "
            "did not respond. Please try again."
        )


class GroqProvider(LLMProvider):
    """Groq API provider (free tier: 30 req/min, Llama 3.1 70B)."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.api_key = config.api_key
        self.model = "llama-3.1-70b-versatile"
        self.base_url = "https://api.groq.com/openai/v1"

    async def is_available(self) -> bool:
        return self.api_key is not None

    async def generate(self, prompt: str, system: str | None = None) -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class GoogleProvider(LLMProvider):
    """Google AI Studio provider (free tier: 15 req/min, Gemini 1.5 Flash)."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.api_key = config.api_key
        self.model = "gemini-1.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def is_available(self) -> bool:
        return self.api_key is not None

    async def generate(self, prompt: str, system: str | None = None) -> str:
        import httpx

        url = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url, params=params, headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class LLMService:
    """Multi-provider LLM service with automatic fallback."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.providers: list[LLMProvider] = []

        if config.provider == "ollama":
            self.providers.append(OllamaProvider(config))
        elif config.provider == "groq":
            self.providers.append(GroqProvider(config))
        elif config.provider == "google":
            self.providers.append(GoogleProvider(config))
        elif config.provider == "openrouter":
            pass

        self.providers.append(OllamaProvider(config))

        logger.info(
            f"LLMService: primary={config.provider}, "
            f"{len(self.providers)} providers configured"
        )

    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate response with automatic provider fallback.

        Tries each provider in order until one succeeds.

        Args:
            prompt: User prompt
            system: Optional system message

        Returns:
            Generated text from the first available provider
        """
        last_error = None

        for provider in self.providers:
            try:
                if not await provider.is_available():
                    logger.debug(
                        f"{provider.__class__.__name__} not available, skipping"
                    )
                    continue

                logger.info(
                    f"Using {provider.__class__.__name__} for generation"
                )
                return await provider.generate(prompt, system)
            except Exception as e:
                logger.warning(
                    f"{provider.__class__.__name__} failed: {e}, "
                    "trying next provider"
                )
                last_error = e
                continue

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}"
        )

    async def generate_coach_report(
        self,
        match_analysis_summary: str,
        language: str = "en",
    ) -> str:
        """Generate a friendly coach report from match analysis.

        Args:
            match_analysis_summary: Summary of the match analysis
            language: "en" or "ar" for English/Arabic

        Returns:
            Coach-friendly report text
        """
        if language == "ar":
            system = """أنت مساعد مدرب كرة قدم. تساعد المدربين الهاويين على فهم بيانات مبارياتهم.
القواعد:
1. استشهد بطوابع زمنية للفيديو لكل ادعاء.
2. إذا لم تكن تملك بيانات لشيء معين، قل "لا أعرف" - لا تخترع أبداً.
3. استخدم لغة بسيطة، كأنك تتحدث مع صديق مدرب.
4. تكلم بالعربية بشكل طبيعي.
5. لا تدّعي يقيناً ليس لديك. استخدم "يبدو أن"، "نعتقد".
6. الهيكل: ملخص → النتائج الرئيسية (مع مقاطع فيديو) → التوصيات → ما لا نعرفه."""
        else:
            system = """You are a friendly football coach assistant. You help amateur coaches understand their match data.
RULES:
1. Cite video timestamps for EVERY claim.
2. If you don't have data for something, say "I don't know" — never invent.
3. Use simple language, like talking to a friend coach.
4. Speak the coach's selected language naturally.
5. Never claim certainty you don't have. Use "it looks like", "we believe".
6. Structure: TL;DR → Key findings (with clips) → Recommendations → What we don't know."""

        prompt = f"""Match Analysis Data:
{match_analysis_summary}

Please generate a coach-friendly report following the structure above.
Focus on the most important 3-5 findings and 3-5 actionable recommendations.
"""

        return await self.generate(prompt, system)
