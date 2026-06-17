import pandas as pd

# ---- 1. Your cost assumptions (you can tweak these) ----
ROWHOUSE_COST_PER_SQFT = 140
STACKED_FLATS_COST_PER_SQFT = 170
MIXED_USE_COST_PER_SQFT = 210
COTTAGE_COURT_COST_PER_SQFT = 150

LAND_BANK_DISCOUNT = 0.3   # 30% of assessed improvement value
PRIVATE_DISCOUNT = 0.8     # 80% of assessed improvement value
DEMO_COST_PER_SQFT = 10    # rough demo cost

# ---- 2. Fake parcel data for now ----
data = [
    {
        "parcel_id": "P1",
        "owner_type": "land_bank",   # or "private"
        "land_value": 5000,
        "improvement_value": 10000,
        "improved_sqft": 800,        # existing building size
        "lot_sqft": 4800,
        "typology": "rowhouse"       # rowhouse, stacked_flats, mixed_use, cottage_court
    },
    {
        "parcel_id": "P2",
        "owner_type": "private",
        "land_value": 8000,
        "improvement_value": 2000,
        "improved_sqft": 400,
        "lot_sqft": 6000,
        "typology": "mixed_use"
    },
]

df = pd.DataFrame(data)

# ---- 3. Helper functions ----

def estimate_acquisition_cost(row):
    if row["owner_type"] == "land_bank":
        discount = LAND_BANK_DISCOUNT
    else:
        discount = PRIVATE_DISCOUNT

    discounted_improvement = row["improvement_value"] * discount
    return row["land_value"] + discounted_improvement

def estimate_demo_cost(row):
    if row["improved_sqft"] > 0:
        return row["improved_sqft"] * DEMO_COST_PER_SQFT
    return 0

def estimate_buildable_area(row):
    footprint = row["lot_sqft"] * 0.4
    stories = 2
    return footprint * stories

def get_cost_per_sqft_for_typology(typology):
    if typology == "rowhouse":
        return ROWHOUSE_COST_PER_SQFT
    if typology == "stacked_flats":
        return STACKED_FLATS_COST_PER_SQFT
    if typology == "mixed_use":
        return MIXED_USE_COST_PER_SQFT
    if typology == "cottage_court":
        return COTTAGE_COURT_COST_PER_SQFT
    return ROWHOUSE_COST_PER_SQFT

def estimate_build_cost(row):
    buildable_area = estimate_buildable_area(row)
    cost_per_sqft = get_cost_per_sqft_for_typology(row["typology"])
    return buildable_area * cost_per_sqft

def estimate_minimum_build_price(row):
    acquisition = estimate_acquisition_cost(row)
    demo = estimate_demo_cost(row)
    build = estimate_build_cost(row)
    return acquisition + demo + build

# ---- 4. Apply the logic ----

df["acquisition_cost"] = df.apply(estimate_acquisition_cost, axis=1)
df["demo_cost"] = df.apply(estimate_demo_cost, axis=1)
df["buildable_area"] = df.apply(estimate_buildable_area, axis=1)
df["build_cost"] = df.apply(estimate_build_cost, axis=1)
df["minimum_build_price"] = df.apply(estimate_minimum_build_price, axis=1)

# ---- 5. Developer-friendly metric: cost per buildable sqft ----
df["cost_per_buildable_sqft"] = df["minimum_build_price"] / df["buildable_area"]

# ---- 6. Classification ----
def classify_cost(row):
    if row["cost_per_buildable_sqft"] < 120:
        return "cheap"
    elif row["cost_per_buildable_sqft"] < 180:
        return "moderate"
    else:
        return "expensive"

df["classification"] = df.apply(classify_cost, axis=1)

print(df[["parcel_id", "minimum_build_price", "cost_per_buildable_sqft", "classification"]])

