import io
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

def ai_auto_clean_file(raw_df, api_key):
    client = genai.Client(api_key=api_key)
    raw_text = raw_df.head(60).to_csv(index=False, header=False)

    clean_prompt = f"""
    You are a Financial Data Engineer. Convert this messy financial spreadsheet (e.g., Screener.in, Tally, ERP export) into a clean CSV with EXACTLY 4 columns:
    Account_Head,Category,Budget_INR,Actual_INR

    STRICT RULES:
    1. Drop all percentage, ratio, margin, or growth rows (e.g., Tax %, Margin %, Growth %, Employee Cost %, EPS, Dividend Payout).
    2. Drop all subtotal/total rows (e.g., Gross Profit, EBITDA, Operating Profit, Financing Profit, PBT, Profit before tax, Net Profit, Total Assets, Total Liabilities).
    3. Map Account_Head strictly to one of these exact labels:
       Revenue, COGS, OpEx, Interest & Tax, Current Assets, Fixed Assets, Current Liabilities, Long-Term Debt, Equity, Operating Cash Flow, Investing Cash Flow, Financing Cash Flow
    4. If the file has multiple years/periods, pick the 2 most recent numeric columns: put the older period in Budget_INR and the latest period in Actual_INR.
    5. Use pure numbers only in Budget_INR and Actual_INR (no commas, no currency symbols, no % signs). Replace missing/blank values with 0.
    6. Return ONLY the raw CSV text starting with the header line. No markdown backticks, no explanation.

    RAW DATA:
    {raw_text}
    """

    for m_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        try:
            resp = client.models.generate_content(model=m_name, contents=clean_prompt).text
            clean_csv = resp.replace("```csv", "").replace("```", "").strip()
            cleaned = pd.read_csv(io.StringIO(clean_csv))
            cleaned["Budget_INR"] = pd.to_numeric(cleaned["Budget_INR"], errors="coerce").fillna(0)
            cleaned["Actual_INR"] = pd.to_numeric(cleaned["Actual_INR"], errors="coerce").fillna(0)
            return cleaned
        except Exception:
            continue
    return None

# --- SIDEBAR ---
st.sidebar.title("⚙️ Control Panel")
st.sidebar.caption("Auto-Adaptive FP&A Engine + AI Smart Data Cleaner.")

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

# --- DATA LOADING + AI SMART CLEANER ---
df = None
if uploaded_file is not None:
    try:
        sheet_choice = None
        if uploaded_file.name.endswith(".csv"):
            df_raw_header = pd.read_csv(uploaded_file)
            uploaded_file.seek(0)
            df_raw_noheader = pd.read_csv(uploaded_file, header=None)
        else:
            xls = pd.ExcelFile(uploaded_file)
            if len(xls.sheet_names) > 1:
                sheet_choice = st.sidebar.selectbox("Select Excel Sheet", xls.sheet_names)
            else:
                sheet_choice = xls.sheet_names[0]
            df_raw_header = pd.read_excel(xls, sheet_name=sheet_choice)
            df_raw_noheader = pd.read_excel(xls, sheet_name=sheet_choice, header=None)

        file_key = f"{uploaded_file.name}_{sheet_choice}"
        auto_clean = st.sidebar.checkbox("✨ Auto-Clean Messy File with AI (Screener/Tally)", value=True)

        if auto_clean:
            if not api_key:
                st.sidebar.warning("AI Auto-Clean ke liye Gemini API key zaroori hai.")
                df = df_raw_header
            else:
                if st.session_state.get("cleaned_file_key") != file_key:
                    with st.spinner("🤖 AI aapki raw file ko clean aur standardize kar raha hai..."):
                        cleaned_df = ai_auto_clean_file(df_raw_noheader, api_key)
                        if cleaned_df is not None and not cleaned_df.empty:
                            st.session_state["cleaned_df"] = cleaned_df
                            st.session_state["cleaned_file_key"] = file_key
                        else:
                            st.error("AI file clean nahi kar paya. Normal mode me load kar rahe hain.")
                            st.session_state["cleaned_df"] = df_raw_header
                df = st.session_state.get("cleaned_df", df_raw_header)
                st.success("✨ AI Smart Cleaner active hai! Messy file automatically clean ho gayi hai.")
        else:
            df = df_raw_header
        use_sample = False
    except Exception as e:
        st.error(f"File padhne me dikkat aayi. Error: {e}")
elif use_sample:
    df = load_sample_data(sample_mode)

# --- MAIN APP ---
st.title("📊 AI CFO Copilot — Adaptive Financial & FP&A Suite")

if df is not None and not df.empty:
    # Clean datetime & newline column names (Screener/Excel fix)
    df.columns = [
        c.strftime("%b %Y") if hasattr(c, "strftime") else str(c).strip()
        for c in df.columns
    ]

    text_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(text_cols) < 1 or len(num_cols) < 2:
        st.warning("Dashboard ke liye kam se kam 1 Text column aur 2 Numeric columns chahiye. Agar file messy hai toh sidebar me '✨ Auto-Clean Messy File with AI' tick karein.")
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
        budget_col = st.sidebar.selectbox("Budget / Previous Period Column", num_cols, index=0)
        actual_col = st.sidebar.selectbox("Actual / Latest Period Column", num_cols, index=1 if len(num_cols) > 1 else 0)
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
                rev_diff = round(((rev_a - rev_b) / abs(rev_b)) * 100, 1) if rev_b else 0.0
                opex_diff = round(((opex_a - opex_b) / abs(opex_b)) * 100, 1) if opex_b else 0.0

                c1.metric("Total Revenue", f"₹{rev_a:,.0f}", f"{rev_diff}% vs Prev/Bgt")
                c2.metric("Gross Profit", f"₹{gp_a:,.0f}", f"GM: {gm_a}% (Prev {gm_b}%)")
                c3.metric("Operating Exp (OpEx)", f"₹{opex_a:,.0f}", f"{opex_diff}% vs Prev/Bgt", delta_color="inverse")
                c4.metric("EBITDA", f"₹{ebitda_a:,.0f}", f"Margin: {ebitda_m_a}% (Prev {ebitda_m_b}%)")
                c5.metric("Net Profit (PAT)", f"₹{net_a:,.0f}", f"Net Margin: {net_m_a}%")

                ai_context_parts.append(
                    f"P&L: Revenue ₹{rev_a:,.0f} (Prev/Bgt ₹{rev_b:,.0f}), COGS ₹{cogs_a:,.0f}, "
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
                    fig_bar = px.bar(pnl_only, x=cat_col, y=[budget_col, actual_col], barmode="group", title="P&L Comparison")
                    st.plotly_chart(fig_bar, use_container_width=True)
                st.divider()

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
                b4.metric("Debt-to-Equity", f"{debt_to_eq}x", "Safe < 1.0x", delta_color="inverse")

                ai_context_parts.append(
                    f"Balance Sheet: Total Assets ₹{tot_assets:,.0f}, Liabilities ₹{tot_liab:,.0f}, Equity ₹{eq_a:,.0f}, "
                    f"Current Ratio {curr_ratio}x, Debt-to-Equity {debt_to_eq}x."
                )
                st.divider()

            if has_cf:
                st.subheader("3️⃣ Cash Flow & Liquidity")
                free_cf = ocf_a + icf_a
                net_cf = ocf_a + icf_a + fcf_fin_a

                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Operating Cash Flow", f"₹{ocf_a:,.0f}")
                f2.metric("Investing Cash Flow (CapEx)", f"₹{icf_a:,.0f}")
                f3.metric("Free Cash Flow (FCF)", f"₹{free_cf:,.0f}")
                f4.metric("Net Cash Change", f"₹{net_cf:,.0f}")

                ai_context_parts.append(
                    f"Cash Flow: Operating CF ₹{ocf_a:,.0f}, Investing CF ₹{icf_a:,.0f}, Free Cash Flow ₹{free_cf:,.0f}, Net Cash Change ₹{net_cf:,.0f}."
                )
                st.divider()

            if not (has_pnl or has_bs or has_cf):
                tot_b, tot_a = summary_df[budget_col].sum(), summary_df[actual_col].sum()
                net_v = tot_a - tot_b
                net_vp = round((net_v / abs(tot_b)) * 100, 2) if tot_b else 0.0

                e1, e2, e3, e4 = st.columns(4)
                e1.metric("Total Budget / Prev", f"₹{tot_b:,.0f}")
                e2.metric("Total Actual / Latest", f"₹{tot_a:,.0f}")
                e3.metric("Net Variance", f"₹{net_v:,.0f}", f"{net_vp}%", delta_color="inverse")
                e4.metric("Red Flag Areas", f"{len(red_flags)} / {len(summary_df)}")

                ai_context_parts.append(f"Expense Summary: Budget ₹{tot_b:,.0f}, Actual ₹{tot_a:,.0f}, Variance ₹{net_v:,.0f} ({net_vp}%).")
                fig_bar = px.bar(summary_df, x=cat_col, y=[budget_col, actual_col], barmode="group", title="Budget vs Actual Comparison")
                st.plotly_chart(fig_bar, use_container_width=True)
                st.divider()

            st.subheader(f"🚨 High Variance Alerts (Threshold: {threshold}%)")
            if not red_flags.empty:
                st.dataframe(red_flags, use_container_width=True, hide_index=True)
            else:
                st.success("Koi bhi line item threshold se bahar nahi gaya hai!")

            with st.expander("View Full Financial Summary Table (Verify AI-Cleaned Data)"):
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ==================== TAB 2: BREAK-EVEN & AUTO CUT-DOWN ====================
        with tab2:
            st.subheader("🎯 Break-Even, Market Trends & Auto Budget Cut-Down Engine")
            if not has_pnl or rev_a <= 0:
                st.info("Is simulator ke liye P&L data (Revenue, COGS, OpEx) zaroori hai.")
            else:
                m1, m2, m3 = st.columns(3)
                with m1:
                    goal_mode = st.radio("Goal Mode", ["Break-Even (0% EBITDA)", "Profitable (Target EBITDA %)"], index=1)
                with m2:
                    rev_trend = st.slider("Market Trend: Revenue Change (%)", -30, 30, -10)
                with m3:
                    inf_trend = st.slider("Market Trend: Cost Inflation (%)", -10, 25, 8)

                target_ebitda_pct = st.slider("Target EBITDA Margin (%)", 5, 40, 18) if "Profitable" in goal_mode else 0.0

                proj_rev = rev_a * (1 + rev_trend / 100.0)
                proj_cogs = cogs_a * (1 + inf_trend / 100.0)
                proj_opex = opex_a * (1 + inf_trend / 100.0)
                proj_gp = proj_rev - proj_cogs
                proj_gm_ratio = (proj_gp / proj_rev) if proj_rev > 0 else 0.0
                proj_ebitda = proj_gp - proj_opex
                proj_ebitda_pct = round((proj_ebitda / proj_rev) * 100, 1) if proj_rev > 0 else 0.0

                break_even_rev = (proj_opex / proj_gm_ratio) if proj_gm_ratio > 0 else 0.0
                savings_needed = max(0.0, (proj_rev * (target_ebitda_pct / 100.0)) - proj_ebitda)

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Projected Revenue", f"₹{proj_rev:,.0f}", f"{rev_trend}% trend")
                k2.metric("Break-Even Revenue", f"₹{break_even_rev:,.0f}")
                k3.metric("Projected EBITDA", f"₹{proj_ebitda:,.0f}", f"Margin: {proj_ebitda_pct}%")
                k4.metric("Budget Cut Needed", f"₹{savings_needed:,.0f}", delta_color="inverse")

                opex_df = summary_df[summary_df[head_col].astype(str).str.lower().apply(
                    lambda x: any(k in x for k in ["opex", "operating exp", "sga", "expense"])
                )].copy()

                if not opex_df.empty:
                    opex_df["Projected_Spend"] = opex_df[actual_col] * (1 + inf_trend / 100.0)
                    opex_df["Priority"] = opex_df[cat_col].apply(tag_priority)
                    cut_caps = {"Discretionary": 0.35, "Semi-Discretionary": 0.15, "Core": 0.05}
                    opex_df["_ord"] = opex_df["Priority"].map({"Discretionary": 1, "Semi-Discretionary": 2, "Core": 3})
                    opex_df = opex_df.sort_values(by=["_ord", "Projected_Spend"], ascending=[True, False])

                    rem = savings_needed
                    cuts = []
                    for _, r in opex_df.iterrows():
                        c_val = min(rem, r["Projected_Spend"] * cut_caps[r["Priority"]]) if rem > 0 else 0.0
                        cuts.append(round(c_val, 0))
                        rem -= c_val

                    opex_df["Recommended_Cut_INR"] = cuts
                    opex_df["Cut_%"] = opex_df.apply(lambda r: round((r["Recommended_Cut_INR"] / r["Projected_Spend"]) * 100, 1) if r["Projected_Spend"] > 0 else 0.0, axis=1)
                    opex_df["Revised_Budget_INR"] = opex_df["Projected_Spend"] - opex_df["Recommended_Cut_INR"]

                    show_cols = [cat_col, "Priority", "Projected_Spend", "Recommended_Cut_INR", "Cut_%", "Revised_Budget_INR"]
                    st.subheader("✂️ Auto-Generated Budget Cut-Down Plan")
                    st.dataframe(opex_df[show_cols], use_container_width=True, hide_index=True)
                    st.download_button("⬇️ Download Revised Budget (CSV)", opex_df[show_cols].to_csv(index=False).encode("utf-8"), "revised_budget.csv", "text/csv")

        # ==================== TAB 3: BUDGET RECONCILIATION ====================
        with tab3:
            st.subheader("🔍 Automated Budget vs Actual Reconciliation")
            rc1, rc2 = st.columns(2)
            bgt_file = rc1.file_uploader("Upload Budget File", type=["xlsx", "csv"], key="rec_b")
            act_file = rc2.file_uploader("Upload Actual ERP File", type=["xlsx", "csv"], key="rec_a")

            if bgt_file and act_file:
                try:
                    df_b = pd.read_csv(bgt_file) if bgt_file.name.endswith(".csv") else pd.read_excel(bgt_file)
                    df_a = pd.read_csv(act_file) if act_file.name.endswith(".csv") else pd.read_excel(act_file)
                    common_cols = list(set(df_b.columns).intersection(set(df_a.columns)))
                    if common_cols:
                        key_col = st.selectbox("Common Key Column", common_cols)
                        b_val = st.selectbox("Budget Amount Column", df_b.select_dtypes(include=["number"]).columns.tolist())
                        a_val = st.selectbox("Actual Amount Column", df_a.select_dtypes(include=["number"]).columns.tolist())
                        gb = df_b.groupby(key_col, as_index=False)[b_val].sum().rename(columns={b_val: "Budget_Amount"})
                        ga = df_a.groupby(key_col, as_index=False)[a_val].sum().rename(columns={a_val: "Actual_Amount"})
                        rec_df = pd.merge(gb, ga, on=key_col, how="outer", indicator=True).fillna(0)
                        rec_df["Difference"] = rec_df["Actual_Amount"] - rec_df["Budget_Amount"]
                        rec_df["Status"] = rec_df["_merge"].map({"both": "✅ Matched", "left_only": "🟡 Unutilized", "right_only": "🔴 Unbudgeted"})
                        st.dataframe(rec_df.drop(columns=["_merge"]), use_container_width=True, hide_index=True)
                    else:
                        st.error("Dono files me kam se kam 1 common column hona chahiye.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.caption("Current loaded file ka quick reconciliation status:")
                q_rec = summary_df.copy()
                q_rec["Recon_Status"] = q_rec.apply(
                    lambda r: "🔴 Unbudgeted" if r[budget_col] == 0 and r[actual_col] != 0 else ("🟡 Unutilized" if r[actual_col] == 0 and r[budget_col] != 0 else "✅ Reconciled"), axis=1
                )
                st.dataframe(q_rec[[cat_col, budget_col, actual_col, "Variance", "Recon_Status"]], use_container_width=True, hide_index=True)

        # ==================== TAB 4: AI CFO CHAT ====================
        with tab4:
            st.subheader("💬 AI CFO Assistant")
            if not api_key:
                st.info("Sidebar me Gemini API key daalein.")
            else:
                if "messages" not in st.session_state:
                    st.session_state.messages = []

                q1, q2, q3 = st.columns(3)
                qp = None
                if q1.button("📉 Full Financial Health Review"):
                    qp = "Mere uploaded financial data (P&L, Balance Sheet, Cash Flow jo bhi available hai) ka complete CFO health review do."
                if q2.button("✂️ Cost Cut-Down Strategy"):
                    qp = "Overruns aur market slowdown ko dekhte hue cost optimize karne ke top 3 recommendations do."
                if q3.button("📋 Boardroom Summary"):
                    qp = "Board meeting ke liye 4-bullet executive summary bana do."

                for msg in st.session_state.messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                prompt = qp or st.chat_input("Apne financials ke baare me kuch bhi pucho...")
                if prompt:
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    data_context = f"""
                    You are an expert Corporate CFO & FP&A Analyst.
                    Answer strictly based on these Python-verified financial figures. Do NOT invent numbers.

                    VERIFIED METRICS:
                    {chr(10).join(ai_context_parts)}

                    DETAILED TABLE:
                    {summary_df.to_markdown(index=False)}
                    """

                    with st.chat_message("assistant"):
                        with st.spinner("Analyzing financials..."):
                            try:
                                client = genai.Client(api_key=api_key)
                                hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
                                full_prompt = f"{data_context}\n\nHistory:\n{hist}\n\nAnswer concisely."
                                ans = None
                                for m_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
                                    try:
                                        ans = client.models.generate_content(model=m_name, contents=full_prompt).text
                                        break
                                    except Exception:
                                        continue
                                if ans:
                                    st.markdown(ans)
                                    st.session_state.messages.append({"role": "assistant", "content": ans})
                                else:
                                    st.error("AI server abhi thoda busy hai. 5 second baad try karein.")
                            except Exception as e:
                                st.error(f"Error: {e}")
else:
    st.info("Sidebar se Sample Data tick karein ya apni Excel/CSV upload karein.")
