import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import anthropic
import os
import json
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any

# --- CONFIGURATION ---
# The data is expected in a 'data' subdirectory.
# The 'data' directory itself will also be served publicly.
DATA_DIR = "./data"
CACHE_FILE = "pws_summary_cache.json"

# --- ANTHROPIC CLIENT SETUP ---
# It is highly recommended to use environment variables for API keys
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY"))

# --- GLOBAL IN-MEMORY STORAGE & LOCK ---
dataframes: Dict[str, pd.DataFrame] = {}
pws_cache: Dict[str, str] = {}
cache_lock = threading.Lock()


# --- CACHE AND DATA LOADING FUNCTIONS ---
def load_cache_from_file():
    """Loads the PWSID summary cache from the local JSON file."""
    global pws_cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            try:
                pws_cache = json.load(f)
                print(f"Loaded {len(pws_cache)} items from {CACHE_FILE}")
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from {CACHE_FILE}. Starting with empty cache.")
                pws_cache = {}


def save_cache_to_file():
    """Saves the in-memory cache to the local JSON file."""
    with open(CACHE_FILE, 'w') as f:
        json.dump(pws_cache, f, indent=4)


def load_all_data():
    """
    Loads all CSV files from the DATA_DIR into memory on startup.
    """
    global dataframes
    print(f"Loading all SDWIS data from '{DATA_DIR}' directory...")
    if not os.path.isdir(DATA_DIR):
        print(f"Error: Data directory '{DATA_DIR}' not found. Please create it and add your CSV files.")
        return

    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            file_key = os.path.splitext(filename)[0]
            file_path = os.path.join(DATA_DIR, filename)
            try:
                df = pd.read_csv(file_path, low_memory=False)
                if 'SUBMISSIONYEARQUARTER' in df.columns:
                    df['sortable_quarter'] = df['SUBMISSIONYEARQUARTER'].str.replace('Q', '').astype(int)
                dataframes[file_key] = df
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    print(f"Data loading complete. Loaded {len(dataframes)} files.")


# --- FASTAPI LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # On application startup
    print("Application startup...")
    load_all_data()
    load_cache_from_file()
    yield
    # On application shutdown
    print("Application shutdown.")


app = FastAPI(lifespan=lifespan)

# --- Mount the data directory to be served publicly ---
# A request to /data/SDWA_PUB_WATER_SYSTEMS.csv will serve that file
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")


# --- DATA PROCESSING & LLM FUNCTIONS ---
def get_data_for_pwsid(pwsid: str) -> Dict[str, Any]:
    pws_data = {}
    for name, df in dataframes.items():
        if 'PWSID' in df.columns and 'sortable_quarter' in df.columns:
            filtered_df = df[(df['PWSID'] == pwsid) & (df['sortable_quarter'] >= 20201)]
            if not filtered_df.empty:
                clean_name = name.replace("SDWA_", "").replace("_", " ").title()
                pws_data[clean_name] = filtered_df.to_dict(orient='records')
    return pws_data


def generate_summary_with_haiku(pwsid: str, data: Dict[str, Any]) -> str:
    # --- MODIFICATION START ---

    # Create a formatted string to hold multiple CSV blocks
    data_as_csv_strings = []
    for table_name, records in data.items():
        if not records:
            continue
        # Convert the list of dictionary records back to a DataFrame
        df = pd.DataFrame(records)
        # Convert DataFrame to a CSV string, excluding the pandas index
        csv_string = df.to_csv(index=False)

        # Add the table name as a header for the model to understand context
        data_as_csv_strings.append(f"--- Data from {table_name} ---\n{csv_string}")

    # Join all the individual CSV blocks into one string
    formatted_data = "\n\n".join(data_as_csv_strings)

    # --- MODIFICATION END ---

    prompt = f"""
    Based on the following data for the public water system with ID {pwsid}, please provide a 1-3 paragraph summary of its water quality history since 2020. The summary should be easily understandable by a regular citizen, written in a clear and reassuring tone unless there are significant issues.

    The data is provided in separate CSV-formatted blocks.

    Data:
    {formatted_data}
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

@app.get("/", include_in_schema=False)
async def root():
    """Serves the main index.html file from the project root."""
    if os.path.exists("index.html"):
        return FileResponse('index.html')
    raise HTTPException(status_code=404, detail="index.html not found in root directory.")


@app.get("/water_quality/{pwsid}")
async def get_water_quality_summary(pwsid: str):
    pwsid = pwsid.upper()  # Standardize PWSID
    if pwsid in pws_cache:
        return {"pwsid": pwsid, "summary": pws_cache[pwsid], "source": "cache"}

    data = get_data_for_pwsid(pwsid)
    if not data:
        raise HTTPException(status_code=404, detail=f"PWSID '{pwsid}' not found or has no data available since 2020.")

    summary = generate_summary_with_haiku(pwsid, data)

    with cache_lock:
        pws_cache[pwsid] = summary
        save_cache_to_file()
        print(f"New summary for {pwsid} generated and saved to cache.")

    return {"pwsid": pwsid, "summary": summary, "source": "generated"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "loaded_dataframes": len(dataframes), "cached_items": len(pws_cache)}

# To run this application:
# 1. Place 'main.py' and 'index.html' in your project root.
# 2. Create a 'data' folder in the root and place your CSVs inside it.
# 3. Install dependencies: pip install "fastapi[all]" pandas anthropic
# 4. Set your Anthropic API key.
# 5. Run from your terminal: uvicorn main:app --reload
