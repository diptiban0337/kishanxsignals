import os
import sys

# Add your project directory to the Python path
path = '/home/diptiban87/kishanxsignals'
if path not in sys.path:
    sys.path.append(path)

# Activate virtual environment
activate_this = '/home/diptiban87/kishanxsignals/venv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Set environment variables
os.environ['FLASK_APP'] = 'app.py'
os.environ['FLASK_ENV'] = 'production'

# Import your Flask app
from app import app as application 