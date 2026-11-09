"""Ollama model discovery and RAM-based model recommendations."""

import httpx
import psutil


MODEL_PRESETS = {
    "low": {
        "label": "Low",
        "recommended_models": ["qwen2.5:1.5b", "phi3:mini", "llama3.2:3b"],
    },
    "mid": {
        "label": "Mid",
        "recommended_models": ["qwen2.5:7b", "llama3.2:3b"],
    },
    "high": {
        "label": "High",
        "recommended_models": ["qwen2.5:14b", "mistral-nemo"],
    },
}


class LLMManager:
    def __init__(self, host: str):
        self.host = host.rstrip("/")

    async def get_installed_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{self.host}/api/tags")
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise ValueError("Ollama returned an invalid model list.")
        return [
            str(model["name"])
            for model in payload["models"]
            if isinstance(model, dict) and isinstance(model.get("name"), str) and model["name"]
        ]

    @staticmethod
    def hardware_profile() -> dict:
        memory_gb = psutil.virtual_memory().total / (1024 ** 3)
        if memory_gb <= 8:
            tier = "low"
        elif memory_gb < 32:
            tier = "mid"
        else:
            tier = "high"
        return {
            "tier": tier,
            "ram_gb": round(memory_gb, 1),
            "recommended_models": MODEL_PRESETS[tier]["recommended_models"],
            "basis": "System RAM only; GPU VRAM is not detected.",
        }
