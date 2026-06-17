import geopandas as gpd
import numpy as np
from pathlib import Path


PARCELS_PATH = Path("data/open/flint_parcels.geojson")
OUTPUT_PATH = Path("data/open/flint_scored.parquet")


def ensure_property_value(gdf):
    # Use Land_Value + Resb_Value primarily, fall back to Assessment
    for col in ["Land_Value", "Resb_Value", "Assessment"]:
        if col not in gdf.columns:
            gdf[col] = 0

    gdf["property_value"] = (
        gdf["Land_Value"].fillna(0) +
        gdf["Resb_Value"].fillna(0)
    )

    # If both are zero but Assessment exists, use that
    mask_zero = gdf["property_value"] <= 0
    gdf.loc[mask_zero, "property_value"] = gdf.loc[mask_zero, "Assessment"].fillna(0)

    return gdf


def derive_distress_flags(gdf):
    # Start with zeros
    gdf["is_vacant"] = 0
    gdf["is_demo"] = 0
    gdf["is_landbank"] = 0

    # Use LandUse, Use_Type, Inv22, Owner_Type if present
    cols = {c.lower(): c for c in gdf.columns}

    landuse_col = cols.get("landuse")
    usetype_col = cols.get("use_type")
    inv_col = cols.get("inv22")
    owner_col = cols.get("owner_type")

    if landuse_col:
        lu = gdf[landuse_col].astype(str).str.lower()
        gdf.loc[lu.str.contains("vacant"), "is_vacant"] = 1

    if usetype_col:
        ut = gdf[usetype_col].astype(str).str.lower()
        gdf.loc[ut.str.contains("vacant"), "is_vacant"] = 1

    if inv_col:
        inv = gdf[inv_col].astype(str).str.lower()
        gdf.loc[inv.str.contains("vacant"), "is_vacant"] = 1

    if owner_col:
        ow = gdf[owner_col].astype(str).str.lower()
        gdf.loc[ow.str.contains("land bank"), "is_landbank"] = 1

    return gdf


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


def landuse_score(row):
    lu = str(row.get("LandUse", "")).lower()
    if "res" in lu or "residential" in lu:
        return 90
    if "vacant" in lu or "grass" in lu or "park" in lu:
        return 80
    if "com" in lu or "commercial" in lu:
        return 60
    if "ind" in lu or "industrial" in lu:
        return 30
    return 50


def zoning_score(row):
    z = str(row.get("Zoning", "")).upper()
    if z.startswith("R"):
        return 85
    if z.startswith("C"):
        return 60
    if z.startswith("I"):
        return 35
    return 50


def value_gradient_score(idx, gdf_3857):
    row = gdf_3857.iloc[idx]
    centroid = row.geometry.centroid
    buffer = centroid.buffer(150)  # ~150m

    neighbors = gdf_3857[gdf_3857.geometry.intersects(buffer)]
    if neighbors.empty:
        return 50

    local_value = row["property_value"]
    neighbor_avg = neighbors["property_value"].mean()

    if neighbor_avg <= 0:
        return 50

    ratio = local_value / neighbor_avg

    if ratio < 0.3:
        return 95
    if ratio < 0.5:
        return 85
    if ratio < 0.8:
        return 70
    return 40


def distress_adjacency_score(idx, gdf_3857):
    row = gdf_3857.iloc[idx]
    centroid = row.geometry.centroid
    buffer = centroid.buffer(100)

    neighbors = gdf_3857[gdf_3857.geometry.intersects(buffer)]
    if neighbors.empty:
        return 50

    distress_count = neighbors["is_vacant"].sum()
    total = len(neighbors)

    if total == 0:
        return 50

    pct = distress_count / total

    if pct > 0.5:
        return 90
    if pct > 0.3:
        return 75
    if pct > 0.15:
        return 60
    return 40


def main():
    print("Loading parcels from:", PARCELS_PATH)
    gdf = gpd.read_file(PARCELS_PATH)

    # Ensure CRS and geometry
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)

    # Work in 3857 for distance/area
    gdf_3857 = gdf.to_crs(3857)

    # Property value + distress flags
    gdf_3857 = ensure_property_value(gdf_3857)
    gdf_3857 = derive_distress_flags(gdf_3857)

    # Area in sqft
    gdf_3857["area_sqft"] = gdf_3857.geometry.area * 10.7639

    size_scores = []
    lu_scores = []
    zon_scores = []
    valgrad_scores = []
    distress_scores = []
    build_scores = []

    print("Scoring parcels...")
    for idx, row in gdf_3857.iterrows():
        s_size = parcel_size_score(row["area_sqft"])
        s_lu = landuse_score(row)
        s_z = zoning_score(row)
        s_vg = value_gradient_score(idx, gdf_3857)
        s_da = distress_adjacency_score(idx, gdf_3857)

        buildability = (
            s_size * 0.20 +
            s_lu * 0.15 +
            s_z * 0.15 +
            s_vg * 0.30 +
            s_da * 0.20
        )

        size_scores.append(s_size)
        lu_scores.append(s_lu)
        zon_scores.append(s_z)
        valgrad_scores.append(s_vg)
        distress_scores.append(s_da)
        build_scores.append(buildability)

    gdf_3857["size_score"] = size_scores
    gdf_3857["landuse_score"] = lu_scores
    gdf_3857["zoning_score"] = zon_scores
    gdf_3857["value_gradient_score"] = valgrad_scores
    gdf_3857["distress_adjacency_score"] = distress_scores
    gdf_3857["buildability_score"] = build_scores

    # Back to 4326 for lat/lon
    gdf_4326 = gdf_3857.to_crs(4326)
    centroids = gdf_4326.geometry.centroid
    gdf_4326["lon"] = centroids.x
    gdf_4326["lat"] = centroids.y

    print("Saving scored parcels to:", OUTPUT_PATH)
    gdf_4326.to_parquet(OUTPUT_PATH, index=False)
    print("Done.")


if __name__ == "__main__":
    main()
