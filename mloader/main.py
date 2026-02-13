"""Compatibility entrypoint for the console script."""

# Ensure logging is set up early
from mloader.cli.config import setup_logging
setup_logging()

# Import the main CLI command.
from mloader.cli.main import main

if __name__ == "__main__":  # pragma: no cover
    main()
