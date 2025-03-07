# mloader/__main__.py

# Import the logging setup early so that it applies to all loggers.
from mloader.cli.config import setup_logging
setup_logging()  # This ensures all logging settings are in place.

# Now import the main CLI command.
from mloader.cli.main import main

if __name__ == "__main__":
    main()