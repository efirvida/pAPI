import subprocess
import threading

from loguru import logger


def stream_output(stream, level="INFO"):
    for line in iter(stream.readline, ""):
        logger.log(level, line.rstrip())


def install_python_dependencies(python_deps: list[str]) -> None:
    command = ["rye", "run", "pip", "install"] + python_deps
    logger.info(
        "Installing Python dependencies requested by addons: {}", " ".join(python_deps)
    )

    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # Hilos para capturar stdout y stderr en tiempo real
    stdout_thread = threading.Thread(
        target=stream_output, args=(process.stdout, "INFO")
    )
    stderr_thread = threading.Thread(
        target=stream_output, args=(process.stderr, "ERROR")
    )

    stdout_thread.start()
    stderr_thread.start()

    process.wait()
    stdout_thread.join()
    stderr_thread.join()

    if process.returncode != 0:
        raise RuntimeError(
            f"Dependency installation failed with code {process.returncode}"
        )
