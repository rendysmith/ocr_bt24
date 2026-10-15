"""OCR Bitrix24 RPA Bot — main entry point.

Orchestrates the full document processing pipeline:
1. Create folders in Bitrix24
2. Download files from Bitrix24
3. Send files to Entera for OCR recognition
4. Upload recognized files back to Bitrix24
5. Move original files to archive folders
6. Clean up temporary files
7. Send email notifications
"""

import asyncio
import os
import shutil
import time
from datetime import datetime

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from utils.bitrix_client import accs_bitrix
from utils.bitrix_file import save_all_files, upload_files_to_bitrix24, move_files
from utils.bitrix_folder import create_folder, get_name_month
from utils.email import send_smtp
from utils.entera_ocr import sendler

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

home_directory = os.path.expanduser(os.getenv("USERPROFILE", ""))
now_ = datetime.now()
year = str(now_.year)
date_temp = now_.strftime("%Y%m%d_b")


async def main() -> None:
    """Run the full OCR document processing pipeline."""
    datas = await accs_bitrix()

    today_path = os.path.join(home_directory, "AppData/Local/Temp", date_temp)
    print("today_path", today_path)

    start = 0
    for data in datas:
        acc_path = data["client"]
        client_id = data["web_id"]

        print(
            f"\n\n=====================================\n"
            f"0 - Создаем папки в bitrix.ubpo.ru...For Unicon {client_id}\n"
            f"{acc_path}"
        )
        folders = get_name_month()
        print(f"folders: {folders}")
        for folder in folders:
            if folders[0] == "12_Декабрь" and folder == "12_Декабрь":
                continue

            print("Folder name:", folder)
            files_path_0 = (
                f"/ACCOUNTING/{year}/AP-Creditors & Suppliers/For Unicon/{folder}"
            )
            create_folder(files_path_0, client_id)

        temp_path_acc = os.path.join(today_path, acc_path)
        print("1 - Создание временных папок для клиента", temp_path_acc)
        if not os.path.exists(temp_path_acc):
            os.makedirs(temp_path_acc)
            os.makedirs(os.path.join(temp_path_acc, "RECOGNIZED"))

        print("2 - Скачать файлы на локальный диск")
        save_all_files(temp_path_acc, data)

        files = [
            f
            for f in os.listdir(temp_path_acc)
            if os.path.isfile(os.path.join(temp_path_acc, f))
        ]
        if len(files) > 0:
            start = 1

    if start == 1:
        print("3 - Отправка и получение файлов с Entera")
        sendler(today_path, datas)

        print("4 - Загрузка распознанных файлов на Bitrix")
        upload_files_to_bitrix24(today_path, datas)

        print("5 - Перемещение исходных файлов на Bitrix24")
        move_files(today_path, datas)
    else:
        print("--- Нет скачанных файлов")

    print("6 - Удаление временной папки")
    shutil.rmtree(today_path, ignore_errors=True)

    print("7 - Рассылка оповещения")
    emails = ["RPA_Service@ubpo.ru", "A.Kuznetsov@ubpo.ru"]
    subject = "Bot Entera_Bitrix24"
    text = f"The Bot Entera_Local\nfinished work at {time.ctime()}"
    print(f"SEND email to {emails}")
    for email in emails:
        send_smtp([email], subject, text)

    print("THE END!")


if __name__ == "__main__":
    asyncio.run(main())
