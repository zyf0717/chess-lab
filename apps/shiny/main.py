import logging

from app import server, ui
from shiny import App

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # Output to console/terminal
)

if __name__ == "__main__":
    app = App(ui, server)
    app.run(port=8008)
