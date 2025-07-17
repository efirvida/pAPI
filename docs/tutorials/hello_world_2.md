## 🚀 Extending Your Addon: Lifecycle Hooks with AddonSetupHook

Let’s continue working on our `hello_world` addon to demonstrate how to define custom behaviors during the addon lifecycle. When **pAPI** discovers an addon, you can control its **startup** and **shutdown** phases. This is especially useful when you need to perform certain actions before the system starts, or just before it shuts down.

Each addon can, optionally, register one or more `AddonSetupHook` classes to manage its lifecycle events. In this tutorial, we’ll implement a basic `AddonSetupHook` to simulate tasks executed during addon startup and shutdown.

---

### 1️⃣ Add the Setup File to Your Addon

Inside your `hello_world` addon directory, create a new Python file named `addon_setup.py` (or any other name you prefer). Your addon structure should look like this:

```
my_addons/
└── hello_world/
    ├── __init__.py
    ├── manifest.yaml
    ├── addon_setup.py
    └── routers.py
```

---

### 2️⃣ Define the `AddonSetupHook`

Now, import `AddonSetupHook` and subclass it. You’ll need to implement the asynchronous `startup` and `shutdown` methods. Here’s a basic example that simulates some heavy async tasks using `sleep`:

```python
from asyncio import sleep
from logging import getLogger

from papi.core.addons import AddonSetupHook

logger = getLogger(__name__)


class HelloWorldAddonSetup(AddonSetupHook):
    async def startup(self):
        logger.info("Initializing 'Hello World' addon...")
        await sleep(10)  # Simulate a heavy async task at startup
        logger.info("'Hello World' addon setup completed.")

    async def shutdown(self):
        logger.info("Shutting down 'Hello World' addon...")
        await sleep(5)  # Simulate a heavy async task at shutdown
        logger.info("'Hello World' addon shutdown completed.")
```

---

### 3️⃣ Register the Hook in `__init__.py`

Finally, import your `HelloWorldAddonSetup` class in the addon's `__init__.py` so that pAPI can discover and register it automatically:

```python
from .routers import router
from .addon_setup import HelloWorldAddonSetup
```

---

That’s all you need!

When the addon is loaded, the `startup` method will be executed automatically. When the application is stopped (e.g. by pressing `Ctrl+C` while running with `uvicorn`), the `shutdown` method will be called.

### ✅ What's Next?

* Add MongoDB models using **Beanie**
