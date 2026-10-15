"""Bitrix24 API configuration.

Reads the Bitrix24 REST API base URL from environment (.env).
"""

import os
from dotenv import load_dotenv

load_dotenv()

url_bitrix: str = os.environ.get("url_bitrix", "")
if not url_bitrix:
    raise ValueError(
        "url_bitrix not set in .env. "
        "Copy .env.example to .env and fill in the value."
    )
