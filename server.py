from __future__ import annotations

import os
from typing import Optional, Dict, Any, List

import httpx

# Совместимость с разными окружениями FastMCP
try:
    from fastmcp import FastMCP
except Exception:
    from mcp.server.fastmcp import FastMCP  # type: ignore

mcp = FastMCP("nasa-4-tools")


def _key() -> str:
    return os.getenv("NASA_API_KEY", "DEMO_KEY")


async def _get(url: str, params: Dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _err(e: Exception) -> Dict[str, Any]:
    msg = str(e) or "Unknown error"
    return {"ok": False, "error": f"{type(e).__name__}: {msg}"}


@mcp.tool()
async def nasa_apod(date: str = "") -> Dict[str, Any]:
    """NASA APOD — Astronomy Picture of the Day (картинка/видео дня).

Назначение:
Инструмент для “быстрого вау-эффекта” и ежедневных космических сводок.
Подходит как стартовый шаг агента перед более “данными-ориентированными”
инструментами (марсоходы, астероиды, снимки Земли).

Параметры:
- date: строка 'YYYY-MM-DD'. Если пустая — вернётся текущий APOD от NASA.
  Если не задана, возвращается APOD за текущий день по версии NASA.

Поведение:
- media_type может быть "image" или "video".
- url — основная ссылка на медиа.
- hdurl — ссылка на версию высокого разрешения (может отсутствовать).

Возвращает:
{
  "ok": true,
  "title": str,
  "date": "YYYY-MM-DD",
  "media_type": "image" | "video",
  "url": str,
  "hdurl": str | null,
  "explanation": str
}

Ошибки:
{
  "ok": false,
  "error": "<тип_ошибки>: <сообщение>"
}

Подсказки для агента:
- Хорош для команд:
  "Покажи космическую картинку дня и кратко поясни, что на ней."
  "Дай APOD за 2020-07-30."
- Если media_type == "video", стоит сообщить пользователю, что это видео,
  и вывести url."""
    try:
        params = {"api_key": _key()}
        if date != "":
            params["date"] = date
        data = await _get("https://api.nasa.gov/planetary/apod", params)

        return {
            "ok": True,
            "title": data.get("title"),
            "date": data.get("date"),
            "media_type": data.get("media_type"),
            "url": data.get("url"),
            "hdurl": data.get("hdurl"),
            "explanation": data.get("explanation"),
        }
    except Exception as e:
        return _err(e)


@mcp.tool()
async def nasa_donki_recent_events(
    event_type: str = "FLR",
    days: int = 3,
    limit: int = 20,
) -> Dict[str, Any]:
    """
NASA DONKI — недавние события космической погоды (Solar Flares, CME, бури).

Назначение:
Инструмент для сводок по космической погоде: вспышки на Солнце, корональные
выбросы массы, геомагнитные бури. Хорошо работает в сочетании с APOD и NeoWs.

Параметры:
- event_type:
  - "FLR" — солнечные вспышки (Solar Flares)
  - "CME" — корональные выбросы массы
  - "GST" — геомагнитные бури
  - "ALL" — собрать несколько базовых типов (FLR, CME, GST)
- days: за сколько последних суток брать события (>=1).
- limit: максимальное число событий в итоговом списке после сортировки.

Возвращает:
{
  "ok": true,
  "range": {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
  "event_types": ["FLR", "CME", ...],
  "count": int,
  "events": [
    {
      "type": "FLR" | "CME" | "GST" | ...,
      "id": str | null,
      "start_time": str | null,
      "source": str | null,
      "link": str | null
    }, ...
  ]
}

Ошибки:
{
  "ok": false,
  "error": "<тип_ошибки>: <сообщение>"
}

Подсказки для агента:
- Примеры команд:
  "Что по космической погоде за последние 3 дня?"
  "Есть ли сильные солнечные вспышки за неделю?"
"""
    try:
        from datetime import date, timedelta

        days = max(int(days), 1)
        limit = max(int(limit), 1)

        end = date.today()
        start = end - timedelta(days=days)
        start_str = start.isoformat()
        end_str = end.isoformat()

        et = (event_type or "FLR").upper()
        if et == "ALL":
            types: List[str] = ["FLR", "CME", "GST"]
        else:
            types = [et]

        events: List[Dict[str, Any]] = []

        for t in types:
            params = {
                "startDate": start_str,
                "endDate": end_str,
                "api_key": _key(),
            }
            data = await _get(f"https://api.nasa.gov/DONKI/{t}", params)
            if not isinstance(data, list):
                continue

            for raw in data:
                event_id = (
                    raw.get("flrID")
                    or raw.get("gstID")
                    or raw.get("cmeID")
                    or raw.get("activityID")
                    or raw.get("eventID")
                )
                start_time = (
                    raw.get("beginTime")
                    or raw.get("startTime")
                    or raw.get("timeStart")
                    or raw.get("timeTag")
                )
                source = (
                    raw.get("sourceLocation")
                    or raw.get("location")
                    or raw.get("source")
                )
                link = raw.get("link") or raw.get("url")

                events.append(
                    {
                        "type": t,
                        "id": event_id,
                        "start_time": start_time,
                        "source": source,
                        "link": link,
                    }
                )

        events_sorted = sorted(
            events,
            key=lambda e: e.get("start_time") or "",
            reverse=True,
        )

        events_limited = events_sorted[:limit]

        return {
            "ok": True,
            "range": {"start_date": start_str, "end_date": end_str},
            "event_types": types,
            "count": len(events_limited),
            "events": events_limited,
        }
    except Exception as e:
        return _err(e)


@mcp.tool()
async def nasa_media_search(
    query: str,
    media_type: str = "image",
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    page: int = 1,
) -> Dict[str, Any]:
    """
NASA Image and Video Library — поиск изображений/видео/аудио.

Назначение:
Инструмент для “подборки картинок”: агент может искать фото/видео NASA по теме
(Марс, запуск ракет, МКС, галактики и т.п.), а затем выдавать ссылки/превью.

Параметры:
- query: строка поиска (ключевые слова, на англ. обычно лучше).
- media_type: "image", "video", "audio" или комбинация через запятую
  (например, "image,video").
- year_start: опциональный нижний предел года (int).
- year_end: опциональный верхний предел года (int).
- page: номер страницы результатов (>=1).

Возвращает:
{
  "ok": true,
  "query": str,
  "media_type": str,
  "page": int,
  "count": int,
  "items": [
    {
      "nasa_id": str,
      "title": str,
      "media_type": "image" | "video" | "audio",
      "date_created": str | null,
      "description": str | null,
      "preview": str | null  # URL превью-изображения
    }, ...
  ]
}

Ошибки:
{
  "ok": false,
  "error": "<тип_ошибки>: <сообщение>"
}

Подсказки для агента:
- Примеры команд:
  "Найди 5 картинок с запуском ракеты Saturn V."
  "Подбери изображения марсианских пейзажей."
"""
    try:
        url = "https://images-api.nasa.gov/search"

        page = max(int(page), 1)

        params: Dict[str, Any] = {
            "q": query,
            "media_type": media_type,
            "page": page,
        }
        if year_start is not None:
            params["year_start"] = int(year_start)
        if year_end is not None:
            params["year_end"] = int(year_end)

        data = await _get(url, params)
        collection = data.get("collection") or {}
        raw_items = collection.get("items") or []

        items: List[Dict[str, Any]] = []
        for it in raw_items:
            data_block = (it.get("data") or [{}])[0]
            links_block = it.get("links") or []

            preview = None
            for ln in links_block:
                href = ln.get("href")
                if href:
                    preview = href
                    break

            items.append(
                {
                    "nasa_id": data_block.get("nasa_id"),
                    "title": data_block.get("title"),
                    "media_type": data_block.get("media_type"),
                    "date_created": data_block.get("date_created"),
                    "description": data_block.get("description"),
                    "preview": preview,
                }
            )

        return {
            "ok": True,
            "query": query,
            "media_type": media_type,
            "page": page,
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        return _err(e)



@mcp.tool()
async def nasa_neows_feed(
    start_date: str,
    end_date: str,
    hazardous_only: bool = False,
    limit: int = 20,
) -> Dict[str, Any]:
    """
NASA NeoWs Feed — околоземные объекты (астероиды) за период.

Назначение:
Инструмент для “детективных” сценариев и работы со структурированными данными:
агент может делать сводки, фильтровать потенциально опасные объекты,
строить мини-топы по размеру или близости.

Параметры:
- start_date: начало периода "YYYY-MM-DD".
- end_date: конец периода "YYYY-MM-DD".
- hazardous_only: если true, возвращать только потенциально опасные астероиды.
- limit: ограничение количества объектов в выдаче (по умолчанию 20).

Что именно отдаём:
Инструмент формирует уплощённый список объектов из ответа feed,
достаёт базовую оценку размера и первое событие сближения (если есть):
- estimated_diameter_m (min/max)
- close_approach_date
- miss_distance_km
- relative_velocity_kmh

Возвращает:
{
  "ok": true,
  "range": {"start_date": "...", "end_date": "..."},
  "hazardous_only": bool,
  "count": <сколько объектов подходит фильтру>,
  "items": [
    {
      "name": str,
      "is_potentially_hazardous": bool,
      "estimated_diameter_m": {"min": float | null, "max": float | null},
      "close_approach_date": "YYYY-MM-DD",
      "miss_distance_km": float | null,
      "relative_velocity_kmh": float | null,
      "nasa_jpl_url": str | null
    }, ...
  ]
}

Ошибки:
{
  "ok": false,
  "error": "<тип_ошибки>: <сообщение>"
}

Подсказки для агента:
- Хорошие команды:
  "Есть ли опасные астероиды за последние 7 дней?"
  "Сделай краткую сводку по объектам на этой неделе."
- Для коротких сводок разумно ставить limit=10–20.
"""
    try:
        params = {"start_date": start_date, "end_date": end_date, "api_key": _key()}
        data = await _get("https://api.nasa.gov/neo/rest/v1/feed", params)

        neo_by_date = data.get("near_earth_objects") or {}
        flat: List[Dict[str, Any]] = []

        for d, arr in neo_by_date.items():
            for obj in arr or []:
                is_h = bool(obj.get("is_potentially_hazardous_asteroid"))
                if hazardous_only and not is_h:
                    continue

                diam = (obj.get("estimated_diameter") or {}).get("meters") or {}
                ca = (obj.get("close_approach_data") or [{}])[0] or {}
                miss = (ca.get("miss_distance") or {}).get("kilometers")
                vel = (ca.get("relative_velocity") or {}).get("kilometers_per_hour")

                flat.append(
                    {
                        "name": obj.get("name"),
                        "is_potentially_hazardous": is_h,
                        "estimated_diameter_m": {
                            "min": diam.get("estimated_diameter_min"),
                            "max": diam.get("estimated_diameter_max"),
                        },
                        "close_approach_date": ca.get("close_approach_date") or d,
                        "miss_distance_km": float(miss) if miss else None,
                        "relative_velocity_kmh": float(vel) if vel else None,
                        "nasa_jpl_url": obj.get("nasa_jpl_url"),
                    }
                )

        return {
            "ok": True,
            "range": {"start_date": start_date, "end_date": end_date},
            "hazardous_only": hazardous_only,
            "count": len(flat),
            "items": flat[: max(1, limit)],
        }
    except Exception as e:
        return _err(e)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
