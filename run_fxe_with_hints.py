import os
import sys
import argparse
import pickle
import time
import yaml
import unicorn 

# Import necessary Unicorn constants and ARM register definitions
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_PC

# Import the core FFXE components
try:
    from fxe import FXEngine
    from models import CFG, FirmwareImage # Assuming CFG and FirmwareImage are in models.py
except ImportError as e:
    print(f"Error importing FFXE components: {e}")
    print("Please ensure you are running this script from the ffxe-usenix24 root directory.")
    print("If you encounter issues, try: export PYTHONPATH=$PYTHONPATH:$(pwd) or 'pip install -e .' in your virtual environment.")
    sys.exit(1)


# --- Configuration Paths (Defined at global scope for accessibility) ---
DEFAULT_BINARY_PATH = 'examples/unit-tests/blinky-o1.bin' # Path to the firmware binary
DEFAULT_PLATFORM_DESCRIPTION = 'mmaps/stm32f429ze.yml' # Path to the platform description YAML
DEFAULT_FUNCTIONS_FILE = 'blinky_functions.txt' # Path to the Ghidra exported functions file
OUTPUT_CFG_DIR = 'cfgs_with_hints' # Directory to save the recovered CFG .pkl file
# --- End Configuration Paths ---


def load_functions_from_ghidra(filepath):
    """
    Loads function entry points and names from a Ghidra-exported text file.
    Returns a dictionary mapping function addresses (int) to names (str).
    """
    functions = {} 
    if not os.path.exists(filepath):
        print(f"Warning: Ghidra functions file '{filepath}' not found. FXE will run without function hints.")
        return functions
    
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 2:
                address_str = parts[0].replace('L', '') # Remove 'L' suffix if present
                address = int(address_str, 16) # Convert hex string to integer
                name = parts[1]
                functions[address] = name
    print(f"Loaded {len(functions)} function hints from Ghidra.")
    return functions

def main():
    # Setup command-line argument parsing
    parser = argparse.ArgumentParser(description="Run FFXE with optional Ghidra function hints and custom Unicorn setup.")
    parser.add_argument('binary_path', nargs='?', default=DEFAULT_BINARY_PATH,
                        help=f"Path to the firmware binary (default: {DEFAULT_BINARY_PATH})")
    parser.add_argument('--platform-desc', default=DEFAULT_PLATFORM_DESCRIPTION,
                        help=f"Path to the platform description YAML (default: {DEFAULT_PLATFORM_DESCRIPTION})")
    parser.add_argument('--functions-file', default=DEFAULT_FUNCTIONS_FILE,
                        help=f"Path to the Ghidra exported functions file (default: {DEFAULT_FUNCTIONS_FILE})")
    parser.add_argument('--output-dir', default=OUTPUT_CFG_DIR,
                        help=f"Directory to save the recovered CFG .pkl file (default: {OUTPUT_CFG_DIR})")
    parser.add_argument('--log-stdout', action='store_true',
                        help="Enable FFXE's internal logging to stdout")
    
    args = parser.parse_args()

    # Load function hints from Ghidra export
    ghidra_function_hints = load_functions_from_ghidra(args.functions_file)

    # Ensure output directory for CFG files exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        print(f"Created output directory: {args.output_dir}")

    print(f"Running FFXE analysis on: {args.binary_path}")

    # --- NEW: External Unicorn Setup and Firmware Loading ---
    # We are explicitly setting up Unicorn here to control memory mapping and initial state precisely.
    
    # Load platform description YAML (e.g., mmaps/stm32f429ze.yml)
    if not os.path.exists(args.platform_desc):
        print(f"Error: Platform description file '{args.platform_desc}' not found.")
        sys.exit(1)
    with open(args.platform_desc, 'r') as pd_file:
        platform_description = yaml.load(pd_file, yaml.Loader)

    # --- CRITICAL ADJUSTMENT FOR BLINKY-O1.BIN: Override flash base to 0x0 ---
    # Ghidra analysis showed blinky-o1.bin is compiled with code starting at 0x0.
    # We must map it at 0x0 in Unicorn for the internal vector table and jumps to be correct.
    override_flash_base = 0x0 
    # Use the original flash size from the YAML, but override the starting address.
    flash_size = platform_description['mmap']['flash']['size']

    # Create Unicorn emulator instance (ARM architecture, Thumb mode)
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    # Set the specific CPU model for better emulation accuracy
    uc.ctl_set_cpu_model(unicorn.arm_const.UC_CPU_ARM_CORTEX_M4)

    # Map memory regions as defined in the platform description YAML.
    # For the 'flash' region, use our overridden 0x0 base address.
    for region_name, kwargs in platform_description['mmap'].items():
        map_address = kwargs['address']
        map_size = kwargs['size']
        
        # If this is the 'flash' region, use our override_flash_base
        if region_name == 'flash':
            map_address = override_flash_base
            map_size = flash_size # Keep the original size from YAML
        
        # Ensure read/write/execute permissions for simplicity during emulation
        perms = (UC_PROT_READ | UC_PROT_WRITE | UC_PROT_EXEC) 
        
        try:
            uc.mem_map(map_address, map_size, perms)
            print(f"Wrapper Debug: Mapped {region_name}: {hex(map_address)} with size {hex(map_size)} (Perms: {perms})")
        except Exception as e:
            print(f"Wrapper Debug: ERROR mapping {region_name} at {hex(map_address)}: {e}")
            sys.exit(1)
            
    # Load firmware raw bytes into the mapped flash memory (which is now at 0x0)
    if not os.path.exists(args.binary_path):
        print(f"Error: Binary file '{args.binary_path}' not found.")
        sys.exit(1)
            
    fw_image = FirmwareImage(args.binary_path, pd=platform_description, base_addr=override_flash_base, vtbases=[0])
    fw_raw_bytes = fw_image.raw
    
    try:
        uc.mem_write(override_flash_base, fw_raw_bytes)
        print(f"Wrapper Debug: Wrote {len(fw_raw_bytes)} bytes to {hex(override_flash_base)} in Unicorn memory.")
        # Verify content written by reading back
        read_back_bytes = uc.mem_read(override_flash_base, min(len(fw_raw_bytes), 32))
        print(f"Wrapper Debug: Read back first 32 bytes from {hex(override_flash_base)}: {read_back_bytes.hex()}")

    except Exception as e:
        print(f"Wrapper Debug: ERROR writing firmware to Unicorn memory: {e}")
        sys.exit(1)

    # --- Determine and Set Initial SP and PC in Unicorn Registers ---
    # These values are found in the first 8 bytes of the firmware image (vector table).
    # For blinky-o1, these are already absolute addresses relative to 0x0.
    initial_sp_from_fw_header = int.from_bytes(fw_raw_bytes[0:4], 'little')
    initial_pc_from_fw_header = int.from_bytes(fw_raw_bytes[4:8], 'little')
    
    adjusted_sp = initial_sp_from_fw_header
    adjusted_pc = initial_pc_from_fw_header

    uc.reg_write(UC_ARM_REG_SP, adjusted_sp)
    uc.reg_write(UC_ARM_REG_PC, adjusted_pc)

    # --- Final Debugging Prints for Unicorn Initial State ---
    print(f"FFXE Debug (Wrapper): Flash base for FW Load: {hex(override_flash_base)}")
    print(f"FFXE Debug (Wrapper): Raw SP from FW Header: {hex(initial_sp_from_fw_header)}")
    print(f"FFXE Debug (Wrapper): Raw PC from FW Header: {hex(initial_pc_from_fw_header)}")
    print(f"FFXE Debug (Wrapper): ADJUSTED Initial SP (used in UC): {hex(adjusted_sp)}")
    print(f"FFXE Debug (Wrapper): ADJUSTED Entry Point (PC used in UC): {hex(adjusted_pc)}")
    # --- End FFXE Debugging Prints ---

    # Instantiate FXEngine, passing the already configured Unicorn instance
    # We pass path=None to prevent FXEngine from attempting to load the firmware internally again.
    # Pass known_functions as hints for future FFXE modifications.
    engine = FXEngine(
        pd=platform_description, # Pass the loaded platform description dictionary
        path=None,               # Crucial: Prevent FXEngine from calling load_fw internally
        log_stdout=args.log_stdout,
        uc_instance=uc,          # NEW: Pass our pre-configured Unicorn instance to FXEngine
        known_functions=ghidra_function_hints, # Pass Ghidra function hints
        flash_base_for_hooks=0x0
    )
    
    # Manually set engine's internal fw_image object (which load_fw normally sets)
    engine.fw = fw_image
    
    # Manually set initial context for FXEngine's internal tracking
    engine.context.pc = adjusted_pc
    engine.context.uc_context = engine.uc.context_save()
    engine.context.callstack.append((
        adjusted_pc,
        adjusted_sp,
        None
    ))
    
    # NEW: Manually set engine.stack_base (which load_fw normally sets)
    engine.stack_base = adjusted_sp 
    
    # --- Run the FFXE analysis ---
    start_time = time.time()
    engine.run() # This should now execute on our pre-configured Unicorn instance
    end_time = time.time()
    processing_time = max(0, end_time - start_time) # Ensure non-negative time
    print(f"\nFFXE Analysis completed in {processing_time:.4f} seconds.")

    # --- Extract nodes and edges in the expected tuple format for visualization scripts ---
    recovered_nodes_for_pkl = set()
    # Iterate through engine.cfg.bblocks (a dict from address to BBlock object)
    for addr, bblock_obj in engine.cfg.bblocks.items():
        recovered_nodes_for_pkl.add((bblock_obj.address, bblock_obj.size))

    recovered_edges_for_pkl = set()
    # Iterate through engine.cfg.edges (a set of tuples: (source_addr, target_addr, edge_type_str))
    # We only care about source and target addresses for visualization
    for u, v, _ in engine.cfg.edges: 
        recovered_edges_for_pkl.add((u, v))

    print(f"Recovered CFG Nodes: {len(recovered_nodes_for_pkl)}")
    print(f"Recovered CFG Edges: {len(recovered_edges_for_pkl)}")

    # Save the recovered CFG to a .pkl file
    binary_name = os.path.basename(args.binary_path)
    output_cfg_filename = f"{binary_name}-ffxe-cfg-with-hints.pkl"
    output_cfg_path = os.path.join(args.output_dir, output_cfg_filename)
    
    with open(output_cfg_path, 'wb') as f:
        pickle.dump({'nodes': recovered_nodes_for_pkl,
                     'edges': recovered_edges_for_pkl}, f)

    print(f"Recovered CFG saved to: {output_cfg_path}")


if __name__ == "__main__":
    main()

