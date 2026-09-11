import pandas as pd
import numpy as np
import os
import logging
import hashlib
import sys

# Configure logging to forcefully print to the console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

print("🚀 Starting Phase 3: Silver Layer Transformation...")

BRONZE_DIR = "data/raw/bronze"
SILVER_DIR = "data/cleaned/silver"

# Ensure Silver directory exists
os.makedirs(SILVER_DIR, exist_ok=True)

# --- PII Masking Helper Functions ---
def mask_email(email):
    if pd.isna(email) or str(email).strip() == '': return email
    parts = str(email).split('@')
    if len(parts) == 2:
        return parts[0][:1] + "***@" + parts[1]
    return "***"

def mask_phone(phone):
    if pd.isna(phone) or str(phone).strip() == '': return phone
    phone_str = str(phone)
    if len(phone_str) >= 4:
        return phone_str[:4] + "XXXXX" + phone_str[-4:]
    return "XXXXX"

def mask_passport(passport):
    if pd.isna(passport) or str(passport).strip() == '': return passport
    p_str = str(passport)
    if len(p_str) >= 4:
        return "X" * (len(p_str) - 4) + p_str[-4:]
    return "XXXX"

def hash_aadhaar(aadhaar):
    if pd.isna(aadhaar) or str(aadhaar).strip() == '': return aadhaar
    return hashlib.sha256(str(aadhaar).encode()).hexdigest()

# --- Transformation Logic ---
def parse_time_and_duration(df):
    """Handles 12-hour time parsing and overnight flight duration calculation."""
    print("  -> Parsing times and calculating durations (handling overnight flights)...")
    
    # Parse departure and arrival times (12-hour format)
    df['dep_dt'] = pd.to_datetime(df['departure_time'], format='%I:%M:%S %p', errors='coerce')
    df['arr_dt'] = pd.to_datetime(df['arrival_time'], format='%I:%M:%S %p', errors='coerce')
    
    # Fallback for any 24-hour formats that might exist
    mask_dep = df['dep_dt'].isna()
    mask_arr = df['arr_dt'].isna()
    if mask_dep.any():
        df.loc[mask_dep, 'dep_dt'] = pd.to_datetime(df.loc[mask_dep, 'departure_time'], format='%H:%M:%S', errors='coerce')
    if mask_arr.any():
        df.loc[mask_arr, 'arr_dt'] = pd.to_datetime(df.loc[mask_arr, 'arrival_time'], format='%H:%M:%S', errors='coerce')
        
    # Overnight logic: if arrival time is before departure time, add 1 day to arrival
    df['arr_dt'] = np.where(df['arr_dt'] < df['dep_dt'], df['arr_dt'] + pd.Timedelta(days=1), df['arr_dt'])
    
    # Calculate duration in hours
    df['calculated_duration_hours'] = round((df['arr_dt'] - df['dep_dt']).dt.total_seconds() / 3600, 2)
    
    # Drop temporary columns
    df = df.drop(columns=['dep_dt', 'arr_dt'])
    return df

def transform_flights():
    print("\n[1/4] Transforming flights...")
    file_path = os.path.join(BRONZE_DIR, "flights.parquet")
    if not os.path.exists(file_path):
        print(f"  ⚠️ Skipping: {file_path} not found.")
        return
        
    df = pd.read_parquet(file_path)
    
    # 1. Clean flight_id (remove special chars, uppercase, handle NaN)
    df['flight_id'] = df['flight_id'].astype(str).str.strip().str.upper().replace('NAN', None)
    
    # 2. Clean airline (replace UNKNOWN, empty, or nan)
    df['airline'] = df['airline'].astype(str).str.strip().str.title()
    df['airline'] = df['airline'].replace(['Unknown', 'Nan', ''], 'Unknown')
    
    # 3. Handle overnight flights and calculate duration
    df = parse_time_and_duration(df)
    
    # 4. Drop exact duplicates based on flight_id
    initial_count = len(df)
    df = df.drop_duplicates(subset=['flight_id'], keep='first')
    print(f"  -> Removed {initial_count - len(df)} duplicate flights.")
    
    df.to_parquet(os.path.join(SILVER_DIR, "flights.parquet"), index=False)
    print("  ✅ Flights transformed and saved to Silver layer.")

def transform_bookings():
    print("\n[2/4] Transforming bookings...")
    file_path = os.path.join(BRONZE_DIR, "bookings.parquet")
    if not os.path.exists(file_path):
        print(f"  ⚠️ Skipping: {file_path} not found.")
        return
        
    df = pd.read_parquet(file_path)
    
    # 1. Clean status
    df['status'] = df['status'].astype(str).str.strip().str.upper()
    df['status'] = df['status'].replace(['NAN', ''], 'UNKNOWN')
    df['status'] = df['status'].replace('INVALID', 'CANCELLED') # Business rule
    
    # 2. PII Masking
    df['passport_number'] = df['passport_number'].apply(mask_passport)
    df['emergency_contact_phone'] = df['emergency_contact_phone'].apply(mask_phone)
    
    # 3. Drop duplicates
    initial_count = len(df)
    df = df.drop_duplicates(subset=['booking_id'], keep='first')
    print(f"  -> Removed {initial_count - len(df)} duplicate bookings.")
    
    df.to_parquet(os.path.join(SILVER_DIR, "bookings.parquet"), index=False)
    print("  ✅ Bookings transformed and saved to Silver layer.")

def transform_payments():
    print("\n[3/4] Transforming payments...")
    file_path = os.path.join(BRONZE_DIR, "payments.parquet")
    if not os.path.exists(file_path):
        print(f"  ⚠️ Skipping: {file_path} not found.")
        return
        
    df = pd.read_parquet(file_path)
    
    # 1. Clean amount (convert to numeric, coerce errors/INVALID to NaN)
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    # 2. Drop duplicates
    initial_count = len(df)
    df = df.drop_duplicates(subset=['payment_id'], keep='first')
    print(f"  -> Removed {initial_count - len(df)} duplicate payments.")
    
    df.to_parquet(os.path.join(SILVER_DIR, "payments.parquet"), index=False)
    print("  ✅ Payments transformed and saved to Silver layer.")

def transform_passengers():
    print("\n[4/4] Transforming passengers...")
    file_path = os.path.join(BRONZE_DIR, "passengers.parquet")
    if not os.path.exists(file_path):
        print(f"  ⚠️ Skipping: {file_path} not found.")
        return
        
    df = pd.read_parquet(file_path)
    
    # 1. Clean names (remove extra spaces)
    df['first_name'] = df['first_name'].astype(str).str.strip().str.title()
    df['last_name'] = df['last_name'].astype(str).str.strip().str.title()
    
    # 2. PII Masking
    df['aadhaar_id'] = df['aadhaar_id'].apply(hash_aadhaar)
    df['email'] = df['email'].apply(mask_email)
    df['phone'] = df['phone'].apply(mask_phone)
    
    # 3. Drop duplicates based on passenger_id
    initial_count = len(df)
    df = df.drop_duplicates(subset=['passenger_id'], keep='first')
    print(f"  -> Removed {initial_count - len(df)} duplicate passengers.")
    
    df.to_parquet(os.path.join(SILVER_DIR, "passengers.parquet"), index=False)
    print("  ✅ Passengers transformed and saved to Silver layer.")

if __name__ == "__main__":
    try:
        print(f"Checking Bronze directory: {os.path.abspath(BRONZE_DIR)}")
        if not os.path.exists(BRONZE_DIR):
            print(f"❌ ERROR: Bronze directory not found at '{BRONZE_DIR}'.")
            print("💡 Please ensure you have successfully run the Phase 2 ingestion script first.")
            sys.exit(1)
            
        files = os.listdir(BRONZE_DIR)
        print(f"Found files in Bronze: {files}\n")
        
        transform_flights()
        transform_bookings()
        transform_payments()
        transform_passengers()
        
        print("\n🎉 Phase 3: Silver Layer Transformation Completed Successfully!")
        print(f"📁 Check your cleaned data in: {os.path.abspath(SILVER_DIR)}")
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR during transformation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)