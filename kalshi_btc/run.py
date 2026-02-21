#!/usr/bin/env python3
"""
Entry point for the Kalshi BTC Prediction Betting application.
Run this file to start the backend server and serve the frontend.

Usage:
    python run.py                     # default: http://0.0.0.0:8000
    python run.py --port 9000
    python run.py --host 127.0.0.1
    python run.py --reload            # auto-reload on code changes (dev mode)
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(description='Kalshi BTC Prediction Betting Server')
    parser.add_argument('--host',   default=os.getenv('HOST', '0.0.0.0'),  help='Bind host')
    parser.add_argument('--port',   default=int(os.getenv('PORT', 8000)),  type=int, help='Bind port')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload (dev)')
    parser.add_argument('--log-level', default='info', choices=['debug','info','warning','error'])
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not found. Run: pip install -r requirements.txt")
        sys.exit(1)

    print("=" * 60)
    print("  Kalshi BTC Prediction Betting")
    print("=" * 60)
    print(f"  Dashboard: http://{args.host}:{args.port}")
    print(f"  API docs:  http://{args.host}:{args.port}/docs")
    print(f"  Kalshi env: {os.getenv('KALSHI_ENV', 'demo')}")
    print("=" * 60)
    print()

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
