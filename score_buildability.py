import geopandas as gpd
import pandas as pd
import numpy as np

# -----------------------------
# Load datasets
# -----------------------------

print("Loading parcels...")
parcels = gpd.read_file("data/open/flint_parcels.geojson").to_crs(3857)

print("Loading Flint landuse...")
landuse = gpd.read_file("data/open/flint_landuse.geojson").to_crs(3857)

print("Loading OSM buildings...")
osm_bld = gpd.read_file("data/open/flint_osm_buildings.geojson").to_crs(3857)

print("Loading Microsoft buildings...")
ms_bld = gpd.read_file("data/open/flint_ms_buildings.geojson").to_crs(3857)

# -----------------------------
# Helper functions
# -----------------------------

def parcel_size_score(area_sqft):
    if area_sqft < 1500:
        return 10
    if area_sqft < 3000:
        return 40
    if area_sqft < 10000:
        return 90
    if area_sqft < 20000:
        return 70
    return 40


def landuse_score(parcel_geom, landuse_gdf):
    intersecting = landuse_gdf[landuse_gdf.intersects(parcel_geom)]

    if intersecting.empty:
        return 50

    lu = intersecting.iloc[0].get("fclass", "").lower()

    if "residential" in lu:
        return 90
    if "grass" in lu or "meadow" in lu or "vacant" in lu:
        return 80
    if "commercial" in lu:
        return 60
    if "industrial" in lu:
        return 30

    return 50


def building_presence_score(parcel_geom, osm_bld, ms_bld):
    osm_hit = osm_bld[osm_bld.intersects(parcel_geom)]
    ms_hit = ms_bld[ms_bld.intersects(parcel_geom)]

    if not osm_hit.empty or not ms_hit.empty:
        return 20
    return 90


def nearest_distance_score(parcel_geom, buildings_gdf):
    if buildings_gdf.empty:
        return 50

    centroid = parcel_geom.centroid

    sindex = buildings_gdf.sindex

    # nearest() returns a numpy array → flatten it
    raw = sindex.nearest(centroid, 1)

    # raw might be: array([1234]) or array([[1234]])
    flat = np.array(raw).flatten()

    nearest_idx = int(flat[0])

    nearest_geom = buildings_gdf.geometry.iloc[nearest_idx]

    dist = float(centroid.distance(nearest_geom))

    if dist < 20:
        return 90
    if dist < 50:
        return 80
    if dist < 100:
        return 60
    if dist < 200:
        return 40
    return 20

# -----------------------------
# Compute Buildability Score
# -----------------------------

scores = []

print("Scoring parcels...")

for idx, row in parcels.iterrows():
    geom = row.geometry
    area = geom.area
    area_sqft = area * 10.7639

    s_size = parcel_size_score(area_sqft)
    s_land = landuse_score(geom, landuse)
    s_bld = building_presence_score(geom, osm_bld, ms_bld)
    s_dist = nearest_distance_score(geom, ms_bld)

    buildability = (
        s_size * 0.30 +
        s_land * 0.25 +
        s_bld * 0.25 +
        s_dist * 0.20
    )

    scores.append(buildability)

parcels["buildability_score"] = scores

# -----------------------------
# Dashboard
# -----------------------------

print("\n--- Buildability Dashboard ---")
print("Total parcels processed:", len(parcels))
print("Average score:", round(parcels["buildability_score"].mean(), 2))
print("Min score:", round(parcels["buildability_score"].min(), 2))
print("Max score:", round(parcels["buildability_score"].max(), 2))

print("\nScore distribution:")
print(parcels["buildability_score"].describe())

# -----------------------------
# Top 50 Parcels Export
# -----------------------------

print("\nExporting Top 50 parcels...")

top50 = parcels.sort_values("buildability_score", ascending=False).head(50)

top50_csv = "data/open/top50_parcels.csv"
top50_geojson = "data/open/top50_parcels.geojson"

top50.to_csv(top50_csv, index=False)
top50.to_crs(4326).to_file(top50_geojson, driver="GeoJSON")

print("Top 50 CSV:", top50_csv)
print("Top 50 GeoJSON:", top50_geojson)

# -----------------------------
# Save outputs (two versions)
# -----------------------------

print("\nSaving full outputs...")

output_3857 = "data/open/flint_parcels_scored_3857.geojson"
parcels.to_file(output_3857, driver="GeoJSON")

output_4326 = "data/open/flint_parcels_scored_4326.geojson"
parcels.to_crs(4326).to_file(output_4326, driver="GeoJSON")

print("Saved:")
print(" - Analysis version:", output_3857)
print(" - Web-ready version:", output_4326)
print("\nAll tasks complete.")



