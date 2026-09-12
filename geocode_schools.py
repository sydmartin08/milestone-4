"""
Geocode all 48 NAIA Women's Wrestling schools to add latitude and longitude.
"""

import csv
import urllib.request
import urllib.parse
import json
import time

def geocode(query):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'NAIA-Wrestling-Student-Research/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Error geocoding '{query}': {e}")
    return None, None

def main():
    with open('data/naia_women_programs.csv', 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

    total = len(reader)
    print(f"Geocoding {total} schools...")
    
    for i, row in enumerate(reader, 1):
        query1 = f"{row['school']}, {row['city']}, {row['state']}"
        lat, lon = geocode(query1)
        if not lat:
            query2 = f"{row['city']}, {row['state']}, USA"
            lat, lon = geocode(query2)
        
        row['latitude'] = lat if lat else ""
        row['longitude'] = lon if lon else ""
        print(f"[{i}/{total}] {row['school']}: ({lat}, {lon})")
        time.sleep(1.0) # Respect OSM Nominatim usage policy

    fieldnames = ['school', 'city', 'state', 'conference', 'latitude', 'longitude']
    with open('data/naia_women_programs.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reader)

    print("Successfully updated data/naia_women_programs.csv with coordinates!")

if __name__ == '__main__':
    main()
