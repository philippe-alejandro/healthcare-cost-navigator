from typing import List

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.ask import AskRequest, AskResult
from app.schemas.providers import ProviderResult
from app.services.nlp import parse_question


router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResult)
async def ask(req: AskRequest, session: AsyncSession = Depends(get_db_session)) -> AskResult:
    parsed = await parse_question(req.question)
    intent = parsed.get("intent", "info")

    if intent == "info":
        return AskResult(
            answer=(
                "I can help with hospital pricing and quality information. Ask about DRG codes, costs, or ratings."
            ),
            intent=intent,
            results=[],
            limit=parsed.get("limit", 5),
            sort=parsed.get("sort", "cost"),
        )

    drg_code = parsed.get("drg_code")
    drg_text = parsed.get("drg_text")
    zipc = parsed.get("zip")
    radius_km = float(parsed.get("radius_km", 40.0))
    limit = int(parsed.get("limit", 5))
    sort = parsed.get("sort", "cost")

    if not zipc:
        return AskResult(answer="Please provide a ZIP code.", intent=intent, results=[], limit=limit, sort=sort)

    # Find ZIP centroid
    zip_row = (
        await session.execute(sa.text("SELECT latitude, longitude FROM zip_codes WHERE zip = :zip"), {"zip": zipc})
    ).first()
    if not zip_row:
        return AskResult(answer="ZIP not found.", intent=intent, results=[], limit=limit, sort=sort)
    lat0, lon0 = zip_row

    if drg_code is None and drg_text:
        drg_row = (
            await session.execute(
                sa.text("SELECT code FROM drgs WHERE description ILIKE :q ORDER BY code LIMIT 1"), {"q": f"%{drg_text}%"}
            )
        ).first()
        if drg_row:
            drg_code = int(drg_row[0])

    if drg_code is None:
        return AskResult(answer="Please specify a DRG code or description.", intent=intent, results=[], limit=limit, sort=sort)

    order_sql = "pr.average_covered_charges ASC"
    if sort == "rating":
        order_sql = "avg_rating DESC NULLS LAST, pr.average_covered_charges ASC"

    query = sa.text(
        f"""
        WITH origin AS (
            SELECT CAST(:lat0 AS numeric) AS lat0, CAST(:lon0 AS numeric) AS lon0
        )
        SELECT 
            p.provider_id,
            p.provider_name,
            p.provider_city,
            p.provider_state,
            p.provider_zip_code,
            d.code AS drg_code,
            d.description AS drg_description,
            pr.average_covered_charges,
            pr.average_total_payments,
            pr.average_medicare_payments,
            AVG(sr.rating) AS avg_rating,
            2 * 6371 * asin(
                sqrt(
                    power(sin(radians((p.latitude - o.lat0)) / 2), 2) +
                    cos(radians(o.lat0)) * cos(radians(p.latitude)) *
                    power(sin(radians((p.longitude - o.lon0)) / 2), 2)
                )
            ) AS distance_km
        FROM providers p
        JOIN prices pr ON pr.provider_id = p.id
        JOIN drgs d ON d.code = pr.drg_code
        JOIN origin o ON TRUE
        LEFT JOIN star_ratings sr ON sr.provider_id = p.id
        WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
          AND d.code = :drg_code
        GROUP BY p.provider_id, p.provider_name, p.provider_city, p.provider_state, p.provider_zip_code,
                 d.code, d.description, pr.average_covered_charges, pr.average_total_payments, pr.average_medicare_payments,
                 o.lat0, o.lon0, p.latitude, p.longitude
        HAVING 2 * 6371 * asin(
                sqrt(
                    power(sin(radians((p.latitude - o.lat0)) / 2), 2) +
                    cos(radians(o.lat0)) * cos(radians(p.latitude)) *
                    power(sin(radians((p.longitude - o.lon0)) / 2), 2)
                )
            ) <= :radius_km
        ORDER BY {order_sql}
        LIMIT :limit
        """
    )
    rows = (
        await session.execute(
            query,
            {"lat0": lat0, "lon0": lon0, "radius_km": radius_km, "limit": limit, "drg_code": drg_code},
        )
    ).fetchall()

    results: list[ProviderResult] = []
    for r in rows:
        results.append(
            ProviderResult(
                provider_id=r.provider_id,
                provider_name=r.provider_name,
                provider_city=r.provider_city,
                provider_state=r.provider_state,
                provider_zip_code=r.provider_zip_code,
                distance_km=float(r.distance_km),
                drg_code=int(r.drg_code),
                drg_description=r.drg_description,
                average_covered_charges=float(r.average_covered_charges) if r.average_covered_charges is not None else None,
                average_total_payments=float(r.average_total_payments) if r.average_total_payments is not None else None,
                average_medicare_payments=float(r.average_medicare_payments) if r.average_medicare_payments is not None else None,
                avg_rating=float(r.avg_rating) if r.avg_rating is not None else None,
            )
        )

    if intent == "cheapest":
        intent_text = f"Cheapest providers for DRG {drg_code} near {zipc}"
    elif intent == "best_ratings":
        intent_text = f"Top-rated providers for DRG {drg_code} near {zipc}"
    else:
        intent_text = f"Results for DRG {drg_code} near {zipc}"

    if not results:
        answer = f"No results found within {radius_km:.0f} km."
    else:
        top = results[0]
        if sort == "rating" and top.avg_rating is not None:
            answer = f"Based on data, {top.provider_name} (rating: {top.avg_rating:.1f}/10) is a top option near {zipc}."
        else:
            # Prefer covered charges, else total payments, else Medicare payments
            price_value = None
            if top.average_covered_charges is not None:
                price_value = top.average_covered_charges
                price_label = "avg covered charges"
            elif top.average_total_payments is not None:
                price_value = top.average_total_payments
                price_label = "avg total payments"
            elif top.average_medicare_payments is not None:
                price_value = top.average_medicare_payments
                price_label = "avg Medicare payments"
            if price_value is not None:
                answer = f"Cheapest appears to be {top.provider_name} with {price_label} ${price_value:,.0f}."
            else:
                answer = f"Cheapest appears to be {top.provider_name}."

    return AskResult(
        answer=answer,
        intent=intent,
        drg_code=drg_code,
        zip=zipc,
        radius_km=radius_km,
        limit=limit,
        sort=sort,
        results=results,
    )


