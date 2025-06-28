import pandas as pd
import os


def filter_sdwis_for_georgia():
    """
    Reads national SDWIS CSV files from an 'input_national' directory,
    filters the data to include only records for the state of Georgia,
    and saves the filtered files to an 'output_georgia' directory.
    """
    # --- Configuration ---
    # Place your national CSV files in this directory
    input_dir = "input_national"
    # The filtered Georgia CSV files will be saved here
    output_dir = "data"
    state_code = 'GA'

    # --- Setup ---
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # List of all files to be processed
    filenames = [
        "SDWA_PUB_WATER_SYSTEMS.csv",
        "SDWA_VIOLATIONS_ENFORCEMENT.csv",
        "SDWA_LCR_SAMPLES.csv",
        "SDWA_SITE_VISITS.csv",
        "SDWA_FACILITIES.csv",
        "SDWA_GEOGRAPHIC_AREAS.csv",
        "SDWA_REF_CODE_VALUES.csv",
        "SDWA_EVENTS_MILESTONES.csv",
        "SDWA_PN_VIOLATION_ASSOC.csv",
        "SDWA_REF_ANSI_AREAS.csv",
        "SDWA_SERVICE_AREAS.csv"
    ]

    print(f"Starting the filtering process for state: {state_code}")

    # --- Processing Loop ---
    for filename in filenames:
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        try:
            print(f"\nProcessing '{filename}'...")
            # Read the full national CSV file
            # Using low_memory=False to prevent DtypeWarning for mixed types
            df = pd.read_csv(input_path, low_memory=False)

            # --- Filtering Logic ---
            if 'PWSID' in df.columns:
                # The primary filter: PWSID starts with the state code (e.g., 'GA')
                # Using .str.startswith and na=False to handle potential non-string data
                original_rows = len(df)
                df_filtered = df[df['PWSID'].astype(str).str.startswith(state_code, na=False)].copy()
                filtered_rows = len(df_filtered)

                print(f"Filtered by 'PWSID'. Kept {filtered_rows} of {original_rows} rows.")

            elif filename == "SDWA_REF_ANSI_AREAS.csv":
                # Special case for ANSI reference file, filter by 'STATE_CODE'
                original_rows = len(df)
                df_filtered = df[df['STATE_CODE'] == state_code].copy()
                filtered_rows = len(df_filtered)

                print(f"Filtered by 'STATE_CODE'. Kept {filtered_rows} of {original_rows} rows.")

            elif filename == "SDWA_REF_CODE_VALUES.csv":
                # This is a national reference file, no state filter needed.
                # We just copy it over as is.
                df_filtered = df.copy()
                print("Copied as-is (national reference file).")

            else:
                # If a file has no obvious state-related column, copy it as is.
                df_filtered = df.copy()
                print(f"Warning: No 'PWSID' or special filter for this file. Copied as-is.")

            # --- Save Filtered Data ---
            # Save the filtered DataFrame to the output directory
            df_filtered.to_csv(output_path, index=False)
            print(f"Successfully saved filtered file to '{output_path}'")

        except FileNotFoundError:
            print(f"Error: Could not find '{input_path}'. Please make sure it exists.")
        except Exception as e:
            print(f"An error occurred while processing '{filename}': {e}")

    print("\n--- Filtering process complete! ---")
    print(f"Your Georgia-specific files are located in the '{output_dir}' directory.")


# --- Run the Script ---
if __name__ == "__main__":
    # Instructions:
    # 1. Create a folder named 'input_national' in the same directory as this script.
    # 2. Place all your national SDWIS CSV files inside the 'input_national' folder.
    # 3. Run this script.
    # 4. The filtered files for Georgia will appear in a new 'output_georgia' folder.
    filter_sdwis_for_georgia()
