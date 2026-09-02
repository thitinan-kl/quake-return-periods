import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import os
from time import time


def recount_day_number(data):
    data['time'] = pd.to_datetime(data['time'], format='mixed')
    data['Day_Number'] = 0
    for cluster_id in data['cluster'].unique():
        if cluster_id == -1:
            continue
        cluster_mask = data['cluster'] == cluster_id
        cluster_data = data[cluster_mask].copy().sort_values('time')
        oldest_date = cluster_data['time'].min().date()
        day_numbers = [(d.date() - oldest_date).days for d in cluster_data['time']]
        data.loc[cluster_mask, 'Day_Number'] = day_numbers
    data = data.sort_values(['cluster', 'time']).reset_index(drop=True)
    return data

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Computes the great-circle distance between two points on a sphere in kilometers.
    """
    R = 6371.0  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

def remove_aftershocks(data, aftershock_days=180):
    #filtered_data = []
    
    # 1. Initialize and clean the dataset
    cluster_data = data.copy().reset_index(drop=True)
    cluster_data = cluster_data.sort_values('Day_Number').reset_index(drop=True)

    print(f"Total records in dataset: {len(cluster_data)}")
    print(f"Last records: {cluster_data['Date'].tail(1)}")
    print(f"Recent mag: {cluster_data['mag'].tail(1)}")
    
    if len(cluster_data) == 0:
        return pd.DataFrame(columns=list(data.columns))
    
    cluster_data['Day_Number'] = pd.to_numeric(cluster_data['Day_Number'], errors='coerce').fillna(0).astype(int)
    max_day = cluster_data['Day_Number'].max()
    
    cluster_filtered = []
    current_interval_start = 0
    
    # 2. First-pass: Group events into sliding time windows
    while True:
        interval_end = current_interval_start + aftershock_days - 1
        interval_data = cluster_data[(cluster_data['Day_Number'] >= current_interval_start) &
                                     (cluster_data['Day_Number'] <= interval_end)]
        
        if len(interval_data) > 0:
            # FIX: Sort by magnitude descending to evaluate largest events first
            sorted_interval = interval_data.sort_values('mag', ascending=False)
            
            interval_maxima = []
            for _, row in sorted_interval.iterrows():
                is_aftershock = False
                
                for existing_max in interval_maxima:
                    # Calculate Gardner-Knopoff dynamic distance for the larger event
                    # 10**(0.1238 * M + 0.983)
                    dynamic_dist_limit = 10**(0.1238 * existing_max['mag'] + 0.983)
                    
                    dist = haversine_distance(
                        row['latitude'], row['longitude'],
                        existing_max['latitude'], existing_max['longitude']
                    )
                    
                    # Check against the dynamic threshold of that specific mainshock
                    if dist <= dynamic_dist_limit:
                        is_aftershock = True
                        break  
                    
                # If it's > 40km away from all larger events, it gets its own max record
                if not is_aftershock:
                    max_mag_record = row.to_dict()
                    max_mag_record['interval'] = interval_end
                    interval_maxima.append(max_mag_record)

            # Add all independent local maximums found in this window
            cluster_filtered.extend(interval_maxima)
        
        current_interval_start = interval_end + 1
        if current_interval_start > max_day:
            break
        
    if not cluster_filtered:
        return pd.DataFrame(columns=list(data.columns))
        
    smooth_data = pd.DataFrame(cluster_filtered).reset_index(drop=True)
    smooth_data['filter'] = 'keep'   
    smooth_data['Day_Number'] = pd.to_numeric(smooth_data['Day_Number'], errors='coerce').fillna(0).astype(int)
    
    print("="*30)
    print("Removing data using spatio-temporal constraints")
    print("="*30)

    # 3. Second-pass: Sequential spatio-temporal cross-verification
    for index in range(1, len(smooth_data)):
        # Calculate distance between sequential candidates
        dist_km = haversine_distance(
            smooth_data.loc[index - 1, 'latitude'], smooth_data.loc[index - 1, 'longitude'],
            smooth_data.loc[index, 'latitude'], smooth_data.loc[index, 'longitude']
        )
        
        # Determine the dynamic limit based on the maximum magnitude of the pair
        max_pair_mag = max(smooth_data.loc[index - 1, 'mag'], smooth_data.loc[index, 'mag'])
        dynamic_dist_limit = 10**(0.1238 * max_pair_mag + 0.983)
        
        # DYNAMIC SPATIAL CONTROL: Check against the calculated Gardner-Knopoff radius
        if dist_km > dynamic_dist_limit:
            continue  # Farther than the dynamic threshold: independent mainshocks
        
        # TEMPORAL & MAGNITUDE CONTROL (Runs only if they are within 40 km)
        if smooth_data.loc[index - 1, 'filter'] == 'keep':
            day_diff = smooth_data.loc[index, 'Day_Number'] - smooth_data.loc[index - 1, 'Day_Number']
            if day_diff <= aftershock_days:
                if smooth_data.loc[index, 'mag'] <= smooth_data.loc[index - 1, 'mag']:
                    smooth_data.loc[index, 'filter'] = 'remove'
                else:
                    smooth_data.loc[index - 1, 'filter'] = 'remove'


    # 4. Finalize catalog
    smooth_data = smooth_data[smooth_data['filter'] != 'remove'].reset_index(drop=True)
    smooth_data = smooth_data.drop(columns=['filter', 'interval'], errors='ignore')
    return smooth_data


########## Main routine ################
# Ensure output folder exists
os.makedirs("Dataset/clustering", exist_ok=True)

# Load earthquake dataset
print("Loading earthquake data...")
df = pd.read_csv("Dataset/Preprocessed_earthquake_data.csv")

# Load the list of countries from a text file
with open('countries.txt', 'r') as file:
    countries = [line.strip() for line in file if line.strip()]

print(f"Total countries to process: {len(countries)}")
print(f"Total earthquake records: {len(df)}")

# DBSCAN parameters (defined once)
EARTH_RADIUS_KM = 6371  # Earth's radius in kilometers

eps_km = 30  # Distance in kilometers
eps_rad = eps_km / EARTH_RADIUS_KM  # Convert to radians for haversine
min_samples = 4

# Process each country
for idx, selected_country in enumerate(countries, 1):
    start_time = time()
    print(f"\n[{idx}/{len(countries)}] Processing: {selected_country}")
    
    # Filter earthquakes for this country (case-insensitive)
    raw_df = df[df['country'].str.contains(selected_country, case=False, na=False)].copy()
    
    #remove aftershocks
    AFTERSHOCK_DAYS = 180
    raw_df['cluster'] = 0 # Initialize a cluster no. columnn with 0
    smooth_data0 = recount_day_number(raw_df)
    smooth_data1 = remove_aftershocks(smooth_data0, AFTERSHOCK_DAYS)
    country_df = recount_day_number(smooth_data1)
    
    if country_df.empty:
        print(f"  ⚠️  No data found for {selected_country}")
        continue
    
    # Skip if too few records
    if len(country_df) < min_samples:
        print(f"  ⚠️  Only {len(country_df)} records - too few for clustering")
        continue
    
    # Prepare coordinates and convert to radians
    coords_rad = np.radians(country_df[['latitude', 'longitude']].to_numpy())
    
    # Run DBSCAN clustering
    db = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        metric='haversine',
        algorithm='ball_tree',  # Changed from 'brute' - much faster!
        n_jobs=-1  # Use all CPU cores
    ).fit(coords_rad)
    
    # Assign clusters
    country_df['cluster'] = db.labels_
    
    # Count valid clusters (exclude noise = -1)
    valid_clusters = country_df[country_df['cluster'] != -1]
    
    if valid_clusters.empty:
        print(f"  ⚠️  No valid clusters found (all noise)")
        continue
    
    # Find the top 3 clusters by size
    cluster_counts = valid_clusters['cluster'].value_counts()
    top_clusters = cluster_counts.head(3).index.tolist()
    
    # Count top 3 cluster size before relabeling
    top3_size = len(valid_clusters[valid_clusters['cluster'].isin(top_clusters)])
    
    # Relabel: top 3 clusters become 1, 2, 3 (biggest -> smallest), all others become -1
    cluster_mapping = {old: new for new, old in enumerate(top_clusters, start=1)}
    country_df['cluster'] = country_df['cluster'].apply(
        lambda x: cluster_mapping.get(x, -1)
    )
    
    # Save results (all records)
    output_filename = f"Dataset/clustering/clustered_earthquakes_{selected_country}.csv"
    country_df.to_csv(output_filename, index=False)
    
    elapsed = time() - start_time
    print(f"  ✓ Completed in {elapsed:.2f}s")
    print(f"  Records: {len(country_df)} | Valid clusters: {len(top_clusters)} | Top 3 size: {top3_size}")

print("\n🎉 All countries processed!")