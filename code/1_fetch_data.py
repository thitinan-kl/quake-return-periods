import requests
import csv
from io import StringIO
from datetime import datetime
import time
import os
import random

# API base URL
api_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Initialize a list to hold all rows of earthquake data
all_data = []

# Request data year by year
start_year = 1900
end_year = datetime.now().year

# Retry configuration
max_retries = 3
retry_delay = 5  # seconds

def fetch_year_data(year, retries=max_retries):
    """Fetch earthquake data for a specific year with retry logic."""
    params = {
        "format": "csv",          # Request CSV format
        "starttime": f"{year}-01-01",  # Start of the year
        "endtime": f"{year}-12-31",   #  End of the year
        "minmagnitude": 4.0,          # Minimum magnitude
        "orderby": "time"             # Order by time
    }
    
    for attempt in range(retries):
        try:
            # Make the GET request with timeout
            response = requests.get(api_url, params=params, timeout=30)
            
            # Check if the request was successful
            if response.status_code == 200:
                print(f"Data fetched for year {year}")
                return response.text
            else:
                print(f"Error fetching data for year {year}. HTTP Status Code: {response.status_code}")
                if attempt < retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    return None
                    
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error for year {year} (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to fetch data for year {year} after {retries} attempts.")
                return None
                
        except requests.exceptions.Timeout as e:
            print(f"Timeout error for year {year} (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to fetch data for year {year} after {retries} attempts.")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request error for year {year}: {str(e)}")
            return None
    
    return None

# Iterate through each year
for year in range(start_year, end_year + 1):
    csv_text = fetch_year_data(year)
    
    if csv_text:
        # Parse the CSV response and add rows to the all_data list
        csv_data = StringIO(csv_text)
        reader = csv.reader(csv_data)
        
        # Add header only once (first year)
        if year == start_year:
            header = next(reader)  # Extract and save the header
            all_data.append(header)
        else:
            next(reader)  # Skip the header for subsequent years
        
        # Append the data rows
        all_data.extend(reader)
    
    # Add a small delay between requests to be respectful to the API
    #time.sleep(0.5)
    time.sleep(random.uniform(1.0, 2.0))

# Save all data to a single CSV file
output_folder = "Dataset"
os.makedirs(output_folder, exist_ok=True)  # Create folder if it doesn't exist
output_file = os.path.join(output_folder, "earthquake_global_data_combined.csv")
with open(output_file, "w", encoding="utf-8", newline="") as file:
    writer = csv.writer(file)
    writer.writerows(all_data)

print(f"Global earthquake data saved to '{output_file}'")
