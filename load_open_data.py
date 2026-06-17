import geopandas as gpd

# Paths to your data
osm_landuse = "data/open/gis_osm_landuse_a_free_1.shp"
osm_buildings = "data/open/gis_osm_buildings_a_free_1.shp"
microsoft_buildings = "data/open/Michigan.geojson"

# Correct Michigan Places file (FIPS 26)
places = "data/open/places/tl_2024_26_place/tl_2024_26_place.shp"

print("Loading Flint boundary...")
places_gdf = gpd.read_file(places)

# Filter to Flint
flint = places_gdf[places_gdf['NAME'] == 'Flint'].to_crs(3857)

print("Loading OSM land polygons...")
landuse = gpd.read_file(osm_landuse).to_crs(3857)
landuse_flint = gpd.overlay(landuse, flint, how='intersection')

print("Loading OSM buildings...")
osm_bld = gpd.read_file(osm_buildings).to_crs(3857)
osm_bld_flint = gpd.overlay(osm_bld, flint, how='intersection')

print("Loading Microsoft buildings...")
ms_bld = gpd.read_file(microsoft_buildings).to_crs(3857)
ms_bld_flint = gpd.overlay(ms_bld, flint, how='intersection')

print("Saving clipped datasets...")
landuse_flint.to_file("data/open/flint_landuse.geojson")
osm_bld_flint.to_file("data/open/flint_osm_buildings.geojson")
ms_bld_flint.to_file("data/open/flint_ms_buildings.geojson")

print("Done.")