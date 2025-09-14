import os
import re
from typing import Any, Dict, Optional

from openai import AsyncOpenAI


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


async def parse_question(question: str) -> Dict[str, Any]:
    """
    Use OpenAI to parse NL into structured intent. Fallback to simple regex if API not configured.
    Returns keys: intent (cheapest|best_ratings|info), drg_code?, drg_text?, zip?, radius_km?, limit?, sort?
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_parse(question)

    client = AsyncOpenAI(api_key=api_key)
    system = (
        "You translate patient questions about hospital pricing and ratings into a strict JSON object."
        " Only include the fields you can infer. Use {intent, drg_code, drg_text, zip, radius_km, limit, sort}."
        " intent must be one of: cheapest, best_ratings, info. sort is cost or rating."
        " Default radius_km to 40 and limit to 5 if not specified."
        " If the question is out of scope (not about hospitals, DRG, pricing, cost, rating), set intent=info."
    )
    user = f"Question: {question}\nReturn ONLY compact JSON."

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        content = resp.choices[0].message.content or "{}"
        import json

        return json.loads(content)
    except Exception:
        return fallback_parse(question)


def fallback_parse(question: str) -> Dict[str, Any]:
    q = question.lower()
    intent = "cheapest" if ("cheapest" in q or "lowest" in q) else ("best_ratings" if "best" in q or "rating" in q else "info")
    drg_code: Optional[int] = None
    m = re.search(r"drg\s*(\d{3})", q)
    if m:
        drg_code = int(m.group(1))
    mzip = re.search(r"(\b\d{5}\b)", q)
    zipc = mzip.group(1) if mzip else None
    mrad = re.search(r"(\d{1,3})\s*(miles|mi|mile)", q)
    radius_km = None
    if mrad:
        miles = float(mrad.group(1))
        radius_km = miles * 1.60934
    return {
        "intent": intent,
        "drg_code": drg_code,
        "zip": zipc,
        "radius_km": radius_km or 40.0,
        "limit": 5,
        "sort": "cost" if intent != "best_ratings" else "rating",
    }


