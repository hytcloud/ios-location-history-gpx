# iOS Location History to GPX Converter
Convert your exported iOS location history (JSON format) into GPX files for mapping, analysis, or travel visualization. Supports single-day or multi-day batch processing, timezone adjustment, and place name caching via Google Maps API.

## Installation
Clone the repository and navigate to the script directory:
```bash
git clone https://github.com/hytcloud/ios-location-gpx.git
cd ios-location-gpx
```
Ensure the following prerequisites are met:
- Python 3.7+ installed on your system
- Required Python packages installed via:
```bash
pip install -r requirements.txt
```
- A valid Google Maps API key for place name lookup
Replace the placeholder in the script:
```python
api_key = "YOUR_API_KEY"
```
with your actual API key from [Google Cloud Console](https://console.cloud.google.com/)
To verify the script runs correctly, try:
```bash
python locate.py --date 2025-04-01 --input location-history.json
```
GPX files will be generated in the current directory with filenames like
```
output_2025-04-01_with_fallback.gpx
```
For multi-day export:
```bash
python locate.py --range 2025-04-01:2025-04-07
```

**Usage**
```py
  locate.py [-d DATE | -r RANGE] [-i INPUT] [-t TIMEZONE] [-nc] [-v]
```

**Options**
- -h, --help                Show this help message and exit
- -d DATE, --date DATE      Target date in YYYY-MM-DD format (e.g. 2025-04-01)
- -r RANGE, --range RANGE   Date range in format YYYY-MM-DD:YYYY-MM-DD (inclusive)
- -i INPUT, --input INPUT   Path to location history JSON file (default: location-history.json)
- -t TIMEZONE, --timezone TIMEZONE Timezone offset in hours from UTC (default: 8 for Taiwan)
- -nc, --nocache            Disable place name cache (always query Google API)
- -v, --verbose             Show detailed processing output (for debugging or inspection)
  
**Notes**
- You must specify either --date or --range.
- Place name lookup requires a valid Google Maps API key.
- Be sure to replace the placeholder in the script: api_key = "YOUR_API_KEY"
- with your actual API key from Google Cloud Console.
- Output GPX files are automatically named as: output_<date>_with_fallback.gpx