import argparse
import os

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ModuleNotFoundError:
    print("[WARNING] python-dotenv not installed. Run 'pip install python-dotenv' to auto-load .env files.")

from rag import grievance_pipeline
from match import process_grievance_with_llm_filter


def run_pipeline(image_path, raw_location, user_text, user_name=None):
    payload = grievance_pipeline(image_path, raw_location, user_text)
    payload["image_path"] = image_path
    payload["raw_location"] = raw_location
    payload["user_text"] = user_text
    payload["user_name"] = user_name or "Anonymous"
    result_data, message = process_grievance_with_llm_filter(payload)
    if isinstance(result_data, dict):
        result_data["message"] = message
        return result_data
    return payload
