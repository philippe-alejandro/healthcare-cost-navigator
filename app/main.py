from fastapi import FastAPI
from app.api.providers import router as providers_router
from app.api.ask import router as ask_router


app = FastAPI(title="Healthcare Cost Navigator")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(providers_router)
app.include_router(ask_router)


