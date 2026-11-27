import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google import genai

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI CFO Copilot", page_icon="📊", layout="wide")

# --- SAMPLE DATA GENERATORS ---
@st.cache_data
def load_sample_data(mode="Full Financials (P&L + BS + CF)"):
    pnl_data = [
        ["P&L", "Revenue", "Product Sales", 12000000, 12600000],
        ["P&L", "Revenue", "SaaS & Services", 4500000, 4900000],
        ["P&L", "COGS", "Raw Materials & Procurement", 4800000, 5300000],
        ["P&L", "COGS", "Cloud Hosting & Delivery", 1200000, 1150000],
        ["P&L", "OpEx", "Marketing & Ads", 1500000, 1880000],
        ["P&L", "OpEx", "Salaries & Payroll", 3200000, 3250000],
        ["P&L", "OpEx", "Operations & Rent", 1400000, 1680000],
        ["P&L", "OpEx", "Logistics & Freight", 1100000, 1390000],
        ["P&L", "OpEx", "HR & Admin", 800000, 780000],
        ["P&L", "Interest & Tax", "Interest & Corporate Tax", 650000, 620000],
    ]
    bs_cf_data = [
        ["Balance Sheet", "Current Assets", "Cash & Bank Equivalents", 3500000, 3800000],
        ["Balance Sheet", "Current Assets", "Accounts Receivable & Inventory", 4200000, 4600000],
        ["Balance Sheet", "Fixed Assets", "Plant, Machinery & IT Assets", 9000000, 9200000],
        ["Balance Sheet", "Current Liabilities", "Accounts Payable & Short-Term Dues", 3800000, 4100000],
        ["Balance Sheet", "Long-Term Debt", "Term Loans & Borrowings", 4500000, 4200000],
        ["Balance Sheet", "Equity", "Shareholders Equity & Reserves", 8400000, 9300000],
        ["Cash Flow", "Operating Cash Flow", "Cash Generated from Operations", 2400000, 2150000],
        ["Cash Flow", "Investing Cash Flow", "CapEx & Equipment Purchase", -900000, -1050000],
        ["Cash Flow", "Financing Cash Flow", "Debt Repayment & Dividends", -500000, -450000],
    ]
    cols = ["Statement", "Account_Head", "Category", "Budget_INR", "Actual_INR"]
    if mode == "Only P&L Data":
        return pd.DataFrame(pnl_data, columns=cols)
    return pd.DataFrame(pnl_data + bs_cf_data, columns=cols)

def tag_priority(cat_name):
    c = str(cat_name).lower()
    if any(k in c for k in ["market", "ad", "brand", "event", "travel", "promo", "sponsor", "influencer", "discount"]):
        return "Discretionary"
    elif any(k in c for k in ["logistic", "freight", "ship", "operat", "maint", "pack", "supply", "admin", "hr", "util"]):
        return "Semi-Discretionary"
    return "Core"

# --- SIDEBAR ---
st.sidebar.title("⚙️ Control Panel")
st.sidebar.caption("Auto-Adaptive FP&A Engine: P&L, Balance Sheet, Cash Flow & Expenses.")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key (Free from AI Studio)", type="password")

st.sidebar.divider()
sample_mode = st.sidebar.selectbox(
    "Sample Data Mode (Testing ke liye)",
    ["Full Financials (P&L + BS + CF)", "Only P&L Data"]
)
use_sample = st.sidebar.checkbox("Use Sample Data", value=True)
uploaded_file = st.sidebar.file_uploader("Ya apni Excel/CSV upload karo", type=["xlsx", "csv"])

# --- DATA LOADING (Multi-Sheet Excel Support) ---
df = None
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            xls = pd.ExcelFile(uploaded_file)
            if len(xls.sheet_names) > 1:
                sheet_choice = st.sidebar.selectbox("Select Excel Sheet", xls.sheet_names)
                df = pd.read_excel(xls, sheet_name=sheet_choice)
            else:
                df = pd.read_excel(xls)
        use_sample = False
    except Exception as e:
        st.error(f"File padhne me dikkat aayi. Ensure karein ki Row 1 me clean headers hon. Error: {e}")
elif use_sample:
    df = load_sample_data(sample_mode)

# --- MAIN APP ---
st.title("📊 AI CFO Copilot — Adaptive Financial & FP&A Suite")

if df is not None and not df.empty:
    text_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(text_cols) < 1 or len(num_cols) < 2:
        st.warning("Dashboard ke liye kam se kam 1 Text column aur 2 Numeric columns (Budget, Actual) chahiye.")
        st.dataframe(df.head())
    else:
        st.sidebar.subheader("🔗 Column Mapping")

        head_options = ["None (Expense-Only Mode)"] + text_cols
        default_head_idx = 0
        for idx, col in enumerate(text_cols, start=1):
            if any(k in col.lower() for k in ["head", "type", "pl", "account", "group"]):
                default_head_idx = idx
                break

        head_col = st.sidebar.selectbox("Financial Head Column (Revenue/Assets/CF)", head_options, index=default_head_idx)
        default_cat_idx = 0
        for idx, col in enumerate(text_cols):
            if any(k in col.lower() for k in ["cat", "dept", "item", "particular", "desc"]):
                default_cat_idx = idx
                break

        cat_col = st.sidebar.selectbox("Category / Line Item Column", text_cols, index=default_cat_idx)
        budget_col = st.sidebar.selectbox("Budget / Target Column", num_cols, index=0)
        actual_col = st.sidebar.selectbox("Actual Column", num_cols, index=1 if len(num_cols) > 1 else 0)
        threshold = st.sidebar.slider("Red Flag Variance Threshold (%)", 5, 50, 15)

        # --- AUTO-DETECTION ENGINE ---
        has_pnl, has_bs, has_cf = False, False, False
        ai_context_parts = []

        if head_col != "None (Expense-Only Mode)":
            df["_Head_Clean"] = df[head_col].astype(str).str.strip().str.lower()

            def match_sum(keywords, col_name):
                mask = df["_Head_Clean"].apply(lambda x: any(k in x for k in keywords))
                return df.loc[mask, col_name].sum(), mask.any()

            # 1. P&L Detection
            rev_a, m_rev = match_sum(["rev", "sales", "turnover", "income"], actual_col)
            rev_b, _ = match_sum(["rev", "sales", "turnover", "income"], budget_col)
            cogs_a, m_cogs = match_sum(["cogs", "cost of goods", "direct cost"], actual_col)
            cogs_b, _ = match_sum(["cogs", "cost of goods", "direct cost"], budget_col)
            opex_a, m_opex = match_sum(["opex", "operating exp", "sga", "expense"], actual_col)
            opex_b, _ = match_sum(["opex", "operating exp", "sga", "expense"], budget_col)
            tax_a, _ = match_sum(["tax", "interest", "depreciation", "finance cost"], actual_col)
            tax_b, _ = match_sum(["tax", "interest", "depreciation", "finance cost"], budget_col)

            has_pnl = m_rev or (m_cogs and m_opex)

            # 2. Balance Sheet Detection
            ca_a, m_ca = match_sum(["current asset"], actual_col)
            fa_a, m_fa = match_sum(["fixed asset", "non-current asset"], actual_col)
            cl_a, m_cl = match_sum(["current liab"], actual_col)
            ltd_a, m_ltd = match_sum(["long-term", "debt", "borrowing", "non-current liab"], actual_col)
            eq_a, m_eq = match_sum(["equity", "reserve", "capital"], actual_col)

            has_bs = any([m_ca, m_fa, m_cl, m_ltd, m_eq])

            # 3. Cash Flow Detection
            ocf_a, m_ocf = match_sum(["operating cash", "ocf"], actual_col)
            icf_a, m_icf = match_sum(["investing cash", "capex"], actual_col)
            fcf_fin_a, m_fcf = match_sum(["financing cash"], actual_col)

            has_cf = any([m_ocf, m_icf, m_fcf])

            # Build Summary Table
            summary_df = df.groupby([head_col, cat_col], as_index=False)[[budget_col, actual_col]].sum()
        else:
            summary_df = df.groupby(cat_col, as_index=False)[[budget_col, actual_col]].sum()

        # Variance Calculation
        summary_df["Variance"] = summary_df[actual_col] - summary_df[budget_col]
        summary_df["Variance_%"] = summary_df.apply(
            lambda r: round((r["Variance"] / abs(r[budget_col])) * 100, 2) if r[budget_col] != 0 else 0.0, axis=1
        )

        def get_status(row):
            head_txt = str(row[head_col]).lower() if head_col != "None (Expense-Only Mode)" else ""
            v_pct = row["Variance_%"]
            if any(k in head_txt for k in ["rev", "sales", "income", "asset", "equity", "operating cash"]):
                return "🔴 Below Target" if v_pct < -threshold else ("🟢 Above Target" if v_pct > 0 else "🟡 On Track")
            return "🔴 Red Flag (Overrun)" if v_pct > threshold else ("🟢 Under Budget" if v_pct < 0 else "🟡 On Track")

        summary_df["Status"] = summary_df.apply(get_status, axis=1)
        red_flags = summary_df[summary_df["Status"].str.contains("🔴")]

        # Active Modules Badge
        detected_modules = []
        if has_pnl: detected_modules.append("P&L Statement")
        if has_bs: detected_modules.append("Balance Sheet")
        if has_cf: detected_modules.append("Cash Flow")
        if not detected_modules: detected_modules.append("Expense Variance")
        st.caption(f"🔎 **Auto-Detected Modules:** {'  •  '.join(detected_modules)}")

        # --- 4 TABS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Adaptive Executive Dashboard",
            "🎯 Break-Even & Auto Cut-Down",
            "🔍 Budget Reconciliation",
            "🤖 AI CFO Chat"
        ])

        # ==================== TAB 1: ADAPTIVE EXECUTIVE DASHBOARD ====================
        with tab1:
            # --- SECTION 1: P&L ---
            if has_pnl:
                st.subheader("1️⃣ Profit & Loss (P&L) Performance")
                gp_a, gp_b = rev_a - cogs_a, rev_b - cogs_b
                gm_a = round((gp_a / rev_a) * 100, 1) if rev_a else 0.0
                gm_b = round((gp_b / rev_b) * 100, 1) if rev_b else 0.0

                ebitda_a, ebitda_b = gp_a - opex_a, gp_b - opex_b
                ebitda_m_a = round((ebitda_a / rev_a) * 100, 1) if rev_a else 0.0
                ebitda_m_b = round((ebitda_b / rev_b) * 100, 1) if rev_b else 0.0

                net_a = ebitda_a - tax_a
                net_m_a = round((net_a / rev_a) * 100, 1) if rev_a else 0.0

                c1, c2, c3, c4, c5 = st.columns(5)
                rev_diff = round(((rev_a - rev_b) / rev_b) * 100, 1) if rev_b else 0.0
                opex_diff = round(((opex_a - opex_b) / opex_b) * 100, 1) if opex_b else 0.0

                c1.metric("Total Revenue", f"₹{rev_a:,.0f}", f"{rev_diff}% vs Bgt")
                c2.metric("Gross Profit", f"₹{gp_a:,.0f}", f"GM: {gm_a}% (Bgt {gm_b}%)")
                c3.metric("Operating Exp (OpEx)", f"₹{opex_a:,.0f}", f"{opex_diff}% vs Bgt", delta_color="inverse")
                c4.metric("EBITDA", f"₹{ebitda_a:,.0f}", f"Margin: {ebitda_m_a}% (Bgt {ebitda_m_b}%)")
                c5.metric("Net Profit (PAT)", f"₹{net_a:,.0f}", f"Net Margin: {net_m_a}%")

                ai_context_parts.append(
                    f"P&L: Revenue ₹{rev_a:,.0f} (Bgt ₹{rev_b:,.0f}), COGS ₹{cogs_a:,.0f}, "
                    f"Gross Margin {gm_a}%, OpEx ₹{opex_a:,.0f}, EBITDA ₹{ebitda_a:,.0f} ({ebitda_m_a}%), Net Profit ₹{net_a:,.0f} ({net_m_a}%)."
                )

                col_l, col_r = st.columns(2)
                with col_l:
                    fig_wf = go.Figure(go.Waterfall(
                        orientation="v",
                        measure=["relative", "relative", "total", "relative", "total", "relative", "total"],
                        x=["Revenue", "COGS", "Gross Profit", "OpEx", "EBITDA", "Int & Tax", "Net Profit"],
                        y=[rev_a, -cogs_a, 0, -opex_a, 0, -tax_a, 0],
                        textposition="outside"
                    ))
                    fig_wf.update_layout(title="P&L Bridge (Revenue to Net Profit)", showlegend=False)
                    st.plotly_chart(fig_wf, use_container_width=True)
                with col_r:
                    pnl_only = summary_df[summary_df[head_col].astype(str).str.lower().apply(
                        lambda x: any(k in x for k in ["rev", "sales", "cogs", "opex", "tax", "interest", "expense"])
                    )]
                    fig_bar = px.bar(pnl_only, x=cat_col, y=[budget_col, actual_col], barmode="group", title="P&L Budget vs Actual")
                    st.plotly_chart(fig_bar, use_container_width=True)
                st.divider()

            # --- SECTION 2: BALANCE SHEET ---
            if has_bs:
                st.subheader("2️⃣ Balance Sheet & Financial Health")
                tot_assets = ca_a + fa_a
                tot_liab = cl_a + ltd_a
                curr_ratio = round(ca_a / cl_a, 2) if cl_a > 0 else 0.0
                debt_to_eq = round(tot_liab / eq_a, 2) if eq_a > 0 else 0.0

                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Total Assets", f"₹{tot_assets:,.0f}")
                b2.metric("Total Liabilities", f"₹{tot_liab:,.0f}")
                b3.metric("Current Ratio", f"{curr_ratio}x", "Healthy > 1.5x")
                b4.metric("Debt-to-Equity", f"{debt_to_eq}x", "Safe < 1.0x", delta_color="inverse
