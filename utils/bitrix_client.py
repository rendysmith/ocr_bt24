"""Bitrix24 account resolution module.

Fetches client accounts from the Entera spaces API and resolves their
Bitrix24 web IDs and accounting email addresses via the UBPO card API.
"""

import asyncio
import json
import os

import aiohttp
from dotenv import load_dotenv

from utils.entera_auth import get_space

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)


async def accs_bitrix() -> list[dict]:
    """Fetch all client accounts with their Bitrix24 and email info.

    Returns:
        List of dicts with keys: "client", "space", "web_id", "email".
    """
    name_accs = await get_space()
    print(name_accs)

    # Entera name → display name overrides
    data_list = {"SP_Test_Group": "Test SLA"}
    url_card = os.environ.get("url_ubpo_card")
    datas: list[dict] = []

    for _, rows in name_accs.iterrows():
        name_acc = rows[0]
        if "Inditex" in name_acc:
            continue

        space = rows[1]
        data: dict = {"client": name_acc, "space": space}

        display_name = data_list.get(name_acc)
        if display_name is not None:
            name_acc = display_name

        url_ubpo = url_card + name_acc
        print("\nURL", url_ubpo)

        async with aiohttp.ClientSession() as session:
            async with session.get(url_ubpo) as res:
                r_text = await res.text()
                print("TEXT URL:", r_text)

                if "Не найден клиент" in r_text:
                    continue

                try:
                    r = await res.json()
                except json.JSONDecodeError:
                    r = json.loads(r_text)

                print(r)

                try:
                    if r.get("Битрикс24") is None or "bitrix" not in r["Битрикс24"]:
                        continue

                    b24 = r["Битрикс24"]
                    data["web_id"] = int(b24.split("/")[-2])
                    print("Web_id:", data["web_id"])

                    data["email"] = None
                    for mailbox in r.get("ОбщиеЯщики", []):
                        if "Accounting" in mailbox:
                            data["email"] = mailbox
                            break

                    datas.append(data)

                except Exception as ex:
                    print(f"\n--- Error <{name_acc}>\n--- {ex}\n--- Url = {url_ubpo}\n")

    return datas


if __name__ == "__main__":
    print("Actualy names")
    for i in asyncio.run(accs_bitrix()):
        print(i)
