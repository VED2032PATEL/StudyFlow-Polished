import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app

# Vercel needs the app object named 'app' at module level
application = app

if __name__ == "__main__":
    app.run(debug=False)
