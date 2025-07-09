import os
from os.path import basename, splitext, isdir, join # Added 'join' for os.path.join
from copy import deepcopy
from glob import glob
from time import perf_counter
from pathlib import Path
import sys
import argparse
import pickle # Added to load the .pkl hints file

import dill

from ffxe import * # Make sure FFXEngine is imported here

"""
script to run ffxe on all nRF52 unit tests
"""
PARENT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJ_ROOT = os.path.realpath(f"{PARENT_DIR}/..")
OUT_DIR = f"{PROJ_ROOT}/tests/cfgs/unit-tests"

# --- Configuration for Hints ---
# Define the absolute path to the directory containing your generated .pkl hint files.
# This is where the previous script saved them.
INPUT_PKL_HINTS_DIR = f"{PROJ_ROOT}/ffxe_hints_pkls"
# --- End Configuration ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FFXE Unit Tests with optional Ghidra hints.")
    parser.add_argument("--use-hints", action="store_true",
                        help=f"Use pre-defined function hints from {INPUT_PKL_HINTS_DIR} for each binary.")
    args = parser.parse_args()

    fw_examples = glob(f'{PROJ_ROOT}/examples/unit-tests/*.bin')

    if not isdir(OUT_DIR):
        Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    ffxe_cfgs = {}
    table = []

    for fw_path in sorted(fw_examples):
        current_firmware_name = basename(fw_path) # e.g., "blinky-o0.bin"
        
        functions_to_pass = None # Initialize to None for no hints by default

        # --- MODIFICATION START ---
        # If --use-hints flag is present, attempt to load the specific .pkl for this binary
        if args.use_hints:
            # Construct the expected .pkl filename for the current binary
            # e.g., "blinky-o0.bin_hints.pkl"
            expected_pkl_filename = current_firmware_name.replace(".bin", "_hints.pkl")
            full_pkl_path = join(INPUT_PKL_HINTS_DIR, expected_pkl_filename)

            try:
                if os.path.exists(full_pkl_path):
                    with open(full_pkl_path, 'rb') as f:
                        functions_to_pass = pickle.load(f)
                    print(f"Loaded {len(functions_to_pass)} Ghidra hints for {current_firmware_name} from {os.path.basename(full_pkl_path)}.")
                else:
                    print(f"Warning: Hints file '{os.path.basename(full_pkl_path)}' not found for {current_firmware_name}. Running without hints for this binary.")
                    functions_to_pass = None # Ensure no hints are passed if file is missing
            except Exception as e:
                print(f"Error loading hints for {current_firmware_name} from '{os.path.basename(full_pkl_path)}': {e}. Running without hints for this binary.")
                functions_to_pass = None
        # --- MODIFICATION END ---

        ffxe = FFXEngine(
            pd="mmaps/nrf52832.yml",
            path=fw_path,
            log_stdout=False,
            log_insn=False,
            log_time=True,
            functions=functions_to_pass # Pass the dynamically loaded hints here
        )

        t = perf_counter()
        ffxe.run()
        elapsed = perf_counter() - t

        total_insns = 0
        total_size = 0
        for block in ffxe.cfg.bblocks.values():
            total_size += block.size
            for insn in ffxe.cs.disasm(
                            ffxe.uc.mem_read(block.addr, block.size), block.size):
                total_insns += 1

        result = "{:<25} : {{ \"blocks\": {:>4d}, \"edges\": {:>4d},  \"elapsed\": \"{:>15.9f} s\" }}".format(
            f'"{basename(fw_path)}"',
            len(ffxe.cfg.bblocks),
            len(ffxe.cfg.edges),
            elapsed
        )

        print(result)
        table.append(result)

        ffxe_cfgs[basename(fw_path)] = ffxe.cfg

    with open('tests/ffxe-cfg-results.json', 'w') as f:
        f.write('{\n  ' + ',\n  '.join(table) + '\n}')

    for fn, cfg in ffxe_cfgs.items():
        (name, ext) = splitext(fn)
        graph = {
            'nodes': set([(b.addr, b.size) for b in cfg.bblocks.values()]),
            'edges': set([(max(cfg.bblocks[e[0]].insns.keys()), e[1]) for e in cfg.edges]),
                # max() is used to get the last address in the bblock
        }
        with open(f"{OUT_DIR}/{name}-ffxe-cfg.pkl", 'wb') as pklfile:
            dill.dump(graph, pklfile)