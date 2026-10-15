# -*- coding: utf-8 -*-
"""Entera OCR: send PDF files for recognition and collect results.

This module handles:
- Async upload of PDF files to Entera
- Polling for recognition status (every 60 seconds)
- Saving recognized results (JPG + metadata)
- Logging progress to MSSQL (entera_before / entera_after tables)
- Merging JPG pages into PDF
"""

import asyncio
import os
import sys
import time
from typing import Any

import aiohttp
import pandas as pd
import requests
from sqlalchemy import create_engine

from utils.db import odbc_params, py_odbc
from utils.doc_types import trans as translate_type, company as clean_company
from utils.entera_auth import get_auth_cookies, get_auth_cookies_sync
from utils.pdf_merge import merge_jpg_to_pdf

# ---------------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------------

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
pd.options.display.expand_frame_repr = False

time_unix = int(time.time())
today = time.strftime("%Y%m%d_b", time.localtime(time.time()))

table_before = "entera_before"
table_after = "entera_after"

conn = py_odbc()
cursor = conn.cursor()
connection_string = f"mssql+pyodbc:///?odbc_connect={odbc_params()}"
engine = create_engine(connection_string)


# ---------------------------------------------------------------------------
# Async upload
# ---------------------------------------------------------------------------

async def get_rec_id(
    session: aiohttp.ClientSession, account: str, file: str, space: str
) -> tuple[str, str]:
    """Upload a single file to Entera and return the recognition task ID.

    Args:
        session: Active aiohttp session.
        account: Client account name.
        file: File name to upload.
        space: Entera space ID.

    Returns:
        Tuple of (file_name, rec_id_or_error).
    """
    today_path = os.path.join(os.environ.get("TEMP", "/tmp"), today)
    url = f"https://app.entera.pro/api/v1/recognitionTasks?spaceId={space}"
    path_to_file = f"{today_path}/{account}/{file}"
    headers = await get_auth_cookies()

    async with session.post(
        url=url, data={"file": open(path_to_file, "rb")}, headers=headers, ssl=False
    ) as r:
        rec_id = await r.json()
        try:
            return file, rec_id["recognitionTask"]["id"]
        except (KeyError, TypeError):
            print(
                f"get_rec_id Error\n{account}\n{file}\n"
                f"https://app.entera.pro/api/v1/documents?spaceId={space}\n{rec_id}"
            )
            return file, "error"


async def _upload_all(account: str, space: str, list_files_filter: list[str]) -> None:
    """Upload a list of files to Entera concurrently.

    Args:
        account: Client account name.
        space: Entera space ID.
        list_files_filter: List of file names to upload.
    """
    today_path = os.path.join(os.environ.get("TEMP", "/tmp"), today)

    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.ensure_future(get_rec_id(session, account, f, space))
            for f in list_files_filter
        ]
        rec_ids = await asyncio.gather(*tasks)

        for file_name, rec_id in rec_ids:
            path_to_file = f"{today_path}/{account}/{file_name}"

            if rec_id != "error":
                cursor.execute(
                    f"INSERT INTO {table_before} "
                    f"(time_unix, client_name, file_name, path_to_file, id_space, rec_id, status) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (time_unix, account, file_name, path_to_file, space, rec_id, "SENT"),
                )
                conn.commit()
                print("+++ INSERT INTO Commit!")
            else:
                print(f"ERROR {path_to_file}")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_df() -> pd.DataFrame:
    """Fetch recent records from entera_before.

    Returns:
        DataFrame with records from the last 24 hours.
    """
    query = f"SELECT * FROM {table_before} WHERE time_unix > ?"
    return pd.read_sql(query, engine, params=(time_unix - 86400,))


# ---------------------------------------------------------------------------
# File sending logic
# ---------------------------------------------------------------------------

def send_of_files(datas: list[dict[str, Any]]) -> None:
    """Send new (not-yet-sent) PDF files to Entera for each client.

    Args:
        datas: List of client data dicts with "client" and "space" keys.
    """
    today_path = os.path.join(os.environ.get("TEMP", "/tmp"), today)
    print("--------------1-SEND-OF-FILES-----------")
    dirname = os.listdir(today_path)

    for row in datas:
        account = row["client"]
        space = row["space"]
        print(f"\n+++ {account} START!")

        if account not in dirname:
            print(f"--- SKIP {account}")
            print(f"== {account} END!")
            continue

        temp_path = os.path.join(today_path, account)
        list_files = [i for i in os.listdir(temp_path) if i.endswith(".pdf")]
        print(account, list_files)

        df = get_df()
        df = df.loc[df["client_name"] == account]

        list_files_filter = [f for f in list_files if f not in df["file_name"].to_list()]

        if not list_files_filter:
            print(f"== {account} END!")
            continue

        print(list_files_filter)
        print(f">>> {account} Number of files = {len(list_files_filter)}")

        if sys.platform == "win32":
            asyncio.set_event_loop(asyncio.ProactorEventLoop())
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(_upload_all(account, space, list_files_filter))
        print(f"== {account} END!")


# ---------------------------------------------------------------------------
# Status checking and result saving
# ---------------------------------------------------------------------------

def check_file(recogn_id: str) -> str:
    """Check recognition status of a file.

    Args:
        recogn_id: Recognition task ID.

    Returns:
        Status string or "ERROR".
    """
    print("3 - Status file")
    url = f"https://app.entera.pro/api/v1/recognitionTasks/{recogn_id}"
    r = requests.get(url=url, headers=get_auth_cookies_sync())
    print(f"----- STATE {recogn_id}", r.json()["recognitionTask"]["state"])
    try:
        return r.json()["recognitionTask"]["state"]
    except (KeyError, TypeError):
        return "ERROR"


def get_api_urls(rec_taskid: str) -> list[list[str]]:
    """Get recognized document page URLs.

    Args:
        rec_taskid: Recognition task ID.

    Returns:
        List of [document_type, page_url] pairs.
    """
    url = f"https://app.entera.pro/api/v1/recognitionTasks/{rec_taskid}"
    r = requests.get(url=url, headers=get_auth_cookies_sync()).json()

    apis: list[list[str]] = []
    for doc in r["recognitionTask"]["documents"]:
        type_doc = doc["type"]
        for page in doc["pages"]:
            apis.append([type_doc, "https://app.entera.pro" + page["url"]])
    return apis


def save_pdf_json(
    account: str, url_doc: list[str], ct: str
) -> tuple[str, str, str, str, str]:
    """Save a recognized document page as JPG and return its metadata.

    Args:
        account: Client account name.
        url_doc: [document_type, page_url] pair.
        ct: Created-date string (unused, kept for signature compat).

    Returns:
        Tuple of (name_file, supplier, type_dc, n_doc, date_doc).
    """
    today_path = os.path.join(os.environ.get("TEMP", "/tmp"), today)
    type_dc = url_doc[0]
    type_dc_2 = translate_type(type_dc)
    url = url_doc[1]
    url_data = url.split("/pages/")[0]
    page = int(url.split("/pages/")[1])
    page_str = f"{page:03d}"

    r = requests.get(url=url_data, headers=get_auth_cookies_sync()).json()

    try:
        supplier = r["document"]["supplier"]["shortName"].replace("/", "-").replace('"', "")
        supplier = clean_company(supplier)
    except (KeyError, TypeError):
        supplier = "None"

    try:
        n_doc = r["document"]["number"].replace("/", "-")
    except (KeyError, TypeError):
        n_doc = "None"

    try:
        date_doc = r["document"]["date"].replace("/", "-")
    except (KeyError, TypeError):
        date_doc = "None"

    ct_val = r["document"]["createdDate"].replace(":", ".")
    name_file = f"{type_dc_2}__{supplier}__{n_doc}__от__{date_doc}_{ct_val}_{page_str}"
    path_and_name_file = f"{today_path}/{account}/RECOGNIZED/{name_file}"
    jpg_file = f"{path_and_name_file}.jpg"

    r_img = requests.get(url=url, headers=get_auth_cookies_sync())

    n = 1
    while not os.path.exists(jpg_file):
        with open(jpg_file, "wb") as out:
            out.write(r_img.content)
        time.sleep(2)
        n += 1
        if n > 10:
            break

    return name_file, supplier, type_dc_2, n_doc, date_doc


def update_status_and_save_filse(datas: list[dict[str, Any]]) -> int:
    """Check status of sent files, save recognized ones, and update DB.

    Args:
        datas: List of client data dicts.

    Returns:
        Number of companies still with unrecognized files.
    """
    ost = 0
    print("--------------2-UPDATE-STATUS-AND-SAVE-FILES-------")

    for dt in datas:
        account = dt["client"]
        print(f"\n+++ {account} START!")

        df = get_df()
        df = df.loc[(df["client_name"] == account) & (df["status"] == "SENT")]

        if len(df) == 0:
            print(f"Processed companies = {ost}")
            ost += 1
            print(f"--- {account} END!")
            continue

        print(f"Number of unrecognized files in {account} = {len(df)}")
        for _, row in df.iterrows():
            old_name_file = row[2]
            rec_taskid = row[5]
            state = check_file(rec_taskid)
            print(row[4], rec_taskid, state)

            if state == "RECOGNIZED":
                print("- Recognized, save and write in SQL")
                urls = get_api_urls(rec_taskid)
                print(urls)

                cursor.execute(
                    f"UPDATE {table_before} SET status = ? WHERE rec_id = ?",
                    (state, rec_taskid),
                )
                conn.commit()
                print("+++ UPDATE Commit!")

                for url in urls:
                    name_file, supplier, type_dc, n_doc, date_doc = save_pdf_json(
                        account, url, "_"
                    )
                    cursor.execute(
                        f"INSERT INTO {table_after} "
                        f"(time_unix, path_from, path_to, supplier, type_dc, n_doc, date_doc) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (time_unix, old_name_file, name_file, supplier, type_dc, n_doc, date_doc),
                    )
                    conn.commit()
                    print("+++ INSERT INTO Commit!")

            elif state == "ERROR":
                cursor.execute(
                    f"UPDATE {table_before} SET status = ? WHERE rec_id = ?",
                    (state, rec_taskid),
                )
                conn.commit()
                print("+++ UPDATE Commit!")

        merge_jpg_to_pdf(account)
        print(f"--- {account} END!")

    return ost


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def sendler(today_path: str, datas: list[dict[str, Any]]) -> None:
    """Main orchestrator: send files, poll for results, save recognized docs.

    Args:
        today_path: Path to today's temp folder.
        datas: List of client data dicts.
    """
    if not os.path.isdir(today_path):
        print("Today folder is NOT")
        cursor.close()
        conn.close()
        print("\nFinally")
        print("THE END!")
        return

    print("OK")
    send_of_files(datas)

    clients = [data["client"] for data in datas]
    print("clients", clients)
    len_sent = 1

    while len_sent != 0:
        print(f"=========(Sent files={len_sent})=========")
        tsec = 60
        print(f"\n{time.ctime()}\nWAIT {tsec} sec.")
        time.sleep(tsec)

        update_status_and_save_filse(datas)

        df = get_df()
        len_sent = len(
            df[(df["status"] == "SENT") & df["client_name"].isin(clients)]
        )
        print("len_sent2", len_sent)

    cursor.close()
    conn.close()
    print("\nFinally")
    print("THE END!")
