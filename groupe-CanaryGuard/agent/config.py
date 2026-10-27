import os
from dotenv import load_dotenv


load_dotenv()

MODEL_API_KEY = os.getenv("MODEL_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen/qwen3.8-flash")

CANARI = os.getenv("CANARI", "CANARI-7Q2X")