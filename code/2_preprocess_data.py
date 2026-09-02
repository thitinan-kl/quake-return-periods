import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
# crate a function to process the data
#  - Load the dataset
#  - Convert time to datetime and extract date
#  - Extract country from place column
#  - Sort by time
#  - Convert latitude/longitude to Cartesian coordinates


# Full state names and their abbreviations
us_states = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"
}

other_us = {"Alaska Earthquake", "Alaska Peninsula", "Alaska region", "Wyoming", 
            "West Virginia", "California Earthquake", "California Earthquakes (First Major Event)", 
            "California Earthquakes (First Event)", "California-Baja California", "California-Nevada border region",
            "Central Alaska", "Central California", "Central Minnesota", "Colorado",
            "Gulf of Alaska", "Gulf of California", "Lake Almanor Earthquake",
            "Louisiana Earthquake", "Montana Earthquake", "near the coast of Northern California", "Nevada Earthquake",
            "New Jersey Earthquake", "Northcentral Nevada", "Northern California", "northern Alaska",
            "NV Earthquake", "Off the coast of Northern California",
            "off the coast of Central America", "off the coast of Washington", "off the coast of Southeastern Alaska",
            "off the east coast of the United States", "Ridgecrest Earthquake Sequence", "Southern Alaska", 
            "Southwestern Alaska", "Texas Earthquake", "Utah Earthquake", "Washington", "Western Nevada", 
            "western Texas"}
mexico = {"MX", "northern East Pacific Rise", "Revilla Gigedo Islands region"}

#Megaquakes events are below
indo = {"1914 Biak Earthquake", "1938 Banda Sea Earthquake", "1939 Sulawesi Earthquake", 
        "1963 Banda Sea Earthquake", "1965 Ceram Sea Earthquake", "2004 Sumatra - Andaman Islands Earthquake",
        "2012 Wharton Basin Earthquake", "Banda Sea", "Bali Sea", "Flores Sea", "Java Sea", "Molucca Sea",
        "off the west coast of northern Sumatra", "Savu Sea", "The 1907 Sumatra Earthquake and Tsunami"}
russia = {"1918 Kuril Islands Earthquake", "1958 Kuril Islands Earthquake", "1963 Kuril Islands Earthquake",
          "2006 Kuril Islands Earthquake", "2007 Kuril Islands Earthquake", "2013 Sea of Okhotsk Earthquake",
          "east of the Kuril Islands", "Kuril Islands", "Laptev Sea", "north of Franz Josef Land", 
          "north of Severnaya Zemlya", "northwest of the Kuril Islands", "Sea of Okhotsk"}
india = {"1934 Bihar-Nepal Earthquake", "1950 Assam-Tibet Earthquake"}
japan = {"1941 Hyuganada Earthquake", "1944 Toankai Earthquake", "1952 Tokachi-Oki Earthquake",
         "1968 Tokachi-Oki Earthquake", "1969 Hokkaido Toho-oki Earthquake", "2003 Tokachi-Oki Earthquake",
         "East of the Izu Islands"}
iran = {"1945 Makran Subduction Zone Earthquake", "central Iran", "Strait of Hormuz"}
canada = {"1949 Haida Gwaii Earthquake", "west of Vancouver Island"}
chile = {"1960 Great Chilean Earthquake (Valdivia Earthquake)", "Easter Island region", 
         "Juan Fernandez Islands region", "southeast of Easter Island"}
papua = {"1971 Bougainville Earthquake", "Bismarck Sea", "D'Entrecasteaux Islands region"}
aus = {"2004 Tasman Sea Earthquake", "Macquarie Island region", "north of Macquarie Island", "south of Tasmania",
       "west of Macquarie Island"}
argentina = {"2025 Southern Drake Passage Earthquake", "Drake Passage"}
timor = {"East Timor region", "Timor region", "Timor Sea"}
china = {"Eastern Xizang", "eastern Xizang-India border region", "western Xizang", 
         "western Xizang-India border region", "Xinjiang-Xizang border region", "Xizang-Qinghai border region",
         "Xizang-Yunnan border region", "Xizang-Nepal border region"}
newz = {"Kermadec Islands region", "south of the Kermadec Islands"}
phil = {"Philippine Islands region", "Philippine Sea"}
indianocean = {"1942 Southwest Indian Ridge Earthquake", "Indian Ocean Triple Junction", "Mid-Indian Ridge",
               "South Indian Ocean", "southeast Indian Ridge", "Southwest Indian Ridge", 
               "western Indian-Antarctic Ridge"}

# Extract country from place column
def extract_country(place):
    if pd.isna(place):
        return "Unknown"
    if ',' in place:
        acountry = place.split(',')[-1].strip()
        if 'region' in acountry:
            country = acountry.split('region')[0].strip()
        else:
            country = acountry
        # Check if it's a US state (full name or abbreviation)
        if country in us_states.values() or country in us_states.keys() or country in other_us:
            return "USA"
        elif country in mexico:
            return "Mexico"
        return country
    elif place in other_us: #places without comma
        return "USA"
    elif place in mexico: #places without comma
        return "Mexico"
    elif place in indo: #places without comma
        return "Indonesia"
    elif place in russia: #places without comma
        return "Russia"
    elif place in india: #places without comma
        return "India"
    elif place in japan: #places without comma
        return "Japan"
    elif place in iran: #places without comma
        return "Iran"
    elif place in canada: #places without comma
        return "Canada"
    elif place in chile: #places without comma
        return "Chile"
    elif place in papua: #places without comma
        return "Papua New Guinea"
    elif place in aus: #places without comma
        return "Australia"
    elif place in argentina: #places without comma
        return "Argentina"
    elif place in timor: #places without comma
        return "Timor Leste"
    elif place in china: #places without comma
        return "China"
    elif place in newz: #places without comma
        return "New Zealand"
    elif place in phil: #places without comma
        return "Philippines"
    elif place in indianocean: #places without comma
        return "In Southern Ocean"
    return place.strip()



def convert_magnitude(data):
    for index, row in data.iterrows():
        mag_type = str(row['magType']).lower()
        if mag_type in ("ms", "ms_20"):
            data.loc[index, 'magType'] = 'mw'
            if 3.0 <= row['mag'] < 6.2:
                data.loc[index, 'mag'] = round((row['mag'] * 0.67) + 2.7, 2)
            elif 6.2 <= row['mag'] <= 8.2:
                data.loc[index, 'mag'] = round((row['mag'] * 0.99) + 0.08, 2)
        elif mag_type in ("mb", "mB", "MB"):
            data.loc[index, 'magType'] = 'mw'
            if 3.5 <= row['mag'] <= 5.5:
                data.loc[index, 'mag'] = round((row['mag'] * 0.85) + 1.03, 2)
            elif 5.5 < row['mag'] <= 7.3:
                data.loc[index, 'mag'] = round((row['mag'] * 1.46) - 2.42, 2)               
        elif "ml" in mag_type:
            data.loc[index, 'magType'] = 'mw'
            if 4.0 <= row['mag'] <= 8.3:
                data.loc[index, 'mag'] = round((row['mag'] * 0.75) + 1.16, 2)
        elif "md" in mag_type:
            data.loc[index, 'magType'] = 'mw'
            data.loc[index, 'mag'] = round((row['mag']*row['mag']*0.03) + (row['mag']*0.65) + 0.69, 2)
    return data


# Load dataset and process
def process_data(file_path):
    print(f"Loading dataset from {file_path}...")
    
    # Load dataset
    data = pd.read_csv(file_path)
    print(f"Loaded {len(data)} rows of earthquake data.")

    # Convert time to datetime and extract date
    print("Processing time data...")
    data['time'] = pd.to_datetime(data['time'], errors='coerce')
    data = data.dropna(subset=['time'])
    data['Date'] = data['time'].dt.date
    data['Date'] = pd.to_datetime(data['Date'])
    data['Day_Number'] = (data['Date'] - data['Date'].min()).dt.days + 1
    print("Time processing completed.")

    # Extract country from place column
    print("Extracting country information...")
    data['country'] = data['place'].apply(extract_country)
    print("Country extraction completed.")

    # Sort by time
    print("Sorting data by time...")
    data = data.sort_values(by='time').reset_index(drop=True)
    data = convert_magnitude(data)
    # Save the updated DataFrame
    output_file = 'Dataset/Preprocessed_earthquake_data.csv'
    data.to_csv(output_file, index=False)
    print(f"Processed data saved to: {output_file}")

    return data

# Run the processing
processed_data = process_data('Dataset/earthquake_global_data_combined.csv')


# Print sample data to verify
print("Sample processed data:")
print(processed_data[['latitude', 'longitude', 'country']].head())
