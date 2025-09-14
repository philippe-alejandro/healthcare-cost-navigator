from pydantic import BaseModel, Field
from typing import Optional


class ProviderResult(BaseModel):
    provider_id: str
    provider_name: str
    provider_city: str
    provider_state: str
    provider_zip_code: str
    distance_km: float
    drg_code: int
    drg_description: str
    average_covered_charges: Optional[float] = None
    average_total_payments: Optional[float] = None
    average_medicare_payments: Optional[float] = None
    avg_rating: Optional[float] = Field(default=None, description="Average star rating 1-10")


class ProviderQuery(BaseModel):
    drg: str
    zip: str
    radius_km: float = 40.0
    limit: int = 20
    sort: str = Field(default="cost", description="cost or rating")


