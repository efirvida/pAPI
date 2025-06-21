## 🚀 Hello World!

pAPI is built around the concept of **addons**—self-contained Python modules that define routes, models, CLI commands, and business logic. Creating your first addon is straightforward and does **not** require modifying the core system.

### 1️⃣ Create Your Addon Structure

In your configured `extra_addons_path` (e.g., `my_addons/`), create a new folder:

```
my_addons/
└── hello_world/
    ├── __init__.py
    ├── manifest.yaml
    └── routers.py
```

### 2️⃣ Define the `manifest.yaml`

This file provides metadata and optional dependencies. At a minimum, define `name` and `version`:

```yaml
name: hello_world
version: 0.1.0
description: A minimal addon that says hello
author: Your Name
```

### 3️⃣ Add Routes with `RESTRouter`

In `routers.py`, use the `RESTRouter` class and `create_response()` helper to define a basic endpoint:

```python
from papi.core.router import RESTRouter
from papi.core.response import create_response

router = RESTRouter()

@router.get("/hello")
async def hello():
    return create_response(data={"message": "Hello from addon!"})
```

Then, import the router in `__init__.py` to ensure it is discovered automatically:

```python
from .routers import router
```

### 4️⃣ Enable Your Addon in `config.yaml`

Add your addon to the global configuration file:

```yaml
logger:
  level: "INFO"
  log_file: ./papi.log

info:
  title: "Testing API Server"
  version: "1.0.0"
  description: "This is a test API server for demonstration purposes."

server:
  host: "127.0.0.1"
  port: 8080

addons:
  extra_addons_path: "my_addons"
  enabled:
    - hello_world
```

### 5️⃣ Run the Server and Test

Start the server with:

```bash
rye run python papi/cli.py webserver
```

Then access your new endpoint at:
`http://localhost:8080/hello`

Or test via `curl`:

```bash
curl -X GET http://localhost:8080/hello -H "accept: application/json"
```

Expected response:

```json
{
  "success": true,
  "message": null,
  "data": {
    "message": "Hello from addon!"
  },
  "error": null,
  "meta": {
    "timestamp": "2025-06-14T15:41:44+00:00",
    "requestId": "207567c1-00b6-4b9b-8962-4e90b9a87beb"
  }
}
```

Swagger docs are available at:
🔗 [http://localhost:8080/docs](http://localhost:8080/docs)

---

> 💡 **What happens behind the scenes?**
>
> * The addon is discovered and loaded automatically
> * All `RESTRouter` routes are registered under the main router
> * The addon is fully integrated into the routing and dependency system

---

### ✅ What's Next?

* Add **Beanie** or **SQLAlchemy** models — pAPI will detect and initialize them automatically
* Add custom CLI commands in `cli.py`
* Implement `AddonSetupHook` for custom startup logic
