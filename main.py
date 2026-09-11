#!/usr/bin/env python3
"""
Run script for BIMFabrikHH API with integrated Celery worker

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class CeleryWorkerManager:
    """Manages the Celery worker process"""

    def __init__(self) -> None:
        self.worker_process = None
        self.is_running = False
        self.output_thread = None

    def _monitor_output(self) -> None:
        """Monitor Celery worker output in a separate thread"""
        if not self.worker_process or not self.worker_process.stdout:
            return

        try:
            for line in iter(self.worker_process.stdout.readline, ""):
                if line:
                    # The worker process configures the shared logging itself
                    # (see the Celery ``setup_logging`` hook) and writes to the
                    # log file directly. Here we only mirror its already
                    # formatted stdout to this process' stdout so the combined
                    # output remains visible via ``docker logs``.
                    sys.stdout.write(f"{line.rstrip()}\n")
                    sys.stdout.flush()
                if not self.is_running:
                    break
        except Exception as e:
            logger.error("Error monitoring Celery output: %s", e)

    def start_worker(self) -> None:
        """
        Start the Celery worker in a separate process.

        Raises:
            RuntimeError: If the worker fails to start.
        """
        """Start the Celery worker in a separate process"""
        logger.info("Starting Celery worker...")
        # Worker pool and concurrency are configurable via the environment so the
        # number of parallel processing jobs can be tuned per deployment.
        # ``prefork`` uses child processes for real parallelism on CPU-bound IFC
        # generation; ``CELERY_WORKER_CONCURRENCY`` sets how many run in parallel.
        # Windows cannot use billiard prefork/spawn reliably (WinError 6).
        # Always solo/1 on nt so a Linux-oriented .env cannot crash local runs.
        # The Linux server never hits this branch; it uses the env values.
        if os.name == "nt":
            worker_pool, worker_concurrency = "solo", "1"
        else:
            worker_pool = os.getenv("CELERY_WORKER_POOL", "prefork")
            worker_concurrency = os.getenv("CELERY_WORKER_CONCURRENCY", "2")

        # Start the worker process directly using celery command
        cmd = [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "src.api.ogc_api.services.generate_bim_modells",
            "worker",
            "--loglevel=info",
            f"--concurrency={worker_concurrency}",
            f"--pool={worker_pool}",
            # ``-E`` enables sending task-related events (worker_send_task_events)
            # to the broker. The celery-exporter (monitoring stack) consumes these
            # events to expose Prometheus metrics (task runtime, success/failure,
            # active tasks, etc.). Without it the exporter sees no task activity.
            "-E",
            "-Q",
            "processing",
        ]

        logger.info("Starting Celery with command: %s", " ".join(cmd))
        self.worker_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,
        )

        self.is_running = True
        logger.info("Celery worker started with PID: %s", self.worker_process.pid)

        # Start output monitoring thread
        self.output_thread = threading.Thread(target=self._monitor_output, daemon=True)
        self.output_thread.start()

        # Give the worker a moment to start up
        time.sleep(2)

        # Check if the worker is still running
        if self.worker_process.poll() is None:
            logger.info("Celery worker is running successfully")
        else:
            logger.error("Celery worker failed to start")
            self.is_running = False
            # Try to get any error output
            try:
                stdout, stderr = self.worker_process.communicate(timeout=2)
                if stdout:
                    logger.error("Celery stdout: %s", stdout)
                if stderr:
                    logger.error("Celery stderr: %s", stderr)
            except Exception as e:
                logger.error("Could not read Celery error output: %s", e)

    def stop_worker(self) -> None:
        """
        Stop the Celery worker process gracefully.
        """
        """Stop the Celery worker process"""
        if self.worker_process and self.is_running:
            logger.info("Stopping Celery worker (PID: %s)...", self.worker_process.pid)
            self.is_running = False

            # Send SIGTERM to gracefully stop the worker
            if os.name == "nt":  # Windows
                self.worker_process.terminate()
            else:  # Unix/Linux
                self.worker_process.send_signal(signal.SIGTERM)

            # Wait for the process to terminate
            try:
                self.worker_process.wait(timeout=10)
                logger.info("Celery worker stopped successfully")
            except subprocess.TimeoutExpired:
                logger.warning(
                    "Celery worker didn't stop gracefully, forcing termination..."
                )
                self.worker_process.kill()
                self.worker_process.wait()
                logger.info("Celery worker force-stopped")

            # Wait for output thread to finish
            if self.output_thread and self.output_thread.is_alive():
                self.output_thread.join(timeout=1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API + Celery stack")

    parser.add_argument(
        "--db",
        choices=["sqlite", "redis"],
        default=os.getenv("BACKEND_DB", "sqlite"),
        help="Backend/Broker database type (sqlite for testing, redis for production)",
    )

    return parser.parse_args()


def signal_handler(_signum: int, _frame: Any) -> None:
    """
    Handle shutdown signals.

    Args:
        _signum: Signal number (unused but required by signal handler signature).
        _frame: Current stack frame (unused but required by signal handler signature).
    """
    logger.info("Received shutdown signal, stopping services...")
    if hasattr(signal_handler, "worker_manager"):
        signal_handler.worker_manager.stop_worker()
    sys.exit(0)


def main_with_celery(db_type: str) -> None:
    """
    Main function that starts both Celery worker and FastAPI app.
    """
    """Main function that starts both Celery worker and FastAPI app"""

    # Set Backend/Broker
    os.environ["BACKEND_DB"] = db_type

    # Configure logging as early as possible in the launcher process.
    from src.api.config.logging_config import setup_logging
    from src.api.web_app import main

    setup_logging()

    # Create worker manager
    worker_manager = CeleryWorkerManager()

    # Store reference for signal handler
    signal_handler.worker_manager = worker_manager

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start Celery worker
        worker_manager.start_worker()

        if not worker_manager.is_running:
            logger.error("Failed to start Celery worker. Exiting.")
            return

        logger.info("Starting FastAPI application...")
        logger.info("=" * 50)

        # Start the FastAPI application
        main()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error("Error: %s", e)
    finally:
        # Ensure worker is stopped
        worker_manager.stop_worker()
        logger.info("All services stopped")


if __name__ == "__main__":
    args = parse_args()
    main_with_celery(db_type=args.db)
