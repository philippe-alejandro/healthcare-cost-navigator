from typing import List, Optional
from pydantic import BaseModel

from .providers import ProviderResult


class AskRequest(BaseModel):
    question: str


class AskResult(BaseModel):
    answer: str
    intent: str
    drg_code: Optional[int] = None
    drg_text: Optional[str] = None
    zip: Optional[str] = None
    radius_km: Optional[float] = None
    limit: int = 5
    sort: str = "cost"
    results: List[ProviderResult] = []


