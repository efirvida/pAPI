# pAPI — Pluggable Python API Framework

> **GitHub**: [https://github.com/efirvida/papi](https://github.com/efirvida/papi)

pAPI is a lightweight, modular micro-framework built on top of FastAPI. It leverages FastAPI’s full feature set—routing, dependency injection, async support—without altering its internals or impacting performance. Instead, it enhances FastAPI’s routing system with dynamic discovery, a plugin-based architecture, and first-class support for agent-native endpoints, such as tools exposed via the Model Context Protocol (MCP). This makes pAPI especially well-suited for building composable microservices, intelligent agent interfaces, and modular backends.

---

## ⚙️ What is pAPI?

pAPI is designed to let you build composable APIs through reusable "addons" (self-contained units of logic). It handles:

- Addon registration and lifecycle
- Auto-discovery of routers and models
- Dependency resolution between addons
- Consistent response formatting
- Database abstraction with async support
- Direct exposure of FastAPI routes as tools compatible with the **Model Context Protocol (MCP)** — enabling seamless integration with LLM-based agents


Aquí tienes una versión más clara, profesional y precisa de la sección, con estilo consistente y mejor redacción técnica:

---

## 🔧 Core Features

### 🧩 Modular Architecture

* Addons are self-contained: they register their own routers, models, and lifecycle hooks.
* Route behavior can be extended or overridden by other addons.
* Each addon can expose tools through standard HTTP endpoints or as **Model Context Protocol (MCP)**-compatible tools for agent-based workflows.

---

### 🤖 Agent-Native Interface

pAPI is designed with LLM-driven agents in mind. It allows you to expose FastAPI endpoints as **Model Context Protocol (MCP)**-compatible tools with minimal effort, supporting both JSON-over-HTTP and **Server-Sent Events (SSE)** for streaming.

✅ One-line tool exposure
✅ Seamless integration with LLM agents

Expose a tool in a single line:

```python
from papi.core.router import RESTRouter

router = RESTRouter()

@router.get("/tool", expose_as_mcp_tool=True)
async def my_tool():
    return {"result": "tool output"}
```

Once exposed, your tools are automatically discoverable via SSE:

```json
{
  "name": "pAPI",
  "type": "sse",
  "url": "http://localhost:8000/sse"
}
```

If you need to expose MCP tools directly without API endpoints, you can use `MCPRouter`, which is a thin wrapper around `FastMCP`:

```python
from papi.core.router import MCPRouter

router = MCPRouter()

@router.tool()
async def my_tool():
    return {"result": "tool output"}
```

---

Start the full API + MCP tools with:

```bash
rye run python papi/cli.py webserver
```

Or launch just the MCP interface:

```bash
rye run python papi/cli.py mcpserver
```

---

### 🗄️ Built-in Database Layer

pAPI offers first-class support for multiple asynchronous databases, making it easy to combine different storage backends within a single application. The database layer is **declarative and dynamic** — connections are only initialized when relevant models are discovered at runtime.

Supported backends:

| Backend    | Library    | Typical Use Case                   |
| ---------- | ---------- | ---------------------------------- |
| MongoDB    | Beanie     | Document-oriented storage          |
| PostgreSQL | SQLAlchemy | Relational databases               |
| Redis      | aioredis   | Caching, queues, distributed locks |

#### ✅ Smart and Flexible Integration

* Models are **automatically discovered** during startup by inspecting enabled addons.
* Each addon can **define its own models** or **extend models from other addons** to add new fields, relations, or behaviors.
* No need for central registration — model discovery is fully modular.
* Unused databases are ignored, so you only pay for what you use.

This architecture allows true decoupling between services. For example, one addon can provide core user models, and another can enhance those with metadata, analytics, or external account bindings — all without modifying the original addon code.

> 💡 Tip: The system is ORM/ODM-agnostic — you can bring your own schema logic and override or compose behaviors freely.

---

### 📦 Unified Response System

pAPI provides an optional but powerful mechanism for standardizing responses across all endpoints. This promotes consistency, improves debuggability, and facilitates client integration—but does not constrain developers. You can continue to use raw FastAPI responses where desired.

#### 🧱 Structured Response Format

The framework offers a unified schema via the `APIResponse` model:

```python
class APIResponse(BaseModel):
    success: bool
    message: Optional[str]
    data: Optional[Any]
    error: Optional[APIError]
    meta: Meta
```

Key components include:

* ✅ `success`: Boolean flag indicating request outcome
* 📦 `data`: Response payload (included only if successful)
* ⚠️ `error`: Structured error object (included only on failure)
* 💬 `message`: Optional human-readable message
* 📊 `meta`: Metadata (e.g., timestamp, request ID)

#### ⚙️ `create_response`: Standardized Response Builder

The `create_response()` helper generates well-formed `APIResponse` objects with minimal boilerplate:

```python
from papi.core.response import create_response

@app.get("/hello")
async def hello():
    return create_response(data={"message": "Hello, world!"})
```

Internally, it wraps the payload with standardized metadata and, when applicable, error details.

```python
def create_response(
    data: Any = None,
    success: bool = True,
    message: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
) -> APIResponse:
    ...
```

Error objects can include:

* `code`: Application-specific error identifier
* `message`: Short description
* `detail`: Arbitrary contextual data
* `status_code`: HTTP status code to be returned

#### 🚨 Unified Exception Handling

The optional `APIException` class makes it easy to raise consistent, structured errors:

```python
raise APIException(
    status_code=403,
    message="Access denied",
    code="PERMISSION_DENIED",
    detail={"required_role": "admin"}
)
```

All `APIException`s are automatically serialized into the same response format used by `create_response`, ensuring uniformity across success and error cases.

> ℹ️ This system is **opt-in**: developers retain full control and can use native FastAPI `JSONResponse`, `Response`, or any custom return logic as needed.

---

### 🛠️ Developer-Friendly CLI

pAPI ships with a powerful, extensible CLI designed to streamline development, introspection, and deployment workflows.

```bash
$ papi_cli start webserver   # Launch the FastAPI server with all registered addons
$ papi_cli start mcpserver   # Run the standalone MCP (agent) server
$ papi_cli shell             # Open an interactive, async-ready developer shell
```

#### 🧠 Key Features

* ✅ **Async-aware interactive shell** (with full `await` support), powered by IPython if available.
* ⚙️ **Config-aware**: automatically loads `config.yaml` and injects environment context.

---

#### 🧪 CLI Overview

```bash
$ rye run python papi/cli.py --help
```

```text
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

  Main entry point for pAPI service management CLI.

Options:
  --config TEXT  Path to configuration file
  -h, --help     Show this message and exit.

Commands:
  webserver*  Start the production FastAPI web server.
  mcpserver   Start the standalone MCP server.
  shell       Launch an interactive IPython shell with the initialized...
```

---

### 🐚 Interactive Shell Utilities

The `shell` command loads a fully-initialized runtime context, including all registered database models and configurations.

#### MongoDB Integration

MongoDB documents are registered and accessible via the `mongo_documents` dictionary:

```python
await mongo_documents["Image"].find().to_list()
```

Each key is the document class name, and the value is the corresponding `Beanie` model class.

#### SQLAlchemy Integration

SQL models are exposed via the `sql_models` dictionary, enabling expressive, async queries with full SQLAlchemy support:

```python
from sqlalchemy import select

stmt = select(sql_models["User"]).where(sql_models["User"].email == "admin@example.com")
result = await db_session.execute(stmt)
user = result.scalar_one_or_none()
```

> This makes the shell ideal for advanced debugging, quick prototyping, and admin scripting—all with full access to the live database and application context.


---

## 📦 Addon System

pAPI provides a robust, modular plugin system via **addons**—isolated Python modules that encapsulate logic, routes, models, configuration, and static assets. This architecture promotes separation of concerns, extensibility, and reusability.

---

### 🧬 Anatomy of an Addon

```
addons/
└── user_auth_system/
    ├── static/
    │   └── static_files/
    ├── __init__.py
    ├── manifest.yaml
    ├── routers.py
    └── models.py
```

Each addon behaves as a self-contained package and is dynamically discovered and registered at runtime based on the configuration.

---

### 📑 `manifest.yaml`

The mandatory `manifest.yaml` file defines metadata and dependencies for each addon:

```yaml
name: user_auth_system
version: 0.1.0
description: Built-in user authentication system
author: pAPI Team

dependencies:
  - image_storage

python_dependencies:
  - passlib
  - pydantic[email]
```

#### 🔗 Addon Dependencies

* The `dependencies` field declares other addons that must be loaded before this one.
* Dependency resolution ensures proper load order and allows addons to **extend or reuse** logic and models from other addons.

#### 🐍 Python Dependencies

* The `python_dependencies` section specifies required PyPI packages for this addon.
* These dependencies will be automatically installed with `pip install` on every startup.
* ⚠️ Use with care: untrusted or unnecessary packages may affect system stability or introduce security risks.

---

## 🧪 Example Configuration (`config.yaml`)

```yaml
logger:
  level: "INFO"
  log_file: ./papi.log

info:                                   # FastAPI settings
  title: "Testing API Server"
  version: "1.0.0"
  description: "Test instance for local development"

server:                                # uvicorn settings
  host: "127.0.0.1"
  port: 8000

database:
  mongodb_uri: "mongodb://root:example@localhost:27017/testing_db?authSource=admin"
  sql_uri: "postgresql+asyncpg://localhost/testing_db"
  redis_uri: "redis://localhost:6379"

addons:
  extra_addons_path: "/path/to/local/addons"
  enabled:
    - user_auth_system # this will load image_storage as dependency
  config:              # Addons configuration
    user_auth_system:
      security:
        access_token_expire_minutes: 60
        allow_weak_passwords: true
        lockout_duration_minutes: 15
        bcrypt_rounds: 15
        hash_algorithm: "HS256"
        max_login_attempts: 5
        secret_key: "your-secret-key"
        token_audience: bohio.com
        token_issuer: bohio.com
        key_rotation:
          rotation_interval_days: 30
          max_historical_keys: 3
    image_storage:
      image_optimization:
        max_dimension:   2048
        jpeg_quality:    85
        png_compression: 6
        webp_quality:    80
        force_format:    WEBP
      cache_ttl:      3600
      cache_prefix:   "pAPI:image_storage:"
      max_image_size: 10485760
      allowed_formats:
        - JPEG
        - PNG
        - WEBP
        - GIF
      storage_backend: local

storage: # mounted as static files to provide global static files foled
  files: "path/to/local/storage/folder/files"
  images: "path/to/local/storage/folder/images" # used for image_storage addon

```

---

## 🚀 Quickstart

```bash
git clone https://github.com/your-org/papi
cd papi
rye sync
rye run python papi/cli.py webserver
```

---
## 🧠 Use Cases

pAPI is designed to enable modern backend patterns with minimal boilerplate. Some typical use cases include:

* **Agent-Integrated APIs**
  Seamlessly expose tool-like endpoints to LLM agents and orchestration frameworks via native MCP support and SSE-compatible interfaces.

* **Plugin-Driven Architectures**
  Build extensible backends for **low-code/no-code platforms** or SaaS systems, where features are delivered as isolated, dynamically loaded addons.

* **Multi-Tenant and Domain-Based Systems**
  Architect modular applications where business logic, models, and routes are grouped by tenant, domain, or business unit.

* **Internal Developer Tools & Microservices**
  Rapidly prototype lightweight internal services or CLI-extended tools that benefit from a unified config, database access, and CLI environment.

---

## 📬 Contributing

We welcome pull requests!

```bash
# fork and clone
git checkout -b feature/my-feature
# write tests if applicable
git commit -m "Add my-feature"
git push origin feature/my-feature
```

Then open a PR on GitHub. 🚀

---

## 🪪 License

MIT License © 2025 — Eduardo Miguel Firvida Donestevez

