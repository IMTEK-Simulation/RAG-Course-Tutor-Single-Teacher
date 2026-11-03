from __future__ import annotations

from urllib.parse import urlsplit
import httpx


def validate_api_url(base_url: str) -> str:
    """Only authenticated teachers choose URLs; public requests cannot override them."""
    requested = urlsplit(base_url.strip().rstrip("/"))
    if (requested.scheme not in {"http", "https"} or not requested.hostname
            or requested.username or requested.password or requested.query or requested.fragment):
        raise ValueError("Bitte eine HTTP(S)-Serveradresse ohne Zugangsdaten, Query oder Fragment angeben.")
    try:
        requested.port
    except ValueError as exc:
        raise ValueError("Ungültiger Server-Port") from exc
    return base_url.strip().rstrip("/")


async def list_models(base_url: str, api_key: str, provider: str = "openai-compatible") -> list[dict]:
    base_url = validate_api_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    endpoint = "/api/tags" if provider == "ollama" else "/models"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(base_url + endpoint, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if provider == "ollama":
        return [{"id": item["name"], "name": item["name"]} for item in payload.get("models", [])]
    return [{"id": item["id"], "name": item.get("name") or item["id"]} for item in payload.get("data", [])]


async def chat(base_url: str, model: str, api_key: str, messages: list[dict],
               provider: str = "openai-compatible", temperature: float = 0,
               max_tokens: int = 1024) -> str:
    base_url = validate_api_url(base_url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": messages, "stream": False}
    if provider == "ollama":
        endpoint = "/api/chat"
        payload["options"] = {"temperature": temperature, "num_predict": max_tokens}
    else:
        endpoint = "/chat/completions"
        payload.update(temperature=temperature, max_tokens=max_tokens)
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(base_url + endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["message"]["content"] if provider == "ollama" else data["choices"][0]["message"]["content"]
