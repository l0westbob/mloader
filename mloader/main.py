# Ensure logging is set up early
from cli.config import setup_logging
setup_logging()

# Import the main CLI command.
from cli.main import main

if __name__ == "__main__":
    main()