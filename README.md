# pAPI – Python/Pluggable API Framework

**pAPI** (short for **Python API** or **Pluggable API**) is a modular micro-framework built on top of [FastAPI](https://fastapi.tiangolo.com/), designed to simplify the creation of composable and interoperable web APIs.

It extends FastAPI’s routing system to enable advanced features such as exposing HTTP endpoints as MCP tools, making it a powerful choice for agent-based applications, modular services, and programmable API ecosystems.

---

## ✨ Features

- 🔌 **Plug-and-play architecture**  
  Extend any FastAPI router with support for modular constructs like `@tool`, `@resource`, and `@prompt`.

- 🧠 **Native MCP support**  
  Easily expose endpoints as MCP-compatible tools using a single parameter (`expose_as_mcp_tool=True`).

- 🧩 **Composable, extensible routing**  
  Custom base routers like `MPCRouter` and `pAPIRouter` allow for clean layering and future extension.

- 🚀 **No compromise on performance**  
  Inherits FastAPI’s async support, validation, and high throughput.

- 🍃 **MongoDB-native persistence**  
  Built-in support for asynchronous ODM using [Beanie](https://github.com/roman-right/beanie), backed by MongoDB.

---

## 🛠️ Quick Example

```python
from papi import pAPIRouter

router = pAPIRouter()

@router.get("/hello", expose_as_mcp_tool=True)
def say_hello(name: str) -> str:
    return f"Hello, {name}!"

@router.tool()
def say_hello_tool(name: str) -> str:
    return f"Hello, {name}!"
```

---

## 🧱 Core Components

| Component       | Description |
|------------------|-------------|
| `MPCRouter`      | Adds support for `@tool`, `@resource`, and `@prompt` decorators, registering them as MCP tools. |
| `RESTRouter`     | Extends `FastAPI.APIRouter` to support `expose_as_mcp_tool` in all route methods. |
| `pAPIRouter`         | Combines both `MPCRouter` and `RESTRouter` into a unified interface for full functionality. |

---

## 🧬 Database Layer

**pAPI** integrates seamlessly with **MongoDB** via the [Beanie ODM](https://beanie-odm.dev/). This enables:

- Fully asynchronous interaction with MongoDB.
- Pydantic-based document models.
- Relationships, indexing, and migrations.

## 📚 Motivation

Modern APIs are evolving toward **context-aware**, **composable**, and **tool-oriented** designs.  
**pAPI** provides a robust foundation for such systems, serving as a bridge between conventional HTTP APIs and modern agent or workflow-driven platforms.

---

## 🔍 Use Cases

- Exposing HTTP services as MCP tools for AI agents.
- Building microservices with tool-aware routing.
- Creating APIs for orchestrated workflows and plugin-based apps.
- Experimentation platforms needing dynamic tool registration.

---

## 🧾 Documentation

Full documentation will be available soon at: [https://papi.dev](https://papi.dev) (placeholder)

---

## 🤝 Contributing

Contributions, bug reports, and suggestions are welcome!  
Open an issue or pull request on GitHub and follow the contribution guidelines.

---

## 🪪 License

MIT License © 2025 — Eduardo Miguel Firvida Donestevez
