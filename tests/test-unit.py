import os
from os.path import basename, splitext, isdir, join
from copy import deepcopy
from glob import glob
from time import perf_counter
from pathlib import Path
import sys
import argparse
import pickle
import logging

import dill

from ffxe import *

PARENT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJ_ROOT = os.path.realpath(f"{PARENT_DIR}/..")
OUT_DIR = f"{PROJ_ROOT}/tests/cfgs/unit-tests"
INPUT_PKL_HINTS_DIR = f"{PROJ_ROOT}/ffxe_hints_pkls"

if __name__ == "__main__":
    #hints
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
        current_firmware_name = basename(fw_path)
        
        functions_to_pass = None 

        if args.use_hints:
            #replaced .bin file with generated .pkl file
            expected_pkl_filename = current_firmware_name.replace(".bin", "_hints.pkl")
            full_pkl_path = join(INPUT_PKL_HINTS_DIR, expected_pkl_filename)

            if os.path.exists(full_pkl_path):
                with open(full_pkl_path, 'rb') as f:
                    functions_to_pass = pickle.load(f)
            else:
                functions_to_pass = None

        ffxe = FFXEngine(
            pd="mmaps/nrf52832.yml",
            path=fw_path,
            log_stdout=False,
            log_insn=False,   
            log_time=True,
            functions=functions_to_pass #function parameter added in the main ffxe method
        )

        t = perf_counter()
        ffxe.run()
        elapsed = perf_counter() - t

        total_insns = 0
        total_size = 0
        for block in ffxe.cfg.bblocks.values():
            total_size += block.size
            for insn in ffxe.cs.disasm(ffxe.uc.mem_read(block.addr, block.size), block.addr):
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

    #save as json file
    with open('tests/ffxe-cfg-results.json', 'w') as f:
        f.write('{\n  ' + ',\n  '.join(table) + '\n}')

    # save as .pkl file
    for fn, cfg in ffxe_cfgs.items():
        (name, ext) = splitext(fn)
        graph = {
            'nodes': set([(b.addr, b.size) for b in cfg.bblocks.values()]),
            'edges': set([(max(cfg.bblocks[e[0]].insns.keys()), e[1]) for e in cfg.edges]),
        }
        with open(f"{OUT_DIR}/{name}-ffxe-cfg.pkl", 'wb') as pklfile:
            dill.dump(graph, pklfile)
