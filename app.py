import streamlit as st
import pandas as pd
import pydeck as pdk
import numpy as np

# =========================
# CORE FINANCE HELPERS
# =========================

def calc_monthly_pni(principal, annual_rate, years):
    if principal <= 0 or annual_rate <= 0:
        return 0
    monthly_rate = annual_rate / 12
    num_payments = years * 12
    return principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)


# =========================
# DATA LOADING (SC0RED PARCELS)
# =========================

@st.cache_data(show_spinner=True)
def load_scored_parcels():
    path = "data/open/flint_scored.parquet"
    df = pd.read_parquet(path)
    # Ensure numeric types
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
    return df


# =========================
# APP CONFIG
# =========================

st.set_page_config(page_title="Real Estate Pro Forma Engine", layout="wide")
st.title("🏠 Master Real Estate Pro Forma Engine")
st.markdown("---")

tab_proforma, tab_buildability = st.tabs(["Pro Forma Engine", "Buildability Engine"])


# =========================
# TAB 1: PRO FORMA ENGINE
# =========================

with tab_proforma:
    st.sidebar.header("1. Strategy & Acquisition")
    strategy = st.sidebar.selectbox("Select Investment Strategy", ["Flip", "Rent", "BRRRR"])

    purchase_price = st.sidebar.number_input("Purchase Price ($)", value=85000, step=5000)

    if strategy in ["Flip", "BRRRR"]:
        rehab_cost = st.sidebar.number_input("Estimated Rehab Cost ($)", value=45000, step=1000)
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

    st.sidebar.header("2. Initial Financing")
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
        st.header("📈 Rental Income & Expenses")
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
        st.markdown("---")
        st.header("💰 Refinance Layer (BRRRR Debt Swap)")
        refi_col1, refi_col2 = st.columns(2)
        
        with refi_col1:
            arv = refi_col1.number_input("After Repair Value (ARV) ($)", value=175000, step=5000)
            refi_ltv = refi_col1.slider("Refinance Cash-Out LTV %", 50, 90, 75) / 100
            
        with refi_col2:
            refi_rate = refi_col2.number_input("Refinance Interest Rate (%)", value=6.20, step=0.1) / 100
            refi_loan_amount = arv * refi_ltv
            refi_monthly_pni = calc_monthly_pni(refi_loan_amount, refi_rate, 30)
            cash_pulled_from_refi = refi_loan_amount - initial_loan_amount
    else:
        arv, refi_loan_amount, refi_monthly_pni, cash_pulled_from_refi = 0, 0, 0, 0

    if strategy == "Flip":
        st.header("🛠️ Flip Exit Metrics")
        arv = st.number_input("After Repair Value (ARV) ($)", value=175000, step=5000)

    st.markdown("---")
    st.header("🔍 Underwriting & Structural Breakout")
    b1, b2, b3 = st.columns(3)

    with b1:
        st.subheader("Initial Debt Structure")
        st.metric("Initial Loan Basis", f"${initial_loan_basis:,.2f}")
        st.metric("Initial Loan Amount", f"${initial_loan_amount:,.2f}")
        st.metric("Initial Monthly P&I Mortgage", f"${initial_monthly_pni:,.2f}")

    with b2:
        if strategy in ["Rent", "BRRRR"]:
            st.subheader("Monthly Property Operations")
            st.metric("Net Operating Income (NOI)", f"${noi:,.2f}")
            st.metric("Total Operating Expenses (OpEx)", f"${total_opex:,.2f}")
        else:
            st.subheader("Holding Phase Metrics")
            st.metric("Monthly Carrying Cost", f"${monthly_hold_costs:,.2f}")
            st.metric("Total Cumulative Carry", f"${total_holding_costs:,.2f}")

    with b3:
        if strategy == "BRRRR":
            st.subheader("Post-Refinance Debt Structure")
            st.metric("New Refinance Loan Amount", f"${refi_loan_amount:,.2f}")
            st.metric("New Refi Monthly P&I Mortgage", f"${refi_monthly_pni:,.2f}")
        elif strategy == "Flip":
            st.subheader("Total Sunk Costs")
            st.metric("Total Capital Sunk", f"${(down_payment_amount + upfront_rehab_cash + closing_costs_buy + total_holding_costs):,.2f}")
        else:
            st.subheader("Financing Baseline")
            st.metric("Active Financing P&I", f"${initial_monthly_pni:,.2f}")

    st.markdown("---")
    st.header(f"📊 Master Dashboard: {strategy.upper()} Metrics")

    if strategy == "Rent":
        total_capital_invested = down_payment_amount + closing_costs_buy
        net_monthly_cash_flow = noi - initial_monthly_pni
        coc_return = (net_monthly_cash_flow * 12) / total_capital_invested if total_capital_invested > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total All-In Capital", f"${total_capital_invested:,.2f}")
        m2.metric("Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}")
        m3.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")

    elif strategy == "Flip":
        total_capital_invested = down_payment_amount + upfront_rehab_cash + closing_costs_buy + total_holding_costs
        flip_profit = arv - total_capital_invested - initial_loan_amount - closing_costs_sell
        roi = (flip_profit / total_capital_invested) * 100 if total_capital_invested > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Active Cash Invested", f"${total_capital_invested:,.2f}")
        m2.metric("Net Flip Profit Margin", f"${flip_profit:,.2f}")
        m3.metric("Return on Investment (ROI)", f"{roi:.2f}%")

    elif strategy == "BRRRR":
        upfront_cash_invested = down_payment_amount + upfront_rehab_cash + closing_costs_buy + total_holding_costs
        net_trapped_equity = upfront_cash_invested - cash_pulled_from_refi
        final_cash_left_in_deal = max(0, net_trapped_equity)
        net_monthly_cash_flow = noi - refi_monthly_pni
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Initial Capital Outlays", f"${upfront_cash_invested:,.2f}")
        m2.metric("Net Cash Trapped In Asset", f"${final_cash_left_in_deal:,.2f}")
        m3.metric("Post-Refi Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}")
        
        if net_trapped_equity <= 0:
            m4.metric("Cash-on-Cash Return", "Infinite (No Cash Left!)")
        else:
            coc_return = (net_monthly_cash_flow * 12) / final_cash_left_in_deal
            m4.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")


# =========================
# TAB 2: BUILDABILITY ENGINE
# =========================

with tab_buildability:
    st.header("🧱 Flint Buildability & Opportunity Radar")
    st.write(
        "This tab uses precomputed scores (buildability, value gradient, distress adjacency) to surface "
        "fringe opportunities and suppressed neighborhoods."
    )

    df = load_scored_parcels()

    st.subheader("Scored Parcel Summary")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Total Parcels", f"{len(df):,}")
    with col_b:
        st.metric("Avg Buildability", f"{df['buildability_score'].mean():.1f}")
    with col_c:
        st.metric("Avg Property Value", f"${df['property_value'].mean():,.0f}")

    st.markdown("---")
    st.subheader("Filters")

    min_val = int(df["property_value"].min())
    max_val = int(df["property_value"].max())
    min_build = int(df["buildability_score"].min())
    max_build = int(df["buildability_score"].max())

    f1, f2, f3 = st.columns(3)
    with f1:
        value_threshold = st.slider(
            "Min Property Value (for thermal layer)",
            min_val,
            max_val if max_val > min_val else min_val + 1,
            min_val,
        )
    with f2:
        build_threshold = st.slider(
            "Min Buildability Score",
            min_build,
            max_build if max_build > min_build else min_build + 1,
            min_build,
        )
    with f3:
        show_opportunities = st.checkbox("Highlight Fringe Opportunities (Glow Zones)", True)

    filtered = df[
        (df["property_value"] >= value_threshold) &
        (df["buildability_score"] >= build_threshold)
    ].copy()

    st.write(f"Filtered parcels: {len(filtered):,}")

    st.markdown("---")
    st.subheader("Top 50 Parcels (by buildability score)")
    top50 = filtered.sort_values("buildability_score", ascending=False).head(50)
    st.dataframe(
        top50[
            [
                "buildability_score",
                "property_value",
                "value_gradient_score",
                "distress_adjacency_score",
                "PIDText",
                "Full_Prop",
            ]
        ]
    )

    st.markdown("---")
    st.subheader("🗺 Investment Thermal Map & Glow Zones")

    if len(filtered) == 0:
        st.info("No parcels match the current filters. Try lowering thresholds.")
    else:
        layer_value = pdk.Layer(
            "ScatterplotLayer",
            filtered,
            get_position=["lon", "lat"],
            get_radius=20,
            get_fill_color="[min(property_value / 1000, 255), 50, 150, 160]",
            pickable=True,
        )

        layer_build = pdk.Layer(
            "ScatterplotLayer",
            filtered,
            get_position=["lon", "lat"],
            get_radius=30,
            get_fill_color="[buildability_score * 2.5, 255 - buildability_score * 2.5, 80, 140]",
            pickable=True,
        )

        layers = [layer_value, layer_build]

        if show_opportunities:
            opp = filtered[
                (filtered["value_gradient_score"] >= 80) &
                (filtered["distress_adjacency_score"] >= 60)
            ]
            layer_opp = pdk.Layer(
                "ScatterplotLayer",
                opp,
                get_position=["lon", "lat"],
                get_radius=60,
                get_fill_color="[255, 255, 0, 255]",
                pickable=True,
            )
            layers.append(layer_opp)

        view_state = pdk.ViewState(
            latitude=float(filtered["lat"].mean()),
            longitude=float(filtered["lon"].mean()),
            zoom=11,
            pitch=45,
        )

        tooltip = {
            "text": "PID: {PIDText}\nAddress: {Full_Prop}\n"
                    "Value: {property_value}\nBuildability: {buildability_score}\n"
                    "Value Gradient: {value_gradient_score}\nDistress Adj.: {distress_adjacency_score}"
        }

        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
        )

        st.pydeck_chart(deck)
