# Simple Website

In this tutorial, we demonstrate how to use static files within each addon module.
Although the main focus of pAPI, like FastAPI, is on building APIs rather than full-stack web applications (like Django), pAPI can still serve static files and web pages easily.

This example is not intended to cover template engines or advanced web development techniques. Instead, it focuses on how to serve static assets using a basic HTML response as an example.

During the addon discovery and initialization process, pAPI will automatically detect a `static` folder at the root of your addon. If such a folder exists, it will be mounted as a static file directory for your module (and made available globally across all modules). This allows you to structure your addon as follows:

---

### 🗂️ Project Structure

```bash
my_addons/
└── website/
    ├── static/
    │   └── style.css
    ├── __init__.py
    ├── manifest.yaml
    └── routers.py
```

---

### 🎨 `style.css`

Here's the styling for our simple page:

```css
body {
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
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
```

---

### 🌐 `routers.py`

```python
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
            <link rel="stylesheet" href="/website/style.css">
        </head>
        <body>
            <div class="container">
                <h1>pAPI</h1>
                <p class="subtitle"><b>p</b>luggable <b>API</b> platform</p>
                <p><span class="status-dot"></span>Server is <b>online</b> and ready</p>
                <a href="https://efirvida.github.io/pAPI/" class="btn">📘 Open API Docs</a>
                <div class="footer">
                    FastAPI · Uvicorn
                </div>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
```

Note: Static files will be available under `/addons_name/` path prefix.

---

### 📦 `__init__.py`

To activate the routes, just import the `routers.py` in your module:

```python
from . import routes
```

---

### 📄 `manifest.yaml`

```yaml
title: "Website Module"
version: "0.1.0"
description: "Base module for public website interface and assets."
```

---

### ⚙️ `config.yaml`

Activate the addon by adding it to your configuration:

```yaml
# Base configuration – see the Hello World example
...

addons:
  extra_addons_path: "my_addons"
  enabled:
    - website
```

---

### 🚀 Launch the server

```bash
rye run python papi/cli.py webserver
```

---

### 🗃️ Global Static File Storage

pAPI also provides a global static file configuration, designed for serving static assets like images, documents, videos, etc., independently of any addon. This can be useful when your API needs to act as a file server.

You can configure it in the `config.yaml` under the `storage` section. Although this feature wasn’t originally intended for serving stylesheets, you can use it creatively, like so:

```yaml
# Base configuration – see the Hello World example
...

addons:
  extra_addons_path: "my_addons"
  enabled:
    - website

storage:
  styles: my_addons/website/static
```

Then, in your HTML, reference static assets like this:

```html
<link rel="stylesheet" href="/storage/styles/style.css">
```

This approach allows centralized serving of static assets across your entire API.
