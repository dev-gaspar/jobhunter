"""Adaptador de Google Gemini para la interfaz AIProvider."""
import time

import requests


class GeminiProvider:
    """Cliente HTTP directo de Gemini con retry + backoff.

    No usa el SDK porque los wrappers oficiales anaden dependencias pesadas
    y el API es simple (POST JSON). Retry maneja 429 (rate limit), 500+ (server)
    y timeouts con backoff creciente.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.api_key = cfg["gemini_api_key"]
        self.model = cfg.get("gemini_model", "gemini-2.5-flash")

    def _url(self) -> str:
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def _request(self, payload: dict, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                r = requests.post(self._url(), json=payload, timeout=60)
                if r.status_code == 429:
                    time.sleep((attempt + 1) * 10)
                    continue
                if r.status_code >= 500:
                    time.sleep(5)
                    continue
                r.raise_for_status()
                t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if t.startswith("```"):
                    t = t.split("\n", 1)[1].rsplit("```", 1)[0]
                return t
            except requests.exceptions.Timeout:
                time.sleep(5)
                continue
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(3)
        raise Exception("Gemini API: max retries exceeded")

    def generate(self, prompt: str, *, temperature: float = 0.4) -> str:
        return self._request({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        })

    def generate_vision(
        self,
        prompt: str,
        img_b64: str,
        mime: str = "image/png",
        *,
        temperature: float = 0.3,
    ) -> str:
        return self._request({
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": img_b64}},
            ]}],
            "generationConfig": {"temperature": temperature},
        })


# ── Wrappers legacy para callers existentes ──
# Durante la migracion los agentes siguen llamando call_gemini(cfg, ...).
# Estos wrappers instancian GeminiProvider por llamada. En fases posteriores
# los agentes se actualizaran para recibir un AIProvider inyectado.

def gemini_url(cfg):
    return GeminiProvider(cfg)._url()


def call_gemini(cfg, prompt):
    return GeminiProvider(cfg).generate(prompt)


def call_gemini_vision(cfg, prompt, img_b64, mime="image/png"):
    return GeminiProvider(cfg).generate_vision(prompt, img_b64, mime)
