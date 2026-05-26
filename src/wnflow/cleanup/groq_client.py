"""Groq HTTP-Client für Cleanup-Calls.

Verwendet httpx (sync). Timeout 5s default, ein Retry bei 5xx,
kein Retry bei 4xx (Auth-Fehler).
"""

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(Exception):
    """Erhoben wenn Groq-Call endgültig fehlschlägt."""


class GroqClient:
    """Synchroner Groq-Client. Throwt GroqError bei jedem End-Fehler."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 5.0,
        retry: int = 1,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._retry = retry

    def clean(self, system_prompt: str, user_text: str) -> str:
        """Sendet System-Prompt + User-Text an Groq, gibt assistant content zurück."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.0,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        attempts = self._retry + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = httpx.post(
                    GROQ_URL,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout_s,
                )
            except httpx.RequestError as exc:
                last_error = exc
                continue

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                return content.strip()

            # 4xx — kein Retry (Auth-Fehler, Bad Request)
            if 400 <= response.status_code < 500:
                raise GroqError(
                    f"Groq API error {response.status_code}: {response.text}"
                )

            # 5xx — retry erlaubt
            last_error = GroqError(
                f"Groq API error {response.status_code}: {response.text}"
            )

        raise GroqError(f"Groq-Call nach {attempts} Versuchen fehlgeschlagen") from last_error
