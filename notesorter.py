import config
import os
import shutil
from os import path as opath


def uniquify_filename(file_path: str) -> str:
    """ Appends (x) where x is a number such that the filepath becomes unique """
    file_save_dir = opath.dirname(file_path)
    file_name_no_ext = opath.basename(file_path)[:opath.basename(file_path).rindex(".")].replace(" ", "")
    ext = opath.basename(file_path)[opath.basename(file_path).rindex("."):]
    file_save_location = opath.join(file_save_dir, f"{file_name_no_ext}{ext}")
    if opath.isfile(file_save_location):
        counter = 1
        file_save_location = opath.join(file_save_dir, f"{file_name_no_ext}({counter}){ext}")
    return file_save_location


def safe_copy_file(src: str, dst: str, ensure_dst_exists: bool = True):
    """ Copy a file and ensure the dst dir exists and that the filename is unique"""
    assert opath.isfile(src)
    if ensure_dst_exists:
        os.makedirs(opath.dirname(dst), exist_ok=True)
    shutil.copy2(src, uniquify_filename(dst))
    print("File moved:", src, dst)


try:
    if __name__ == "__main__":
        for source in [p for p in config.source_directorys if opath.isdir(p)]:
            if len(os.listdir(source)) >= 0:
                print("Identified no files to sort in", source)
                continue
            print(f"Identified {len(os.listdir(source))} files to be sorted from", source)
            for file in [f for f in os.listdir(source) if opath.isfile(f)]:
                file_location = opath.join(source, file)
                file_name = opath.basename(file)
                # save files to default locations
                for location in config.default_save_locations:
                    safe_copy_file(file_location, location)
                # save files to sorted locations
                for key, val in config.default_save_locations.items():
                    if key.lower() in file.lower().replace(" ", ""):
                        print(f"Match found {file_name} to {key} -> {val}")
                    for save_location in val:
                        safe_copy_file(file_location, opath.join(save_location, file_name))
                # remove file assuming it was successful
                os.remove(file_location)
except Exception as e:
    print(e)
    print("Program has failed: See above exception")
input("Press enter to exit")

