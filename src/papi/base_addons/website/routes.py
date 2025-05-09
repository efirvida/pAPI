from fastapi import APIRouter
from fastapi.responses import HTMLResponse

website_router = APIRouter()


@website_router.get("/")
async def website_index():
    html_content = """
    <html>
        <head>
            <title>pAPI</title>
        </head>
        <body>
            <h1>I'm Online</h1>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
