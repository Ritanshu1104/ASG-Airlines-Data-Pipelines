import pandas as pd
import os
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

SILVER_DIR = "data/cleaned/silver"
GOLD_DIR = "data/mart/gold"

os.makedirs(GOLD_DIR, exist_ok=True)

def load_silver_data():
    logging.info("Loading Silver layer data into memory...")
    flights = pd.read_parquet(os.path.join(SILVER_DIR, "flights.parquet"))
    bookings = pd.read_parquet(os.path.join(SILVER_DIR, "bookings.parquet"))
    payments = pd.read_parquet(os.path.join(SILVER_DIR, "payments.parquet"))
    passengers = pd.read_parquet(os.path.join(SILVER_DIR, "passengers.parquet"))
    return flights, bookings, payments, passengers

def create_dimensions(flights, passengers):
    logging.info("Creating Dimension Tables...")
    
    # 1. Dim_Flight
    dim_flight = flights[['flight_id', 'airline', 'source', 'destination', 'calculated_duration_hours']].copy()
    dim_flight = dim_flight.drop_duplicates(subset=['flight_id'])
    
    # 2. Dim_Passenger
    dim_passenger = passengers.copy()
    dim_passenger = dim_passenger.drop_duplicates(subset=['passenger_id'])
    
    return dim_flight, dim_passenger

def create_facts(flights, bookings, payments, dim_flight):
    logging.info("Creating Fact Tables and Calculating KPIs...")
    
    # 1. Fact_Bookings (Enriched with flight details for easier Power BI slicing)
    fact_bookings = bookings.merge(
        dim_flight[['flight_id', 'airline', 'source', 'destination', 'calculated_duration_hours']], 
        on='flight_id', 
        how='left'
    )
    
    # Calculate Booking KPIs
    # Anomaly/Delay Flag: If the flight duration is > 4 hours, flag it as a potential long-haul/anomaly
    fact_bookings['is_long_haul_anomaly'] = fact_bookings['calculated_duration_hours'].apply(lambda x: 'Yes' if pd.notna(x) and x > 4.0 else 'No')
    
    # 2. Fact_Payments
    fact_payments = payments.copy()
    
    # Filter out invalid/NaN amounts for revenue calculations
    fact_payments['is_valid_payment'] = fact_payments['amount'].notna()
    
    return fact_bookings, fact_payments

def calculate_aggregate_kpis(fact_bookings, fact_payments, dim_flight):
    logging.info("Calculating Aggregate Business KPIs...")
    
    # 1. Average Flight Duration by Airline
    avg_duration_airline = dim_flight.groupby('airline')['calculated_duration_hours'].mean().reset_index()
    avg_duration_airline.columns = ['airline', 'avg_duration_hours']
    
    # 2. Route-wise Traffic (Total Bookings per Route)
    route_traffic = fact_bookings.groupby(['source', 'destination']).size().reset_index(name='total_bookings')
    
    # 3. Airline Distribution (Market Share based on total flights operated)
    airline_distribution = dim_flight['airline'].value_counts().reset_index()
    airline_distribution.columns = ['airline', 'total_flights_operated']
    
    # 4. Cancellation/Delay Rate by Airline
    cancellation_rate = fact_bookings.groupby('airline')['status'].apply(lambda x: (x == 'CANCELLED').sum() / len(x) * 100).reset_index()
    cancellation_rate.columns = ['airline', 'cancellation_rate_pct']
    
    return avg_duration_airline, route_traffic, airline_distribution, cancellation_rate

def save_to_gold(dim_flight, dim_passenger, fact_bookings, fact_payments, kpis):
    logging.info("Saving Gold layer tables...")
    
    dim_flight.to_parquet(os.path.join(GOLD_DIR, "dim_flight.parquet"), index=False)
    dim_passenger.to_parquet(os.path.join(GOLD_DIR, "dim_passenger.parquet"), index=False)
    fact_bookings.to_parquet(os.path.join(GOLD_DIR, "fact_bookings.parquet"), index=False)
    fact_payments.to_parquet(os.path.join(GOLD_DIR, "fact_payments.parquet"), index=False)
    
    # Save KPI summary tables
    avg_duration_airline, route_traffic, airline_distribution, cancellation_rate = kpis
    avg_duration_airline.to_parquet(os.path.join(GOLD_DIR, "kpi_avg_duration_by_airline.parquet"), index=False)
    route_traffic.to_parquet(os.path.join(GOLD_DIR, "kpi_route_traffic.parquet"), index=False)
    airline_distribution.to_parquet(os.path.join(GOLD_DIR, "kpi_airline_distribution.parquet"), index=False)
    cancellation_rate.to_parquet(os.path.join(GOLD_DIR, "kpi_cancellation_rate.parquet"), index=False)
    
    logging.info("✅ Gold layer saved successfully!")

if __name__ == "__main__":
    try:
        print("🚀 Starting Phase 4: Gold Layer Data Modeling & KPI Calculation...")
        
        # Load
        flights, bookings, payments, passengers = load_silver_data()
        
        # Transform & Model
        dim_flight, dim_passenger = create_dimensions(flights, passengers)
        fact_bookings, fact_payments = create_facts(flights, bookings, payments, dim_flight)
        
        # Calculate KPIs
        kpis = calculate_aggregate_kpis(fact_bookings, fact_payments, dim_flight)
        
        # Save
        save_to_gold(dim_flight, dim_passenger, fact_bookings, fact_payments, kpis)
        
        print("\n🎉 Phase 4: Gold Layer Modeling Completed Successfully!")
        print(f"📁 Check your analytical data in: {os.path.abspath(GOLD_DIR)}")
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR during Gold layer transformation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)