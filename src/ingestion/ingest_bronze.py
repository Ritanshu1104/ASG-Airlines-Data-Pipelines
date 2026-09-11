import pandas as pd
import os
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def ingest_to_bronze(file_path, output_dir):
    """
    Reads an Excel file with multiple sheets and saves each sheet 
    as a separate Parquet file in the Bronze layer.
    """
    if not os.path.exists(file_path):
        logging.error(f"Source file not found at '{file_path}'. Please ensure the Excel file is in the root directory.")
        return

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Define the sheets we expect to ingest
    sheets_to_ingest = ['flights', 'bookings', 'payments', 'passengers']
    
    logging.info(f"Starting ingestion from '{file_path}'...")
    
    try:
        # Read all sheets from the Excel file
        excel_file = pd.ExcelFile(file_path)
        available_sheets = [sheet.lower() for sheet in excel_file.sheet_names]
        
        for sheet in sheets_to_ingest:
            if sheet in available_sheets:
                logging.info(f"Reading sheet: '{sheet}'")
                
                # FIX: Use dtype=str to prevent pandas from auto-parsing dates/times 
                # into datetime objects, which causes pyarrow serialization errors.
                df = pd.read_excel(excel_file, sheet_name=sheet, dtype=str)
                
                # Drop completely empty rows if any exist at the bottom of the sheet
                df.dropna(how='all', inplace=True)
                
                # Replace string 'nan' with actual None for proper null handling in the Silver layer
                df.replace('nan', None, inplace=True)
                
                # Save to Bronze layer as Parquet
                output_path = os.path.join(output_dir, f"{sheet}.parquet")
                df.to_parquet(output_path, index=False, engine='pyarrow')
                
                logging.info(f"✅ Successfully saved '{sheet}' to Bronze layer ({len(df)} rows, {len(df.columns)} columns)")
            else:
                logging.warning(f"⚠️ Sheet '{sheet}' not found in the Excel file. Available sheets: {excel_file.sheet_names}")
                
        logging.info("🎉 Bronze layer ingestion completed successfully!")
        
    except Exception as e:
        logging.error(f"❌ Error during ingestion: {str(e)}")

if __name__ == "__main__":
    # Define paths relative to the project root
    SOURCE_FILE = "UseCase - Airlines.xlsx" 
    BRONZE_DIR = "data/raw/bronze"
    
    ingest_to_bronze(SOURCE_FILE, BRONZE_DIR)