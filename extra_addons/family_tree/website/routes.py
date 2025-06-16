from fastapi.responses import HTMLResponse

from papi.core import RESTRouter

router = RESTRouter(prefix="/family-tree")


@router.http("/")
async def family_tree_home_website():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width,initial-scale=1.0" />
            <title>My Family Tree</title>
            <link rel="stylesheet" href="/family_tree/libs/family-chart/dist/styles/family-chart.css">
            <link rel="stylesheet" href="/family_tree/css/style.css">
        </head>
        <body>
          <div id="FamilyChart" class="f3"></div>
        </body>
        <script src="/family_tree/libs/d3.min.js"></script>
        <script type="module" src="/family_tree/libs/family-chart/dist/family-chart.js"></script>
        <script type="module" src="/family_tree/libs/lodash.min.js"></script>
        <script type="module" src="/family_tree/js/script.js"></script>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
