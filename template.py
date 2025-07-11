import os
from typing import List, Dict, Any
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# List of files to create
listings = [
    "src/__init__.py",
    "src/helper.py",
    "app.py",
    ".env",
    "README.md",
    "src/prompt.py",
    "requirements.txt",
    "config/settings.py",
    "setup.py",
    "research/trails.ipynb",
]

for filepath in listings:
    try:
        # Convert string to Path object
        filepath = Path(filepath)
        # Get directory and filename
        filedir = filepath.parent
        filename = filepath.name

        # Create directory if it doesn't exist
        if filedir != Path(".") and not filedir.exists():
            filedir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created directory: {filedir}")

        # Create file if it doesn't exist
        if not filepath.exists():
            # Customize content based on file type
            if filename.endswith(".py"):
                content = f"# {filename}\n\n# This is a placeholder for the {filename} file.\n\n"
            elif filename.endswith(".md"):
                content = f"# {filename}\n\nThis is a placeholder for the {filename} file.\n\n"
            elif filename.endswith(".txt"):
                content = f"# {filename}\n\nThis is a placeholder for the {filename} file.\n\n"
            elif filename.endswith(".ipynb"):
                content = """{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# trails.ipynb\\n\\nThis is a placeholder for the trails.ipynb Jupyter notebook."
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}"""
            else:
                content = f"# {filename}\n\nThis is a placeholder for the {filename} file.\n\n"

            # Write content to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"Created file: {filepath}")
        else:
            logging.info(f"File already exists: {filepath}")

    except OSError as e:
        logging.error(f"Failed to process {filepath}: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error for {filepath}: {str(e)}")