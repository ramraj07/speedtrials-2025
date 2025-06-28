import pandas as pd
from fastapi import FastAPI, HTTPException
import anthropic
import os
import json
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any

# --- CONFIGURATION ---
DATA_DIR = "./data"
CACHE_FILE = "pws_summary_cache.json"

# --- ANTHROPIC CLIENT SETUP ---
# It is highly recommended to use environment variables for API keys
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY"))

# --- GLOBAL IN-MEMORY STORAGE ---
# These will be populated on application startup
dataframes: Dict[str, pd.DataFrame] = {}
pws_cache: Dict[str, str] = {}
cache_lock = threading.Lock()

# --- CACHE AND DATA LOADING FUNCTIONS ---
def load_cache_from_file():
    """Loads the PWSID summary cache from the local JSON file into memory."""
    global pws_cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            try:
                pws_cache = json.load(f)
                print(f"Loaded {len(pws_cache)} items from {CACHE_FILE}")
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from {CACHE_FILE}. Starting with an empty cache.")
                pws_cache = {}

def save_cache_to_file():
    """Saves the in-memory cache to the local JSON file."""
    with open(CACHE_FILE, 'w') as f:
        # Use indent for a human-readable file that's friendly for version control
        json.dump(pws_cache, f, indent=4)

def load_all_data():
    """
    Loads all CSV files from the DATA_DIR into a dictionary of pandas DataFrames.
    This function is called once on application startup.
    """
    global dataframes
    print("Loading all SDWIS data into memory...")
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            file_key = os.path.splitext(filename)[0]
            try:
                df = pd.read_csv(os.path.join(DATA_DIR, filename), low_memory=False)
                # Pre-process the sortable quarter column to optimize filtering later
                if 'SUBMISSIONYEARQUARTER' in df.columns:
                    df['sortable_quarter'] = df['SUBMISSIONYEARQUARTER'].str.replace('Q', '').astype(int)
                dataframes[file_key] = df
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    print(f"Data loading complete. Loaded {len(dataframes)} files.")


# --- FASTAPI LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on application startup
    print("Application startup...")
    load_all_data()
    load_cache_from_file()
    yield
    # Code to run on application shutdown (optional)
    print("Application shutdown.")


app = FastAPI(lifespan=lifespan)


# --- DATA PROCESSING & LLM FUNCTIONS (MODIFIED) ---

def get_data_for_pwsid(pwsid: str) -> Dict[str, Any]:
    """
    Filters the pre-loaded DataFrames for a given PWSID.
    """
    pws_data = {}
    for name, df in dataframes.items():
        if 'PWSID' in df.columns and 'sortable_quarter' in df.columns:
            # Filter the already-loaded dataframe
            filtered_df = df[(df['PWSID'] == pwsid) & (df['sortable_quarter'] >= 20201)]
            if not filtered_df.empty:
                pws_data[name] = filtered_df.to_dict(orient='records')
    return pws_data

def generate_summary_with_haiku(pwsid: str, data: Dict[str, Any]) -> str:
    """
    Generates a water quality summary using Anthropic's Claude 3 Haiku model.
    (This function's core logic remains unchanged)
    """
    prompt = f"""
    Based on the following data for the public water system with ID {pwsid}, please provide a 1-3 paragraph summary of its water quality history since 2020. The summary should be easily understandable by a regular citizen.

    Data:
    {str(data)}
    """
    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary with Anthropic API: {e}")


# --- API ENDPOINTS ---

@app.get("/water_quality/{pwsid}")
async def get_water_quality_summary(pwsid: str):
    """
    This endpoint takes a Public Water System ID (PWSID) and returns a
    summary of its water quality history using a persistent file cache.
    """
    # 1. Check the in-memory cache first
    if pwsid in pws_cache:
        return {"pwsid": pwsid, "summary": pws_cache[pwsid], "source": "cache"}

    # 2. If not cached, get data from the pre-loaded dataframes
    data = get_data_for_pwsid(pwsid)
    if not data:
        raise HTTPException(status_code=404, detail="PWSID not found or no data available after 2020.")

    # 3. Generate a new summary
    summary = generate_summary_with_haiku(pwsid, data)

    # 4. Update the cache (in-memory and file) in a thread-safe way
    with cache_lock:
        pws_cache[pwsid] = summary
        save_cache_to_file()
        print(f"New summary for {pwsid} generated and saved to cache.")

    return {"pwsid": pwsid, "summary": summary, "source": "generated"}

@app.get("/health")
async def health_check():
    """A simple health check endpoint to confirm the service is running."""
    return {"status": "ok", "loaded_dataframes": list(dataframes.keys()), "cached_items": len(pws_cache)}

# To run this application:
# 1. Install necessary libraries: pip install "fastapi[all]" pandas anthropic
# 2. Save the code as a Python file (e.g., `main.py`).
# 3. Place the CSV data files in the same directory.
# 4. Set your Anthropic API key.
# 5. Run from your terminal: uvicorn main:app --reload