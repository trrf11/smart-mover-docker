# Smart Mover Docker - FastAPI Application
# Main entry point for the web application

from fastapi import FastAPI

app = FastAPI(
    title="Smart Mover",
    description="Intelligently move watched media from cache to array",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Dashboard endpoint - placeholder."""
    return {"status": "Smart Mover is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7878)
