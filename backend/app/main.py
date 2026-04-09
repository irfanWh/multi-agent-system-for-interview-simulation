from fastapi import FastAPI

app = FastAPI(title="InterviewAI")

@app.get("/health")
def health_check():
    return {"status": "ok"}
