#!/usr/bin/env python3
"""
Main entry point for the capacity planner application.
"""

import sys
import click
from .cli.commands import cli


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()