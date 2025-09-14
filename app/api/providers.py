from typing import List

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.providers import ProviderResult


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=List[ProviderResult])
async def list_providers(
    drg: str = Query(..., description="DRG code (e.g., 470) or description text"),
    zip: str = Query(..., description="ZIP code"),
    radius_km: float = Query(40.0, ge=1.0, le=200.0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("cost", pattern="^(cost|rating)$"),
    session: AsyncSession = Depends(get_db_session),
):
    # ZIP centroid
    zip_row = (
        await session.execute(
            sa.text("SELECT latitude, longitude FROM zip_codes WHERE zip = :zip"),
            {"zip": zip.zfill(5)},
        )
    ).first()
    if not zip_row:
        raise HTTPException(status_code=404, detail="ZIP not found")
    lat0, lon0 = zip_row

    # DRG code vs description
    try:
        drg_code = int(drg)
        drg_filter_sql = "d.code = :drg_code"
        drg_params = {"drg_code": drg_code}
    except ValueError:
        drg_filter_sql = "d.description ILIKE :drg_text"
        drg_params = {"drg_text": f"%{drg}%"}

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
          AND {drg_filter_sql}
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

    result = await session.execute(
        query,
        {"lat0": lat0, "lon0": lon0, "radius_km": radius_km, "limit": limit, **drg_params},
    )
    rows = result.fetchall()
    output: list[ProviderResult] = []
    for r in rows:
        output.append(
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
    return output


