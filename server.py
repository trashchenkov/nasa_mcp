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
async def nasa_apod(date: Optional[str] = None) -> Dict[str, Any]:
    """NASA APOD — Astronomy Picture of the Day (картинка/видео дня).

Назначение:
Инструмент для “быстрого вау-эффекта” и ежедневных космических сводок.
Подходит как стартовый шаг агента перед более “данными-ориентированными”
инструментами (марсоходы, астероиды, снимки Земли).

Параметры:
- date: опционально, дата в формате "YYYY-MM-DD".
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
        if date:
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
async def nasa_mars_rover_photos(
    rover: str,
    earth_date: str,
    camera: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
NASA Mars Rover Photos — фотографии марсоходов по земной дате.

Назначение:
Классический учебный инструмент для демонстрации работы агента с реальными
изображениями и фильтрами. Отлично подходит для сравнений разных камер и дат.

Параметры:
- rover: имя марсохода:
  "curiosity", "opportunity", "spirit".
- earth_date: земная дата съёмки в формате "YYYY-MM-DD".
- camera: опционально, фильтр камеры.
  Примеры распространённых камер:
  "FHAZ", "RHAZ", "MAST", "CHEMCAM", "NAVCAM", "MAHLI", "MARDI".
  Если не указана, возвращаются фото всех доступных камер на эту дату.
- limit: ограничение количества элементов в выдаче (по умолчанию 10).

Поведение:
- API может вернуть 0 фото на конкретную дату — это нормальный сценарий.
- При указании камеры, не работавшей в этот день, тоже будет 0 результатов.

Возвращает:
{
  "ok": true,
  "rover": "curiosity|opportunity|spirit",
  "earth_date": "YYYY-MM-DD",
  "camera": str | null,
  "count": <сколько фото найдено всего>,
  "items": [
    {
      "id": int,
      "camera": str,
      "img_src": str,
      "earth_date": "YYYY-MM-DD",
      "rover_name": str
    }, ...
  ]
}

Ошибки:
{
  "ok": false,
  "error": "<тип_ошибки>: <сообщение>"
}

Подсказки для агента:
- Отлично для запросов:
  "Покажи 5 фото Curiosity за 2018-06-01."
  "Сравни снимки FHAZ и MAST на одной дате."
- Если результатов много, достаточно 5–10 для просмотра.
"""
    try:
        rover = rover.strip().lower()
        params = {"earth_date": earth_date, "api_key": _key()}
        if camera:
            params["camera"] = camera

        data = await _get(
            f"https://api.nasa.gov/mars-photos/api/v1/rovers/{rover}/photos",
            params,
        )
        photos = data.get("photos") or []
        items = [
            {
                "id": p.get("id"),
                "camera": (p.get("camera") or {}).get("name"),
                "img_src": p.get("img_src"),
                "earth_date": p.get("earth_date"),
                "rover_name": (p.get("rover") or {}).get("name"),
            }
            for p in photos[: max(1, limit)]
        ]

        return {
            "ok": True,
            "rover": rover,
            "earth_date": earth_date,
            "camera": camera,
            "count": len(photos),
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


@mcp.tool()
async def nasa_epic_latest(
    mode: str = "natural",
    limit: int = 5,
) -> Dict[str, Any]:
    """
NASA EPIC — последние метаданные снимков Земли (DSCOVR/EPIC).

Назначение:
Визуальный инструмент для демонстрации “Земля из космоса”.
Хорошо дополняет APOD: APOD — про Вселенную в целом,
EPIC — про нашу планету “прямо сейчас”.

Параметры:
- mode: тип обработки изображений:
  "natural" — естественные цвета,
  "enhanced" — усиленная обработка.
- limit: сколько последних записей вернуть (по умолчанию 5).

Поведение:
- Инструмент возвращает метаданные (identifier/caption/date/image).
- При желании можно расширить тул, чтобы он собирал готовые URL картинок
  по шаблону EPIC, но для компактного демо часто достаточно метаданных.

Возвращает:
{
  "ok": true,
  "mode": "natural|enhanced",
  "count": <сколько записей доступно всего>,
  "items": [
    {
      "identifier": str,
      "caption": str,
      "date": str,
      "image": str
    }, ...
  ]
}

Ошибки:
{
  "ok": false,
  "error": "<тип_ошибки>: <сообщение>"
}

Подсказки для агента:
- Команды:
  "Покажи последние 3 снимка Земли."
  "Сравни natural и enhanced на последних данных."
"""
    try:
        mode = mode.strip().lower()
        params = {"api_key": _key()}
        data = await _get(f"https://api.nasa.gov/EPIC/api/{mode}", params)

        arr = data if isinstance(data, list) else []
        items = [
            {
                "identifier": it.get("identifier"),
                "caption": it.get("caption"),
                "date": it.get("date"),
                "image": it.get("image"),
            }
            for it in arr[: max(1, limit)]
        ]

        return {"ok": True, "mode": mode, "count": len(arr), "items": items}
    except Exception as e:
        return _err(e)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
