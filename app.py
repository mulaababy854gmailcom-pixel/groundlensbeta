import streamlit as st

# --- APP CONFIGURATION & STYLING ---
st.set_page_config(page_title="Real Estate Pro Forma Engine", layout="wide")
st.title("🏠 Master Real Estate Pro Forma Engine")
st.markdown("---")

# --- SIDEBAR: GLOBAL STRATEGY SWITCH & ACQUISITION ---
st.sidebar.header("1. Strategy & Acquisition")
strategy = st.sidebar.selectbox("Select Investment Strategy", ["Flip", "Rent", "BRRRR"])

purchase_price = st.sidebar.number_input("Purchase Price ($)", value=200000, step=5000)
rehab_cost = st.sidebar.number_input("Estimated Rehab Cost ($)", value=40000, step=1000)
closing_costs_buy = st.sidebar.number_input("Purchase Closing Costs ($)", value=4000, step=500)

# --- SIDEBAR: INITIAL FINANCING ---
st.sidebar.header("2. Initial Financing")
down_payment_pct = st.sidebar.slider("Down Payment %", 0, 100, 20) / 100
interest_rate_init = st.sidebar.number_input("Initial Loan Interest Rate (%)", value=6.5, step=0.1) / 100
loan_term_years = st.sidebar.number_input("Initial Loan Term (Years)", value=30, step=5)

# Calculate Initial Loan Details
down_payment_amount = purchase_price * down_payment_pct
initial_loan_amount = purchase_price - down_payment_amount

# Monthly Mortgage Calculation Function (Standard Amortization)
def calc_monthly_pni(principal, annual_rate, years):
    if principal <= 0 or annual_rate <= 0:
        return 0
    monthly_rate = annual_rate / 12
    num_payments = years * 12
    return principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)

initial_monthly_pni = calc_monthly_pni(initial_loan_amount, interest_rate_init, loan_term_years)

# --- MAIN PAGE: STRATEGY-SPECIFIC INPUTS ---
col1, col2 = st.columns(2)

with col1:
    if strategy in ["Flip", "BRRRR"]:
        st.header("🛠️ Rehab & Exit Variables")
        arv = st.number_input("After Repair Value (ARV) ($)", value=300000, step=5000)
        holding_months = st.number_input("Holding Period (Months)", value=6, step=1)
        monthly_hold_costs = st.number_input("Monthly Holding Costs (Taxes, Ins, Utilities) ($)", value=1200, step=100)
        closing_costs_sell = st.number_input("Selling Closing Costs (Agent Fees, Title) ($)", value=18000, step=500)
        total_holding_costs = holding_months * monthly_hold_costs
    else:
        arv, holding_months, total_holding_costs, closing_costs_sell = 0, 0, 0, 0

with col2:
    if strategy in ["Rent", "BRRRR"]:
        st.header("📈 Rental Income & Expenses")
        gross_rent = st.number_input("Gross Monthly Rent ($)", value=2200, step=100)
        vacancy_pct = st.slider("Vacancy Rate %", 0, 20, 5) / 100
        taxes_monthly = st.number_input("Monthly Property Taxes ($)", value=200, step=25)
        ins_monthly = st.number_input("Monthly Insurance ($)", value=100, step=25)
        pm_pct = st.slider("Property Management Fee %", 0, 15, 8) / 100
        reserves_monthly = st.number_input("Monthly Maint. & CapEx Reserves ($)", value=220, step=20)
        
        # Operational Math
        vacancy_loss = gross_rent * vacancy_pct
        egi = gross_rent - vacancy_loss
        pm_fees = egi * pm_pct
        total_opex = taxes_monthly + ins_monthly + pm_fees + reserves_monthly
        noi = egi - total_opex
    else:
        gross_rent, opex, noi, total_opex = 0, 0, 0, 0

# --- BRRRR CASH-OUT REFINANCE LAYER ---
if strategy == "BRRRR":
    st.markdown("---")
    st.header("💰 Refinance Layer (BRRRR Debt Swap)")
    refi_col1, refi_col2 = st.columns(2)
    with refi_col1:
        refi_ltv = st.slider("Refinance Cash-Out LTV %", 50, 90, 75) / 100
        refi_loan_amount = arv * refi_ltv
    with refi_col2:
        refi_rate = st.number_input("Refinance Interest Rate (%)", value=6.75, step=0.1) / 100
        refi_monthly_pni = calc_monthly_pni(refi_loan_amount, refi_rate, 30)

# --- THE MASTER PERFORMANCE DASHBOARD ---
st.markdown("---")
st.header(f"📊 Master Dashboard: {strategy.upper()} Metrics")

# Math calculations dynamically shifting by Strategy
if strategy == "Rent":
    total_capital_invested = down_payment_amount + closing_costs_buy
    net_monthly_cash_flow = noi - initial_monthly_pni
    coc_return = (net_monthly_cash_flow * 12) / total_capital_invested if total_capital_invested > 0 else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total All-In Capital", f"${total_capital_invested:,.2f}")
    m2.metric("Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}")
    m3.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")

elif strategy == "Flip":
    total_capital_invested = down_payment_amount + rehab_cost + closing_costs_buy + total_holding_costs
    # Profit = Sale Price - All Cash Put In - Cost to Pay off Loan Principal - Costs to Sell
    flip_profit = arv - total_capital_invested - initial_loan_amount - closing_costs_sell
    roi = (flip_profit / total_capital_invested) * 100 if total_capital_invested > 0 else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Active Cash Invested", f"${total_capital_invested:,.2f}")
    m2.metric("Net Flip Profit Margin", f"${flip_profit:,.2f}")
    m3.metric("Return on Investment (ROI)", f"{roi:.2f}%")

elif strategy == "BRRRR":
    # Cash needed to execute the upfront phase
    initial_capital_invested = down_payment_amount + rehab_cost + closing_costs_buy + total_holding_costs
    # Cash returned or paid out at refinance point
    net_refi_proceeds = refi_loan_amount - initial_loan_amount
    trapped_equity = initial_capital_invested - net_refi_proceeds
    # If trapped equity is negative, it's an infinite return (all cash pulled out + extra)
    final_cash_left_in_deal = max(0, trapped_equity)
    
    net_monthly_cash_flow = noi - refi_monthly_pni
    coc_return = (net_monthly_cash_flow * 12) / final_cash_left_in_deal if final_cash_left_in_deal > 0 else float('inf')

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Initial Purchase Cash Needed", f"${initial_capital_invested:,.2f}")
    m2.metric("Cash Left In Deal (Trapped Equity)", f"${final_cash_left_in_deal:,.2f}" if final_cash_left_in_deal > 0 else "Perfect BRRRR ($0 Left!)")
    m3.metric("Post-Refi Monthly Cash Flow", f"${net_monthly_cash_flow:,.2f}")
    if coc_return == float('inf'):
        m4.metric("Cash-on-Cash Return", "Infinite (No Cash Left!)")
    else:
        m4.metric("Cash-on-Cash Return", f"{coc_return * 100:.2f}%")
