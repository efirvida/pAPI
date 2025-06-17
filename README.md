# pAPI – Example Addons and Tutorials

This repository provides **example addons** and **step-by-step tutorials** for the [pAPI](https://github.com/efirvida/papi) framework.

It is intended as a resource for learning and experimentation for developers building with or extending the modular **pAPI** system.

---

## 📁 Directory Structure

```
.
├── examples
│   └── family_tree
├── functionalities
│   ├── image_storage
│   └── user_auth_system
├── tutorials
│   ├── hello_world         
│   ├── weather             
│   └── website             
├── README.md
```

---

## 🧩 Functionalities vs Examples vs Tutorials

* **Examples** (`examples/` and `functionalities/`) are ready-to-use addons that showcase pAPI's capabilities.

  * `examples/`: Fully working addons demonstrating complete use cases.
  * `functionalities/`: Modular pieces of functionality you can plug into your API to enhance it.
* **Tutorials** (`tutorials/`) are step-by-step guides to help you build your own addons from scratch.

---

## 🛠 Requirements

Make sure you have installed:

* [rye](https://rye-up.com)
* Python 3.10 or newer

Optional services you may need, depending on the addon:

* A running **MongoDB** instance (for Beanie ODM)
* A running **SQL** server (for SQLAlchemy)
* A running **Redis** server

---

## 📚 Learn More

Check out the [official pAPI documentation](https://efirvida.github.io/pAPI/) to learn how to:

* Build your own addons
* Extend the CLI
* Use the MCP protocol

---

## 🤝 Contributing

Contributions are welcome! If you'd like to improve an example, add a new tutorial, or share a useful addon:

1. Fork this repository.
2. Create a new branch:

   ```bash
   git checkout -b my-feature
   ```
3. Commit your changes:

   ```bash
   git commit -am 'Add my feature'
   ```
4. Push to the branch:

   ```bash
   git push origin my-feature
   ```
5. Open a Pull Request.

Please make sure your code is well-documented and tested where applicable. If you're adding a tutorial, aim for clarity and step-by-step instructions.
