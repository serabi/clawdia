"""Weather MCP server stub — Phase 1 health endpoint only."""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def health(request):
    return JSONResponse({"status": "ok"})


app = Starlette(routes=[Route("/health", health)])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
