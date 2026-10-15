"""Bitrix24 file operations.

Handles downloading files from Bitrix24, uploading recognized documents back,
and moving original files to archive folders.
"""

import os
import time
from datetime import datetime

import pandas as pd
import requests
import urllib3
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from sqlalchemy import create_engine

from utils.settings import url_bitrix
from utils.bitrix_folder import create_folder, get_file_name, get_name_month, move_one_file
from utils.db import odbc_params, py_odbc
from utils.email import send_mail_win32, send_smtp_html

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings()
pd.set_option("display.max_columns", None)

today = time.strftime("%Y%m%d_b", time.localtime(time.time()))
year = time.strftime("%Y", time.localtime(time.time()))
homepath = os.path.expanduser(os.getenv("USERPROFILE", ""))

service_name = "!Разложить документы"


# ---------------------------------------------------------------------------
# Download files from Bitrix24
# ---------------------------------------------------------------------------

def save_file(url: str, path: str) -> None:
    """Download a file from a URL and save it to the given path.

    Args:
        url: Source URL (must contain /~<name>).
        path: Local directory to save the file in.
    """
    name_file = url.split("/~")[1]
    response = requests.get(url, verify=False)

    if response.status_code != 200:
        print(f"Не удалось загрузить файл. Код состояния: {response.status_code}")
        return

    if "Content-Type" not in response.headers:
        print("Заголовок Content-Type не найден.")
        return

    content_type = response.headers["Content-Type"]
    parts = content_type.split("/")
    if len(parts) != 2:
        print("Не удалось определить расширение файла.")
        return

    extension = parts[1]
    filename = f"{path}/{name_file}.{extension}"
    with open(filename, "wb") as file:
        file.write(response.content)
    print(f"Файл сохранен как: {filename}")


def save_all_files(temp_path: str, data: dict) -> None:
    """Download all files from Bitrix24 folders for a given client.

    Args:
        temp_path: Local temp directory for the client.
        data: Client data dict with "client" and "web_id" keys.
    """
    client = data["client"]
    client_id = int(data["web_id"])

    print(f"1 {client} - это Bitrix24")
    folders = get_name_month()

    for folder in folders:
        if folders[0] == "12_Декабрь" and folder == "12_Декабрь":
            continue

        files_path = (
            f"/ACCOUNTING/{year}/AP-Creditors %26 Suppliers/For Unicon/{folder}"
        )
        url = f"{url_bitrix}/disk.getfiles?folderPath={files_path}&clientId={client_id}"
        print(url)
        r = requests.get(url, verify=False).json()

        if r.get("result") is None:
            print("Error!!!", r)
            continue

        result = r["result"]

        if "files" in result:
            for _v, url_file in result["files"].items():
                save_file(url_file, temp_path)
        elif "status" in result:
            text = result["status"]
            if text != "success":
                text = f"{client}\n{folder}\n{text}"
                send_mail_win32(
                    "A.Kuznetsov@ubpo.ru", "Error: NO folder on BT24", text
                )


# ---------------------------------------------------------------------------
# Upload recognized files to Bitrix24
# ---------------------------------------------------------------------------

DOC_TYPE_FOLDERS: dict[str, str] = {
    "Договор": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Agreements/{service_name}",
    "Приложение к договору": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Agreements/{service_name}",
    "Дополнительное соглашение": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Agreements/{service_name}",
    "CONTRACT": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Agreements/{service_name}",
    "CONTRACT_ATTACHMENT": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Agreements/{service_name}",
    "SUPPLEMENTARY_AGREEMENT": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Agreements/{service_name}",
    "Письмо на возврат": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Correspondence/{service_name}",
    "Акт сверки": f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Reconciliation acts/{service_name}",
    "Авансовый отчет": f"/ACCOUNTING/{year}/ES - Employee service/Expenses reports/{service_name}",
}

VENDOR_TYPES = {
    "Счёт", "Счет", "Счет-фактура", "Счёт-фактура",
    "Акт", "УПД", "ТОРГ-12", "ТОРГ-2", "Приказ",
    "Детализация-спецификация", "Отчет агента", "Акт зачета", "ГТД",
    "OFFER", "VAT_INVOICE", "CERTIFICATE", "TORG12", "TORG2",
    "AGENT_REPORT",
}


def _get_folder_name(type_d: str) -> str:
    """Determine the Bitrix24 folder path for a given document type.

    Args:
        type_d: Document type string.

    Returns:
        Bitrix24 folder path.
    """
    if type_d in DOC_TYPE_FOLDERS:
        return DOC_TYPE_FOLDERS[type_d]
    return f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/Vendor documents/{service_name}"


def upload_one_file(folder_name: str, file_path: str, client_id: int) -> None:
    """Upload a single file to Bitrix24.

    Args:
        folder_name: Destination folder path in Bitrix24.
        file_path: Local path to the file.
        client_id: Bitrix24 client (web) ID.
    """
    url = f"{url_bitrix}/disk.addfile"
    data = {"folderPath": folder_name, "clientId": client_id}

    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        files = {"file": (file_name, f, "application/pdf")}
        response = requests.post(url, data=data, files=files, verify=False)

    if response.status_code == 200:
        print("Файл успешно загружен.")
    else:
        print(
            f"Произошла ошибка при загрузке файла. "
            f"Код ошибки: {response.status_code}"
        )
        print(response.text)


def upload_files(file_name: str, web_id: str, account: str) -> None:
    """Upload a recognized file to the correct Bitrix24 folder by document type.

    Args:
        file_name: Name of the file to upload.
        web_id: Bitrix24 web ID (client ID).
        account: Client account name.
    """
    type_d = file_name.split("__")[0]
    print(f"\nType docs = {type_d}")

    local_path_recog = f"{homepath}/AppData/Local/Temp/{today}/{account}/RECOGNIZED"
    file_path = os.path.join(local_path_recog, file_name)
    folder_name = _get_folder_name(type_d)

    create_folder(folder_name, web_id)
    upload_one_file(folder_name, file_path, web_id)


def load_files(today_path: str, web_id: str, account: str) -> None:
    """Upload all PDF files from a client's RECOGNIZED folder.

    Args:
        today_path: Path to today's temp folder.
        web_id: Bitrix24 web ID.
        account: Client account name.
    """
    local_path_recog = os.path.join(today_path, account, "RECOGNIZED")
    print("Local temp path Recogn -", local_path_recog)

    files = [f for f in os.listdir(local_path_recog) if f.endswith(".pdf")]
    for f in files:
        upload_files(f, web_id, account)


def upload_files_to_bitrix24(today_path: str, datas: list[dict]) -> None:
    """Upload recognized files to Bitrix24 for all clients.

    Args:
        today_path: Path to today's temp folder.
        datas: List of client data dicts with "client" and "web_id" keys.
    """
    if not os.path.exists(today_path):
        print("FOLDER NO")
        return

    dirname = os.listdir(today_path)
    for dt in datas:
        account = dt["client"]
        web_id = dt["web_id"]
        if account in dirname:
            print(account, "Есть в B24.")
            load_files(today_path, web_id, account)


# ---------------------------------------------------------------------------
# Move original files to archive folders
# ---------------------------------------------------------------------------

time_unix = time.time()

conn = py_odbc()
cursor = conn.cursor()
connection_string = f"mssql+pyodbc:///?odbc_connect={odbc_params()}"
engine = create_engine(connection_string)


def get_df(account: str) -> pd.DataFrame:
    """Fetch recent non-SENT records for a given client.

    Args:
        account: Client account name.

    Returns:
        DataFrame with records from the last 4 days where status != 'SENT'.
    """
    query = (
        "SELECT * FROM entera_before "
        "WHERE time_unix > ? AND client_name = ? AND status != 'SENT'"
    )
    return pd.read_sql(query, engine, params=(time_unix - 345600, account))


def move_files(today_path: str, datas: list[dict]) -> None:
    """Move original files in Bitrix24 to archive folders.

    For each client, moves files from "For Unicon" to either
    "Transferred to OCR" (success) or "Unrecognized" (failure).
    Sends email on failure.

    Args:
        today_path: Path to today's temp folder.
        datas: List of client data dicts with "client", "web_id", "email" keys.
    """
    if not os.path.exists(today_path):
        print("FOLDER NO")
        return

    dirname = os.listdir(today_path)

    for dat in datas:
        account = dat["client"]
        client_id = dat["web_id"]
        email_address = dat["email"]

        if account not in dirname:
            continue

        print(account, "Есть в BITRIX24.")
        df = get_df(account)
        print(len(df))
        print(df)

        if len(df) == 0:
            print(f"{account} NO FILES TO MOVING")
            continue

        print(f"{account} Number of record = {len(df)}")

        for _, row in df.iterrows():
            status_reg = row["status"]
            name_link = os.path.splitext(row["file_name"])[0]
            file_path = f"https://bitrix.ubpo.ru/~{name_link}"
            print("===============================", file_path)

            file_name = get_file_name(file_path)
            if file_name is None:
                continue

            folders = get_name_month()
            for folder in folders:
                if folders[0] == "12_Декабрь" and folder == "12_Декабрь":
                    continue

                from_path = (
                    f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/For Unicon/"
                    f"{folder}/{file_name}"
                )
                print("FROM", from_path)

                if status_reg in ("ERROR", "NO_RECOGNIZED"):
                    to_path = (
                        f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/"
                        f"For Unicon/Unrecognized"
                    )
                    print(f"Send mail to {email_address}")
                    text = (
                        f"<p>Внимание!</p><p>Файла - {file_name}</p>"
                        f"<p>НЕ был распознан.</p>"
                    )
                    send_smtp_html(email_address, "Robot Sharepoint", text)
                else:
                    to_path = (
                        f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/"
                        f"For Unicon/Transferred to OCR"
                    )

                print("TO  ", to_path)
                create_folder(to_path, client_id)
                move_one_file(from_path, to_path, client_id)
