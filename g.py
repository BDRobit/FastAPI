from fastapi import FastAPI

app = FastAPI(title="Mi API en Windows EC2")

@app.get("/")
def root():
    return {"message": "Hola desde FastAPI en Windows Server 2025"}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ff")
def ff():
    return {"status": "ok"}