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
                    # Ensure quarter column is numeric for sorting
                    df['sortable_quarter'] = pd.to_numeric(df['SUBMISSIONYEARQUARTER'].str.replace('Q', ''),
                                                           errors='coerce')
                    df.dropna(subset=['sortable_quarter'], inplace=True)  # Drop rows where conversion failed
                    df['sortable_quarter'] = df['sortable_quarter'].astype(int)
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
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")


# --- DATA PROCESSING & LLM FUNCTIONS ---

def get_data_for_pwsid(pwsid: str) -> Dict[str, Any]:
    """
    Filters data for a given PWSID, applying separate sampling rules for
    pre-2020 and post-2020 records before combining them.
    """
    pws_data = {}
    for name, df in dataframes.items():
        if 'PWSID' in df.columns and 'sortable_quarter' in df.columns:
            # Filter all data for the specific PWSID first
            df_pws = df[df['PWSID'] == pwsid]

            if df_pws.empty:
                continue

            # Split data into pre-2020 and post-2020 periods
            pre_2020_df = df_pws[df_pws['sortable_quarter'] < 20201]
            post_2020_df = df_pws[df_pws['sortable_quarter'] >= 20201]

            # Sample pre-2020 data if it exceeds the max limit
            if len(pre_2020_df) > 50:
                pre_2020_df = pre_2020_df.sample(n=50, random_state=42)  # random_state for reproducible samples

            # Sample post-2020 data if it exceeds the max limit
            if len(post_2020_df) > 300:
                post_2020_df = post_2020_df.sample(n=300, random_state=42)

            # Combine the sampled dataframes
            combined_df = pd.concat([pre_2020_df, post_2020_df])

            # Sort the final combined dataframe to preserve chronological order
            if not combined_df.empty:
                combined_df = combined_df.sort_values('sortable_quarter', ascending=True)
                clean_name = name.replace("SDWA_", "").replace("_", " ").title()
                pws_data[clean_name] = combined_df.to_dict(orient='records')

    return pws_data


def generate_summary_with_haiku(pwsid: str, data: Dict[str, Any]) -> str:
    """
    Generates a summary using a detailed prompt that instructs the model
    to avoid preambles and understand the data sampling.
    """
    prompt = f"""
    You are a helpful assistant specializing in water quality reports. Your task is to provide a clear, concise summary for a citizen regarding the water quality history for the public water system with ID {pwsid}.

    Here are the rules you must follow:
    - Write in a clear and reassuring tone. If there are significant issues (like multiple violations), mention them calmly and factually.
    - The summary should be 1-3 paragraphs long.
    - **Do not use a preamble or any introductory phrases.** Begin the summary directly. For example, instead of saying "Based on the data provided...", start with something like "The water quality for this system has been generally satisfactory..." or "Records for this water system show a few violations over the past several years...".
    - The data provided contains a sample of up to 100 records from before 2020 and up to 500 recent records from 2020 onwards. Your summary should synthesize findings from both periods if data is available for both.

    Use the following data to generate your summary:
    {str(data)}
    """
    print(f"{len(prompt)=}")
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
        raise HTTPException(status_code=404, detail=f"PWSID '{pwsid}' not found or has no data available.")

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
# 4. Set your Anthropic API key as an environment variable (ANTHROPIC_API_KEY).
# 5. Run from your terminal: uvicorn main:app --reload