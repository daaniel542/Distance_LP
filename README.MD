# 🛫 Lane Distance Calculator

A logistics application that calculates direct (crow-flight) distances between cities for shipping lane analysis.

## 🚀 Features

- **Geocoding with Caching**: Efficiently geocodes city locations with SQLite caching
- **Rate-Limited API Calls**: Respects geocoding service limits
- **Multiple Input Formats**: Supports Excel (.xlsx, .xls) and CSV files

## 📋 Input Format

Your input file should have at least 2 columns:

| Origin | Destination | Shipments (Optional) |
|--------|-------------|---------------------|
| New York, US | Los Angeles, US | 150 |
| London, GB | Paris, FR | 89 |
| Tokyo, JP | Seoul, KR | 234 |

**City Format**: `City Name, Country Code`
- City names should be spelled out (e.g., "New York", "Los Angeles")
- Country codes should be 2-letter ISO codes (e.g., "US", "GB", "FR")

## 🛠️ Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   