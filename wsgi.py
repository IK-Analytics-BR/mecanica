import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'app'))
os.chdir(BASE_DIR)
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))
from app.main_mysql import app
if __name__ == '__main__':
    app.run()
