# tests/test-unit.py
import os
from os.path import basename, splitext, isdir, join
from copy import deepcopy
from glob import glob
from time import perf_counter
from pathlib import Path
import sys
import argparse
import pickle
import logging # Added for verbose logging control

import dill

from ffxe import * # Make sure FFXEngine is imported here

"""
script to run ffxe on all nRF52 unit tests
"""
PARENT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJ_ROOT = os.path.realpath(f"{PARENT_DIR}/..")
OUT_DIR = f"{PROJ_ROOT}/tests/cfgs/unit-tests"

# --- Configuration for Hints ---
INPUT_PKL_HINTS_DIR = f"{PROJ_ROOT}/ffxe_hints_pkls"
# --- End Configuration ---

# List of binaries that showed decreased performance with hints
PROBLEMATIC_BINARIES = [
    "blinky-o0.bin", "blinky-o1.bin", "blinky-o2.bin", "blinky-o3.bin",
    "gpiote-o0.bin", "gpiote-o1.bin", "gpiote-o2.bin", "gpiote-o3.bin",
    "saadc-o1.bin", "saadc-o2.bin",
    "simple_timer-o0.bin",
    "spi-o1.bin", "spi-o3.bin",
    "timer-o0.bin", "timer-o1.bin", "timer-o2.bin", "timer-o3.bin"
]


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

        # If --use-hints flag is present, attempt to load the specific .pkl for this binary
        if args.use_hints:
            # Construct the expected .pkl filename for the current binary
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

        ffxe = FFXEngine(
            pd="mmaps/nrf52832.yml",
            path=fw_path,
            log_stdout=False, # Keep this False by default
            log_insn=False,   # Keep this False by default
            log_time=True,
            functions=functions_to_pass # Pass the dynamically loaded hints here
        )

        # --- START: Conditional Verbose Logging for Problematic Binaries ---
        if args.use_hints and current_firmware_name in PROBLEMATIC_BINARIES:
            # Set the logger's overall level to DEBUG
            ffxe.logger.setLevel(logging.DEBUG) 
            # Iterate through existing handlers (e.g., file handler, stream handler)
            for handler in ffxe.logger.handlers: 
                # Ensure console handler (StreamHandler) displays DEBUG messages
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(logging.DEBUG)
                # Ensure file handler (FileHandler) writes DEBUG messages to file
                if isinstance(handler, logging.FileHandler):
                    handler.setLevel(logging.DEBUG)
            ffxe.log_insn = True # Enable logging of individual instructions
            ffxe.logger.info(f"DEBUG: Verbose logging ENABLED for {current_firmware_name} (with hints).")
        # --- END: Conditional Verbose Logging ---

        t = perf_counter()
        ffxe.run()
        elapsed = perf_counter() - t

        total_insns = 0
        total_size = 0
        for block in ffxe.cfg.bblocks.values():
            total_size += block.size
            # Ensure proper mode for Capstone disassembler when reading memory
            # This part of the code might need to dynamically adjust cs.mode based on block.addr
            # or the current emulation state if not already handled by FFXE's hooks.
            # For now, assuming FFXE's internal hooks handle mode changes correctly before disasm.
            try:
                # Need to ensure ffxe.cs.mode is correctly set for disasm here.
                # The disasm call inside _hook_block already handles this.
                # This loop is for counting, so it might not need the same rigor as emulation.
                # However, if it causes errors, it points to a deeper issue.
                for insn in ffxe.cs.disasm(ffxe.uc.mem_read(block.addr, block.size), block.addr):
                     total_insns += 1
            except Exception as e:
                # Log any errors during disasm for counting, but don't stop the main flow
                print(f"Warning: Error during instruction count disasm for block 0x{block.addr:x} in {current_firmware_name}: {e}")


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