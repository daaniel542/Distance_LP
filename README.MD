# 🛫 Lane Distance Calculator
This application calculates direct, “as-the-crow-flies” distances between cities for logistics and lane analysis.

Primary Method: The app uses official UNLOCODEs to determine locations and compute the most accurate distances possible.

Automatic Fallback: If a UNLOCODE match is not available, the app automatically falls back to the Mapbox Geocoding API for location lookup and distance calculation.

Accuracy Note: Results using UNLOCODEs are the most accurate. When the Mapbox fallback is used, distances may vary by approximately in the range of ± 1-20 miles due to geocoding limitations.

## 🚀 Features

- **Geocoding with Caching**: Efficiently geocodes city locations with SQLite caching
- **Multiple Input Formats**: Supports Excel (.xlsx, .xls) and CSV files

## 📋 Input Format

Your input file must have at least 2 columns, Origin and Destination. However using providing Origin and Destination LOCODEs will greatly improve accuracy:


| Origin       | Destination     | Origin LOCODE | Dest LOCODE |  
| ------------ | --------------- | -------------- | ------------ |  
| New York, US | Los Angeles, US | USNYC          | USLAX        |  
| London, GB   | Paris, FR       | GBLON          | FRPAR        |  
| Tokyo, JP    | Seoul, KR       | JPTYO          | KRSEL        | 


**City Format**: `City Name, Country Code`
- City names should be spelled out (e.g., "New York", "Los Angeles")
- Country codes should be 2-letter ISO codes (e.g., "US", "GB", "FR")
- Input format must be exactly similar to the example input provided above, or the app will not run as expected!

## 🛠️ Installation
To run locally:
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   
## 📋 Sample Outpupt

| Origin         | Destination      | Origin LOCODE | Destination LOCODE | Origin latitude | Origin longitude | Destination latitude | Destination longitude | Distance_miles | Used UNLOCODEs | Ambiguous Origin | Ambiguous Destination | Error_msg |
|----------------|------------------|---------------|--------------------|-----------------|------------------|----------------------|-----------------------|----------------|----------------|------------------|-----------------------|-----------|
| New York, US   | Los Angeles, US  | USNYC         | USLAX              | 40.700000       | -74.0000         | 34.050000            | -118.250000           | 2446.348553    | True           |                  |                       |           |
| London, GB     | Paris, FR        | GBLON         | FRPAR              | 51.507400       | -0.1278          | 48.850000            | 2.350000              | 213.823477     | True           |                  |                       |           |
| Tokyo, JP      | Seoul, KR        | JPTYO         | KRSEL              | 35.683333       | 139.7500         | 37.516667            | 126.933333            | 721.536981     | True           |                  |                       |           |

## API Stuff
The geocoding uses Mapbox data. See details regarding using their API servers. To implement this, create and store API Token into an .env file within the home directory, Distance_LP.
