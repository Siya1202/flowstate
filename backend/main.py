from fastapi import FastAPI
from backend.ingestion.upload import router as upload_router

app = FastAPI(title="Flowstate API")

app.include_router(upload_router)

@app.get("/")
def root():
    return {"status": "Flowstate is running"}