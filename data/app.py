import pandas as pd
from fastapi import FastAPI, HTTPException
from cachetools import TTLCache
import google.generativeai as genai
import os
from typing import Dict, Any

# It is recommended to use environment variables for API keys
# For example: genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()

# In-memory cache with a Time-To-Live (TTL) of 1 hour
cache = TTLCache(maxsize=100, ttl=3600)

# Assumes the CSV files are in the same directory as the script
DATA_DIR = "./"


def get_data_for_pwsid(pwsid: str) -> Dict[str, Any]:
    """
    Reads all CSV files in the specified directory, filters the data for the given PWSID
    and for records after 2020, and returns a dictionary of dataframes.
    """
    pws_data = {}
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(DATA_DIR, filename), low_memory=False)
                if 'PWSID' in df.columns and 'SUBMISSIONYEARQUARTER' in df.columns:
                    # Convert SUBMISSIONYEARQUARTER to a sortable format
                    # This handles the 'YYYYQX' format and allows for easy filtering
                    df['sortable_quarter'] = df['SUBMISSIONYEARQUARTER'].str.replace('Q', '').astype(int)

                    # Filter for the given PWSID and for data from 2020 onwards
                    filtered_df = df[
                        (df['PWSID'] == pwsid) & (df['sortable_quarter'] >= 20201)]  # 20201 represents 2020 Q1

                    if not filtered_df.empty:
                        # Convert the filtered dataframe to a dictionary for easy use in the prompt
                        pws_data[filename] = filtered_df.to_dict(orient='records')
            except Exception as e:
                # In a production environment, you would have more robust logging
                print(f"Error processing {filename}: {e}")
    return pws_data


def generate_summary_with_haiku(pwsid: str, data: Dict[str, Any]) -> str:
    """
    Generates a water quality summary using a large language model.
    """
    # The prompt is carefully constructed to guide the language model
    # to produce the desired output.
    prompt = f"""
    Based on the following data for the public water system with ID {pwsid}, please provide a 1-3 paragraph summary of its water quality history since 2020. The summary should be easily understandable by a regular citizen.

    Data:
    {data}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Proper error handling is crucial for a robust application
        raise HTTPException(status_code=500, detail=f"Error generating summary: {e}")


@app.get("/water_quality/{pwsid}")
async def get_water_quality_summary(pwsid: str):
    """
    This endpoint takes a Public Water System ID (PWSID) and returns a
    summary of its water quality history.
    """
    # Check the cache first to see if we have a recent summary
    if pwsid in cache:
        return {"pwsid": pwsid, "summary": cache[pwsid]}

    # If not in cache, process the data
    data = get_data_for_pwsid(pwsid)
    if not data:
        raise HTTPException(status_code=404, detail="PWSID not found or no data available after 2020.")

    # Generate a new summary
    summary = generate_summary_with_haiku(pwsid, data)

    # Store the new summary in the cache
    cache[pwsid] = summary

    return {"pwsid": pwsid, "summary": summary}


@app.get("/health")
async def health_check():
    """
    A simple health check endpoint to confirm the service is running.
    """
    return {"status": "ok"}

# To run this application, save the code as a Python file (e.g., `main.py`)
# and use an ASGI server like Uvicorn from your terminal:
# uvicorn main:app --reload
# You would also need to ensure the CSV files are in the same directory.
# Remember to replace "YOUR_API_KEY" with a valid Google AI API key.