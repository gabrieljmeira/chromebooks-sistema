"""Rode da raiz: python scripts/init_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from database import init_db

if __name__ == '__main__':
    init_db()
    print('Banco inicializado com os Chromebooks CH-001 a CH-020.')
