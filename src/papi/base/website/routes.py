from fastapi.responses import HTMLResponse

from papi.core.router import RESTRouter

website_router = RESTRouter()


@website_router.http("/")
async def website_index():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>pAPI - Pluggable API</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f9fafb;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    color: #2c3e50;
                }
                .container {
                    text-align: center;
                    background-color: #ffffff;
                    padding: 2.5rem 3rem;
                    border-radius: 1rem;
                    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
                    max-width: 500px;
                }
                h1 {
                    font-size: 2.25rem;
                    margin-bottom: 0.5rem;
                }
                .subtitle {
                    font-size: 1.1rem;
                    color: #7f8c8d;
                    margin-bottom: 1.5rem;
                }
                .status-dot {
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background-color: #2ecc71;
                    margin-right: 8px;
                    vertical-align: middle;
                }
                .footer {
                    margin-top: 2rem;
                    font-size: 0.9rem;
                    color: #95a5a6;
                }
                b {
                    font-weight: 600;
                }
                .btn {
                    display: inline-block;
                    margin-top: 1.5rem;
                    padding: 0.75rem 1.5rem;
                    font-size: 1rem;
                    color: #fff;
                    background-color: #3498db;
                    border: none;
                    border-radius: 8px;
                    text-decoration: none;
                    transition: background-color 0.3s ease;
                }
                .btn:hover {
                    background-color: #2980b9;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>pAPI</h1>
                <p class="subtitle"><b>p</b>luggable <b>API</b> platform</p>
                <p><span class="status-dot"></span>Server is <b>online</b> and ready</p>
                <a href="/docs" class="btn">📘 Open API Docs</a>
                <div class="footer">
                    FastAPI · Uvicorn
                </div>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
