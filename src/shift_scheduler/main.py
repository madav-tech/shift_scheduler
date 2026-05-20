from fastapi import FastAPI

app = FastAPI(title="Shift Scheduler")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
