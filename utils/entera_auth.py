"""Entera API integration module.

Provides async and sync authentication to the Entera recognition service
and utilities for listing user spaces.
"""

import asyncio
import os
from typing import Optional

import aiohttp
import pandas as pd
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)


async def get_auth_cookies() -> Optional[dict[str, str]]:
    """Authenticate to Entera and return a JWT cookie header.

    Retries up to 180 times with a 5-second delay between attempts.

    Returns:
        Dictionary with a single "Cookie" key, or None on failure.
    """
    login_en = os.environ.get("entera_login")
    passwrd_en = os.environ.get("entera_pass")

    data = {"login": login_en, "password": passwrd_en}
    url = "https://id.entera.pro/api/v1/login"

    max_attempts = 180
    for attempt in range(max_attempts):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url=url, json=data) as response:
                    status = response.status
                    print(f"Attempt {attempt + 1}: Status {status}")

                    if status == 200:
                        cookies = response.cookies
                        if "ENTERA_JWT" in cookies:
                            return {"Cookie": f"ENTERA_JWT={cookies['ENTERA_JWT'].value}"}
                        print("JWT token not found in response cookies")
                        return None
        except Exception as ex:
            print(f"Error occurred: {ex}")

        await asyncio.sleep(5)

    print(f"Failed to authenticate after {max_attempts} attempts")
    return None


def get_auth_cookies_sync() -> Optional[dict[str, str]]:
    """Synchronous wrapper around :func:`get_auth_cookies`.

    Returns:
        Same as :func:`get_auth_cookies`.
    """
    return asyncio.run(get_auth_cookies())


async def get_space() -> pd.DataFrame:
    """Fetch all Entera spaces available to the current user.

    Returns:
        DataFrame with columns for space name and space ID.
    """
    headers = await get_auth_cookies()
    url = "https://app.entera.pro/api/v1/currentUser"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            r = await response.json()
            spaces = r["user"]["spaces"]

    entera_acc_list = [[s["name"].strip(), s["id"]] for s in spaces]
    for s in spaces:
        print(s["name"].strip(), s["id"])

    return pd.DataFrame(entera_acc_list)
