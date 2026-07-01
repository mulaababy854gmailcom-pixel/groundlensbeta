import streamlit as st

# --- APP CONFIGURATION & STYLING ---
st.set_page_config(page_title="Real Estate Pro Forma Engine", layout="wide")
st.title("🏠 Master Real Estate Pro Forma Engine")
st.markdown("---")

# --- SIDEBAR: GLOBAL STRATEGY SWITCH & ACQUISITION ---
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

# --- SIDEBAR: INITIAL FINANCING ---
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

def calc_monthly_pni(principal, annual_rate, years):
    if principal <= 0 or annual_rate <= 0:
        return 0
    monthly_rate = annual_rate / 12
    num_payments = years * 12
    return principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)

initial_monthly_pni = calc_monthly_pni(initial_loan_amount, interest_rate_init, loan_term_years)

# --- OPERATIONAL LAYER ---
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

# --- REFINANCE LAYER ---
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

# --- UNDERWRITING BREAKOUT ---
st.markdown("---")
st.header("🔍 Underwriting & Structural Breakout")
b1, b2, b3 = st.columns(3)

with b1:
    st.subheader("Initial Debt Structure")
    st.metric("Initial Loan Basis", f"${initial_loan_basis:,.2f}")
    st.metric("Initial Loan Amount", f"${initial_loan_amount:,.2f}")
    st.metric("Initial Monthly P&I Mortgage", f"${initial_monthly_pni:,.2f}", help="This is the monthly mortgage payment before any refinance execution.")

with b2:
    if strategy in ["Rent", "BRRRR"]:
        st.subheader("Monthly Property Operations")
        st.metric("Net Operating Income (NOI)", f"${noi:,.2f}", help="Effective Gross Income minus operating expenses. Mortgage is not included yet.")
        st.metric("Total Operating Expenses (OpEx)", f"${total_opex:,.2f}")
    else:
        st.subheader("Holding Phase Metrics")
        st.metric("Monthly Carrying Cost", f"${monthly_hold_costs:,.2f}")
        st.metric("Total Cumulative Carry", f"${total_holding_costs:,.2f}")

with b3:
    if strategy == "BRRRR":
        st.subheader("Post-Refinance Debt Structure")
        st.metric("New Refinance Loan Amount", f"${refi_loan_amount:,.2f}")
        st.metric("New Refi Monthly P&I Mortgage", f"${refi_monthly_pni:,.2f}", help="This replaces your initial mortgage payment once the refinance closing table settles.")
    elif strategy == "Flip":
        st.subheader("Total Sunk Costs")
        st.metric("Total Capital Sunk", f"${(down_payment_amount + upfront_rehab_cash + closing_costs_buy + total_holding_costs):,.2f}")
    else:
        st.subheader("Financing Baseline")
        st.metric("Active Financing P&I", f"${initial_monthly_pni:,.2f}")

# --- MASTER DASHBOARD ---
st.markdown("---")
st.header(f"📊 Master Dashboard: {strategy.upper()} Metrics")

if strategy == "Rent":
    total_capital_invested = down_payment_amount + closing_costs_buy
    net_monthly_cash_flow = noi - initial_monthly_pni
    coc_return = (net_monthly_cash_flow * 12) / total_capital_invested if total_capital_invested > 0 else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total All-In Capital", f"${total_capital_invested:,.2f}")
    m2.metric("Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}", help="NOI minus Initial Mortgage Payment")
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
    m3.metric("Post-Refi Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}", help="NOI minus New Refinance Mortgage Payment")
    
    if net_trapped_equity <= 0:
        m4.metric("Cash-on-Cash Return", "Infinite (No Cash Left!)")
    else:
        coc_return = (net_monthly_cash_flow * 12) / final_cash_left_in_deal
        m4.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")
