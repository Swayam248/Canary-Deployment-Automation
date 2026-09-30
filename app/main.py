from fastapi import FastAPI, Response

app = FastAPI()

VERSION = "v2"


@app.get("/")
def root():
    return {
        "message": "Hello from Canary Deployment",
        "version": VERSION
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": VERSION
    }