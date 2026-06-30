import streamlit as st
import pandas as pd
import numpy as np
import json
import pydeck as pdk
from shapely.geometry import shape

# =========================
# PAGE CONFIG + THEME
# =========================

st.set_page_config(page_title="Flint Parcel Atlas", layout="wide", page_icon=None)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace;
}

.stApp {
    background-color: #EDE7D9;
    color: #1B1B16;
}

section[data-testid="stSidebar"] {
    background-color: #1F2E3D;
    color: #EDE7D9;
}
section[data-testid="stSidebar"] * {
    color: #EDE7D9 !important;
}
section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {
    color: #B5562F;
}

h1, h2, h3 {
    font-family: 'IBM Plex Serif', serif !important;
    color: #1F2E3D;
    letter-spacing: -0.01em;
}

.atlas-eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #B5562F;
    font-weight: 600;
    margin-bottom: -0.4rem;
}

.atlas-rule {
    border: none;
    border-top: 1px solid #C9C0A8;
    margin: 1.1rem 0 1.3rem 0;
}

/* card-style metrics, assessor-card look */
.parcel-card {
    background-color: #FAF7EE;
    border: 1px solid #C9C0A8;
    border-left: 4px solid #B5562F;
    padding: 0.9rem 1.1rem;
    border-radius: 2px;
    margin-bottom: 0.7rem;
}
.parcel-card .label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #5C5848;
    font-weight: 600;
}
.parcel-card .value {
    font-family: 'IBM Plex Serif', serif;
    font-size: 1.55rem;
    color: #1F2E3D;
    font-weight: 600;
    margin-top: 0.1rem;
}

/* the "stamp" badge for buildability score */
.stamp-wrap {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    padding: 0.6rem 0 0.4rem 0;
}
.stamp {
    width: 86px;
    height: 86px;
    border-radius: 50%;
    border: 3px solid #B5562F;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    transform: rotate(-6deg);
    font-family: 'IBM Plex Mono', monospace;
    color: #B5562F;
    background: repeating-radial-gradient(circle, #FAF7EE 0px, #FAF7EE 2px);
}
.stamp .score-num {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1;
}
.stamp .score-lbl {
    font-size: 0.5rem;
    letter-spacing: 0.08em;
    margin-top: 2px;
}

div[data-testid="stMetric"] {
    background-color: #FAF7EE;
    border: 1px solid #C9C0A8;
    border-left: 3px solid #2C4A6E;
    padding: 0.7rem 0.9rem 0.5rem 0.9rem;
    border-radius: 2px;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5C5848 !important;
}
div[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Serif', serif !important;
    color: #1F2E3D !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    font-size: 0.78rem;
    letter-spacing: 0.06em;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================
# CORE FINANCE HELPERS
# =========================

def calc_monthly_pni(principal, annual_rate, years):
    if principal <= 0 or annual_rate <= 0:
        return 0
    monthly_rate = annual_rate / 12
    num_payments = years * 12
    return principal * (monthly_rate * (1 + monthly_rate) ** num_payments) / (
        (1 + monthly_rate) ** num_payments - 1
    )


# ================================
# DATA LOADING + SCORING (cached together, computed once)
# ================================

def _safe_col(df, col, default=0):
    """Return a column if present, else a same-length default series. Lets the
    scorer degrade gracefully if crime/school/utility data hasn't been joined
    into the geojson yet, instead of crashing."""
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


@st.cache_data(show_spinner="Loading parcel atlas\u2026")
def load_scored_parcels():
    with open("flint_parcels_scored.geojson", "r") as f:
        data = json.load(f)

    records = []
    for feature in data["features"]:
        props = dict(feature["properties"])
        props["geometry"] = shape(feature["geometry"])
        records.append(props)

    df = pd.DataFrame(records)

    # ---- Property value (Michigan: SEV * 2, fallback to land + structure) ----
    if "property_value" not in df.columns:
        df["property_value"] = _safe_col(df, "HomeSEV") * 2
    missing_mask = df["property_value"].isna() | (df["property_value"] == 0)
    df.loc[missing_mask, "property_value"] = _safe_col(df, "Land_Value") + _safe_col(df, "Resb_Value")

    # ---- Suppression index: is this parcel undervalued relative to its context? ----
    ecf = _safe_col(df, "ECF", default=1.0)
    df["suppression_index"] = np.clip((1 - ecf), 0, 1) * 30

    df["value_ratio"] = _safe_col(df, "Resb_Value") / (_safe_col(df, "Land_Value") + 1)
    df["suppression_index"] += np.clip((1 - df["value_ratio"]), 0, 1) * 20

    year_built = _safe_col(df, "Year_Built", default=1950)
    df["suppression_index"] += np.clip((1950 - year_built) / 100, 0, 1) * 15
    df["suppression_index"] += _safe_col(df, "QCTs", default=False).apply(lambda x: 15 if x else 0)
    df["suppression_index"] += _safe_col(df, "Rental", default=False).apply(lambda x: 10 if x else 0)
    df["suppression_index"] += _safe_col(df, "Inv22", default=False).apply(lambda x: 10 if x else 0)
    df["suppression_index"] = np.clip(df["suppression_index"], 0, 100)

    # ---- Proximity-to-value gradient: nearby higher-value parcels within ~1-2 min drive ----
    # Approximate "1-2 minutes" as a ~0.5 mile radius using a simple grid-cell lookup on
    # centroid coordinates, since this is far cheaper than a real routing call per parcel
    # and good enough for a fringe-opportunity screen.
    df["centroid"] = df["geometry"].apply(lambda g: g.centroid)
    df["cx"] = df["centroid"].apply(lambda c: c.x)
    df["cy"] = df["centroid"].apply(lambda c: c.y)

    if "nearby_avg_value" in df.columns:
        nearby_avg_value = df["nearby_avg_value"]
    else:
        # Coarse spatial bucket (~0.5mi grid cells) -> mean property value per bucket,
        # used as a stand-in for "value of the surrounding pocket" until a real
        # drive-time isochrone join is available.
        bucket_size = 0.007  # roughly 0.5 mile in decimal degrees at this latitude
        df["_bx"] = (df["cx"] / bucket_size).round()
        df["_by"] = (df["cy"] / bucket_size).round()
        bucket_means = df.groupby(["_bx", "_by"])["property_value"].transform("mean")
        nearby_avg_value = bucket_means
        df.drop(columns=["_bx", "_by"], inplace=True)

    df["nearby_avg_value"] = nearby_avg_value
    df["value_gap_pct"] = np.where(
        df["nearby_avg_value"] > 0,
        np.clip(1 - (df["property_value"] / df["nearby_avg_value"]), 0, 1),
        0,
    )

    # ---- Crime, schools, utilities: join if present, else neutral default ----
    df["crime_score"] = _safe_col(df, "crime_index", default=50)        # 0 (high crime) - 100 (low crime), expects pre-normalized input
    df["school_score"] = _safe_col(df, "school_rating_20min", default=50)  # 0-100, avg rating of schools within 20 min drive
    df["utility_score"] = _safe_col(df, "utilities_present", default=True).apply(
        lambda x: 100 if x else 0
    )

    # ---- Composite buildability score ----
    # Weighted blend: physical buildability (if already computed upstream) plus the
    # opportunity signals requested: suppression, proximity value-gap, crime, schools, utilities.
    base_buildability = _safe_col(df, "buildability_score", default=50)
    df["buildability_score"] = (
        base_buildability.clip(0, 100) * 0.35
        + df["suppression_index"] * 0.20
        + df["value_gap_pct"] * 100 * 0.15
        + df["crime_score"] * 0.10
        + df["school_score"] * 0.10
        + df["utility_score"] * 0.10
    ).clip(0, 100)

    # ---- Geometry prep, done once here instead of per-render ----
    df["polygon"] = df["geometry"].apply(lambda g: list(g.exterior.coords))
    df["build_norm"] = (
        (df["buildability_score"] - df["buildability_score"].min())
        / max(1e-9, (df["buildability_score"].max() - df["buildability_score"].min()))
    )
    df["color"] = df["build_norm"].apply(build_color)

    return df


def build_color(score):
    """Maps 0-1 score to a blueprint-navy -> rust-copper ramp instead of a default
    red/yellow heat scale, to match the rest of the visual system."""
    navy = np.array([44, 74, 110])
    rust = np.array([181, 86, 47])
    rgb = navy + (rust - navy) * score
    return [int(rgb[0]), int(rgb[1]), int(rgb[2]), 190]


# =========================
# SESSION STATE HELPERS
# =========================

def init_session_state():
    defaults = {
        "selected_pid": None,
        "selected_row": None,
        "purchase_price": 85000,
        "rehab_cost": 45000,
        "arv_flip": 175000,
        "arv_brrrr": 175000,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def set_selected_parcel(row):
    st.session_state["selected_pid"] = row.get("PIDText")
    st.session_state["selected_row"] = row.to_dict()

    pv = float(row.get("property_value", 0) or 0)
    st.session_state["purchase_price"] = max(1000, round(pv))
    st.session_state["rehab_cost"] = max(0, round(pv * 0.5))


init_session_state()

# =========================
# HEADER
# =========================

st.markdown('<div class="atlas-eyebrow">Genesee County &middot; Flint, MI</div>', unsafe_allow_html=True)
st.title("Flint Parcel Atlas")
st.caption("Pro forma modeling and buildability scoring for fringe-opportunity parcels")
st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)

tab_proforma, tab_buildability = st.tabs(["Pro Forma", "Buildability Atlas"])


# =========================
# TAB 1: PRO FORMA ENGINE
# =========================

with tab_proforma:
    st.sidebar.markdown('<div class="atlas-eyebrow">Step 1</div>', unsafe_allow_html=True)
    st.sidebar.header("Strategy & Acquisition")
    strategy = st.sidebar.selectbox("Investment Strategy", ["Flip", "Rent", "BRRRR"])

    purchase_price = st.sidebar.number_input(
        "Purchase Price ($)",
        value=int(st.session_state["purchase_price"]),
        step=5000,
        key="purchase_price_input",
    )

    if strategy in ["Flip", "BRRRR"]:
        rehab_cost = st.sidebar.number_input(
            "Estimated Rehab Cost ($)",
            value=int(st.session_state["rehab_cost"]),
            step=1000,
            key="rehab_cost_input",
        )
        include_rehab_in_loan = st.sidebar.checkbox("Finance Rehab? (Wrap into Initial Loan)", value=True)
        holding_months = st.sidebar.number_input("Holding Period (Months)", value=6, step=1)
        monthly_hold_costs = st.sidebar.number_input("Monthly Holding Costs ($)", value=400, step=50)
        total_holding_costs = holding_months * monthly_hold_costs
        closing_costs_sell = st.sidebar.number_input("Selling Closing Costs ($)", value=12000, step=500)
    else:
        rehab_cost = 0
        include_rehab_in_loan = False
        holding_months = 0
        monthly_hold_costs = 0
        total_holding_costs = 0
        closing_costs_sell = 0

    closing_costs_buy = st.sidebar.number_input("Purchase Closing Costs ($)", value=4000, step=500)

    st.sidebar.markdown('<div class="atlas-eyebrow">Step 2</div>', unsafe_allow_html=True)
    st.sidebar.header("Initial Financing")
    down_payment_pct = st.sidebar.slider("Down Payment % (On Financed Capital)", 0, 100, 20) / 100
    interest_rate_init = st.sidebar.number_input("Initial Interest Rate (%)", value=6.20, step=0.1) / 100
    loan_term_years = st.sidebar.number_input("Initial Loan Term (Years)", value=30, step=5)

    if include_rehab_in_loan:
        initial_loan_basis = purchase_price + rehab_cost
        down_payment_amount = initial_loan_basis * down_payment_pct
        initial_loan_amount = initial_loan_basis - down_payment_amount
        upfront_rehab_cash = 0
    else:
        initial_loan_basis = purchase_price
        down_payment_amount = purchase_price * down_payment_pct
        initial_loan_amount = purchase_price - down_payment_amount
        upfront_rehab_cash = rehab_cost

    initial_monthly_pni = calc_monthly_pni(initial_loan_amount, interest_rate_init, loan_term_years)

    if strategy in ["Rent", "BRRRR"]:
        st.subheader("Rental Income & Expenses")
        rent_col1, rent_col2 = st.columns(2)

        with rent_col1:
            gross_rent = rent_col1.number_input("Gross Monthly Rent ($)", value=1800, step=100)
            vacancy_pct = rent_col1.slider("Vacancy Rate %", 0, 20, 5) / 100
            taxes_monthly = rent_col1.number_input("Monthly Property Taxes ($)", value=200, step=25)

        with rent_col2:
            ins_monthly = rent_col2.number_input("Monthly Insurance ($)", value=100, step=25)
            pm_pct = rent_col2.slider("Property Management Fee %", 0, 15, 8) / 100
            reserves_monthly = rent_col2.number_input("Monthly Maint. & CapEx Reserves ($)", value=220, step=20)

        vacancy_loss = gross_rent * vacancy_pct
        egi = gross_rent - vacancy_loss
        pm_fees = egi * pm_pct
        total_opex = taxes_monthly + ins_monthly + pm_fees + reserves_monthly
        noi = egi - total_opex
    else:
        gross_rent, total_opex, noi, egi = 0, 0, 0, 0

    if strategy == "BRRRR":
        st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)
        st.subheader("Refinance Layer (BRRRR Debt Swap)")
        refi_col1, refi_col2 = st.columns(2)

        with refi_col1:
            arv = refi_col1.number_input(
                "After Repair Value (ARV) ($)", value=int(st.session_state["arv_brrrr"]), step=5000, key="arv_brrrr_input"
            )
            refi_ltv = refi_col1.slider("Refinance Cash-Out LTV %", 50, 90, 75) / 100

        with refi_col2:
            refi_rate = refi_col2.number_input("Refinance Interest Rate (%)", value=6.20, step=0.1) / 100
            refi_loan_amount = arv * refi_ltv
            refi_monthly_pni = calc_monthly_pni(refi_loan_amount, refi_rate, 30)
            cash_pulled_from_refi = refi_loan_amount - initial_loan_amount
    else:
        arv, refi_loan_amount, refi_monthly_pni, cash_pulled_from_refi = 0, 0, 0, 0

    if strategy == "Flip":
        st.subheader("Flip Exit Metrics")
        arv = st.number_input(
            "After Repair Value (ARV) ($)", value=int(st.session_state["arv_flip"]), step=5000, key="arv_flip_input"
        )

    st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)
    st.header(f"Master Dashboard \u2014 {strategy.upper()}")

    if strategy == "Rent":
        total_capital_invested = down_payment_amount + closing_costs_buy
        net_monthly_cash_flow = noi - initial_monthly_pni
        coc_return = (net_monthly_cash_flow * 12) / total_capital_invested if total_capital_invested > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total All-In Capital", f"${total_capital_invested:,.2f}")
        m2.metric("Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}")
        m3.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")

    elif strategy == "Flip":
        # Total project cost = purchase + rehab + buy/sell closing + holding,
        # independent of how it's financed. Profit = ARV minus total project
        # cost minus payoff of the loan balance at sale.
        total_cash_invested = down_payment_amount + upfront_rehab_cash + closing_costs_buy + total_holding_costs
        # Profit at sale = ARV minus payoff of the initial loan balance minus all cash
        # already put in minus closing costs to sell. This avoids double-subtracting
        # purchase/rehab costs that are already embedded in initial_loan_amount.
        flip_profit = arv - initial_loan_amount - total_cash_invested - closing_costs_sell
        roi = (flip_profit / total_cash_invested) * 100 if total_cash_invested > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Cash Invested", f"${total_cash_invested:,.2f}")
        m2.metric("Net Flip Profit", f"${flip_profit:,.2f}")
        m3.metric("Return on Investment (ROI)", f"{roi:.2f}%")

    elif strategy == "BRRRR":
        upfront_cash_invested = (
            down_payment_amount + upfront_rehab_cash + closing_costs_buy + total_holding_costs
        )
        net_trapped_equity = upfront_cash_invested - cash_pulled_from_refi
        final_cash_left_in_deal = max(0, net_trapped_equity)
        net_monthly_cash_flow = noi - refi_monthly_pni

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Initial Capital Outlays", f"${upfront_cash_invested:,.2f}")
        m2.metric("Net Cash Trapped In Asset", f"${final_cash_left_in_deal:,.2f}")
        m3.metric("Post-Refi Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}")

        if net_trapped_equity <= 0:
            m4.metric("Cash-on-Cash Return", "Infinite (No Cash Left)")
        else:
            coc_return = (net_monthly_cash_flow * 12) / final_cash_left_in_deal
            m4.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")


# =========================
# TAB 2: BUILDABILITY ATLAS
# =========================

with tab_buildability:
    st.markdown('<div class="atlas-eyebrow">Opportunity Radar</div>', unsafe_allow_html=True)
    st.header("Buildability Atlas")
    st.write(
        "Composite score blends physical buildability, value suppression, proximity to "
        "higher-value pockets, crime, school access, and utility availability. Surfaces "
        "fringe parcels worth a closer look."
    )

    try:
        df = load_scored_parcels()
    except FileNotFoundError:
        st.error(
            "flint_parcels_scored.geojson not found. Place the scored parcel file in the "
            "app's working directory to populate this tab."
        )
        st.stop()

    missing_signals = [
        name for name, col in [
            ("crime data", "crime_index"),
            ("school ratings", "school_rating_20min"),
            ("utility flags", "utilities_present"),
        ] if col not in df.columns
    ]
    if missing_signals:
        st.caption(
            f"Note: {', '.join(missing_signals)} not found in source data \u2014 "
            "neutral defaults used for those factors until joined."
        )

    st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)
    st.subheader("Scored Parcel Summary")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("Total Parcels", f"{len(df):,}")
    with col_b:
        st.metric("Avg Buildability", f"{df['buildability_score'].mean():.1f}")
    with col_c:
        st.metric("Avg Property Value", f"${df['property_value'].mean():,.0f}")
    with col_d:
        st.metric("Avg Suppression Index", f"{df['suppression_index'].mean():.1f}")

    st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)
    st.subheader("Parcel Map \u2014 Buildability")

    center_lat = df["cy"].mean()
    center_lon = df["cx"].mean()

    polygon_layer = pdk.Layer(
        "PolygonLayer",
        df,
        get_polygon="polygon",
        get_fill_color="color",
        get_line_color=[237, 231, 217],
        get_line_width=8,
        pickable=True,
        stroked=True,
        filled=True,
        extruded=False,
    )

    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=12, pitch=40)

    tooltip = {
        "html": """
            <b>Parcel:</b> {PIDText}<br/>
            <b>Buildability:</b> {buildability_score}<br/>
            <b>Suppression:</b> {suppression_index}<br/>
            <b>Value:</b> ${property_value}
        """,
        "style": {
            "backgroundColor": "#1F2E3D",
            "color": "#EDE7D9",
            "fontFamily": "'IBM Plex Mono', monospace",
            "fontSize": "12px",
        },
    }

    deck = pdk.Deck(
        layers=[polygon_layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/dark-v11",
        tooltip=tooltip,
    )
    st.pydeck_chart(deck)

    st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)
    st.subheader("Top 50 Parcels")

    top50 = df.sort_values("buildability_score", ascending=False).head(50)
    display_cols = [
        "buildability_score", "property_value", "suppression_index",
        "value_gap_pct", "crime_score", "school_score", "utility_score",
        "PIDText", "Full_Prop",
    ]
    display_cols = [c for c in display_cols if c in top50.columns]
    st.dataframe(top50[display_cols], use_container_width=True)

    st.markdown('<hr class="atlas-rule">', unsafe_allow_html=True)
    st.markdown("#### Focus a Parcel")
    st.caption("Selecting a parcel prefills the Pro Forma tab with its assessed value.")

    if len(top50) > 0:
        pid_options = ["(none)"] + list(top50["PIDText"].astype(str))
        selected_pid = st.selectbox("Select a parcel from Top 50", pid_options)

        if selected_pid != "(none)":
            row = top50[top50["PIDText"].astype(str) == selected_pid].iloc[0]
            set_selected_parcel(row)

            score = row["buildability_score"]
            st.markdown(
                f"""
                <div class="stamp-wrap">
                    <div class="stamp">
                        <div class="score-num">{score:.0f}</div>
                        <div class="score-lbl">SCORE</div>
                    </div>
                    <div>
                        <div class="parcel-card" style="margin-bottom:0;">
                            <div class="label">Parcel {row.get('PIDText', '')}</div>
                            <div class="value">{row.get('Full_Prop', 'Address unavailable')}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Assessed Value", f"${row.get('property_value', 0):,.0f}")
            c2.metric("Suppression", f"{row.get('suppression_index', 0):.0f}")
            c3.metric("Nearby Avg Value", f"${row.get('nearby_avg_value', 0):,.0f}")
            c4.metric("Value Gap", f"{row.get('value_gap_pct', 0) * 100:.0f}%")
    else:
        st.info("No parcels in Top 50 under current data.")
