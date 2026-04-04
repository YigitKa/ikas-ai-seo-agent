"""pytest configuration — sets required env vars before any module imports."""

import os

# Set required env vars before any app module is imported.
# This prevents the interactive TTY prompt from running in test mode.
os.environ.setdefault("IKAS_STORE_NAME", "test-store")
os.environ.setdefault("IKAS_CLIENT_ID", "test-client-id")
os.environ.setdefault("IKAS_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AI_PROVIDER", "none")
