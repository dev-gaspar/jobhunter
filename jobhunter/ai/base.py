"""Interfaz (puerto) de proveedor de IA.

El resto del codigo depende de esta interfaz, no de un proveedor concreto.
Permite swap futuro a OpenAI/Claude/etc. sin tocar agentes ni pipeline.
"""
from typing import Protocol


class AIProvider(Protocol):
    def generate(self, prompt: str, *, temperature: float = 0.4) -> str:
        """Genera texto a partir de un prompt plano."""
        ...

    def generate_vision(
        self,
        prompt: str,
        img_b64: str,
        mime: str = "image/png",
        *,
        temperature: float = 0.3,
    ) -> str:
        """Genera texto a partir de prompt + imagen en base64."""
        ...
