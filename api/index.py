"""
KisanMitra — api/index.py
Vercel Serverless Function entrypoint for FastAPI backend.
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.local_server import app

# Vercel discovers the `app` ASGI instance
