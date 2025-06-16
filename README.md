<div align="center">
  <img src="logo.svg" alt="pAPI Logo" width="300"/>
</div>

# pAPI – Python/Pluggable API Framework

**pAPI** is a modular micro-framework built on top of FastAPI for composing scalable, tool-oriented APIs. It extends FastAPI’s routing system with native support for modular service architectures, addon discovery, and LLM tooling.

> 📚 **Documentation**: Full documentation is currently a work in progress (WIP).  
> 👉 [https://efirvida.github.io/pAPI/](https://efirvida.github.io/pAPI/)  
> 🧪 Example addons are available in the [`extra_addons` branch](https://github.com/efirvida/pAPI/tree/extra_addons)

---

## ✨ Key Features

- 🔌 **Plug-and-Play Architecture**  
  Modular addon system with automatic route discovery and dependency resolution.

- 🧠 **LLM Tooling & MCP Integration**  
  Expose endpoints as tools for agent frameworks using SSE and standard response models.

- 🧬 **Multi-Database Support**  
  Native support for MongoDB (Beanie), SQL databases (SQLAlchemy), and Redis.

- 📦 **Standardized API Responses**  
  Unified success/error format with automatic metadata injection and exception handling.

- ⚡ **Performance-Optimized**  
  Fully async, lazily loaded, and built on FastAPI’s high-performance core.

- 🛠️ **Developer Tooling**  
  Extensible CLI system and async-enabled IPython shell for rapid development.

---

## 🧩 Addon System

pAPI is built around a **composable addon architecture**, where each addon functions like a LEGO® piece—self-contained, reusable, and designed to interlock with others.

These addons can:

* Register API routes (`RESTRouter`)
* Define database models (Beanie or SQLAlchemy)
* Hook into startup processes (`AddonSetupHook`)
* Extend the CLI with custom commands

Together, they form a cohesive and scalable API system, enabling you to build robust, modular services by simply connecting or extending the building blocks your application needs.

Addons are declared in `config.yaml`, allowing clean separation of concerns and easy configuration.

---

## 📊 Use Cases

- **AI Agent Tooling**  
  Build modular tools for LLMs and agents.

- **Composable Microservices**  
  Create reusable, pluggable service components.

- **Rapid API Prototyping**  
  Launch structured APIs quickly with standardized behavior.

- **Security and Auth Systems**  
  Implement RBAC/ABAC policies using addon-based security modules.

---

## 🚀 Getting Started

```bash
git clone https://github.com/efirvida/pAPI.git
cd pAPI
rye sync
rye run python papi/cli.py --help
````

---

## 🧠 Learn More

Check the documentation for:

* Addon development
* CLI usage
* Response formatting
* Database integrations
* MCP/LLM support

👉 [https://efirvida.github.io/pAPI/](https://efirvida.github.io/pAPI/)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push and open a Pull Request

---

## 🪪 License

MIT License © 2025 — Eduardo Miguel Firvida Donestevez

