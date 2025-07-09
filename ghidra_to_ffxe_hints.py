# ghidra_to_ffxe_hints.py
# This script reads all _functions.txt files from a specified input directory,
# filters them to include only functions at executable addresses (heuristic-based),
# converts the function addresses and names into a list of (address, size, name) tuples,
# and saves each list as a separate .pkl file in a specified output directory.

import pickle
import os
import glob # To find all .txt files
import traceback # For detailed error reporting

# --- Configuration ---
# Define the absolute path to the directory containing your raw Ghidra .txt function files.
INPUT_TXT_FILES_DIR = "/home/alex/ffxe-usenix24/function_txt_files"

# Define the absolute path to the directory where the output .pkl files will be saved.
OUTPUT_PKL_FILES_DIR = "/home/alex/ffxe-usenix24/ffxe_hints_pkls"

# --- Heuristic for Executable Addresses ---
# For ARM Cortex-M, executable code is typically in Flash or Code RAM.
# These regions usually start at specific base addresses and have specific sizes.
# This is a simplified heuristic based on common nRF52 memory maps.
# You might need to refine this based on your 'nrf52832.yml' or firmware specifics.
# Example: Flash typically starts around 0x0 or 0x10000000 and is executable.
# This is a basic check. A more robust check would parse nrf52832.yml's 'mmap' section.

# Let's use the memory map from nrf52832.yml for a more accurate check.
# We'll need to load it.
import yaml
NRF52_MMAP_PATH = "/home/alex/ffxe-usenix24/mmaps/nrf52832.yml"
EXECUTABLE_RANGES = []
try:
    with open(NRF52_MMAP_PATH, 'r') as f:
        nrf52_mmap = yaml.safe_load(f)
        if 'mmap' in nrf52_mmap:
            for region_name, props in nrf52_mmap['mmap'].items():
                # Check if region has 'perms' and 'x' (execute) permission
                if 'perms' in props and (props['perms'] & 0b001): # Assuming 0b001 is execute bit
                    start_addr = props['address']
                    size = props['size']
                    EXECUTABLE_RANGES.append((start_addr, start_addr + size))
                    print(f"DEBUG: Added executable range: 0x{start_addr:x}-0x{start_addr+size:x} ({region_name})")
        if not EXECUTABLE_RANGES:
            print("WARNING: No executable memory regions found in {}. All functions will be considered non-executable.".format(NRF52_MMAP_PATH))
except FileNotFoundError:
    print(f"ERROR: nrf52832.yml not found at {NRF52_MMAP_PATH}. Cannot determine executable ranges. All functions will be considered non-executable.")
except Exception as e:
    print(f"ERROR: Failed to parse nrf52832.yml: {e}. All functions will be considered non-executable.")
    traceback.print_exc()

def is_address_executable(address):
    # Check if the address falls within any of the defined executable ranges
    for start, end in EXECUTABLE_RANGES:
        # For Thumb mode, LSB can be 1, so clear it for range check
        if (address & ~1) >= start and (address & ~1) < end:
            return True
    return False


def convert_single_ghidra_output(txt_file_path, output_pkl_path):
    """
    Converts a single Ghidra .txt function file into an FFXE-compatible .pkl hints file,
    filtering for executable addresses.
    """
    ffxe_hints = []
    total_functions_in_txt = 0
    exported_functions_count = 0

    try:
        with open(txt_file_path, 'r') as f:
            for line in f:
                total_functions_in_txt += 1
                line = line.strip()
                if not line:
                    continue # Skip empty lines

                parts = line.split(',')
                if len(parts) == 2:
                    address_str = parts[0].strip()
                    func_name = parts[1].strip()

                    try:
                        address = int(address_str.replace('L', ''), 16)

                        # --- Filtering Logic Applied Here ---
                        if is_address_executable(address):
                            # FFXE expects (address, size, name)
                            # Size is 0, as FFXE determines it dynamically
                            ffxe_hints.append((address, 0, func_name))
                            exported_functions_count += 1
                        else:
                            print(f"Skipping non-executable function: {func_name} at 0x{address:x} in {os.path.basename(txt_file_path)}")
                        # --- End Filtering Logic ---

                    except ValueError:
                        print(f"Warning: Could not parse address from line: '{line}' in {os.path.basename(txt_file_path)}. Skipping.")
                else:
                    print(f"Warning: Unexpected line format: '{line}' in {os.path.basename(txt_file_path)}. Expected '0xADDRESSL,FUNCTION_NAME'. Skipping.")

        if ffxe_hints:
            with open(output_pkl_path, 'wb') as f:
                pickle.dump(ffxe_hints, f)
            print(f"Successfully generated '{os.path.basename(output_pkl_path)}' with {exported_functions_count} executable functions (out of {total_functions_in_txt} total).")
        else:
            print(f"No valid executable function hints found in '{os.path.basename(txt_file_path)}'. No PKL file generated.")

    except FileNotFoundError:
        print(f"Error: Input .txt file '{txt_file_path}' not found. Skipping.")
    except Exception as e:
        print(f"An unexpected error occurred processing '{os.path.basename(txt_file_path)}': {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print(f"Starting conversion of .txt files from: {INPUT_TXT_FILES_DIR}")

    # Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_PKL_FILES_DIR):
        os.makedirs(OUTPUT_PKL_FILES_DIR)
        print(f"Created output directory: {OUTPUT_PKL_FILES_DIR}")

    # Find all .txt files in the input directory
    txt_files = glob.glob(os.path.join(INPUT_TXT_FILES_DIR, "*.txt"))

    if not txt_files:
        print(f"No .txt files found in the input directory: {INPUT_TXT_FILES_DIR}. Please check the path and file extensions.")
    else:
        print(f"Found {len(txt_files)} .txt files to process.")
        for txt_file_path in sorted(txt_files): # Process in sorted order for consistency
            base_filename = os.path.basename(txt_file_path)
            pkl_filename = base_filename.replace("_functions.txt", "_hints.pkl")
            output_pkl_path = os.path.join(OUTPUT_PKL_FILES_DIR, pkl_filename)

            convert_single_ghidra_output(txt_file_path, output_pkl_path)

    print("Conversion process complete.")