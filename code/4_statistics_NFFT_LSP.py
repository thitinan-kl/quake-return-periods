import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
#from sklearn.cluster import DBSCAN
from datetime import timedelta #, datetime
#nofrom shapely.geometry import Point
import os
from nfft import nfft
from scipy.signal import find_peaks
from astropy.timeseries import LombScargle

# =============================================================================
# Functions
# =============================================================================

def recount_day_number(data):
    data['time'] = pd.to_datetime(data['time'], format='mixed', errors='coerce')
    
    # Drop rows with NaT (invalid dates)
    nat_count = data['time'].isna().sum()
    if nat_count > 0:
        print(f"  Dropping {nat_count} rows with invalid/missing dates")
        data = data.dropna(subset=['time']).copy()
    
    data['Day_Number'] = 0
    for cluster_id in data['cluster'].unique():
        if cluster_id == -1:
            continue
        cluster_mask = data['cluster'] == cluster_id
        cluster_data = data[cluster_mask].copy()
        cluster_data = cluster_data.sort_values('time')
        
        if len(cluster_data) == 0:
            continue
            
        oldest_date = cluster_data['time'].min()
        if pd.isna(oldest_date):
            continue
        oldest_date = oldest_date.date()
        
        # Use index from sorted cluster_data to assign correctly
        for idx in cluster_data.index:
            current_time = data.loc[idx, 'time']
            if pd.isna(current_time):
                continue
            current_date = current_time.date()
            day_diff = (current_date - oldest_date).days
            data.loc[idx, 'Day_Number'] = day_diff
            
    data = data.sort_values(['cluster', 'time']).reset_index(drop=True)
    #print("Day_Number column recounted successfully after smoothing!")
    #print(f"Updated {len(data)} records across {len(data['cluster'].unique())} clusters")
    #print(data[['time', 'cluster', 'Day_Number', 'mag']].head(10))
    return data


def remove_aftershocks(data, aftershock_days=180):
    filtered_data = []
    
    for cluster_id, cluster_data in data.groupby('cluster'):
        cluster_data = cluster_data.copy().reset_index(drop=True)
        cluster_data = cluster_data.sort_values('Day_Number').reset_index(drop=True)
        
        #print(f"\n--- Cluster {cluster_id} ---")
        #print(f"Total records in cluster: {len(cluster_data)}")
        
        if len(cluster_data) == 0:
            continue
            
        # Ensure Day_Number is numeric
        cluster_data['Day_Number'] = pd.to_numeric(cluster_data['Day_Number'], errors='coerce').fillna(0).astype(int)
        max_day = cluster_data['Day_Number'].max()
        
        interval_count = 0
        cluster_filtered = []
        current_interval_start = 0
        
        while True:
            interval_end = current_interval_start + aftershock_days - 1
            interval_data = cluster_data[(cluster_data['Day_Number'] >= current_interval_start) &
                                         (cluster_data['Day_Number'] <= interval_end)]
            
            if len(interval_data) > 0:
                # idxmax returns an index label; use .loc to get the row as Series
                max_mag_idx = interval_data['mag'].idxmax()
                # Convert to dict to avoid duplicate index issues when creating DataFrame
                max_mag_record = interval_data.loc[max_mag_idx].to_dict()
                max_mag_record['interval'] = interval_end
                #print(f"  Interval {interval_count}: Days {current_interval_start} - {interval_end}")
                #print(f"    Records in interval: {len(interval_data)}")
                #print(f"    Max magnitude: {max_mag_record['mag']:.2f} on Day {max_mag_record['Day_Number']:.1f}")
                
                cluster_filtered.append(max_mag_record)
                interval_count += 1
            
            current_interval_start = interval_end + 1
            if current_interval_start > max_day:
                break
        
        if cluster_filtered:
            cluster_df = pd.DataFrame(cluster_filtered)
            filtered_data.append(cluster_df)
            #print(f"  Kept {len(cluster_filtered)} records from {len(cluster_data)} original records")
    
    # Combine all filtered data
    if filtered_data:
        smooth_data = pd.concat(filtered_data, ignore_index=True)
    else:
        # Return empty DataFrame with same columns as input + 'filter' if you like
        return pd.DataFrame(columns=list(data.columns) + ['filter'])
    
    #print("="*30)
    #print("removing data")
    #print("="*30)

    # Ensure proper index and column assignment
    smooth_data = smooth_data.reset_index(drop=True)
    smooth_data['filter'] = 'keep'   # safe even if empty (but we've already returned on empty)
    
    # Make sure Day_Number is numeric
    smooth_data['Day_Number'] = pd.to_numeric(smooth_data['Day_Number'], errors='coerce').fillna(0).astype(int)
    
    # Iterate safely by integer positions
    for index in range(1, len(smooth_data)):
        # Only compare rows in the same cluster
        if smooth_data.loc[index, 'cluster'] != smooth_data.loc[index - 1, 'cluster']:
            continue
        
        if smooth_data.loc[index - 1, 'filter'] == 'keep':
            day_diff = smooth_data.loc[index, 'Day_Number'] - smooth_data.loc[index - 1, 'Day_Number']
            if day_diff <= aftershock_days:
                if smooth_data.loc[index, 'mag'] <= smooth_data.loc[index - 1, 'mag']:
                    smooth_data.loc[index, 'filter'] = 'remove'
                else:
                    smooth_data.loc[index - 1, 'filter'] = 'remove'
    
    smooth_data = smooth_data[smooth_data['filter'] != 'remove'].reset_index(drop=True)
    # drop the 'filter' column if you don't want it in the return
    smooth_data = smooth_data.drop(columns=['filter'], errors='ignore')
    return smooth_data


def split_clusters_80_20(data):
    """Split EACH cluster individually into 80% training and 20% testing data.

    Uses the 'time' column for chronological ordering (same convention as
    NFFT_global.py and LSP-gobal.py).
    """
    train_data = []
    test_data = []
    
    for cluster_id in data['cluster'].unique():
        if cluster_id == -1:  # Skip noise cluster
            continue
        
        cluster_data = data[data['cluster'] == cluster_id].copy()
        cluster_data = cluster_data.sort_values('time').reset_index(drop=True)
        
        print(f"Cluster {cluster_id}: {len(cluster_data)} records")
        
        if len(cluster_data) < 5:  # Need minimum records for meaningful split
            print("  Too few records, adding all to training set")
            train_data.append(cluster_data)
            continue
        
        # Calculate 80/20 split point for THIS specific cluster
        split_point = int(len(cluster_data) * 0.8)
        
        cluster_80 = cluster_data.iloc[:split_point]  # First 80% by date
        cluster_20 = cluster_data.iloc[split_point:]  # Last 20% by date
        
        print(f"  Cluster {cluster_id} split: {len(cluster_80)} train, {len(cluster_20)} test")
        
        train_data.append(cluster_80)
        if len(cluster_20) > 0:
            test_data.append(cluster_20)
    
    # Combine all clusters
    train_combined = pd.concat(train_data, ignore_index=True) if train_data else pd.DataFrame()
    test_combined = pd.concat(test_data, ignore_index=True) if test_data else pd.DataFrame()
    
    return train_combined, test_combined


def predict_and_error(train_data, test_data):
    """Predict future events using a fixed return period (in days) and
    evaluate error against the test data.

    The logic mirrors LSP-gobal.py / NFFT_global.py but uses the
    statistics mean-gap-based return period or mode or median.
    """
    results = []
    summary = []

    if train_data.empty or test_data.empty:
        return pd.DataFrame(results), pd.DataFrame(summary)

    # make sure time columns are datetime
    train_data['time'] = pd.to_datetime(train_data['time'], errors='coerce')
    test_data['time'] = pd.to_datetime(test_data['time'], errors='coerce')
 
    # Calculate gap of train data
    gaps = [(train_data.iloc[i]['time'].date() - train_data.iloc[i-1]['time'].date()).days
                for i in range(1, len(train_data))]
    
    #### User-defined whether we want to use mean, mode or median to evaluate gap intervals
    return_period_days = np.mean(gaps)
    #mode_result = stats.mode(np.array(gaps), keepdims=True)
    #return_period_days = mode_result.mode[0]
    #return_period_days = np.median(gaps)
    
    for cluster_id in train_data['cluster'].unique():
        if cluster_id == -1:
            continue
        
        print(f"\n=== Statistics Prediction - Cluster {cluster_id} ===")

        cluster_test = test_data[test_data['cluster'] == cluster_id].copy()
        cluster_test['time'] = pd.to_datetime(cluster_test['time']).dt.date
        cluster_test = cluster_test.sort_values('time').reset_index(drop=True)

        if cluster_test.empty:
            print("  No test data for this cluster")
            continue

        last_train_date = train_data[train_data['cluster'] == cluster_id]['time'].max().date()

        print(f"  Using fixed return period (mean gap): {return_period_days:.2f} days")
        print(f"  Last train date: {last_train_date}")

        current_pred_date = last_train_date + timedelta(days=int(return_period_days))
        errors = []

        while current_pred_date <= cluster_test['time'].max():
            # Find nearest test record
            nearest = cluster_test.iloc[(cluster_test['time'] - current_pred_date).abs().argsort()[:1]]
            nearest_date = nearest['time'].values[0]
            error_days = abs((nearest_date - current_pred_date).days)

            results.append({
                'cluster': cluster_id,
                'predicted_date': current_pred_date,
                'nearest_test_date': nearest_date,
                'error_days': error_days
            })

            errors.append(error_days)
            print(f"  Predicted: {current_pred_date} | Nearest: {nearest_date} | Error: {error_days} days")

            current_pred_date += timedelta(days=int(return_period_days))

        avg_error = np.mean(errors) if errors else None
        summary.append({
            'cluster': cluster_id,
            'return_period_days': return_period_days,
            'predictions': len(errors),
            'average_error_days': avg_error,
            'average_error_years': round(avg_error / 365, 3) if avg_error is not None else None,
        })

    return pd.DataFrame(results), pd.DataFrame(summary)

#For NFFT
def plot_time_series(cluster_data, cluster, country):
    """Plot time series of earthquake magnitudes"""
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Sort data by Day_Number to ensure proper line connections
        sorted_data = cluster_data.sort_values('Day_Number')
        
        # Plot with connected lines and points
        ax.plot(sorted_data['Day_Number'], sorted_data['mag'], 
               marker='o', markersize=4, alpha=0.7, linewidth=1.5)
        
        ax.set_xlabel('Day Number')
        ax.set_ylabel('Magnitude')
        ax.set_title(f'{country} Cluster {cluster} - Time Series')
        ax.grid(True)
        
        # Create directory if it doesn't exist
        os.makedirs('./graphs', exist_ok=True)
        fig.savefig(f'./graphs/{country}_cluster_{cluster}_time_series.png')
        plt.close(fig)
    except Exception as e:
        print(f"Error plotting time series: {e}")

class Datavalue:
    """Class to store peak analysis data"""
    def __init__(self):
        self.years = 0
        self.freq = 0
        self.amp = 0


def calculateYears(num_days, frequency):
    """Convert frequency to years based on number of days"""
    if frequency == 0:
        return 0
    return (num_days / frequency) / 365.25  # Convert days to years


def predict_and_error_nfftlsp(train_data, test_data, return_period):
    results = []
    summary = []

    # make sure date columns are datetime
    train_data['time'] = pd.to_datetime(train_data['time'], errors='coerce')
    test_data['time'] = pd.to_datetime(test_data['time'], errors='coerce')

    for cluster_id in train_data['cluster'].unique():
        if cluster_id == -1:
            continue
        
        print(f"\n=== Cluster {cluster_id} Prediction ===")

        cluster_test = test_data[test_data['cluster'] == cluster_id].copy()
        cluster_test['time'] = pd.to_datetime(cluster_test['time']).dt.date
        cluster_test = cluster_test.sort_values('time').reset_index(drop=True)

        if cluster_test.empty:
            print("  No test data for this cluster")
            continue

        last_train_date = train_data[train_data['cluster'] == cluster_id]['time'].max().date()

        print(f"  Using fixed return period: {return_period:.2f} days")
        print(f"  Last train date: {last_train_date}")

        current_pred_date = last_train_date + timedelta(days=int(return_period))
        errors = []

        while current_pred_date <= cluster_test['time'].max():
            # Find nearest test record
            nearest = cluster_test.iloc[(cluster_test['time'] - current_pred_date).abs().argsort()[:1]]
            nearest_date = nearest['time'].values[0]
            error_days = abs((nearest_date - current_pred_date).days)

            results.append({
                'cluster': cluster_id,
                'predicted_date': current_pred_date,
                'nearest_test_date': nearest_date,
                'error_days': error_days
            })

            errors.append(error_days)
            print(f"  Predicted: {current_pred_date} | Nearest: {nearest_date} | Error: {error_days} days")

            current_pred_date += timedelta(days=int(return_period))

        avg_error = np.mean(errors) if errors else None
        summary.append({
            'cluster': cluster_id,
            'return_period': return_period,
            'predictions': len(errors),
            'average_error_days': round(avg_error/365,2)
        })

    return pd.DataFrame(results), pd.DataFrame(summary)


def run_NFFT (countries, min_magnitude, use_split):
    all_peak_data = []  # Store all results here
    country_results = {}  # Store results by country for organization
    all_prediction_results = []
    all_prediction_summaries = []
    AFTERSHOCK_DAYS = 180

    # Create directories
    os.makedirs("result", exist_ok=True)
    os.makedirs("graphs", exist_ok=True)
    if use_split:
        os.makedirs('train', exist_ok=True)
        os.makedirs('test', exist_ok=True)

    for country in countries:

        print(f"\n{'='*50}")
        print(f"PROCESSING NFFT FOR COUNTRY: {country}")
        print(f"{'='*50}")
        
        # file_path = f"./earthquake_data_2025-06-04/pre/clustered_earthquakes_{country}.csv"
        file_path = f"./Dataset/data4calculation/{country}_data.csv"
        
        try:
            data = pd.read_csv(file_path)
        except FileNotFoundError:
            print(f"File not found for {country}: {file_path}")
            continue
        
        if len(data) == 0:
            print(f"No data found for {country}")
            continue
        
        # Initialize country-specific results
        country_results[country] = {
            'peak_data': [],
            'additional_peak_data': {}
        }
        
        #clusters = data['cluster'].unique()
        data.columns = data.columns.str.lower()
        
        # Remove duplicate columns if any (can happen after lowercasing)
        data = data.loc[:, ~data.columns.duplicated()]
        
        country_data = data.copy()
        
        country_data['time'] = pd.to_datetime(country_data['time'], format='mixed', errors='coerce')
        #unique_clusters = country_data['cluster'].unique()
        for cluster_id in sorted(data['cluster'].unique()):
            if cluster_id == -1:
                cluster_peaks = {
                    "country": country,
                    "cluster": cluster_id,
                    "return_P_nomes": "",
                    "avg_gap": 0,
                    "Number of record": 0,
                    "Number of the day": 0,
                    "percent": 0,
                    "highest_amplitude": 0,
                    "highest_frequency": 0,
                    "highest_years_not_normalised": 0
                }
                country_results[country]['peak_data'].append(cluster_peaks)
                all_peak_data.append(cluster_peaks)
                continue
            
            cluster_data = country_data[country_data['cluster'] == cluster_id].copy()
            print(f"Cluster data size: {len(cluster_data)}")
            
            if len(cluster_data) < 10:
                cluster_peaks = {
                    "country": country,
                    "cluster": cluster_id,
                    "return_P_nomes": "",
                    "avg_gap": 0,
                    "Number of record": 0,
                    "Number of the day": 0,
                    "percent": 0,
                    "highest_amplitude": 0,      # Initialize with default values
                    "highest_frequency": 0,
                    "highest_years_not_normalised": 0
                }
                country_results[country]['peak_data'].append(cluster_peaks)
                all_peak_data.append(cluster_peaks)
                continue
                
            if use_split:
                # Split data and process both parts
                data_80, data_20 = split_clusters_80_20(cluster_data)
                
                # Filter by magnitude FIRST (matches NFFT_Thai.py order)
                filtered_data_80 = data_80[data_80['mag'] >= min_magnitude].copy()
                filtered_data_20 = data_20[data_20['mag'] >= min_magnitude].copy()
                
                # Check if filtered data has enough records
                if len(filtered_data_80) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records in training data after magnitude filtering (min_mag={min_magnitude}).")
                    cluster_peaks = {
                        "country": country,
                        "cluster": cluster_id,
                        "return_P_nomes": "",
                        "avg_gap": 0,
                        "Number of record": len(filtered_data_80),
                        "Number of the day": 0,
                        "percent": 0,
                        "highest_amplitude": 0,
                        "highest_frequency": 0,
                        "highest_years_not_normalised": 0
                    }
                    country_results[country]['peak_data'].append(cluster_peaks)
                    all_peak_data.append(cluster_peaks)
                    continue
                
                # Process training data (80%) - matches NFFT_Thai.py order
                smooth_data0_80 = recount_day_number(filtered_data_80) 
                smooth_data1_80 = remove_aftershocks(smooth_data0_80, AFTERSHOCK_DAYS)
                smooth_data1_80 = recount_day_number(smooth_data1_80) 
                
                # Check if data is empty after aftershock removal
                if len(smooth_data1_80) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records after aftershock removal in training data.")
                    cluster_peaks = {
                        "country": country,
                        "cluster": cluster_id,
                        "return_P_nomes": "",
                        "avg_gap": 0,
                        "Number of record": len(smooth_data1_80),
                        "Number of the day": 0,
                        "percent": 0,
                        "highest_amplitude": 0,
                        "highest_frequency": 0,
                        "highest_years_not_normalised": 0
                    }
                    country_results[country]['peak_data'].append(cluster_peaks)
                    all_peak_data.append(cluster_peaks)
                    continue
                
                # Process test data (20%) - matches NFFT_Thai.py order
                smooth_data0_20 = recount_day_number(filtered_data_20)
                smooth_data1_20 = remove_aftershocks(smooth_data0_20, AFTERSHOCK_DAYS)
                smooth_data1_20 = recount_day_number(smooth_data1_20)
                
                # Save split files
                excel_filename_train = f"train/{country}-{cluster_id}-TRAIN-{min_magnitude}-NFFT.csv"
                excel_filename_test = f"test/{country}-{cluster_id}-TEST-{min_magnitude}-NFFT.csv"
                smooth_data1_80.to_csv(excel_filename_train, index=False)
                smooth_data1_20.to_csv(excel_filename_test, index=False)
                
                # Use training data for analysis
                analysis_data = smooth_data1_80
            else:
                # Use all data without splitting 
                
                # Filter by magnitude
                filtered_cluster = cluster_data[cluster_data['mag'] >= min_magnitude].copy()
                
                # Check if filtered data has enough records
                if len(filtered_cluster) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records after magnitude filtering (min_mag={min_magnitude}).")
                    cluster_peaks = {
                        "country": country,
                        "cluster": cluster_id,
                        "return_P_nomes": "",
                        "avg_gap": 0,
                        "Number of record": len(filtered_cluster),
                        "Number of the day": 0,
                        "percent": 0,
                        "highest_amplitude": 0,
                        "highest_frequency": 0,
                        "highest_years_not_normalised": 0
                    }
                    country_results[country]['peak_data'].append(cluster_peaks)
                    all_peak_data.append(cluster_peaks)
                    continue
                
                # Process: recount_day_number -> remove_aftershocks -> recount_day_number (matches NFFT_Thai.py)
                smooth_data0 = recount_day_number(filtered_cluster)
                smooth_data1 = remove_aftershocks(smooth_data0, AFTERSHOCK_DAYS)
                analysis_data = recount_day_number(smooth_data1)
                
                # Check if data is empty after aftershock removal
                if len(analysis_data) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records after aftershock removal.")
                    cluster_peaks = {
                        "country": country,
                        "cluster": cluster_id,
                        "return_P_nomes": "",
                        "avg_gap": 0,
                        "Number of record": len(analysis_data),
                        "Number of the day": 0,
                        "percent": 0,
                        "highest_amplitude": 0,
                        "highest_frequency": 0,
                        "highest_years_not_normalised": 0
                    }
                    country_results[country]['peak_data'].append(cluster_peaks)
                    all_peak_data.append(cluster_peaks)
                    continue
                
                # Save all data
                # excel_filename_all = f"result/data/{country}-{cluster_id}-ALL-{min_magnitude}-NFFT.csv"
                # analysis_data.to_csv(excel_filename_all, index=False)
                
            if len(analysis_data) < 5:
                cluster_peaks = {
                    "country": country,
                    "cluster": cluster_id,
                    "return_P_nomes": "",
                    "avg_gap": 0,
                    "Number of record": 0,
                    "Number of the day": 0,
                    "percent": 0,
                    "highest_amplitude": 0,      # Initialize with default values
                    "highest_frequency": 0,
                    "highest_years_not_normalised": 0
                }
                country_results[country]['peak_data'].append(cluster_peaks)
                all_peak_data.append(cluster_peaks)
                continue
                
            # Sort the data by time from low to high
            analysis_data = analysis_data.sort_values(by='Day_Number').reset_index(drop=True)
            
            y = analysis_data['mag'].to_numpy()
            N = len(y)
                
            analysis_data.loc[0,'delta'] = 0
            analysis_data['delta'] = analysis_data['Day_Number'] - analysis_data['Day_Number'].shift(1)
            avg_gap = analysis_data['delta'].mean()
            
            if N < 5:
                cluster_peaks = {
             "country": country,
             "cluster": cluster_id,
             "return_P_nomes": "",
             "avg_gap": 0,
             "Number of record": 0,
             "Number of the day": 0,
             "percent": 0,
             "highest_amplitude": 0,      # Initialize with default values
             "highest_frequency": 0,
             "highest_years_not_normalised": 0
         }
                country_results[country]['peak_data'].append(cluster_peaks)
                all_peak_data.append(cluster_peaks)
                print(f"Skipping {country} Cluster {cluster_id} due to insufficient data after filtering.")
                continue
            
            num_day = analysis_data['Day_Number'].max() - analysis_data['Day_Number'].min()
            if num_day == 0:
                num_day = 1  # Avoid division by zero
                
            # Set frequency bounds
            if avg_gap >= 365*2.5: #540
                lower_bound = (N//2)*0.10 
                upper_bound = (N//2)*0.40
            elif(avg_gap >= 365):
                lower_bound = (N//2)*0.40
                upper_bound = (N//2)*0.60
            else:
                lower_bound = (N//2)*0.60
                upper_bound = (N//2)*0.90
                
            x = analysis_data['Day_Number'].to_numpy()
            print(f"Data points: {len(x)}, Time span: {num_day} days")
            print(f"Average gap: {avg_gap:.4f} days")
            print(f"Frequency bounds: {lower_bound:.4f} to {upper_bound:.4f}")
            
            if len(x) < 5:
                print(f"Skipping {country} Cluster {cluster_id} due to insufficient data.")
                cluster_peaks = {
                    "country": country,
                    "cluster": cluster_id,
                    "return_P_nomes": "",
                    "avg_gap": avg_gap,
                    "Number of record": N,
                    "Number of the day": num_day,
                    "percent": 0,
                    "highest_amplitude": 0,      # Initialize with default values
                    "highest_frequency": 0,
                    "highest_years_not_normalised": 0
                }
                country_results[country]['peak_data'].append(cluster_peaks)
                all_peak_data.append(cluster_peaks)
                continue
                
            # Normalize x
            x = x - min(x)
            if max(x) == 0:
                x_nom = np.zeros_like(x)
            else:
                x_nom = [i * 0.4999 / max(x) for i in x]
            
            # Perform NFFT
            try:
                xf = np.fft.fftfreq(N, 1.0 / N)
                if len(y) % 2 == 0:
                    yf = np.abs(nfft(x_nom[:N], y, sigma=5))
                else:
                    yf = np.abs(nfft(x_nom[:N], y[:-1], sigma=5))
                    
                amp = 1.0 / N * yf
                peaks, _ = find_peaks(amp[:int(N // 2)], distance=3, prominence=0.01, height=0.01)
                
                print(f"Found {len(peaks)} peaks")
                
            except Exception as e:
                print(f"Error in NFFT calculation: {e}")
                cluster_peaks = {
             "country": country,
             "cluster": cluster_id,
             "return_P_nomes": "",
             "avg_gap": 0,
             "Number of record": 0,
             "Number of the day": 0,
             "percent": 0,
             "highest_amplitude": 0,      # Initialize with default values
             "highest_frequency": 0,
             "highest_years_not_normalised": 0
         }
                country_results[country]['peak_data'].append(cluster_peaks)
                all_peak_data.append(cluster_peaks)
                continue
            
            # Create unique cluster information for each country-cluster pair
            cluster_peaks = {
                "country": country,
                "cluster": cluster_id,
                "return_P_nomes": "",
                "avg_gap": avg_gap,
                "Number of record": N,
                "Number of the day": num_day,
                "percent": 0,
                "highest_amplitude": 0,      # Initialize with default values
                "highest_frequency": 0,
                "highest_years_not_normalised": 0
            }
            
            # Create frequency plot
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(xf[:int(N // 2)], amp[:int(N // 2)], color='red', linewidth=1)
            ax.axvspan(xmin=0, xmax=lower_bound, color="yellow", alpha=0.3, label="Low freq")
            ax.axvspan(xmin=lower_bound, xmax=upper_bound, color="green", alpha=0.3, label="Target freq")
            ax.axvspan(xmin=upper_bound, xmax=len(xf) // 2, color="red", alpha=0.3, label="High freq")
            ax.set_title(f"{country} Cluster {cluster_id} (N={N}, Days={num_day})")
            ax.set_xlabel('Frequency')
            ax.set_ylabel('Amplitude')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Process peaks
            highest_peak_amplitude = 0
            highest_peak_frequency = 0
            highest_peak_years = 0
            valid_peaks = 0
            
            for z, peak in enumerate(peaks):
                peak_frequency = xf[peak]
                peak_amplitude = amp[peak]
                
                if lower_bound <= peak_frequency <= upper_bound:
                    valid_peaks += 1
                    test_data_point = Datavalue()
                    test_data_point.years = calculateYears(num_day, peak_frequency)
                    test_data_point.freq = peak_frequency
                    test_data_point.amp = peak_amplitude
                    
                    if peak_amplitude > highest_peak_amplitude:
                        highest_peak_amplitude = peak_amplitude
                        highest_peak_frequency = peak_frequency
                        highest_peak_years = test_data_point.years
                        
                    ax.plot(peak_frequency, peak_amplitude, 'bo', markersize=6)
            
            print(f"Valid peaks in target frequency range: {valid_peaks}")
            
            # Update the cluster_peaks dictionary directly
            if highest_peak_amplitude > 0.0:
                cluster_peaks["highest_amplitude"] = highest_peak_amplitude
                cluster_peaks["highest_frequency"] = highest_peak_frequency
                cluster_peaks["highest_years_not_normalised"] = highest_peak_years

                # Calculate return period
                nomes = (highest_peak_frequency / (N // 2)) * 100 if (N // 2) > 0 else 0
                if nomes > 0:
                    return_P_nomes = (num_day / nomes) / 365
                else:
                    return_P_nomes = None

                cluster_peaks["percent"] = nomes
                cluster_peaks["return_P_nomes"] = round(return_P_nomes,3)

                # Convert return_P_nomes (years) → days for prediction
                if return_P_nomes is not None:
                    period_days = return_P_nomes * 365.0
                else:
                    period_days = 0.0

                gap_days = max(1, int(round(period_days)))

                print(f"Highest peak: freq={highest_peak_frequency:.6f}, amp={highest_peak_amplitude:.6f}, "
                      f"nomes={nomes:.4f}, return_P_nomes={return_P_nomes}, gap_days={gap_days}")
            else:
                print(f"No valid peaks found in target frequency range for {country} cluster {cluster_id}")
                period_days = 0.0

            # Call prediction only if we have valid gap_days and split is enabled
            if use_split and period_days > 0.0:
                try:
                    prediction_results, prediction_summary = predict_and_error_nfftlsp(
                        smooth_data1_80, smooth_data1_20, gap_days
                    )
                    prediction_results["country"] = country
                    prediction_summary["country"] = country
                    country_results[country].setdefault('prediction_results', []).append(prediction_results)
                    country_results[country].setdefault('prediction_summary', []).append(prediction_summary)
                    all_prediction_results.append(prediction_results)
                    all_prediction_summaries.append(prediction_summary)
                except Exception as e:
                    print(f"Error during prediction for {country} cluster {cluster_id}: {e}")
            elif not use_split:
                print(f"  Skipping validation for {country} cluster {cluster_id} - using all data for return period calculation only.")

            # Save frequency plot
            plt.tight_layout()
            fig.savefig(f'./graphs/{country}_cluster_{cluster_id}.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            # Plot and save time series
            plot_time_series(analysis_data, cluster_id, country)
            
            # Store results in both country-specific and global lists
            country_results[country]['peak_data'].append(cluster_peaks)
            all_peak_data.append(cluster_peaks)
            
            # Calculate average frequency and years for logging
            if len(peaks) > 0:
                avg_freq = np.mean(xf[peaks])
                avg_years = calculateYears(max(x), avg_freq)
                print(f"Average frequency: {avg_freq:.4f}, Average period: {avg_years:.2f} years")

    # Save single combined results file
    if all_peak_data:
        df_all_peaks = pd.DataFrame(all_peak_data)
        df_all_peaks.to_csv(f'result/NFFT_M{min_magnitude}.csv', index=False)
        print(f"\nAnalysis complete! Results saved to NFFT_M{min_magnitude}.csv")
        print(f"Processed {len(all_peak_data)} clusters across {len(country_results)} countries")
        print(df_all_peaks.head())
    else:
        
        print("No peak data to save.")

    # Save combined prediction results only if split was used
    if use_split and all_prediction_results:
        df_all_results = pd.concat(all_prediction_results, ignore_index=True)
        df_all_summary = pd.concat(all_prediction_summaries, ignore_index=True)

        df_all_results.to_csv(f"result/NFFT_validate_M{min_magnitude}.csv", index=False)
        df_all_summary.to_csv(f"result/NFFT_vasummary_M{min_magnitude}.csv", index=False)

        print(f"\nPrediction results saved to result/NFFT_validate_M{min_magnitude}.csv")
        print(f"Summary saved to result/NFFT_vasummary_M{min_magnitude}.csv")
        print(df_all_summary.head())
    elif not use_split:
        print("Skipping validation - using all data for return period calculation only.")
    else:
        print("No prediction results to save.")
        
        
def run_LSP (countries, min_magnitude, use_split):
    all_peak_data = []
    country_results = {}
    output_dir = "LSP"
    AFTERSHOCK_DAYS = 180
    #min_magnitude = 4

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs('./graphs', exist_ok=True)

    # Only create train/test directories if splitting
    if use_split:
        os.makedirs('train', exist_ok=True)
        os.makedirs('test', exist_ok=True)

    all_prediction_results = []
    all_prediction_summaries = []
    for country in countries:
        print(f"\n{'='*50}")
        print(f"PROCESSING COUNTRY: {country}")
        print(f"{'='*50}")
        
        file_path = f"./Dataset/data4calculation/{country}_data.csv"
        try:
            data = pd.read_csv(file_path)
        except FileNotFoundError:
            print(f"File not found for {country}: {file_path}")
            continue
        
        if len(data) == 0:
            print(f"No data found for {country}")
            continue
        
        # Initialize country-specific results
        data.columns = data.columns.str.lower()
        country_results[country] = {'peak_data': []}
        
        # Remove duplicate columns if any (can happen after lowercasing)
        data = data.loc[:, ~data.columns.duplicated()]
        
        country_data = data.copy()
        
        # Convert time column to datetime
        country_data['time'] = pd.to_datetime(country_data['time'], format='mixed', errors='coerce')
        
        for cluster_id in sorted(data['cluster'].unique()):
            if cluster_id == -1:
                zero_peak_info = {
                    'country': country,
                    'cluster': cluster_id,
                    'return_p_years': "",
                    'best_frequency': 0,
                    'best_power': 0,
                    'num_records': 0,
                    "Number of the day": 0,
                    'time_span_days': 0
                    
                }
                country_results[country]['peak_data'].append(zero_peak_info)
                all_peak_data.append(zero_peak_info)
                continue
                
            cluster_data = country_data[country_data['cluster'] == cluster_id].copy()
            print(f"Cluster data size: {len(cluster_data)}")
            zero_peak_info = {
                'country': country,
                'cluster': cluster_id,
                'return_p_years': "",
                'best_frequency': 0,
                'best_power': 0,
                'num_records': 0,
                "Number of the day": 0,
                'time_span_days': 0,
                
            }
            if len(cluster_data) < 10:
                print(f"Cluster {cluster_id} skipped: Less than 10 initial records.")
                country_results[country]['peak_data'].append(zero_peak_info)
                all_peak_data.append(zero_peak_info)
                continue
            if use_split:
                # Split data and process both parts
                data_80, data_20 = split_clusters_80_20(cluster_data)
                
                # Process training data
                smooth_data0 = recount_day_number(data_80) 
                data_20 = recount_day_number(data_20) 
                
                
                filtered_data_80 = data_80[data_80['mag'] >= min_magnitude].copy()
                filtered_data_20 = data_20[data_20['mag'] >= min_magnitude].copy()
                
                # Check if filtered data has enough records
                if len(filtered_data_80) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records in training data after magnitude filtering (min_mag={min_magnitude}).")
                    zero_peak_info['num_records'] = len(filtered_data_80)
                    country_results[country]['peak_data'].append(zero_peak_info)
                    all_peak_data.append(zero_peak_info)
                    continue
                
                smooth_data0_80 = recount_day_number(filtered_data_80) 
                smooth_data1_80 = remove_aftershocks(smooth_data0_80, AFTERSHOCK_DAYS)
                smooth_data1_80 = recount_day_number(smooth_data1_80) 
                
                # Check if data is empty after aftershock removal
                if len(smooth_data1_80) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records after aftershock removal in training data.")
                    zero_peak_info['num_records'] = len(smooth_data1_80)
                    country_results[country]['peak_data'].append(zero_peak_info)
                    all_peak_data.append(zero_peak_info)
                    continue
                
                smooth_data0_20 = recount_day_number(filtered_data_20)
                smooth_data1_20 = remove_aftershocks(smooth_data0_20, AFTERSHOCK_DAYS)
                smooth_data1_20 = recount_day_number(smooth_data1_20)
                
                # Save split files
                excel_filename_train = f"train/{country}-{cluster_id}-TRAIN-{min_magnitude}-LSP.csv"
                excel_filename_test = f"test/{country}-{cluster_id}-TEST-{min_magnitude}-LSP.csv"
                
                smooth_data1_80.to_csv(excel_filename_train, index=False)
                smooth_data1_20.to_csv(excel_filename_test, index=False)
                
                # Use training data for analysis
                analysis_data = smooth_data1_80
            else:
                # Use all data without splitting
                filtered_cluster = cluster_data[cluster_data['mag'] >= min_magnitude].copy()
                
                # Check if filtered data has enough records
                if len(filtered_cluster) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records after magnitude filtering (min_mag={min_magnitude}).")
                    zero_peak_info['num_records'] = len(filtered_cluster)
                    country_results[country]['peak_data'].append(zero_peak_info)
                    all_peak_data.append(zero_peak_info)
                    continue
                
                smooth_data0 = recount_day_number(filtered_cluster)
                analysis_data = remove_aftershocks(smooth_data0, AFTERSHOCK_DAYS)
                analysis_data = recount_day_number(analysis_data)
                
                # Check if data is empty after aftershock removal
                if len(analysis_data) < 5:
                    print(f"  Cluster {cluster_id} skipped: Less than 5 records after aftershock removal.")
                    zero_peak_info['num_records'] = len(analysis_data)
                    country_results[country]['peak_data'].append(zero_peak_info)
                    all_peak_data.append(zero_peak_info)
                    continue
                
                # Save all data file
                # excel_filename_all = f"result/data/LSP{country}-{cluster_id}-ALL-4-LSP.csv"
                # analysis_data.to_csv(excel_filename_all, index=False)
        
            if len(analysis_data) < 5:
                print(f"Cluster {cluster_id} skipped: Less than 5 records after filtering.")
                # Set num_records based on filtered data size before continuing
                zero_peak_info['num_records'] = len(analysis_data)
                country_results[country]['peak_data'].append(zero_peak_info)
                all_peak_data.append(zero_peak_info)
                continue
            analysis_data.loc[0,'delta'] = 0
            analysis_data['delta'] = analysis_data['Day_Number'] - analysis_data['Day_Number'].shift(1)
            avg_gap = analysis_data['delta'].mean()
            # Sort the data by time from low to high
            cluster_data = analysis_data.sort_values(by='Day_Number').reset_index(drop=True)
            
            x = cluster_data['Day_Number'].values - cluster_data['Day_Number'].values[0]
            y = cluster_data['mag'].to_numpy()
            N = len(y)
            num_day = cluster_data['Day_Number'].max() - cluster_data['Day_Number'].min()
            
    # =============================================================================
    #         if N % 2 != 0:
    #             N -= 1
    #             x = x[:N]
    # =============================================================================

    # =============================================================================
    #         # Normalize data
    #         if max(x) == 0:
    #             x_normalise = np.zeros_like(x)
    #         else:
    # =============================================================================
            x_normalise = np.array([i * 0.4999 / max(x) for i in x])

            

            try:
                # Lomb-Scargle analysis
                ls = LombScargle(x_normalise, y)
                frequencies, power = ls.autopower(minimum_frequency=0.01, maximum_frequency=N)
                
                
                cluster_data['delta'] = cluster_data['Day_Number'] - cluster_data['Day_Number'].shift(1)
                #avg_gap = cluster_data['delta'].mean()
                
                # Dynamic bounds based on avg_gap

                freq_range_min_ls = frequencies[int(len(frequencies) * 0.40)]
                freq_range_max_ls = frequencies[int(len(frequencies) * 0.99)]
                
                # Filter frequency and power arrays within the desired range
                filtered_indices = (frequencies >= freq_range_min_ls) & (frequencies <= freq_range_max_ls)
                filtered_frequency = frequencies[filtered_indices]
                filtered_power = power[filtered_indices]
                
                if len(filtered_frequency) == 0:
                    print(f"No valid frequencies found for {country} Cluster {cluster_id}")
                    # Set num_records based on filtered data size before continuing
                    zero_peak_info['num_records'] = N
                    zero_peak_info["Number of the day"] = num_day
                    country_results[country]['peak_data'].append(zero_peak_info)
                    all_peak_data.append(zero_peak_info)
                    continue
                    
                # Find the best period within the filtered range
                best_freq_lomb = filtered_frequency[np.argmax(filtered_power)]
                best_period = 1. / best_freq_lomb if best_freq_lomb != 0 else 0
                best_power = filtered_power[np.argmax(filtered_power)]
                
                # Plot Lomb-Scargle Periodogram
                fig_l, axs_l = plt.subplots(1, figsize=(10, 6))
                axs_l.plot(frequencies, power, color='red', linewidth=1, label="Full Data")
                
                # Highlight frequency range
                axs_l.axvspan(freq_range_min_ls, freq_range_max_ls, color='green', alpha=0.3, label='Selected Frequency Range')
                
                # Mark best frequency
                axs_l.plot(best_freq_lomb, best_power, 'ro', label=f'Best Frequency: {best_freq_lomb:.2f}')
                
                axs_l.set_xlabel('Frequency')
                axs_l.set_ylabel('Power')
                axs_l.legend()
                axs_l.grid()
                axs_l.set_title(f'Lomb-Scargle Periodogram Analysis: {country} Cluster {cluster_id} N: {N}, day: {num_day}')
                
                # Save Lomb-Scargle plot
                lomb_save_path = os.path.join(output_dir, f'{country}_lomb_cluster_{cluster_id}.png')
                fig_l.savefig(lomb_save_path, dpi=300)
                plt.close(fig_l)
                
                # Plot Time-Series Data
                fig_t, axs_t = plt.subplots(1, figsize=(10, 6))
                axs_t.plot(x, y, '.', color='blue')
                axs_t.set_xlabel('Days')
                axs_t.set_ylabel('Magnitude')
                axs_t.set_title(f'Time-Series Data: {country} Cluster {cluster_id}')
                
                # Save Time-Series plot
                time_series_save_path = os.path.join(output_dir, f'{country}_time_series_cluster_{cluster_id}.png')
                fig_t.savefig(time_series_save_path, dpi=300)
                plt.close(fig_t)
                
                # Store peak data
                #nomes = (best_freq_lomb/N)*100
                return_P_nomes = (num_day / best_freq_lomb) / 365
    # =============================================================================
    #             if nomes > 0:
    #                 return_P_nomes = (num_day / best_freq_lomb) / 365
    #             else:
    #                 return_P_nomes = None
    #                 
    # =============================================================================
                peak_info = {
                    'country': country,
                    'cluster': cluster_id,
                    'return_p_years': round(return_P_nomes,3),
                    'best_frequency': best_freq_lomb,
                    'best_power': best_power,
                    'num_records': N,
                    "Number of the day": num_day,
                    'time_span_days': max(x) - min(x),
                    
                }
                
                if return_P_nomes is not None:
                    period_days = return_P_nomes * 365.0
                else:
                    period_days = 0
                    
                # Only run predictions if data was split
                if use_split and period_days > 0.0:
                    try:
                        prediction_results, prediction_summary = predict_and_error(
                            smooth_data1_80, smooth_data1_20, period_days
                        )
                        prediction_results["country"] = country
                        prediction_summary["country"] = country
                        country_results[country].setdefault('prediction_results', []).append(prediction_results)
                        country_results[country].setdefault('prediction_summary', []).append(prediction_summary)
                        all_prediction_results.append(prediction_results)
                        all_prediction_summaries.append(prediction_summary)
                    except Exception as e:
                        print(f"Error during prediction for {country} cluster {cluster_id}: {e}")
                elif not use_split:
                    print(f"  Skipping validation for {country} cluster {cluster_id} - using all data for return period calculation only.")
                
                country_results[country]['peak_data'].append(peak_info)
                all_peak_data.append(peak_info)
                
                print(f"Best frequency: {best_freq_lomb:.4f}, Period: {best_period:.2f} days, Power: {best_power:.4f}")
                
            except Exception as e:
                print(f"Error in Lomb-Scargle analysis for {country} Cluster {cluster_id}: {e}")
                # Set num_records based on filtered data size before continuing
                zero_peak_info['num_records'] = N
                zero_peak_info["Number of the day"] = num_day
                country_results[country]['peak_data'].append(zero_peak_info)
                all_peak_data.append(zero_peak_info)
                continue

    # Save single combined results file
    if all_peak_data:
        df_all_peaks = pd.DataFrame(all_peak_data)
        df_all_peaks.to_csv(f'result/LSP-M{min_magnitude}.csv', index=False)
        print(f"\nAnalysis complete! Results saved to LSP-M{min_magnitude}.csv.csv")
        print(f"Processed {len(all_peak_data)} clusters across {len(country_results)} countries")
        print(df_all_peaks.head())
    else:
        print("No peak data to save.")

    # Only save prediction results if data was split
    if use_split and all_prediction_results:
        df_all_results = pd.concat(all_prediction_results, ignore_index=True)
        df_all_summary = pd.concat(all_prediction_summaries, ignore_index=True)

        os.makedirs("result", exist_ok=True)
        df_all_results.to_csv(f"result/LSP_validate_M{min_magnitude}.csv", index=False)
        df_all_summary.to_csv(f"result/LSP_vasummary_M{min_magnitude}.csv", index=False)

        print(f"\nPrediction results saved to result/LSP_validate_M{min_magnitude}.csv")
        print(f"Summary saved to result/LSP_vasummary_M{min_magnitude}.csv")
        print(df_all_summary.head())
    elif not use_split:
        print("Skipping validation - using all data for return period calculation only.")
    else:
        print("No prediction results to save.")
    
    
    
# =============================================================================
# MAIN SCRIPT
# =============================================================================

# while True:
#     split_data = input("\nDo you want to split the data for validation? (yes/no): ").strip().lower()
#     if split_data in ['yes', 'y', 'no', 'n']:
#         break
#     print("Please enter 'yes' or 'no'")

# use_split = split_data in ['yes', 'y']
# print(f"\nUsing data split: {use_split}")
use_split = False  #Set to True if validating with seen/unseen data

# Create result folders
os.makedirs("result", exist_ok=True)
#os.makedirs("result/data", exist_ok=True)
os.makedirs("graphs", exist_ok=True)
os.makedirs("Dataset/data4calculation", exist_ok=True)
if use_split:
    os.makedirs('train', exist_ok=True)
    os.makedirs('test', exist_ok=True)

with open('countries.txt', 'r') as file:
    countries = [line.strip() for line in file if line.strip()]

for min_magnitude in range(4,9): #loop while < the 2nd number i.e. (4,9)
    all_gap_results = []
    all_prediction_results = []
    all_prediction_summaries = []
    AFTERSHOCK_DAYS = 180
    #min_magnitude = 5
    #countries = ["New Zealand"]

    for country in countries:
        print(f"\n{'='*50}")
        print(f"PROCESSING COUNTRY: {country}")
        print(f"{'='*50}")
    
        file_path = f"./Dataset/clustering/clustered_earthquakes_{country}.csv"
        if not os.path.exists(file_path):
            print(f"File not found for {country}")
            continue
    
        data = pd.read_csv(file_path)
        if len(data) == 0:
            continue
    
        data.columns = data.columns.str.lower()
        
        # Remove duplicate columns if any (can happen after lowercasing)
        data = data.loc[:, ~data.columns.duplicated()]
    
        data['time'] = pd.to_datetime(data['time'], format='mixed', errors='coerce')
    
        gap_analysis_improved = {}
        country_results = []
    
        for cluster_id in sorted(data['cluster'].unique()):
            if cluster_id == -1:
                continue
    
            print(f"\n--- Processing {country} Cluster {cluster_id} ---")
            cluster_data = data[data['cluster'] == cluster_id].copy()
            if len(cluster_data) < 10:
                gap_analysis_improved[cluster_id] = {
                    'country': country,
                    'cluster_id': cluster_id,
                    "return_P": "",
                    'total_earthquakes': "",
                    'total_gaps': "",
                    'exact_mode': "",
                    'min_gap': "",
                    'max_gap': "",
                    'mean_gap': "",
                    'median_gap': "",
                    'std_gap': ""
                    
                }
                continue
    
            filtered_cluster = cluster_data[cluster_data['mag'] >= min_magnitude].copy()
            
            # Check if filtered data has enough records
            if len(filtered_cluster) < 2:
                print(f"  Cluster {cluster_id} skipped: Less than 2 records after magnitude filtering (min_mag={min_magnitude}).")
                gap_analysis_improved[cluster_id] = {
                    'country': country,
                    'cluster_id': cluster_id,
                    "return_P": "",
                    'total_earthquakes': len(filtered_cluster),
                    'total_gaps': "",
                    'exact_mode': "",
                    'min_gap': "",
                    'max_gap': "",
                    'mean_gap': "",
                    'median_gap': "",
                    'std_gap': "",
                  
                }
                continue
            
            smooth_data0 = recount_day_number(filtered_cluster)
            smooth_data1 = remove_aftershocks(smooth_data0, AFTERSHOCK_DAYS)
            analysis_data = recount_day_number(smooth_data1)
            
            # Check if analysis_data has enough records after aftershock removal
            if len(analysis_data) < 2:
                print(f"  Cluster {cluster_id} skipped: Less than 2 records after aftershock removal.")
                gap_analysis_improved[cluster_id] = {
                    'country': country,
                    'cluster_id': cluster_id,
                    "return_P": "",
                    'total_earthquakes': len(analysis_data),
                    'total_gaps': "",
                    'exact_mode': "",
                    'min_gap': "",
                    'max_gap': "",
                    'mean_gap': "",
                    'median_gap': "",
                    'std_gap': ""
               
                }
                continue
    
            # Save data AFTER aftershock removal and recount_day_number
            analysis_data["country"] = country
            analysis_data["cluster_id"] = cluster_id
            country_results.append(analysis_data)
    
            # Plot graph
            plt.figure(figsize=(12, 5))
            plt.plot(analysis_data['time'], analysis_data['mag'], marker='o', linestyle='-')
            plt.title(f"Time Series of Magnitude - {country} Cluster {cluster_id}")
            plt.xlabel("Time")
            plt.ylabel("Magnitude")
            plt.grid(True)
            plot_path = f"./graphs/{country}_{cluster_id}_statisticsM{min_magnitude}_timeseries.png"
            plt.savefig(plot_path, dpi=300)
            plt.close()
    
            # Calculate gap
            gaps = [(analysis_data.iloc[i]['time'].date() - analysis_data.iloc[i-1]['time'].date()).days
                    for i in range(1, len(analysis_data))]
            if not gaps:
                gap_analysis_improved[cluster_id] = {
                    'country': country,
                    'cluster_id': cluster_id,
                    "return_P": "",
                    'total_earthquakes': "",
                    'total_gaps': "",
                    'exact_mode': "",
                    'min_gap': "",
                    'max_gap': "",
                    'mean_gap': "",
                    'median_gap': "",
                    'std_gap': ""
                }
                continue
    
            gaps_array = np.array(gaps)
            mode_result = stats.mode(gaps_array, keepdims=True)
            mean_gap = np.mean(gaps)
            gap_analysis_improved[cluster_id] = {
                'country': country,
                'cluster_id': cluster_id,
                   "return_P": round(mean_gap / 365, 3),
                'total_earthquakes': len(analysis_data),
                'total_gaps': len(gaps),
                'exact_mode': mode_result.mode[0],
                'min_gap': np.min(gaps),
                'max_gap': np.max(gaps),
                'mean_gap': mean_gap,
                'median_gap': np.median(gaps),
                'std_gap': np.std(gaps),
             
            }
    
            # If user selected data split, evaluate prediction error based on mean gap
            if use_split and mean_gap > 0:
                try:
                    # Split the already smoothed series for validation
                    train_data, test_data = split_clusters_80_20(analysis_data)
               
                    # Save split files
                    excel_filename_train = f"train/{country}-{cluster_id}-TRAIN-{min_magnitude}-statistics.csv"
                    excel_filename_test = f"test/{country}-{cluster_id}-TEST-{min_magnitude}-statistics.csv"
                    train_data.to_csv(excel_filename_train, index=False)
                    test_data.to_csv(excel_filename_test, index=False)
                
                    if not train_data.empty and not test_data.empty:
                        prediction_results, prediction_summary = predict_and_error(
                            train_data, test_data)
                        if not prediction_results.empty:
                            prediction_results["country"] = country
                            prediction_results["cluster_id"] = cluster_id
                            all_prediction_results.append(prediction_results)
                        if not prediction_summary.empty:
                            prediction_summary["country"] = country
                            prediction_summary["cluster_id"] = cluster_id
                            all_prediction_summaries.append(prediction_summary)
                except Exception as e:
                    print(f"Error during statistics prediction for {country} cluster {cluster_id}: {e}")
    
        # Create cluster mapping from ALL clusters in gap_analysis_improved (includes empty records)
        all_cluster_ids = sorted(gap_analysis_improved.keys())
        cluster_mapping = {old_id: new_id + 1 for new_id, old_id in enumerate(all_cluster_ids)}
        #print(f"  Renumbered clusters: {cluster_mapping}")
        
        # Renumber clusters in gap_analysis_improved
        gap_analysis_renumbered = {}
        for old_id, record in gap_analysis_improved.items():
            new_id = cluster_mapping[old_id]
            record['cluster_id'] = new_id
            gap_analysis_renumbered[new_id] = record
        gap_analysis_improved = gap_analysis_renumbered
    
        # ✅ Save all clusters of this country to one CSV
        if country_results:
            all_country_data = pd.concat(country_results, ignore_index=True)
            print(f"{country} main shock records = {len(all_country_data)}")
            
            # Apply the same cluster mapping to the data
            all_country_data['cluster'] = all_country_data['cluster'].map(cluster_mapping)
            
            excel_filename_all = f"./Dataset/data4calculation/{country}_data.csv"
    
            all_country_data.to_csv(excel_filename_all, index=False)
            print(f"Saved all {country} clusters to {excel_filename_all}")
    
        if gap_analysis_improved:
            gap_df = pd.DataFrame.from_dict(gap_analysis_improved, orient='index')
            all_gap_results.append(gap_df)
    
    # Save global result
    if all_gap_results:
        gap_analysis = pd.concat(all_gap_results, ignore_index=True)
        gap_analysis.to_csv(f"result/statistics-M{min_magnitude}.csv", index=False)
        print(f"\nGlobal gap analysis saved to result/statistics-M{min_magnitude}.csv")
    else:
        print("No gap analysis results to save.")
    
    # Save prediction results only if split was used
    if use_split and all_prediction_results:
        df_all_results = pd.concat(all_prediction_results, ignore_index=True)
        #df_all_summary = pd.concat(all_prediction_summaries, ignore_index=True)
    
        df_all_results.to_csv(f"result/statistics_validate_M{min_magnitude}.csv", index=False)
        #df_all_summary.to_csv(f"result/statistics_vasummary_M{min_magnitude}.csv", index=False)
    
        print(f"\nStatistics prediction results saved to result/statistics_validate_M{min_magnitude}.csv")
        #print("Statistics summary saved to result/statistics_vasummary_M{min_magnitude}.csv")
    elif not use_split:
        print("Skipping statistics validation - using all data for return period calculation only.")
    else:
        print("No statistics prediction results to save.")

    run_NFFT(countries, min_magnitude, use_split)
    run_LSP(countries, min_magnitude, use_split)
    
    