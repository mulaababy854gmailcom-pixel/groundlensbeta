import streamlit as st
import pandas as pd
import numpy as np
import json
import pydeck as pdk
from shapely.geometry import shape

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="Flint Parcel Atlas", layout="wide", page_icon=None)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@0,500;0,600;0,700;1,500&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"]          { font-family: 'IBM Plex Mono', monospace; }
.stApp                              { background: #EDE7D9; color: #1B1B16; }
h1,h2,h3                           { font-family:'IBM Plex Serif',serif !important; color:#1F2E3D; letter-spacing:-0.01em; }
hr                                  { border:none; border-top:1px solid #C9C0A8; margin:1rem 0 1.2rem; }

section[data-testid="stSidebar"]    { background:#1F2E3D; }
section[data-testid="stSidebar"] *  { color:#EDE7D9 !important; }
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] { background:#162533; }

.eyebrow { font-size:.68rem; letter-spacing:.18em; text-transform:uppercase;
           color:#B5562F; font-weight:600; margin-bottom:-.3rem; }

/* stat cards */
.sc-wrap { margin-bottom:.3rem; }
.sc      { background:#FAF7EE; border:1px solid #C9C0A8; border-left:4px solid var(--ac,#2C4A6E);
           border-radius:2px; padding:.7rem 1rem .55rem; box-sizing:border-box; height:100%; }
.sc-lbl  { font-size:.63rem; text-transform:uppercase; letter-spacing:.13em; color:#5C5848;
           font-weight:600; margin-bottom:.2rem; }
.sc-val  { font-family:'IBM Plex Serif',serif; font-size:1.4rem; color:#1F2E3D;
           font-weight:600; line-height:1.1; }
.sc-sub  { font-size:.68rem; color:#7A7060; margin-top:.15rem; }

/* grade badge */
.grade-wrap { display:flex; align-items:center; gap:1.2rem; background:#FAF7EE;
              border:1px solid #C9C0A8; border-radius:2px; padding:.9rem 1.1rem; margin-bottom:.5rem; }
.grade-badge { width:70px; height:70px; border-radius:50%; display:flex; flex-direction:column;
               align-items:center; justify-content:center; transform:rotate(-5deg);
               border:3px solid var(--gc,#2C4A6E); font-family:'IBM Plex Mono',monospace; }
.grade-ltr   { font-size:1.6rem; font-weight:700; color:var(--gc,#2C4A6E); line-height:1; }
.grade-sub   { font-size:.45rem; letter-spacing:.08em; color:var(--gc,#2C4A6E); }
.grade-msg   { font-size:.8rem; color:#3A3830; line-height:1.5; }
.grade-title { font-family:'IBM Plex Serif',serif; font-size:1rem; font-weight:600;
               color:#1F2E3D; margin-bottom:.2rem; }

/* stamp for parcel */
.stamp-wrap { display:flex; align-items:center; gap:1rem; margin:0.5rem 0; }
.stamp      { width:80px; height:80px; border-radius:50%; border:3px solid #B5562F;
              display:flex; flex-direction:column; align-items:center; justify-content:center;
              transform:rotate(-6deg); font-family:'IBM Plex Mono',monospace; flex-shrink:0;
              background:#FAF7EE; }
.stamp-num  { font-size:1.4rem; font-weight:700; color:#B5562F; line-height:1; }
.stamp-lbl  { font-size:.45rem; letter-spacing:.1em; color:#B5562F; }

/* breakdown bars */
.bar-row    { display:flex; align-items:center; gap:.6rem; margin:.35rem 0; }
.bar-label  { font-size:.68rem; color:#5C5848; min-width:160px; }
.bar-track  { flex:1; background:#D9D1C3; border-radius:1px; height:8px; }
.bar-fill   { height:8px; border-radius:1px; background:var(--bc,#2C4A6E); }
.bar-amt    { font-size:.7rem; color:#1F2E3D; font-weight:600; min-width:80px; text-align:right; }

/* info box */
.info-box { background:#F5F0E4; border:1px solid #C9C0A8; border-left:4px solid #B5562F;
            border-radius:2px; padding:.8rem 1rem; font-size:.78rem; color:#3A3830;
            line-height:1.6; margin:.6rem 0; }
.info-box strong { color:#B5562F; }

.stTabs [data-baseweb="tab"] { font-family:'IBM Plex Mono',monospace; text-transform:uppercase;
                                font-size:.75rem; letter-spacing:.06em; }
div[data-testid="column"]    { padding-left:.25rem !important; padding-right:.25rem !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def sc(label, value, accent="#2C4A6E", sub=None):
    sub_html = f'<div class="sc-sub">{sub}</div>' if sub else ""
    return (f'<div class="sc" style="--ac:{accent}"><div class="sc-lbl">{label}</div>'
            f'<div class="sc-val">{value}</div>{sub_html}</div>')

def stat_row(items, accent="#2C4A6E", subs=None):
    cols = st.columns(len(items))
    for i, (col, (lbl, val)) in enumerate(zip(cols, items)):
        sub = subs[i] if subs and i < len(subs) else None
        col.markdown(f'<div class="sc-wrap">{sc(lbl, val, accent, sub)}</div>', unsafe_allow_html=True)

def deal_grade(primary_val, strategy):
    """Return (letter, color, title, message) based on deal type and primary metric."""
    thresholds = {
        "Rental":    [(12,"A","#2A6E3A","Strong cash flow — worth underwriting fully"),
                      (8, "B","#3A6E2A","Solid deal — verify expenses closely"),
                      (5, "C","#8A6E1A","Marginal — thin margin for error"),
                      (0, "D","#8A2A1A","Negative or weak — renegotiate or pass")],
        "Flip":      [(30,"A","#2A6E3A","High-margin flip — strong risk-adjusted return"),
                      (20,"B","#3A6E2A","Decent flip — watch rehab cost creep"),
                      (10,"C","#8A6E1A","Thin margin — one surprise kills the deal"),
                      (0, "D","#8A2A1A","Negative return — reprice or pass")],
        "BRRRR":     [(10,"A","#2A6E3A","Cash flowing after refi — textbook BRRRR"),
                      (5, "B","#3A6E2A","Positive post-refi — verify rent comps"),
                      (0, "C","#8A6E1A","Breaking even — tight but workable"),
                      (-1,"D","#8A2A1A","Negative post-refi cash flow — restructure")],
        "Ground Up": [(20,"A","#2A6E3A","Strong development margin — proceed"),
                      (12,"B","#3A6E2A","Viable project — tighten hard costs"),
                      (8, "C","#8A6E1A","Thin spread — value-engineer the design"),
                      (0, "D","#8A2A1A","Below minimum — land or cost problem")],
    }
    tbl = thresholds.get(strategy, thresholds["Flip"])
    for threshold, letter, color, msg in tbl:
        if primary_val >= threshold:
            return letter, color, msg
    last = tbl[-1]
    return last[1], last[2], last[3]

def bar_row(label, amount, total, color="#2C4A6E"):
    pct = max(0, min(100, (amount / total * 100) if total > 0 else 0))
    return (f'<div class="bar-row"><div class="bar-label">{label}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.0f}%;--bc:{color}"></div></div>'
            f'<div class="bar-amt">${amount:,.0f}</div></div>')


# ─── FINANCE ─────────────────────────────────────────────────────────────────

def monthly_pni(principal, annual_rate, years):
    if principal <= 0 or annual_rate <= 0:
        return 0
    r = annual_rate / 12
    n = years * 12
    return principal * r * (1 + r)**n / ((1 + r)**n - 1)

def construction_interest(loan_amount, annual_rate, months, draw_factor=0.55):
    """Interest-only cost during build. draw_factor (~55%) accounts for progressive
    draws — not all the loan is outstanding day-one."""
    if loan_amount <= 0 or annual_rate <= 0:
        return 0
    return loan_amount * draw_factor * (annual_rate / 12) * months


# ─── DATA LOADING ─────────────────────────────────────────────────────────────

def _safe(df, col, default=0):
    return df[col] if col in df.columns else pd.Series([default]*len(df), index=df.index)

@st.cache_data(show_spinner="Loading parcels…")
def load_scored_parcels():
    with open("flint_parcels_scored.geojson") as f:
        data = json.load(f)
    records = [dict(feat["properties"], geometry=shape(feat["geometry"])) for feat in data["features"]]
    df = pd.DataFrame(records)

    # ── property value
    if "property_value" not in df.columns:
        df["property_value"] = _safe(df,"HomeSEV")*2
    mask = df["property_value"].isna() | (df["property_value"]==0)
    df.loc[mask,"property_value"] = _safe(df,"Land_Value") + _safe(df,"Resb_Value")

    # ── suppression index (how undervalued vs cost/condition signals)
    ecf = _safe(df,"ECF",1.0)
    df["suppression_index"] = np.clip(1-ecf,0,1)*30
    df["value_ratio"] = _safe(df,"Resb_Value") / (_safe(df,"Land_Value")+1)
    df["suppression_index"] += np.clip(1-df["value_ratio"],0,1)*20
    df["suppression_index"] += np.clip((1950-_safe(df,"Year_Built",1950))/100,0,1)*15
    df["suppression_index"] += _safe(df,"QCTs",False).apply(lambda x:15 if x else 0)
    df["suppression_index"] += _safe(df,"Rental",False).apply(lambda x:10 if x else 0)
    df["suppression_index"] += _safe(df,"Inv22",False).apply(lambda x:10 if x else 0)
    df["suppression_index"] = np.clip(df["suppression_index"],0,100)

    # ── centroids
    df["_geom"] = df["geometry"]
    df["cx"] = df["_geom"].apply(lambda g: g.centroid.x)
    df["cy"] = df["_geom"].apply(lambda g: g.centroid.y)

    # ── nearby value gradient (0.5mi grid bucket)
    if "nearby_avg_value" not in df.columns:
        bucket = 0.007
        df["_bx"] = (df["cx"]/bucket).round()
        df["_by"] = (df["cy"]/bucket).round()
        df["nearby_avg_value"] = df.groupby(["_bx","_by"])["property_value"].transform("mean")
        df.drop(columns=["_bx","_by"],inplace=True)

    df["value_gap_pct"] = np.where(
        df["nearby_avg_value"]>0,
        np.clip(1-(df["property_value"]/df["nearby_avg_value"]),0,1), 0)

    # ── optional signals (degrade gracefully)
    df["crime_score"]  = _safe(df,"crime_index",50)
    df["school_score"] = _safe(df,"school_rating_20min",50)
    df["utility_score"]= _safe(df,"utilities_present",True).apply(lambda x:100 if x else 0)

    # ── composite buildability
    base = _safe(df,"buildability_score",50).clip(0,100)
    df["buildability_score"] = (
        base*0.30 + df["suppression_index"]*0.20 + df["value_gap_pct"]*100*0.15
        + df["crime_score"]*0.12 + df["school_score"]*0.12 + df["utility_score"]*0.11
    ).clip(0,100)

    # ── map geometry (done once here, not on every render)
    df["polygon"] = df["_geom"].apply(lambda g: list(g.exterior.coords))
    df["build_norm"] = (df["buildability_score"] - df["buildability_score"].min()) / \
                       max(1e-9, df["buildability_score"].max()-df["buildability_score"].min())
    df["color"] = df["build_norm"].apply(_color)
    return df

def _color(s):
    navy, rust = np.array([44,74,110]), np.array([181,86,47])
    c = (navy+(rust-navy)*s).astype(int)
    return [int(c[0]),int(c[1]),int(c[2]),195]


# ─── SESSION STATE ────────────────────────────────────────────────────────────

for k,v in {"selected_pid":None,"selected_row":None,
            "purchase_price":85000,"rehab_cost":45000,
            "arv_flip":175000,"arv_brrrr":175000}.items():
    if k not in st.session_state: st.session_state[k]=v

def set_parcel(row):
    st.session_state["selected_pid"] = row.get("PIDText")
    st.session_state["selected_row"]  = row.to_dict()
    pv = float(row.get("property_value",0) or 0)
    st.session_state["purchase_price"] = max(1000, round(pv))
    st.session_state["rehab_cost"]     = max(0, round(pv*0.5))


# ─── HEADER ──────────────────────────────────────────────────────────────────

st.markdown('<div class="eyebrow">Genesee County · Flint, MI</div>', unsafe_allow_html=True)
st.title("Flint Parcel Atlas")
st.caption("Pro forma modeling · Buildability scoring · Fringe-opportunity identification")
st.markdown("---")

tab_pf, tab_atlas = st.tabs(["Pro Forma", "Buildability Atlas"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PRO FORMA
# ═══════════════════════════════════════════════════════════════════════════════

with tab_pf:

    # ── sidebar ──────────────────────────────────────────────────────────────
    st.sidebar.markdown('<div class="eyebrow">Deal Setup</div>', unsafe_allow_html=True)

    strategy = st.sidebar.selectbox(
        "Deal Type",
        ["Rental", "Flip", "BRRRR", "Ground Up Construction"])

    unit_label = st.sidebar.selectbox(
        "Asset Type",
        ["SFR — 1 unit","Duplex — 2 units","Triplex — 3 units","Quadplex — 4 units",
         "Small Multifamily — 5-20 units","Multifamily — 20+ units"])
    UNIT_MAP = {"SFR — 1 unit":1,"Duplex — 2 units":2,"Triplex — 3 units":3,
                "Quadplex — 4 units":4,"Small Multifamily — 5-20 units":10,
                "Multifamily — 20+ units":24}
    unit_count = UNIT_MAP[unit_label]
    is_commercial = unit_count >= 5

    st.sidebar.markdown("---")
    st.sidebar.markdown('<div class="eyebrow">Acquisition</div>', unsafe_allow_html=True)

    if strategy == "Ground Up Construction":
        land_cost       = st.sidebar.number_input("Land / Lot Cost ($)", value=15000, step=1000)
        bldg_sqft       = st.sidebar.number_input("Building Size (sq ft)", value=1400, step=100)
        hard_cost_sqft  = st.sidebar.number_input("Hard Cost ($/sq ft)", value=95, step=5)
        soft_cost_pct   = st.sidebar.slider("Soft Costs % of Hard", 5, 20, 12) / 100
        contingency_pct = st.sidebar.slider("Contingency %", 5, 20, 10) / 100
        const_months    = st.sidebar.number_input("Construction Period (months)", value=8, step=1)
        const_rate      = st.sidebar.number_input("Construction Loan Rate (%)", value=9.5, step=0.25) / 100
        const_ltc       = st.sidebar.slider("Construction Loan LTC %", 50, 85, 75) / 100
        ground_up_exit  = st.sidebar.selectbox("Exit Strategy", ["Sell at Completion","Hold as Rental"])
        closing_costs_buy = st.sidebar.number_input("Closing Costs — Acquisition ($)", value=1500, step=500)
        perm_rate = perm_years = 0
        if ground_up_exit == "Hold as Rental":
            perm_rate  = st.sidebar.number_input("Permanent Loan Rate (%)", value=6.75, step=0.1) / 100
            perm_ltv   = st.sidebar.slider("Permanent LTV %", 50, 80, 70) / 100
            perm_years = st.sidebar.number_input("Permanent Loan Term (yrs)", value=30, step=5)
        purchase_price = land_cost
        rehab_cost = down_payment_pct = interest_rate_init = loan_term_years = 0
        include_rehab_in_loan = False
    else:
        purchase_price  = st.sidebar.number_input("Purchase Price ($)",
            value=int(st.session_state["purchase_price"]), step=5000)
        closing_costs_buy = st.sidebar.number_input("Purchase Closing Costs ($)", value=4000, step=500)

        if strategy in ["Flip","BRRRR"]:
            rehab_cost           = st.sidebar.number_input("Estimated Rehab Cost ($)",
                value=int(st.session_state["rehab_cost"]), step=1000)
            include_rehab_in_loan = st.sidebar.checkbox("Finance Rehab? (Wrap into Loan)", value=True)
            holding_months       = st.sidebar.number_input("Holding Period (months)", value=6, step=1)
            monthly_hold_costs   = st.sidebar.number_input("Monthly Holding Costs ($)", value=400, step=50)
            total_holding_costs  = holding_months * monthly_hold_costs
            closing_costs_sell   = st.sidebar.number_input("Selling Closing Costs ($)", value=12000, step=500)
        else:
            rehab_cost = 0; include_rehab_in_loan=False
            holding_months=0; monthly_hold_costs=0; total_holding_costs=0; closing_costs_sell=0

        st.sidebar.markdown("---")
        st.sidebar.markdown('<div class="eyebrow">Financing</div>', unsafe_allow_html=True)
        down_payment_pct   = st.sidebar.slider("Down Payment %", 0, 100, 20) / 100
        interest_rate_init = st.sidebar.number_input("Interest Rate (%)", value=6.20, step=0.1) / 100
        loan_term_years    = st.sidebar.number_input("Loan Term (years)", value=30, step=5)
        bldg_sqft = hard_cost_sqft = soft_cost_pct = contingency_pct = 0
        const_months = const_rate = const_ltc = 0
        land_cost = 0; ground_up_exit = "Sell at Completion"

        if include_rehab_in_loan:
            loan_basis        = purchase_price + rehab_cost
            down_payment_amt  = loan_basis * down_payment_pct
            initial_loan_amt  = loan_basis - down_payment_amt
            upfront_rehab_cash = 0
        else:
            loan_basis        = purchase_price
            down_payment_amt  = purchase_price * down_payment_pct
            initial_loan_amt  = purchase_price - down_payment_amt
            upfront_rehab_cash = rehab_cost

        initial_monthly_pni = monthly_pni(initial_loan_amt, interest_rate_init, loan_term_years)

    # ── main area: strategy-specific inputs + dashboard ──────────────────────

    # ── Ground Up Construction ────────────────────────────────────────────────
    if strategy == "Ground Up Construction":
        hard_costs_total = bldg_sqft * hard_cost_sqft
        soft_costs_total = hard_costs_total * soft_cost_pct
        contingency_amt  = hard_costs_total * contingency_pct
        total_const_cost = hard_costs_total + soft_costs_total + contingency_amt
        total_project    = land_cost + closing_costs_buy + total_const_cost
        const_loan_amt   = total_project * const_ltc
        equity_required  = total_project - const_loan_amt
        const_interest   = construction_interest(const_loan_amt, const_rate, const_months)
        total_cash_in    = equity_required + const_interest

        st.subheader("Construction Cost Breakdown")
        col_a, col_b = st.columns([1.4, 1])
        with col_a:
            total_for_bar = max(total_project + const_interest, 1)
            bars_html = (
                bar_row("Land / Lot", land_cost, total_for_bar, "#B5562F") +
                bar_row("Hard Costs (construction)", hard_costs_total, total_for_bar, "#2C4A6E") +
                bar_row("Soft Costs (arch, permits, fees)", soft_costs_total, total_for_bar, "#4A7C6E") +
                bar_row("Contingency", contingency_amt, total_for_bar, "#7A6E3A") +
                bar_row("Construction Interest", const_interest, total_for_bar, "#6E3A3A")
            )
            st.markdown(bars_html, unsafe_allow_html=True)
        with col_b:
            stat_row([
                ("Hard Cost / Sq Ft", f"${hard_cost_sqft}"),
                ("Total Sq Ft", f"{bldg_sqft:,}"),
            ], accent="#2C4A6E")
            stat_row([
                ("Total Project Cost", f"${total_project:,.0f}"),
                ("Construction Loan", f"${const_loan_amt:,.0f}"),
            ], accent="#2C4A6E")
            stat_row([
                ("Equity Required", f"${equity_required:,.0f}"),
                ("Construction Interest", f"${const_interest:,.0f}"),
            ], accent="#B5562F")

        st.markdown("---")
        st.subheader("Exit & Return")
        if ground_up_exit == "Sell at Completion":
            sell_arv   = st.number_input("Sale Price / ARV ($)", value=max(180000, int(total_project*1.3)), step=5000)
            sell_costs = st.number_input("Selling Costs ($)", value=round(sell_arv*0.07/1000)*1000, step=500)
            net_profit    = sell_arv - const_loan_amt - total_cash_in - sell_costs
            roc           = (net_profit / total_project * 100) if total_project > 0 else 0
            equity_roi    = (net_profit / total_cash_in * 100) if total_cash_in > 0 else 0
            profit_margin = (net_profit / sell_arv * 100) if sell_arv > 0 else 0
            grade, gcolor, gmsg = deal_grade(roc, "Ground Up")
        else:
            if perm_rate > 0 and perm_years > 0:
                perm_loan = total_project * perm_ltv
                perm_pni  = monthly_pni(perm_loan, perm_rate, perm_years)
            else:
                perm_loan = perm_pni = 0
            sell_arv = sell_costs = net_profit = 0
            roc = equity_roi = profit_margin = 0
            grade, gcolor, gmsg = "—", "#888", "Set up rental income in sidebar"

        st.markdown("---")
        st.markdown('<div class="eyebrow">Master Dashboard — Ground Up</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="grade-wrap">'
            f'<div class="grade-badge" style="--gc:{gcolor}"><div class="grade-ltr">{grade}</div>'
            f'<div class="grade-sub">DEAL GRADE</div></div>'
            f'<div><div class="grade-title">Return on Cost: {roc:.1f}%</div>'
            f'<div class="grade-msg">{gmsg}</div></div></div>', unsafe_allow_html=True)
        if ground_up_exit == "Sell at Completion":
            stat_row([
                ("Total Cash Required", f"${total_cash_in:,.0f}"),
                ("Net Development Profit", f"${net_profit:,.0f}"),
                ("Return on Cost", f"{roc:.1f}%"),
                ("Equity ROI", f"{equity_roi:.1f}%"),
                ("Profit Margin", f"{profit_margin:.1f}%"),
            ], accent="#2C4A6E",
               subs=["Equity + construction interest","After loan payoff & closing costs",
                     "Profit ÷ total project cost","Profit ÷ your cash in","Profit ÷ sale price"])

    # ── Rental ────────────────────────────────────────────────────────────────
    elif strategy == "Rental":
        st.subheader(f"Rental Income — {unit_label}")
        if unit_count == 1:
            gross_rent = st.number_input("Gross Monthly Rent ($)", value=1100, step=50)
        else:
            per_unit = st.number_input("Rent Per Unit ($/mo)", value=900, step=50)
            gross_rent = per_unit * unit_count
            st.info(f"{unit_count} units × ${per_unit:,}/mo = **${gross_rent:,}/mo** gross rent")

        c1, c2 = st.columns(2)
        with c1:
            vacancy_pct    = st.slider("Vacancy Rate %", 0, 20, 7 if unit_count>1 else 5) / 100
            taxes_monthly  = st.number_input("Property Taxes ($/mo)", value=200+unit_count*80, step=25)
            ins_monthly    = st.number_input("Insurance ($/mo)", value=100+unit_count*40, step=25)
        with c2:
            pm_pct         = st.slider("Property Mgmt Fee %", 0, 15, 8) / 100
            reserves       = st.number_input("Maint. & CapEx Reserves ($/mo)", value=100*unit_count, step=20)
            water_sewer    = st.number_input("Water/Sewer if owner-paid ($/mo)", value=0 if unit_count==1 else 40*unit_count, step=20)

        egi         = gross_rent * (1 - vacancy_pct)
        pm_fees     = egi * pm_pct
        total_opex  = taxes_monthly + ins_monthly + pm_fees + reserves + water_sewer
        noi         = egi - total_opex
        net_cf      = noi - initial_monthly_pni
        coc         = (net_cf * 12 / (down_payment_amt + closing_costs_buy) * 100) if (down_payment_amt + closing_costs_buy) > 0 else 0
        cap_rate    = (noi * 12 / purchase_price * 100) if purchase_price > 0 else 0
        grm         = purchase_price / (gross_rent * 12) if gross_rent > 0 else 0
        dscr        = (noi / initial_monthly_pni) if initial_monthly_pni > 0 else 0

        st.markdown("---")
        st.markdown('<div class="eyebrow">Rental Income Summary</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].markdown(sc("Gross Rent/mo", f"${gross_rent:,.0f}", "#2C4A6E"), unsafe_allow_html=True)
        cols[1].markdown(sc("Effective Gross Income", f"${egi:,.0f}", "#2C4A6E", f"After {vacancy_pct*100:.0f}% vacancy"), unsafe_allow_html=True)
        cols[2].markdown(sc("Total Opex/mo", f"${total_opex:,.0f}", "#B5562F"), unsafe_allow_html=True)
        cols[3].markdown(sc("NOI/mo", f"${noi:,.0f}", "#4A7C6E"), unsafe_allow_html=True)

        st.markdown("---")
        grade, gcolor, gmsg = deal_grade(coc, "Rental")
        st.markdown('<div class="eyebrow">Master Dashboard — Rental</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="grade-wrap">'
            f'<div class="grade-badge" style="--gc:{gcolor}"><div class="grade-ltr">{grade}</div>'
            f'<div class="grade-sub">DEAL GRADE</div></div>'
            f'<div><div class="grade-title">Cash-on-Cash: {coc:.1f}%</div>'
            f'<div class="grade-msg">{gmsg}</div></div></div>', unsafe_allow_html=True)

        if is_commercial:
            stat_row([
                ("Monthly Cash Flow", f"${net_cf:,.2f}"),
                ("Cash-on-Cash Return", f"{coc:.1f}%"),
                ("Cap Rate", f"{cap_rate:.1f}%"),
                ("DSCR", f"{dscr:.2f}x"),
                ("GRM", f"{grm:.1f}x"),
            ], accent="#2C4A6E",
               subs=["After debt service","Annual CF ÷ cash in","NOI ÷ purchase price",
                     "NOI ÷ debt service (lender wants >1.25)","Price ÷ annual gross rent"])
        else:
            stat_row([
                ("Total Capital Invested", f"${down_payment_amt+closing_costs_buy:,.0f}"),
                ("Monthly Cash Flow", f"${net_cf:,.2f}"),
                ("Cash-on-Cash Return", f"{coc:.1f}%"),
                ("Cap Rate", f"{cap_rate:.1f}%"),
            ], accent="#2C4A6E")

    # ── Flip ──────────────────────────────────────────────────────────────────
    elif strategy == "Flip":
        st.subheader("Flip Exit Metrics")
        st.caption("After Repair Value — use recent sold comps within 0.5 miles, similar bed/bath and sq ft.")
        arv = st.number_input("After Repair Value (ARV) ($)",
            value=int(st.session_state["arv_flip"]), step=5000, key="arv_flip_in")
        max_offer = arv * 0.70 - rehab_cost
        st.markdown(
            f'<div class="info-box">70% Rule max offer: <strong>${max_offer:,.0f}</strong> '
            f'(= ARV × 70% − rehab). Your purchase price of <strong>${purchase_price:,.0f}</strong> is '
            f'{"<strong style=\'color:#2A6E3A\'>within range</strong>" if purchase_price<=max_offer else "<strong style=\'color:#8A2A1A\'>above the 70% rule — tight deal</strong>"}.'
            f'</div>', unsafe_allow_html=True)

        total_cash_in  = down_payment_amt + upfront_rehab_cash + closing_costs_buy + total_holding_costs
        flip_profit    = arv - initial_loan_amt - total_cash_in - closing_costs_sell
        roi            = (flip_profit / total_cash_in * 100) if total_cash_in > 0 else 0
        profit_margin  = (flip_profit / arv * 100) if arv > 0 else 0
        annualized_roi = (roi / holding_months * 12) if holding_months > 0 else 0

        total_for_bar = max(total_cash_in + initial_loan_amt + closing_costs_sell, 1)
        bars_html = (
            bar_row("Down Payment", down_payment_amt, total_for_bar, "#2C4A6E") +
            bar_row("Rehab (cash portion)", upfront_rehab_cash, total_for_bar, "#B5562F") +
            bar_row("Loan Balance", initial_loan_amt, total_for_bar, "#4A7C6E") +
            bar_row("Holding Costs", total_holding_costs, total_for_bar, "#7A6E3A") +
            bar_row("Selling Costs", closing_costs_sell, total_for_bar, "#6E3A3A")
        )
        st.markdown("**Cost Breakdown**")
        st.markdown(bars_html, unsafe_allow_html=True)

        st.markdown("---")
        grade, gcolor, gmsg = deal_grade(roi, "Flip")
        st.markdown('<div class="eyebrow">Master Dashboard — FLIP</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="grade-wrap">'
            f'<div class="grade-badge" style="--gc:{gcolor}"><div class="grade-ltr">{grade}</div>'
            f'<div class="grade-sub">DEAL GRADE</div></div>'
            f'<div><div class="grade-title">ROI: {roi:.1f}%</div>'
            f'<div class="grade-msg">{gmsg}</div></div></div>', unsafe_allow_html=True)
        stat_row([
            ("Total Cash Invested", f"${total_cash_in:,.0f}"),
            ("Net Flip Profit", f"${flip_profit:,.0f}"),
            ("Return on Investment", f"{roi:.1f}%"),
            ("Annualized ROI", f"{annualized_roi:.1f}%"),
            ("Profit Margin", f"{profit_margin:.1f}%"),
        ], accent="#2C4A6E",
           subs=["Your out-of-pocket","After all costs & payoff",
                 "Profit ÷ cash invested",f"ROI annualized over {holding_months}mo hold",
                 "Profit ÷ ARV"])

    # ── BRRRR ─────────────────────────────────────────────────────────────────
    elif strategy == "BRRRR":
        c1, c2 = st.columns(2)
        with c1:
            arv        = st.number_input("After Repair Value (ARV) ($)",
                value=int(st.session_state["arv_brrrr"]), step=5000, key="arv_brrrr_in")
            refi_ltv   = st.slider("Refinance Cash-Out LTV %", 50, 80, 75) / 100
        with c2:
            refi_rate  = st.number_input("Refinance Interest Rate (%)", value=6.75, step=0.1) / 100
            refi_years = st.number_input("Refi Loan Term (years)", value=30, step=5)
        refi_loan_amt   = arv * refi_ltv
        refi_pni        = monthly_pni(refi_loan_amt, refi_rate, refi_years)
        cash_from_refi  = refi_loan_amt - initial_loan_amt

        if unit_count == 1:
            gross_rent = st.number_input("Gross Monthly Rent ($)", value=1100, step=50)
        else:
            per_unit   = st.number_input("Rent Per Unit ($/mo)", value=900, step=50)
            gross_rent = per_unit * unit_count
        vacancy_pct   = st.slider("Vacancy %", 0, 20, 7) / 100
        taxes_monthly = st.number_input("Taxes ($/mo)", value=200, step=25)
        ins_monthly   = st.number_input("Insurance ($/mo)", value=100, step=25)
        pm_pct        = st.slider("Mgmt Fee %", 0, 15, 8) / 100
        reserves      = st.number_input("Reserves ($/mo)", value=150, step=25)
        egi         = gross_rent*(1-vacancy_pct)
        total_opex  = taxes_monthly+ins_monthly+egi*pm_pct+reserves
        noi         = egi-total_opex
        net_cf      = noi-refi_pni

        upfront_cash  = down_payment_amt + upfront_rehab_cash + closing_costs_buy + total_holding_costs
        net_trapped   = upfront_cash - cash_from_refi
        cash_left     = max(0, net_trapped)
        coc_label     = "Infinite — No Cash Left" if net_trapped<=0 else f"{net_cf*12/cash_left*100:.1f}%"

        st.markdown("---")
        grade, gcolor, gmsg = deal_grade(net_cf, "BRRRR")
        st.markdown('<div class="eyebrow">Master Dashboard — BRRRR</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="grade-wrap">'
            f'<div class="grade-badge" style="--gc:{gcolor}"><div class="grade-ltr">{grade}</div>'
            f'<div class="grade-sub">DEAL GRADE</div></div>'
            f'<div><div class="grade-title">Post-Refi Cash Flow: ${net_cf:,.0f}/mo</div>'
            f'<div class="grade-msg">{gmsg}</div></div></div>', unsafe_allow_html=True)
        stat_row([
            ("Upfront Cash Invested", f"${upfront_cash:,.0f}"),
            ("Cash Pulled at Refi", f"${cash_from_refi:,.0f}"),
            ("Net Cash Left In Deal", f"${cash_left:,.0f}"),
            ("Post-Refi Cash Flow", f"${net_cf:,.0f}/mo"),
            ("Cash-on-Cash", coc_label),
        ], accent="#2C4A6E",
           subs=["Total out-of-pocket before refi","Returned to you at refinance",
                 "Your trapped equity in asset","Monthly NOI minus new debt service",
                 "Annualized CF ÷ remaining cash"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUILDABILITY ATLAS
# ═══════════════════════════════════════════════════════════════════════════════

with tab_atlas:
    st.markdown('<div class="eyebrow">Opportunity Radar</div>', unsafe_allow_html=True)
    st.header("Buildability Atlas")

    try:
        df = load_scored_parcels()
    except FileNotFoundError:
        st.error("**flint_parcels_scored.geojson not found.** Place the scored GeoJSON in the app directory.")
        st.markdown("""
        <div class="info-box">
        <strong>To score all Flint parcels:</strong><br>
        1. Download the full parcel shapefile from the <strong>Genesee County GIS portal</strong>
           (gis.gc.net or the Flint open data portal).<br>
        2. Convert to GeoJSON with QGIS or <code>ogr2ogr -f GeoJSON output.geojson input.shp</code>.<br>
        3. Rename to <code>flint_parcels_scored.geojson</code> and place next to app.py.<br>
        4. The app will score all parcels automatically on first load.
        </div>""", unsafe_allow_html=True)
        st.stop()

    # ── data quality note ─────────────────────────────────────────────────────
    parcel_count = len(df)
    if parcel_count < 500:
        st.markdown(
            f'<div class="info-box">⚠ <strong>Only {parcel_count:,} parcels loaded.</strong> '
            f'Flint has ~35,000 parcels. To score all of them: download the full parcel layer from '
            f'<strong>Genesee County GIS</strong> or <strong>City of Flint Open Data</strong>, '
            f'convert to GeoJSON, replace flint_parcels_scored.geojson, and restart the app. '
            f'The scoring logic here will run automatically on any size file.</div>',
            unsafe_allow_html=True)

    missing = [n for n,c in [("crime data","crime_index"),("school ratings","school_rating_20min"),
                              ("utility flags","utilities_present")] if c not in df.columns]
    if missing:
        st.caption(f"Using neutral defaults for: {', '.join(missing)} — join those columns for a fully-weighted score.")

    # ── summary stats ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Portfolio Summary")
    stat_row([
        ("Parcels Loaded", f"{parcel_count:,}"),
        ("Avg Buildability Score", f"{df['buildability_score'].mean():.1f} / 100"),
        ("Avg Property Value", f"${df['property_value'].mean():,.0f}"),
        ("Avg Suppression Index", f"{df['suppression_index'].mean():.1f} / 100"),
        ("High-Opportunity Parcels", f"{(df['buildability_score']>=70).sum():,}"),
    ], accent="#B5562F",
       subs=["In current dataset","Composite multi-factor score",
             "SEV × 2 or land + structure","How undervalued vs context signals",
             "Score ≥ 70"])

    # ── map filters ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Parcel Map — Buildability")
    f1, f2, f3 = st.columns(3)
    min_score   = f1.slider("Min Buildability Score", 0, 100, 0)
    max_value   = f2.number_input("Max Property Value ($)", value=int(df["property_value"].max()+1), step=5000)
    min_gap     = f3.slider("Min Value Gap vs Nearby %", 0, 100, 0)

    map_df = df[
        (df["buildability_score"] >= min_score) &
        (df["property_value"] <= max_value) &
        (df["value_gap_pct"]*100 >= min_gap)
    ]
    st.caption(f"{len(map_df):,} parcels match current filters")

    if len(map_df) > 0:
        center_lat = map_df["cy"].mean()
        center_lon = map_df["cx"].mean()

        polygon_layer = pdk.Layer(
            "PolygonLayer", map_df,
            get_polygon="polygon", get_fill_color="color",
            get_line_color=[237,231,217], get_line_width=8,
            pickable=True, stroked=True, filled=True, extruded=False)

        view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=12, pitch=40)

        tooltip = {"html": (
            "<b>Parcel:</b> {PIDText}<br/>"
            "<b>Address:</b> {Full_Prop}<br/>"
            "<b>Buildability:</b> {buildability_score}<br/>"
            "<b>Suppression:</b> {suppression_index}<br/>"
            "<b>Value:</b> ${property_value}"),
            "style": {"backgroundColor":"#1F2E3D","color":"#EDE7D9",
                      "fontFamily":"'IBM Plex Mono',monospace","fontSize":"12px"}}

        # Use carto provider — no Mapbox token required
        try:
            deck = pdk.Deck(
                layers=[polygon_layer],
                initial_view_state=view_state,
                map_provider="carto",
                map_style="dark_matter",
                tooltip=tooltip)
        except Exception:
            # Fallback for older pydeck versions
            deck = pdk.Deck(
                layers=[polygon_layer],
                initial_view_state=view_state,
                map_style=None,
                tooltip=tooltip)
        st.pydeck_chart(deck, use_container_width=True)
    else:
        st.info("No parcels match current filters.")

    # ── neighborhood breakdown ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Neighborhood Breakdown")
    st.caption("Parcels grouped by approximate area (0.5-mile grid cells). Useful for spotting which pockets score highest.")
    bucket = 0.007
    df["_bx"] = (df["cx"]/bucket).round()
    df["_by"] = (df["cy"]/bucket).round()
    nbhd = (df.groupby(["_bx","_by"])
              .agg(parcels=("buildability_score","count"),
                   avg_score=("buildability_score","mean"),
                   avg_value=("property_value","mean"),
                   avg_suppression=("suppression_index","mean"),
                   avg_gap=("value_gap_pct","mean"))
              .reset_index()
              .sort_values("avg_score", ascending=False)
              .head(15))
    nbhd["avg_value"] = nbhd["avg_value"].map("${:,.0f}".format)
    nbhd["avg_score"] = nbhd["avg_score"].map("{:.1f}".format)
    nbhd["avg_suppression"] = nbhd["avg_suppression"].map("{:.1f}".format)
    nbhd["avg_gap"] = (nbhd["avg_gap"]*100).map("{:.0f}%".format)
    nbhd = nbhd.rename(columns={"parcels":"Parcels","avg_score":"Avg Score",
                                 "avg_value":"Avg Value","avg_suppression":"Avg Suppression",
                                 "avg_gap":"Avg Value Gap"})
    st.dataframe(nbhd[["Parcels","Avg Score","Avg Value","Avg Suppression","Avg Value Gap"]],
                 use_container_width=True)
    df.drop(columns=["_bx","_by"],inplace=True)

    # ── top 50 ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Top 50 Parcels by Buildability")
    top50 = df.sort_values("buildability_score",ascending=False).head(50)
    RENAME = {"buildability_score":"Score","property_value":"Assessed Value",
              "suppression_index":"Suppression","value_gap_pct":"Value Gap vs Nearby",
              "crime_score":"Crime (0-100)","school_score":"Schools (0-100)",
              "utility_score":"Utilities","PIDText":"Parcel ID","Full_Prop":"Address"}
    show_cols = [c for c in RENAME if c in top50.columns]
    display = top50[show_cols].rename(columns=RENAME).copy()
    if "Value Gap vs Nearby" in display.columns:
        display["Value Gap vs Nearby"] = (display["Value Gap vs Nearby"]*100).map("{:.0f}%".format)
    if "Assessed Value" in display.columns:
        display["Assessed Value"] = display["Assessed Value"].map("${:,.0f}".format)
    st.dataframe(display, use_container_width=True)

    # ── parcel focus ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Focus a Parcel → Pre-Fill Pro Forma")
    st.caption("Select a parcel below to instantly load its assessed value into the Pro Forma tab.")
    pids = ["(none)"] + list(top50["PIDText"].astype(str))
    chosen = st.selectbox("Select Parcel ID", pids)
    if chosen != "(none)":
        row = top50[top50["PIDText"].astype(str)==chosen].iloc[0]
        set_parcel(row)
        score = row["buildability_score"]
        st.markdown(
            f'<div class="stamp-wrap">'
            f'<div class="stamp"><div class="stamp-num">{score:.0f}</div>'
            f'<div class="stamp-lbl">SCORE</div></div>'
            f'<div style="flex:1"><div style="font-size:.65rem;text-transform:uppercase;'
            f'letter-spacing:.12em;color:#B5562F;font-weight:600;">Parcel {row.get("PIDText","")}</div>'
            f'<div style="font-family:\'IBM Plex Serif\',serif;font-size:1.1rem;color:#1F2E3D;'
            f'font-weight:600;margin:.15rem 0;">{row.get("Full_Prop","Address unavailable")}</div>'
            f'<div style="font-size:.72rem;color:#5C5848;">Pro Forma tab pre-filled with this parcel\'s value</div>'
            f'</div></div>', unsafe_allow_html=True)
        stat_row([
            ("Assessed Value", f"${row.get('property_value',0):,.0f}"),
            ("Suppression Index", f"{row.get('suppression_index',0):.0f} / 100"),
            ("Nearby Avg Value", f"${row.get('nearby_avg_value',0):,.0f}"),
            ("Value Gap vs Nearby", f"{row.get('value_gap_pct',0)*100:.0f}%"),
            ("Buildability Score", f"{score:.0f} / 100"),
        ], accent="#B5562F")
