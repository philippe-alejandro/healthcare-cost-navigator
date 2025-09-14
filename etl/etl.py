import asyncio
import csv
import os
import random
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


async def load_zip_centroids(session: AsyncSession, path: str) -> None:
    if not Path(path).exists():
        return
    with open(path, newline="") as f:
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

        with open(DATA_CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            drg_seen: set[int] = set()
            provider_seen: set[str] = set()
            for row in reader:
                prov_id = row["provider_id"].strip()
                prov_name = row["provider_name"].strip()
                prov_city = row["provider_city"].strip()
                prov_state = row["provider_state"].strip()
                prov_zip = row["provider_zip_code"].strip().zfill(5)
                drg_code, drg_desc = parse_drg(row["ms_drg_definition"])  # type: ignore[index]

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

                avg_cov = Decimal(row["average_covered_charges"]) if row.get("average_covered_charges") else None
                avg_total = Decimal(row["average_total_payments"]) if row.get("average_total_payments") else None
                avg_medicare = Decimal(row["average_medicare_payments"]) if row.get("average_medicare_payments") else None
                discharges = int(row["total_discharges"]) if row.get("total_discharges") else None

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

        # Generate mock ratings (deterministic per provider_id)
        result = await session.execute(sa.text("SELECT id, provider_id FROM providers"))
        providers = result.fetchall()
        for pid, prov_ccn in providers:
            random.seed(prov_ccn)
            rating = random.randint(6, 10)
            await session.execute(
                insert(StarRating)
                .values(provider_id=pid, rating=rating, source="mock")
                .prefix_with("OR IGNORE")
            )

        await session.commit()
        print("ETL completed.")


if __name__ == "__main__":
    asyncio.run(run_etl())


