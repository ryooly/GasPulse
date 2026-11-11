import time
import signal
import sys
from app.modules.automation.automation_engine import start_all, shutdown_all


def handle_exit(signum, frame):
    """Handles termination signals (e.g., from Docker/Kubernetes) for a graceful shutdown"""
    print("Shutting down the automation engine safely...")
    shutdown_all()
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for a graceful shutdown
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print("Starting the automation engine as a separate worker...")
    # Start the engine; set run_now=True to execute immediately upon worker startup
    start_all(run_now=True)

    print("Automation worker is running in the background. Press Ctrl+C to stop.")

    # Infinite loop to keep the Python process alive (since APScheduler runs in a background thread)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        shutdown_all()