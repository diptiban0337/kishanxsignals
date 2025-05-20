import os
import sys

# Get the absolute path of the project directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add the project directory to Python path
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Set environment variables
os.environ['FLASK_APP'] = 'app.py'
os.environ['FLASK_ENV'] = 'development'

# Import the Flask app
from app import app as application

# For local development
if __name__ == "__main__":
    application.run(port=5000) 