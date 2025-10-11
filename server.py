from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import time

app = FastAPI()

async def count_generator():
    """Generator that counts from 1 to 10 with 2-second intervals"""
    for i in range(1, 11):
        yield f"data: {i}\n\n"
        await asyncio.sleep(2)

@app.get("/stream")
async def stream_count():
    """
    Endpoint that streams count from 1-10 with 2-second intervals
    Uses Server-Sent Events (SSE) format
    """
    return StreamingResponse(
        count_generator(),
        media_type="text/event-stream"
    )

@app.get("/")
async def root():
    """Root endpoint with usage instructions"""
    return {
        "message": "FastAPI Streaming Counter",
        "endpoint": "/stream",
        "description": "Streams count from 1-10 with 2-second intervals",
        "usage": "Visit http://localhost:8000/stream in your browser or use curl"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)