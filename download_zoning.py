import requests
import json
import math

URL = "https://services5.arcgis.com/1wJx5z9Yf2tZq0jS/ArcGIS/rest/services/City_of_Flint_Zoning/FeatureServer/0/query"

count_params = {
    "where": "1=1",
    "returnCountOnly": "true",
    "f": "json"
}

print("Requesting zoning count...")
count_response = requests.get(URL, params=count_params)
count_json = count_response.json()

total = count_json["count"]
print(f"Total zoning features: {total}")

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
    data = r.json()
    all_features.extend(data["features"])

geojson = {
    "type": "FeatureCollection",
    "features": all_features
}

with open("flint_zoning.geojson", "w", encoding="utf-8") as f:
    json.dump(geojson, f)

print("Saved flint_zoning.geojson")