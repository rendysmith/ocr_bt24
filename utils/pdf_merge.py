"""Merge recognized JPG pages into PDF documents."""

import os
import time

import img2pdf

today = time.strftime("%Y%m%d_b", time.localtime(time.time()))
homepath = os.path.expanduser(os.getenv("USERPROFILE", ""))


def merge_jpg_to_pdf(account_or_path: str, is_account: bool = True) -> None:
    """Merge JPG files into a single PDF for a given account or path.

    The function groups JPG files by their base name (stripping the page
    suffix) and creates one PDF per group.

    Args:
        account_or_path: Client account name (if is_account=True) or
                         direct path to RECOGNIZED folder.
        is_account: If True, prepend the standard temp path.
    """
    if is_account:
        local_path_recog = (
            f"{homepath}/AppData/Local/Temp/{today}/{account_or_path}/RECOGNIZED"
        )
    else:
        local_path_recog = account_or_path

    print(f"+++ Merge jpg to pdf {local_path_recog}")

    try:
        jpg_files = [a for a in os.listdir(local_path_recog) if a.endswith(".jpg")]
    except OSError:
        jpg_files = [a for a in os.listdir(local_path_recog) if ".jpg" in a]

    # Strip page suffix to group multi-page documents
    jpg_groups = {i.split(".jpg")[0][:-4] for i in jpg_files}

    for group_name in jpg_groups:
        jpg_list = [
            f"{local_path_recog}/{j}"
            for j in jpg_files
            if group_name in j
        ]

        file_name = f"{local_path_recog}/{group_name}.pdf"

        if os.path.exists(file_name):
            print("File already created -", file_name)
            continue

        with open(f"{local_path_recog}/{group_name}.pdf", "wb") as f:
            f.write(img2pdf.convert(jpg_list))

        print("Merge files -", jpg_list)

    print(f"--- Merge PDF {local_path_recog} OK!")
