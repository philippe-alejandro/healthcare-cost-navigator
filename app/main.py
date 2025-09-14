from fastapi import FastAPI


app = FastAPI(title="Healthcare Cost Navigator")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


