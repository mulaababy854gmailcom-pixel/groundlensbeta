@st.cache_data(show_spinner=True)
def load_scored_parcels():
    url = "https://github.com/mulaababy854gmailcom-pixel/groundlensbeta/releases/download/v1.0.0/flint_scored.parquet"
    df = pd.read_parquet(url)

    for col in [
        "property_value",
        "buildability_score",
        "value_gradient_score",
        "distress_adjacency_score",
        "lat",
        "lon",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["suppression_index"] = (
        df["value_gradient_score"] * 0.6 +
        df["distress_adjacency_score"] * 0.4
    )

    if "CenTract" not in df.columns:
        df["CenTract"] = "Unknown"
    if "Ward" not in df.columns:
        df["Ward"] = "Unknown"

    return df
