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

def fmt_val(val, unit_suffix):
    return f"₹{val:,.0f}{unit_suffix}"

def ai_auto_clean_file(raw_df, api_key):
    client = genai.Client(api_key=api_key)
    raw_text = raw_df.head(60).to_csv(index=False, header=False)

    clean_prompt = f"""
    You are a Financial Data Engineer. Convert this messy financial spreadsheet (e.g., Screener.in, Tally, ERP export) into a clean CSV with EXACTLY 4 columns:
    Account_Head,Category,Previous_Period,Latest_Period

    STRICT RULES:
    1. Drop all percentage, ratio, margin, or growth rows (e.g., Tax %, Margin %, Growth %, Employee Cost %, EPS, Dividend Payout).
    2. Drop all subtotal/total rows (e.g., Gross Profit, EBITDA, Operating Profit, Financing Profit, PBT, Profit before tax, Net Profit, Total Assets, Total Liabilities).
    3. Map Account_Head strictly to one of these exact labels:
       Revenue, COGS, OpEx, Interest & Tax, Current Assets, Fixed Assets, Current Liabilities, Long-Term Debt, Equity, Operating Cash Flow, Investing Cash Flow, Financing Cash Flow
    4. If the file has multiple years/periods, pick the 2 most recent numeric columns: put the older period in Previous_Period and the latest period in Latest_Period.
    5. Use pure numbers only in Previous_Period and Latest_Period (no commas, no currency symbols, no % signs). Replace missing/blank values with 0.
    6. Return ONLY the raw CSV text starting with the header line. No markdown backticks, no explanation.

    RAW DATA:
    {raw_text}
    """

    for m_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        try:
            resp = client.models.generate_content(model=m_name, contents=clean_prompt).text
            clean_csv = resp.replace("```csv", "").replace("```", "").strip()
            cleaned = pd.read_csv(io.StringIO(clean_csv))
            cleaned["Previous_Period"] = pd.to_numeric(cleaned["Previous_Period"], errors="coerce").fillna(0)
            cleaned["Latest_Period"] = pd.to_numeric(cleaned["Latest_Period"], errors="coerce").fillna(0)
            return cleaned
        except Exception:
            continue
    return None

# --- SIDEBAR ---
st.sidebar.title("⚙️ Control Panel")
st.sidebar.caption("Smart FP&A Engine + AI Auto-Cleaner + Plain-Language Insights.")

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
            sheet_choice = st.sidebar.selectbox("Select Excel Sheet", xls.sheet_names) if len(xls.sheet_names) > 1 else xls.sheet_names[0]
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
        else:
            df = df_raw_header
        use_sample = False
    except Exception as e:
        st.error(f"File padhne me dikkat aayi. Error: {e}")
elif use_sample:
    df = load_sample_data(sample_mode)

# --- MAIN APP ---
st.title("📊 AI CFO Copilot — Smart Financial & FP&A Suite")

if df is not None and not df.empty:
    df.columns = [
        c.strftime("%b %Y") if hasattr(c, "strftime") else str(c).strip()
        for c in df.columns
    ]

    text_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(text_cols) < 1 or len(num_cols) < 2:
        st.warning("Dashboard ke liye kam se kam 1 Text column aur 2 Numeric columns chahiye.")
        st.dataframe(df.head())
    else:
        st.sidebar.subheader("🔗 Column & Unit Settings")

        # Smart Unit Selector (Auto-guess Crores if max value < 1,00,000)
        max_num = df[num_cols].abs().max().max()
        default_unit_idx = 2 if (uploaded_file is not None and max_num < 100000) else 0
        unit_choice = st.sidebar.selectbox("Currency Unit", ["INR (₹)", "Lakhs (₹ L)", "Crores (₹ Cr)"], index=default_unit_idx)
        unit_suffix = "" if "INR" in unit_choice else (" L" if "Lakhs" in unit_choice else " Cr")

        head_options = ["None (Expense-Only Mode)"] + text_cols
        default_head_idx = 0
        for idx, col in enumerate(text_cols, start=1):
            if any(k in col.lower() for k in ["head", "type", "pl", "account", "group"]):
                default_head_idx = idx
                break

        head_col = st.sidebar.selectbox("Financial Head Column", head_options, index=default_head_idx)
        default_cat_idx = 0
        for idx, col in enumerate(text_cols):
            if any(k in col.lower() for k in ["cat", "dept", "item", "particular", "desc"]):
                default_cat_idx = idx
                break

        cat_col = st.sidebar.selectbox("Category / Line Item Column", text_cols, index=default_cat_idx)
        budget_col = st.sidebar.selectbox("Base / Budget / Previous Column", num_cols, index=0)
        actual_col = st.sidebar.selectbox("Current / Actual / Latest Column", num_cols, index=1 if len(num_cols) > 1 else 0)
        threshold = st.sidebar.slider("Red Flag Variance Threshold (%)", 5, 50, 15)

        # Smart Mode Labels (Budget vs Actual OR YoY Period Comparison)
        is_budget_mode = "budget" in budget_col.lower() or "target" in budget_col.lower()
        base_label = "Budget" if is_budget_mode else "Previous"
        curr_label = "Actual" if is_budget_mode else "Latest"

        # --- AUTO-DETECTION ENGINE ---
        has_pnl, has_bs, has_cf = False, False, False
        ai_context_parts = []
        verdict_points = []

        if head_col != "None (Expense-Only Mode)":
            df["_Head_Clean"] = df[head_col].astype(str).str.strip().str.lower()

            def match_sum(keywords, col_name):
                mask = df["_Head_Clean"].apply(lambda x: any(k in x for k in keywords))
                return df.loc[mask, col_name].sum(), mask.any()

            # 1. P&L
            rev_a, m_rev = match_sum(["rev", "sales", "turnover", "income"], actual_col)
            rev_b, _ = match_sum(["rev", "sales", "turnover", "income"], budget_col)
            cogs_a, m_cogs = match_sum(["cogs", "cost of goods", "direct cost"], actual_col)
            cogs_b, _ = match_sum(["cogs", "cost of goods", "direct cost"], budget_col)
            opex_a, m_opex = match_sum(["opex", "operating exp", "sga", "expense"], actual_col)
            opex_b, _ = match_sum(["opex", "operating exp", "sga", "expense"], budget_col)
            tax_a, _ = match_sum(["tax", "interest", "depreciation", "finance cost"], actual_col)

            has_pnl = m_rev or (m_cogs and m_opex)

            # 2. Balance Sheet
            ca_a, m_ca = match_sum(["current asset"], actual_col)
            fa_a, m_fa = match_sum(["fixed asset", "non-current asset"], actual_col)
            cl_a, m_cl = match_sum(["current liab"], actual_col)
            ltd_a, m_ltd = match_sum(["long-term", "debt", "borrowing", "non-current liab"], actual_col)
            eq_a, m_eq = match_sum(["equity", "reserve", "capital"], actual_col)
            has_bs = any([m_ca, m_fa, m_cl, m_ltd, m_eq])

            # 3. Cash Flow
            ocf_a, m_ocf = match_sum(["operating cash", "ocf"], actual_col)
            icf_a, m_icf = match_sum(["investing cash", "capex"], actual_col)
            fcf_fin_a, m_fcf = match_sum(["financing cash"], actual_col)
            has_cf = any([m_ocf, m_icf, m_fcf])

            summary_df = df.groupby([head_col, cat_col], as_index=False)[[budget_col, actual_col]].sum()
        else:
            summary_df = df.groupby(cat_col, as_index=False)[[budget_col, actual_col]].sum()

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
        st.caption(f"🔎 **Auto-Detected:** {' • '.join(detected_modules)}  |  **Comparison:** {base_label} vs {curr_label}  |  **Unit:** {unit_choice}")

        # --- 4 TABS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Smart Executive Dashboard",
            "🎯 Break-Even & Auto Cut-Down",
            "🔍 Budget Reconciliation",
            "🤖 AI CFO Chat"
        ])

        # ==================== TAB 1: SMART EXECUTIVE DASHBOARD ====================
        with tab1:
            if has_pnl:
                gp_a, gp_b = rev_a - cogs_a, rev_b - cogs_b
                gm_a = round((gp_a / rev_a) * 100, 1) if rev_a else 0.0
                gm_b = round((gp_b / rev_b) * 100, 1) if rev_b else 0.0
                ebitda_a, ebitda_b = gp_a - opex_a, gp_b - opex_b
                ebitda_m_a = round((ebitda_a / rev_a) * 100, 1) if rev_a else 0.0
                ebitda_m_b = round((ebitda_b / rev_b) * 100, 1) if rev_b else 0.0
                net_a = ebitda_a - tax_a
                net_m_a = round((net_a / rev_a) * 100, 1) if rev_a else 0.0
                rev_diff = round(((rev_a - rev_b) / abs(rev_b)) * 100, 1) if rev_b else 0.0
                opex_diff = round(((opex_a - opex_b) / abs(opex_b)) * 100, 1) if opex_b else 0.0

                rev_word = "badha hai (📈)" if rev_diff >= 0 else "gira hai (📉)"
                profit_word = "Profitable" if net_a > 0 else "Loss me"
                verdict_points.append(f"**Business Health:** Company **{profit_word}** hai — Total Revenue **{fmt_val(rev_a, unit_suffix)}** ({rev_diff}% {rev_word}) aur Net Profit **{fmt_val(net_a, unit_suffix)}** ({net_m_a}% margin).")
                verdict_points.append(f"**Operating Efficiency:** EBITDA Margin **{ebitda_m_a}%** hai (pichle period me {ebitda_m_b}% tha). Operating Expenses **{opex_diff}%** change hue hain.")

            if has_bs:
                tot_assets = ca_a + fa_a
                tot_liab = cl_a + ltd_a
                curr_ratio = round(ca_a / cl_a, 2) if cl_a > 0 else 0.0
                debt_to_eq = round(tot_liab / eq_a, 2) if eq_a > 0 else 0.0
                liq_status = "Safe & Liquid ✅" if curr_ratio >= 1.5 else "Liquidity Tight ⚠️"
                verdict_points.append(f"**Balance Sheet Health:** Current Ratio **{curr_ratio}x** ({liq_status}) aur Debt-to-Equity **{debt_to_eq}x** hai.")

            if not red_flags.empty:
                top_rf = red_flags.sort_values("Variance_%", ascending=False).iloc[0]
                verdict_points.append(f"**Action Alert:** `{top_rf[cat_col]}` me **{top_rf['Variance_%']}%** ka variance hai — isko review karein ya Tab 2 me cut-down simulate karein.")

            if verdict_points:
                with st.container(border=True):
                    st.markdown("#### 🧠 Quick CFO Verdict (Simple Summary)")
                    for pt in verdict_points:
                        st.markdown(f"- {pt}")

            # --- SECTION 1: P&L ---
            if has_pnl:
                st.subheader("1️⃣ Profit & Loss (P&L) Performance")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Total Revenue", fmt_val(rev_a, unit_suffix), f"{rev_diff}% vs {base_label}", help="Company ki kul kamai (Sales + Income).")
                c2.metric("Gross Profit", fmt_val(gp_a, unit_suffix), f"GM: {gm_a}% ({base_label} {gm_b}%)", help="Revenue minus Direct Cost (COGS). Jitna zyada, utna achha.")
                c3.metric("Operating Exp (OpEx)", fmt_val(opex_a, unit_suffix), f"{opex_diff}% vs {base_label}", delta_color="inverse", help="Business chalane ka kharch (Salaries, Marketing, Rent, Logistics).")
                c4.metric("EBITDA", fmt_val(ebitda_a, unit_suffix), f"Margin: {ebitda_m_a}%", help="Core operating profit (Interest aur Tax katne se pehle). 15%+ healthy maana jata hai.")
                c5.metric("Net Profit (PAT)", fmt_val(net_a, unit_suffix), f"Net Margin: {net_m_a}%", help="Saare kharch, Interest aur Tax ke baad bacha hua asli munafa.")

                ai_context_parts.append(
                    f"P&L ({unit_choice}): Revenue {fmt_val(rev_a, unit_suffix)} ({base_label} {fmt_val(rev_b, unit_suffix)}), "
                    f"Gross Margin {gm_a}%, OpEx {fmt_val(opex_a, unit_suffix)}, EBITDA {fmt_val(ebitda_a, unit_suffix)} ({ebitda_m_a}%), Net Profit {fmt_val(net_a, unit_suffix)} ({net_m_a}%)."
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
                    fig_wf.update_layout(title="P&L Bridge (Revenue se Net Profit tak ka safar)", showlegend=False)
                    st.plotly_chart(fig_wf, use_container_width=True)
                with col_r:
                    pnl_only = summary_df[summary_df[head_col].astype(str).str.lower().apply(
                        lambda x: any(k in x for k in ["rev", "sales", "cogs", "opex", "tax", "interest", "expense"])
                    )]
                    fig_bar = px.bar(pnl_only, x=cat_col, y=[budget_col, actual_col], barmode="group", title=f"P&L Comparison ({base_label} vs {curr_label})")
                    st.plotly_chart(fig_bar, use_container_width=True)
                st.divider()

            # --- SECTION 2: BALANCE SHEET ---
            if has_bs:
                st.subheader("2️⃣ Balance Sheet & Financial Health")
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Total Assets", fmt_val(tot_assets, unit_suffix), help="Company ki kul sampatti (Cash, Inventory, Plant, Machinery).")
                b2.metric("Total Liabilities", fmt_val(tot_liab, unit_suffix), help="Company par kul karz aur baki payments.")
                b3.metric("Current Ratio", f"{curr_ratio}x", "Healthy > 1.5x", help="Current Assets / Current Liabilities. 1.5x se upar matlab short-term bills dene ke liye paryapt cash hai.")
                b4.metric("Debt-to-Equity", f"{debt_to_eq}x", "Safe < 1.0x", delta_color="inverse", help="Total Liabilities / Equity. 1.0x se kam matlab company par karz ka bojh kam hai.")

                ai_context_parts.append(f"Balance Sheet: Assets {fmt_val(tot_assets, unit_suffix)}, Liabilities {fmt_val(tot_liab, unit_suffix)}, Current Ratio {curr_ratio}x, Debt-to-Equity {debt_to_eq}x.")
                st.divider()

            # --- SECTION 3: CASH FLOW ---
            if has_cf:
                st.subheader("3️⃣ Cash Flow & Liquidity")
                free_cf = ocf_a + icf_a
                net_cf = ocf_a + icf_a + fcf_fin_a
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Operating Cash Flow", fmt_val(ocf_a, unit_suffix), help="Asli business operations se haath me aaya hua cash.")
                f2.metric("Investing CF (CapEx)", fmt_val(icf_a, unit_suffix), help="Nayi machine, building, ya tech kharidne me laga cash.")
                f3.metric("Free Cash Flow (FCF)", fmt_val(free_cf, unit_suffix), help="Operating CF minus CapEx. Ye free cash growth ya debt kam karne ke liye bachta hai.")
                f4.metric("Net Cash Change", fmt_val(net_cf, unit_suffix), help="Pure period me company ke bank balance me kul badlav.")

                ai_context_parts.append(f"Cash Flow: Operating CF {fmt_val(ocf_a, unit_suffix)}, Free Cash Flow {fmt_val(free_cf, unit_suffix)}.")
                st.divider()

            # --- FALLBACK: EXPENSE-ONLY ---
            if not (has_pnl or has_bs or has_cf):
                tot_b, tot_a = summary_df[budget_col].sum(), summary_df[actual_col].sum()
                net_v = tot_a - tot_b
                net_vp = round((net_v / abs(tot_b)) * 100, 2) if tot_b else 0.0
                e1, e2, e3, e4 = st.columns(4)
                e1.metric(f"Total {base_label}", fmt_val(tot_b, unit_suffix))
                e2.metric(f"Total {curr_label}", fmt_val(tot_a, unit_suffix))
                e3.metric("Net Variance", fmt_val(net_v, unit_suffix), f"{net_vp}%", delta_color="inverse")
                e4.metric("Red Flag Areas", f"{len(red_flags)} / {len(summary_df)}")

                ai_context_parts.append(f"Summary: {base_label} {fmt_val(tot_b, unit_suffix)}, {curr_label} {fmt_val(tot_a, unit_suffix)}, Variance {net_vp}%.")
                fig_bar = px.bar(summary_df, x=cat_col, y=[budget_col, actual_col], barmode="group", title=f"{base_label} vs {curr_label} Comparison")
                st.plotly_chart(fig_bar, use_container_width=True)
                st.divider()

            st.subheader(f"🚨 High Variance Alerts (Threshold: {threshold}%)")
            if not red_flags.empty:
                st.dataframe(red_flags, use_container_width=True, hide_index=True)
            else:
                st.success("Koi bhi line item threshold se bahar nahi gaya hai!")

            with st.expander("View Full Financial Summary Table (Verify Data)"):
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
                k1.metric("Projected Revenue", fmt_val(proj_rev, unit_suffix), f"{rev_trend}% trend")
                k2.metric("Break-Even Revenue", fmt_val(break_even_rev, unit_suffix), help="Zero loss ke liye minimum itna revenue chahiye.")
                k3.metric("Projected EBITDA", fmt_val(proj_ebitda, unit_suffix), f"Margin: {proj_ebitda_pct}%")
                k4.metric("Budget Cut Needed", fmt_val(savings_needed, unit_suffix), delta_color="inverse")

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

                    opex_df["Recommended_Cut"] = cuts
                    opex_df["Cut_%"] = opex_df.apply(lambda r: round((r["Recommended_Cut"] / r["Projected_Spend"]) * 100, 1) if r["Projected_Spend"] > 0 else 0.0, axis=1)
                    opex_df["Revised_Budget"] = opex_df["Projected_Spend"] - opex_df["Recommended_Cut"]

                    show_cols = [cat_col, "Priority", "Projected_Spend", "Recommended_Cut", "Cut_%", "Revised_Budget"]
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
                if q1.button("📉 Simple Hinglish Health Review"):
                    qp = "Mere financial data ko bilkul simple Hinglish me samjhao—kya achha chal raha hai aur kahan risk hai?"
                if q2.button("✂️ Cost Cut-Down Strategy"):
                    qp = "Overruns aur market slowdown ko dekhte hue cost optimize karne ke top 3 practical recommendations do."
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
                    Answer strictly based on these Python-verified financial figures (Unit: {unit_choice}). Do NOT invent numbers.

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
                                full_prompt = f"{data_context}\n\nHistory:\n{hist}\n\nAnswer clearly and concisely."
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
