import pickle
import os
import glob 
import yaml 

INPUT_TXT_FILES_DIR = "/home/alex/ffxe-usenix24/function_txt_files"
OUTPUT_PKL_FILES_DIR = "/home/alex/ffxe-usenix24/ffxe_hints_pkls"
NRF52_MMAP_PATH = "/home/alex/ffxe-usenix24/mmaps/nrf52832.yml"

EXECUTABLE_RANGES = []

with open(NRF52_MMAP_PATH, 'r') as f:
    nrf52_mmap = yaml.safe_load(f)
    if 'mmap' in nrf52_mmap:
        for region_name, props in nrf52_mmap['mmap'].items():
            if 'perms' in props and (props['perms'] & 0b001):
                start_addr = props['address']
                size = props['size']
                EXECUTABLE_RANGES.append((start_addr, start_addr + size))


def is_address_executable(address):
    if not EXECUTABLE_RANGES: 
        return True

    for start, end in EXECUTABLE_RANGES:
        if (address & ~1) >= start and (address & ~1) < end:
            return True
    return False


def convert_single_ghidra_output(txt_file_path, output_pkl_path):
    ffxe_hints = []

    with open(txt_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue # Skip empty lines

            parts = line.split(',')
            address_str = parts[0].strip()
            func_name = parts[1].strip()

            address = int(address_str.replace('L', ''), 16)
            
            #Set size to 0. will be done when run
            if is_address_executable(address):
                ffxe_hints.append((address, 0, func_name))


    if ffxe_hints:
        with open(output_pkl_path, 'wb') as f:
            pickle.dump(ffxe_hints, f)


if __name__ == "__main__":
    # Find all .txt files in the input directory
    txt_files = glob.glob(os.path.join(INPUT_TXT_FILES_DIR, "*.txt"))

    if txt_files: 
        for txt_file_path in sorted(txt_files): 
            base_filename = os.path.basename(txt_file_path)
            pkl_filename = base_filename.replace("_functions.txt", "_hints.pkl")
            output_pkl_path = os.path.join(OUTPUT_PKL_FILES_DIR, pkl_filename)

            convert_single_ghidra_output(txt_file_path, output_pkl_path)
