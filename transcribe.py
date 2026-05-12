#!/usr/bin/env python3
"""Convenience entry point for local or in-container execution."""

from transcribe_cli.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
