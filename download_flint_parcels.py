import requests
import json
import math

# Flint Parcel FeatureServer Layer
URL = "https://services5.arcgis.com/lqqWNtSxx8Akj04A/arcgis/rest/services/Main_COF_Parcel_view/FeatureServer/0/query"

# -----------------------------------------
# STEP 1 — Get total parcel count
# -----------------------------------------

count_params = {
    "where": "1=1",
    "returnCountOnly": "true",
    "f": "json"
}

print("Requesting parcel count...")
count_response = requests.get(URL, params=count_params)

if count_response.status_code != 200:
    print("Error requesting count:", count_response.text)
    raise SystemExit

count_json = count_response.json()

if "count" not in count_json:
    print("Server did not return a count. Full response:")
    print(count_response.text)
    raise SystemExit

total = count_json["count"]
print(f"Total parcels: {total}")

# -----------------------------------------
# STEP 2 — Download parcels in batches
# -----------------------------------------

batch_size = 2000
batches = math.ceil(total / batch_size)

all_features = []

for i in range(batches):
    print(f"Downloading batch {i+1} of {batches}...")

    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultOffset": i * batch_size,
        "resultRecordCount": batch_size
    }

    r = requests.get(URL, params=params)

    if r.status_code != 200:
        print("Error downloading batch:", r.text)
        break

    data = r.json()

    if "features" not in data:
        print("Batch missing 'features'. Full response:")
        print(r.text)
        break

    all_features.extend(data["features"])

print(f"Downloaded {len(all_features)} total features.")

# -----------------------------------------
# STEP 3 — Save final GeoJSON
# -----------------------------------------

geojson = {
    "type": "FeatureCollection",
    "features": all_features
}

output_path = "flint_parcels.geojson"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(geojson, f)

print(f"Saved {output_path} with {len(all_features)} parcels.")