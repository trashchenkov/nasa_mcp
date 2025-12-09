# server.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any

import httpx

# Совместимость с разными сборками/окружениями FastMCP
try:
    # Вариант из пакета fastmcp
    from fastmcp import FastMCP
except Exception:
    # Вариант из пакета mcp
    from mcp.server.fastmcp import FastMCP  # type: ignore

mcp = FastMCP("nasa-mini")


def _get_nasa_key() -> str:
    return os.getenv("NASA_API_KEY", "DEMO_KEY")


@mcp.tool()
async def nasa_apod(date: Optional[str] = None) -> Dict[str, Any]:
    """
    NASA APOD (Astronomy Picture of the Day).

    Аргументы:
    - date: опционально, дата в формате YYYY-MM-DD.
      Если не указана, вернётся APOD за сегодня (по данным NASA).

    Возвращает:
    - ok: bool
    - title: str
    - date: str
    - explanation: str (коротко)
    - media_type: 'image' | 'video'
    - url: ссылка на медиа
    - hdurl: может отсутствовать
    - error: при ошибке

    Использует публичный NASA API.
    """
    api_key = _get_nasa_key()
    url = "https://api.nasa.gov/planetary/apod"

    params = {"api_key": api_key}
    if date:
        params["date"] = date

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params=params)
            # Иногда NASA отдаёт текст ошибки в json с 4xx
            if r.status_code >= 400:
                try:
                    payload = r.json()
                except Exception:
                    payload = {"message": r.text}

                return {
                    "ok": False,
                    "error": {
                        "where": "nasa",
                        "kind": "http_error",
                        "status": r.status_code,
                        "message": payload.get("msg") or payload.get("error") or payload.get("message") or "Unknown error",
                    },
                }

            data = r.json()

        # Немного “укоротим” explanation, чтобы агенту было легче
        explanation = (data.get("explanation") or "").strip()
        if len(explanation) > 600:
            explanation = explanation[:600].rstrip() + "…"

        return {
            "ok": True,
            "title": data.get("title"),
            "date": data.get("date"),
            "media_type": data.get("media_type"),
            "url": data.get("url"),
            "hdurl": data.get("hdurl"),
            "explanation": explanation,
            "service_version": data.get("service_version"),
            "note": "Используется ключ NASA_API_KEY или DEMO_KEY.",
        }

    except httpx.ConnectTimeout:
        return {
            "ok": False,
            "error": {
                "where": "nasa",
                "kind": "connect_timeout",
                "message": "Connection timed out",
            },
        }
    except httpx.RequestError as e:
        return {
            "ok": False,
            "error": {
                "where": "nasa",
                "kind": "request_error",
                "message": str(e),
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "where": "server",
                "kind": "unexpected",
                "message": str(e),
            },
        }


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
