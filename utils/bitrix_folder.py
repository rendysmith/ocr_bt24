"""Bitrix24 folder and file operations.

Handles creating folders, moving files, extracting file names from HTTP headers,
and resolving month names for folder paths.
"""

import datetime
import locale
from urllib.parse import unquote
from typing import Optional

import requests

from utils.settings import url_bitrix
from utils.email import send_mail_win32


def create_folder(folder_name: str, client_id: int) -> None:
    """Create a folder in Bitrix24 if it does not already exist.

    Args:
        folder_name: Path of the folder to create.
        client_id: Bitrix24 client (web) ID.
    """
    url = f"{url_bitrix}/disk.addfolder"
    data = {"clientId": client_id, "folderPath": folder_name}
    response = requests.post(url, data=data, verify=False)

    print(f"-- Имя папки: {folder_name}")
    if response.status_code == 200:
        status = response.json()["result"]["status"]
        if status == "OK":
            print("--- Папка успешно создана.")
        elif status == "Folder exists":
            print("--- Папка уже существует.")
        else:
            text = f"--- ERROR! CREATE\n{folder_name}\n{response.json()}"
            print(text)
            send_mail_win32(
                "A.Kuznetsov@ubpo.ru", "Error: create folder on BT24", text
            )
    else:
        print(
            f"Произошла ошибка при создании папки. "
            f"Код ошибки: {response.status_code}"
        )
        print(response.text)


def move_one_file(from_path: str, to_path: str, client_id: int) -> None:
    """Move a file within Bitrix24 from one folder to another.

    Args:
        from_path: Source file path.
        to_path: Destination folder path.
        client_id: Bitrix24 client (web) ID.
    """
    url = f"{url_bitrix}/disk.movefile"
    data = {"filePath": from_path, "folderPath": to_path, "clientId": client_id}
    response = requests.post(url, data=data, verify=False)

    if response.status_code == 200:
        status = response.json()["result"]["status"]
        if status == "OK":
            print("--- Файл успешно перемещен.")
        elif status == "File not exist":
            print(f"--- Файл не найден. {from_path}")
        else:
            print("--- ERROR! MOVE", response.json())
    else:
        print(
            f"Произошла ошибка при загрузке файла. "
            f"Код ошибки: {response.status_code}"
        )
        print(response.text)


def get_file_name(url: str) -> Optional[str]:
    """Extract a file name from an HTTP Content-Disposition header.

    Args:
        url: URL to fetch headers from.

    Returns:
        Decoded file name, or None if not found.
    """
    response = requests.get(url, verify=False)
    if response.status_code != 200:
        print(f"Ошибка при получении контента: {response.status_code}")
        return None

    content_disposition = response.headers.get("content-disposition")
    print(content_disposition)
    if not content_disposition:
        print("Имя файла не найдено в заголовках.")
        return None

    file_name = content_disposition.split("filename*=utf-8''")[1]
    return unquote(file_name)


def get_name_month() -> tuple[str, str]:
    """Get the current and previous month names in Russian locale.

    Returns:
        Tuple of (previous_month_name, current_month_name),
        e.g. ("09_Сентябрь", "10_Октябрь").
    """
    locale.setlocale(locale.LC_ALL, "ru_RU.UTF-8")
    current_date = datetime.date.today()
    previous_date = current_date - datetime.timedelta(days=30)

    current_month = current_date.strftime("%m_%B")
    previous_month = previous_date.strftime("%m_%B")
    return previous_month, current_month
