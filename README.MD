# 🛫 Lane Distance Calculator

A logistics application that calculates direct (crow-flight) distances between cities for shipping lane analysis.

The app will calculate distances using UNLOCODEs, however if it's unable to calculate them, it will use MAPBOX API to calculate with Geocoding formulas.

The most accurate calculations will be from the UNLOCODES. 
Expect at least an ±20 miles when using MAPBOX API for calculations

## 🚀 Features

- **Geocoding with Caching**: Efficiently geocodes city locations with SQLite caching
- **Multiple Input Formats**: Supports Excel (.xlsx, .xls) and CSV files

## 📋 Input Format

Your input file should have at least 2 columns:

| Origin       | Destination     | Origin LOCODE | Dest LOCODE |  
| ------------ | --------------- | -------------- | ------------ |  
| New York, US | Los Angeles, US | USNYC          | USLAX        |  
| London, GB   | Paris, FR       | GBLON          | FRPAR        |  
| Tokyo, JP    | Seoul, KR       | JPTYO          | KRSEL        | 


**City Format**: `City Name, Country Code`
- City names should be spelled out (e.g., "New York", "Los Angeles")
- Country codes should be 2-letter ISO codes (e.g., "US", "GB", "FR")

## 🛠️ Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   
## 📋 Sample Outpupt

| Origin         | Destination      | Origin LOCODE | Destination LOCODE | Origin latitude | Origin longitude | Destination latitude | Destination longitude | Distance_miles | Used UNLOCODEs | Ambiguous Origin | Ambiguous Destination | Error_msg |
|----------------|------------------|---------------|--------------------|-----------------|------------------|----------------------|-----------------------|----------------|----------------|------------------|-----------------------|-----------|
| New York, US   | Los Angeles, US  | USNYC         | USLAX              | 40.700000       | -74.0000         | 34.050000            | -118.250000           | 2446.348553    | True           |                  |                       |           |
| London, GB     | Paris, FR        | GBLON         | FRPAR              | 51.507400       | -0.1278          | 48.850000            | 2.350000              | 213.823477     | True           |                  |                       |           |
| Tokyo, JP      | Seoul, KR        | JPTYO         | KRSEL              | 35.683333       | 139.7500         | 37.516667            | 126.933333            | 721.536981     | True           |                  |                       |           |

