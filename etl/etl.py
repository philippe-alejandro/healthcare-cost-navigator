import asyncio
import csv
import os
import random
import re
from decimal import Decimal
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Provider, DRG, Price, StarRating, ZipCode
from app.db.session import ASYNC_SESSION_MAKER


DATA_CSV_PATH = os.getenv("CMS_CSV", "data/sample_prices_ny.csv")
ZIP_CENTROIDS_PATH = os.getenv("ZIP_CSV", "data/zipcodes.csv")


def parse_drg(ms_drg_definition: str) -> tuple[Optional[int], str]:
    if not ms_drg_definition:
        return None, ""
    parts = ms_drg_definition.split("-", 1)
    try:
        code = int(parts[0].strip())
    except Exception:
        code = None
    desc = parts[1].strip() if len(parts) > 1 else ms_drg_definition.strip()
    return code, desc


def first_nonempty(row: dict, keys: list[str]) -> Optional[str]:
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s != "":
            return s
    return None


def clean_money(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
def clean_state(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().upper()[:2]

    s = str(value).strip()
    if s == "":
        return None
    s = s.replace(",", "").replace("$", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return Decimal(s)
    except Exception:
        return None


async def load_zip_centroids(session: AsyncSession, path: str) -> None:
    if not Path(path).exists():
        return
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append(
                {
                    "zip": r["zip"].zfill(5),
                    "city": r.get("city", "").strip(),
                    "state": r.get("state", "").strip(),
                    "latitude": Decimal(r["latitude"]) if r.get("latitude") else None,
                    "longitude": Decimal(r["longitude"]) if r.get("longitude") else None,
                }
            )
        if rows:
            stmt = pg_insert(ZipCode).values(rows).on_conflict_do_nothing(index_elements=[ZipCode.__table__.c.zip])
            await session.execute(stmt)


async def run_etl() -> None:
    async with ASYNC_SESSION_MAKER() as session:
        await session.run_sync(lambda s: None)

        await load_zip_centroids(session, ZIP_CENTROIDS_PATH)

        if not Path(DATA_CSV_PATH).exists():
            await session.commit()
            print(f"CSV not found at {DATA_CSV_PATH}; skipping prices load")
            return

        with open(DATA_CSV_PATH, newline="", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            drg_seen: set[int] = set()
            provider_seen: set[str] = set()
            for row in reader:
                # Map provider fields across possible schemas
                prov_id = first_nonempty(row, ["provider_id", "Rndrng_Prvdr_CCN"]) or ""
                prov_name = first_nonempty(row, ["provider_name", "Rndrng_Prvdr_Org_Name"]) or ""
                prov_city = first_nonempty(row, ["provider_city", "Rndrng_Prvdr_City"]) or ""
                # Prefer two-letter abbreviation; do NOT use Rndrng_Prvdr_St (street address)
                prov_state = clean_state(first_nonempty(row, ["provider_state", "Rndrng_Prvdr_State_Abrvtn"]))
                prov_zip = (first_nonempty(row, ["provider_zip_code", "Rndrng_Prvdr_Zip5"]) or "").zfill(5)

                # DRG mapping: either explicit code/desc columns or combined definition
                if row.get("DRG_Cd") or row.get("DRG_Desc"):
                    try:
                        drg_code = int(str(row.get("DRG_Cd", "")).strip() or 0) or None
                    except Exception:
                        drg_code = None
                    drg_desc = str(row.get("DRG_Desc", "")).strip()
                else:
                    drg_code, drg_desc = parse_drg(str(row.get("ms_drg_definition", "")))

                if drg_code is None:
                    continue

                if drg_code not in drg_seen:
                    stmt = (
                        pg_insert(DRG)
                        .values(code=drg_code, description=drg_desc)
                        .on_conflict_do_nothing(index_elements=[DRG.__table__.c.code])
                    )
                    await session.execute(stmt)
                    drg_seen.add(drg_code)

                if prov_id not in provider_seen:
                    stmt = (
                        pg_insert(Provider)
                        .values(
                            provider_id=prov_id,
                            provider_name=prov_name,
                            provider_city=prov_city,
                            provider_state=prov_state,
                            provider_zip_code=prov_zip,
                        )
                        .on_conflict_do_nothing(index_elements=[Provider.__table__.c.provider_id])
                    )
                    await session.execute(stmt)
                    provider_seen.add(prov_id)

                avg_cov = clean_money(first_nonempty(row, ["average_covered_charges", "Avg_Submtd_Cvrd_Chrg"]))
                avg_total = clean_money(first_nonempty(row, ["average_total_payments", "Avg_Tot_Pymt_Amt"]))
                avg_medicare = clean_money(first_nonempty(row, ["average_medicare_payments", "Avg_Mdcr_Pymt_Amt"]))
                discharges_str = first_nonempty(row, ["total_discharges", "Tot_Dschrgs"]) or ""
                try:
                    discharges = int(re.sub(r"[^0-9]", "", discharges_str)) if discharges_str else None
                except Exception:
                    discharges = None

                await session.execute(
                    sa.text(
                        """
                        INSERT INTO prices (provider_id, drg_code, total_discharges, average_covered_charges, average_total_payments, average_medicare_payments)
                        SELECT p.id, :drg_code, :discharges, :avg_cov, :avg_total, :avg_medicare
                        FROM providers p WHERE p.provider_id = :prov_id
                        """
                    ),
                    {
                        "prov_id": prov_id,
                        "drg_code": drg_code,
                        "discharges": discharges,
                        "avg_cov": avg_cov,
                        "avg_total": avg_total,
                        "avg_medicare": avg_medicare,
                    },
                )

        # Populate provider lat/lon from ZIP centroids
        await session.execute(
            sa.text(
                """
                UPDATE providers p
                SET latitude = z.latitude, longitude = z.longitude
                FROM zip_codes z
                WHERE p.provider_zip_code = z.zip AND (p.latitude IS NULL OR p.longitude IS NULL)
                """
            )
        )

        # Generate mock ratings (deterministic per provider_id)
        result = await session.execute(sa.text("SELECT id, provider_id FROM providers"))
        providers = result.fetchall()
        for pid, prov_ccn in providers:
            random.seed(prov_ccn)
            rating = random.randint(6, 10)
            # Insert only if not exists, no unique constraint required
            await session.execute(
                sa.text(
                    """
                    INSERT INTO star_ratings(provider_id, rating, source)
                    SELECT :pid, :rating, 'mock'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM star_ratings WHERE provider_id = :pid
                    )
                    """
                ),
                {"pid": pid, "rating": rating},
            )

        await session.commit()
        print("ETL completed.")


if __name__ == "__main__":
    asyncio.run(run_etl())


