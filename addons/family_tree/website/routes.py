from fastapi.responses import HTMLResponse

from papi.core import pAPIRouter

router = pAPIRouter(prefix="/family-tree")


@router.http("/")
async def family_tree_home_website():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width,initial-scale=1.0" />
            <title>my-family-chart</title>
            <script src="/static/family_tree/js/d3.min.js"></script>
            <script type="module" src="/static/family_tree/js/family-chart.min.js"></script>
            <link rel="stylesheet" href="/static/family_tree/css/family-chart.css">
            <link rel="stylesheet" href="/static/family_tree/css/style.css">
        </head>
        <body>
          <div id="FamilyChart" class="f3"></div>
        </body>
        <script type="module" src="/static/family_tree/js/script.js"></script>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
