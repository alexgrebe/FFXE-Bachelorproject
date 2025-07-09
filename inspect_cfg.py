# inspect_cfg.py - Final check for function information

import pickle
import os

# --- Configuration ---
PKL_FILE_PATH = 'tests/cfgs/unit-tests/blinky-o1-ffxe-cfg.pkl' # <--- CONFIRM THIS IS THE CORRECT PATH YOU USED

# --- Load the pickled CFG data ---
print(f"Attempting to load: {PKL_FILE_PATH}")

if not os.path.exists(PKL_FILE_PATH):
    print(f"Error: The file '{PKL_FILE_PATH}' does not exist.")
    print("Please ensure the path is correct and the FFXE analysis generated the .pkl file.")
else:
    try:
        with open(PKL_FILE_PATH, 'rb') as f:
            recovered_cfg_data = pickle.load(f)

        print("\n--- Successfully loaded the .pkl file! ---")
        print(f"Type of the loaded object: {type(recovered_cfg_data)}")

        # --- Re-inspect ALL dictionary keys ---
        if isinstance(recovered_cfg_data, dict):
            print("\n--- ALL Keys found in the loaded dictionary ---")
            all_keys = list(recovered_cfg_data.keys())
            for key in all_keys:
                print(f"- '{key}'")
                # Try to print type and a sample of the value for each key
                value = recovered_cfg_data[key]
                print(f"  Type: {type(value)}")
                if isinstance(value, (list, set, dict)) and len(value) > 0:
                    print(f"  Length/Size: {len(value)}")
                    if isinstance(value, (list, set)):
                        # For list/set, get the first element for sampling
                        sample_element = next(iter(value))
                        print(f"  Sample first element: {sample_element}")
                        if isinstance(sample_element, dict):
                            print(f"  Sample element keys: {list(sample_element.keys())}")
                        elif hasattr(sample_element, '__dict__'):
                            print(f"  Sample element attributes: {list(sample_element.__dict__.keys())}")
                    elif isinstance(value, dict):
                        # For dict, get first key-value pair
                        first_k = next(iter(value))
                        print(f"  Sample first key-value: {first_k}: {value[first_k]}")
                elif isinstance(value, (int, float, str, bool)):
                    print(f"  Value: {value}")
                else:
                    print(f"  (Complex object, inspect further if relevant)")

        print("\n--- End of inspection ---")

    except Exception as e:
        print(f"An error occurred while loading or inspecting the .pkl file: {e}")
        print("This might happen if the .pkl file was created with a different Python version or library.")