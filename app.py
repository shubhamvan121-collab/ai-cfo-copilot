



import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google import genai

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI CFO Copilot — Full FP&A Suite", page_icon="📊", layout="wide")

# --- SAMPLE DATA GENERATOR (P&L + BS + CF + FORECAST) ---
@st.cache_data
def load_sample_data(mode="Full 3-Statement + Forecast"):
    pnl_data = [
        ["P&L", "Revenue", "Product Sales", 12000000, 12600000, 13400000],
        ["P&L", "Revenue", "SaaS & Services", 4500000, 4900000, 5400000],
        ["P&L", "COGS", "Raw Materials & Procurement", 4800000, 5650000, 5900000],
        ["P&L", "COGS", "Cloud Hosting & Delivery", 1200000, 1320000, 1400000],
        ["P&L", "OpEx", "Marketing & Performance Ads", 1500000, 1980000, 1800000],
        ["P&L", "OpEx", "Salaries & Payroll", 3200000, 3350000, 3500000],
        ["P&L", "OpEx", "Operations & Rent", 1400000, 1720000, 1650000],
        ["P&L", "OpEx", "Logistics & Freight", 1100000, 1450000, 1380000],
        ["P&L", "OpEx", "HR & Admin", 800000, 780000, 820000],
        ["P&L", "Interest & Tax", "Interest & Corporate Tax", 650000, 620000, 680000],
    ]
    bs_cf_data = [
        ["Balance Sheet", "Current Assets", "Cash & Bank Equivalents", 3500000, 3200000, 3900000],
        ["Balance Sheet", "Current Assets", "Accounts Receivable", 2400000, 2950000, 2700000],
        ["Balance Sheet", "Current Assets", "Inventory & Raw Stock", 1800000, 2450000, 2100000],
        ["Balance Sheet", "Fixed Assets", "Plant, Machinery & IT Assets", 9000000, 9200000, 9600000],
        ["Balance Sheet", "Current Liabilities", "Accounts Payable & Short-Term Dues", 3800000, 4450000, 4100000],
        ["Balance Sheet", "Long-Term Debt", "Term Loans & Borrowings", 4500000, 4200000, 3900000],
        ["Balance Sheet", "Equity", "Shareholders Equity & Reserves", 8400000, 9150000, 10300000],
        ["Cash Flow", "Operating Cash Flow", "Cash Generated from Operations", 2400000, 1850000, 2600000],
        ["Cash Flow", "Investing Cash Flow", "CapEx & Equipment Purchase", -900000, -1150000, -1000000],
        ["Cash Flow", "Financing Cash Flow", "Debt Repayment & Dividends", -500000, -450000, -500000],
    ]
    cols = ["Statement", "Account_Head", "Category", "Budget_INR", "Actual_INR", "Forecast_INR"]
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

def call_gemini(api_key, prompt_text):
    client = genai.Client(api_key=api_key)
    for m_name in ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.8-flash"]:
        try:
            resp = client.models.generate_content(model=m_name, contents=prompt_text)
            if resp and resp.text:
                return resp.text
        except Exception:
            continue
    return None

def ai_auto_clean_table(raw_df, source_name, api_key):
    raw_text = raw_df.head(70).to_csv(index=False, header=False)
    clean_prompt = f"""
    You are a Senior FP&A Data Engineer. Convert this raw financial table (from file/sheet: "{source_name}") into a clean CSV with EXACTLY 6 columns:
    Statement,Account_Head,Category,Budget_INR,Actual_INR,Forecast_INR

    STRICT RULES:
    1. Drop all percentage, ratio, margin, or growth rows (e.g., Tax %, Margin %, Growth %, Employee Cost %, EPS, Dividend Payout).
    2. Drop all subtotal/total rows (e.g., Gross Profit, EBITDA, Operating Profit, Financing Profit, PBT, Profit before tax, Net Profit, Total Assets, Total Liabilities).
    3. Set Statement to one of: P&L, Balance Sheet, Cash Flow, Forecast.
    4. Set Account_Head strictly to one of:
       Revenue, COGS, OpEx, Interest & Tax, Current Assets, Fixed Assets, Current Liabilities, Long-Term Debt, Equity, Operating Cash Flow, Investing Cash Flow, Financing Cash Flow
    5. Column mapping:
       - If Budget, Actual, and Forecast exist -> map them directly.
       - If multiple historical years exist (like Screener.in) -> put 2nd latest year in Budget_INR, latest year in Actual_INR, and 0 in Forecast_INR.
       - If only Forecast exists -> put 0 in Budget_INR, 0 in Actual_INR, and forecast value in Forecast_INR.
    6. Pure numbers only in Budget_INR, Actual_INR, Forecast_INR (no commas, no ₹, no %). Replace blanks with 0.
    7. Return ONLY raw CSV text starting with the header line. No markdown backticks, no explanation.

    RAW DATA:
    {raw_text}
    """
    resp = call_gemini(api_key, clean_prompt)
    if not resp:
        return None
    try:
        clean_csv = resp.replace("```csv", "").replace("```", "").strip()
        cleaned = pd.read_csv(io.StringIO(clean_csv))
        for col in ["Budget_INR", "Actual_INR", "Forecast_INR"]:
            if col not in cleaned.columns:
                cleaned[col] = 0.0
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0.0)
        return cleaned
    except Exception:
        return None

# --- SIDEBAR ---
st.sidebar.title("⚙️ FP&A Control Panel")
st.sidebar.caption("Upload P&L, Balance Sheet, Cash Flow & Forecast ek saath — AI sab merge karke analyze karega.")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key (Free from AI Studio)", type="password")

st.sidebar.divider()
sample_mode = st.sidebar.selectbox(
    "Sample Data Mode (1-Click Testing)",
    ["Full 3-Statement + Forecast", "Only P&L Data"]
)
use_sample = st.sidebar.checkbox("Use Sample Data", value=True)

uploaded_files = st.sidebar.file_uploader(
    "📂 Upload 1 ya Multiple Files (P&L + BS + CF + Forecast)",
    type=["xlsx", "csv"],
    accept_multiple_files=True
)

# --- MULTI-FILE & MULTI-SHEET LOADER ---
df = None
if uploaded_files:
    auto_clean = st.sidebar.checkbox("✨ AI Auto-Clean & Merge All Docs (Recommended)", value=True)
    file_sig = "_".join([f"{f.name}_{f.size}" for f in uploaded_files]) + f"_{auto_clean}"

    if st.session_state.get("master_file_sig") != file_sig:
        combined_frames = []
        with st.spinner("📂 Saare documents (P&L, BS, CF, Forecast) padh kar unified FP&A model bana rahe hain..."):
            for f in uploaded_files:
                try:
                    if f.name.endswith(".csv"):
                        raw_h = pd.read_csv(f)
                        f.seek(0)
                        raw_nh = pd.read_csv(f, header=None)
                        sheets_to_process = [(f.name, raw_h, raw_nh)]
                    else:
                        xls = pd.ExcelFile(f)
                        sheets_to_process = []
                        for s_name in xls.sheet_names:
                            raw_h = pd.read_excel(xls, sheet_name=s_name)
                            raw_nh = pd.read_excel(xls, sheet_name=s_name, header=None)
                            if not raw_nh.empty:
                                sheets_to_process.append((f"{f.name} | {s_name}", raw_h, raw_nh))

                    for src_label, df_h, df_nh in sheets_to_process:
                        if auto_clean and api_key:
                            cleaned = ai_auto_clean_table(df_nh, src_label, api_key)
                            if cleaned is not None and not cleaned.empty:
                                cleaned["Source_Doc"] = src_label
                                combined_frames.append(cleaned)
                                continue
                        # Fallback normal load
                        df_h.columns = [c.strftime("%b %Y") if hasattr(c, "strftime") else str(c).strip() for c in df_h.columns]
                        df_h["Source_Doc"] = src_label
                        combined_frames.append(df_h)
                except Exception as e:
                    st.sidebar.error(f"Error reading {f.name}: {e}")

        if combined_frames:
            master_df = pd.concat(combined_frames, ignore_index=True)
            st.session_state["master_df"] = master_df
            st.session_state["master_file_sig"] = file_sig
        else:
            st.session_state["master_df"] = None

    df = st.session_state.get("master_df", None)
    use_sample = False
elif use_sample:
    df = load_sample_data(sample_mode)

# --- MAIN APP ---
st.title("📊 AI CFO Copilot — Full FP&A Decision & Deep-Dive Suite")

if df is not None and not df.empty:
    df.columns = [c.strftime("%b %Y") if hasattr(c, "strftime") else str(c).strip() for c in df.columns]
    text_cols = [c for c in df.select_dtypes(include=["object", "category"]).columns.tolist() if c != "Source_Doc"]
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(text_cols) < 1 or len(num_cols) < 2:
        st.warning("Kam se kam 1 Text aur 2 Numeric columns chahiye. Sidebar me '✨ AI Auto-Clean & Merge All Docs' ON karein aur API Key daalein.")
        st.dataframe(df.head())
    else:
        st.sidebar.subheader("🔗 Column & Unit Settings")
        max_num = df[num_cols].abs().max().max()
        default_unit_idx = 2 if (uploaded_files and max_num < 100000) else 0
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
        budget_col = st.sidebar.selectbox("Budget / Previous Column", num_cols, index=0)
        actual_col = st.sidebar.selectbox("Actual / Latest Column", num_cols, index=1 if len(num_cols) > 1 else 0)

        fc_options = ["None"] + num_cols
        default_fc_idx = 0
        for idx, col in enumerate(num_cols, start=1):
            if any(k in col.lower() for k in ["forecast", "proj", "est", "next"]):
                default_fc_idx = idx
                break
        forecast_col = st.sidebar.selectbox("Forecast Column (Optional)", fc_options, index=default_fc_idx)
        threshold = st.sidebar.slider("Red Flag Variance Threshold (%)", 5, 50, 15)

        is_budget_mode = "budget" in budget_col.lower() or "target" in budget_col.lower()
        base_label = "Budget" if is_budget_mode else "Previous"
        curr_label = "Actual" if is_budget_mode else "Latest"
        has_forecast = (forecast_col != "None" and df[forecast_col].abs().sum() > 0)

        # --- AUTO-DETECTION ENGINE ---
        has_pnl, has_bs, has_cf = False, False, False
        ai_context_parts = []
        decision_alerts = []

        agg_cols = [budget_col, actual_col] + ([forecast_col] if has_forecast else [])

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

            rev_f = match_sum(["rev", "sales", "turnover", "income"], forecast_col)[0] if has_forecast else 0.0
            cogs_f = match_sum(["cogs", "cost of goods", "direct cost"], forecast_col)[0] if has_forecast else 0.0
            opex_f = match_sum(["opex", "operating exp", "sga", "expense"], forecast_col)[0] if has_forecast else 0.0

            # 2. Balance Sheet
            ca_a, m_ca = match_sum(["current asset"], actual_col)
            fa_a, m_fa = match_sum(["fixed asset", "non-current asset"], actual_col)
            cl_a, m_cl = match_sum(["current liab"], actual_col)
            ltd_a, m_ltd = match_sum(["long-term", "debt", "borrowing", "non-current liab"], actual_col)
            eq_a, m_eq = match_sum(["equity", "reserve", "capital"], actual_col)
            has_bs = any([m_ca, m_fa, m_cl, m_ltd, m_eq])

            # 3. Cash Flow
            ocf_a, m_ocf = match_sum(["operating cash", "ocf"], actual_col)
            ocf_b, _ = match_sum(["operating cash", "ocf"], budget_col)
            icf_a, m_icf = match_sum(["investing cash", "capex"], actual_col)
            fcf_fin_a, m_fcf = match_sum(["financing cash"], actual_col)
            has_cf = any([m_ocf, m_icf, m_fcf])

            summary_df = df.groupby([head_col, cat_col], as_index=False)[agg_cols].sum()
        else:
            summary_df = df.groupby(cat_col, as_index=False)[agg_cols].sum()

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
        if has_pnl: detected_modules.append("P&L")
        if has_bs: detected_modules.append("Balance Sheet")
        if has_cf: detected_modules.append("Cash Flow")
        if has_forecast: detected_modules.append("Forecast")
        if not detected_modules: detected_modules.append("Expense Variance")
        docs_count = len(uploaded_files) if uploaded_files else 1
        st.caption(f"🔎 **Loaded Docs:** {docs_count}  |  **Modules:** {' • '.join(detected_modules)}  |  **Unit:** {unit_choice}")

        # ==================== INTERACTIVE GLOBAL SEARCH & LINE-ITEM DEEP-DIVE ====================
        with st.container(border=True):
            st.markdown("#### 🔍 Interactive Line-Item Search & Full Point Analysis")
            s_col1, s_col2 = st.columns([2, 2])
            search_query = s_col1.text_input(
                "Kisi bhi point ko search karo (e.g., COGS, Marketing, Inventory, Cash, Revenue)",
                placeholder="Type keyword to filter & analyze..."
            )
            all_items = summary_df[cat_col].astype(str).unique().tolist()
            if search_query:
                filtered_items = [
                    item for item in all_items
                    if search_query.lower() in item.lower() or (
                        head_col != "None (Expense-Only Mode)" and
                        any(search_query.lower() in str(h).lower() for h in summary_df.loc[summary_df[cat_col] == item, head_col])
                    )
                ]
            else:
                filtered_items = all_items

            selected_point = s_col2.selectbox(
                "Ya specific line item select karo (Deep-Dive ke liye)",
                ["-- Select a Point for Full Analysis --"] + filtered_items
            )

            if selected_point != "-- Select a Point for Full Analysis --":
                pt_row = summary_df[summary_df[cat_col] == selected_point].iloc[0]
                p1, p2, p3, p4 = st.columns(4)
                p1.metric(f"{base_label}", fmt_val(pt_row[budget_col], unit_suffix))
                p2.metric(f"{curr_label}", fmt_val(pt_row[actual_col], unit_suffix), f"{pt_row['Variance_%']}%")
                p3.metric("Variance", fmt_val(pt_row["Variance"], unit_suffix), pt_row["Status"])
                if has_forecast:
                    fc_diff = round(((pt_row[forecast_col] - pt_row[actual_col]) / abs(pt_row[actual_col])) * 100, 1) if pt_row[actual_col] else 0.0
                    p4.metric("Forecast", fmt_val(pt_row[forecast_col], unit_suffix), f"{fc_diff}% vs {curr_label}")
                else:
                    p4.metric("Category Priority", tag_priority(selected_point))

                # Mini visual for selected point
                chart_vals = {base_label: pt_row[budget_col], curr_label: pt_row[actual_col]}
                if has_forecast:
                    chart_vals["Forecast"] = pt_row[forecast_col]
                fig_pt = px.bar(
                    x=list(chart_vals.keys()), y=list(chart_vals.values()),
                    color=list(chart_vals.keys()),
                    title=f"Point Drill-Down: {selected_point} ({unit_choice})",
                    height=260
                )
                fig_pt.update_layout(showlegend=False, xaxis_title="", yaxis_title=unit_choice)
                st.plotly_chart(fig_pt, use_container_width=True)

                if st.button(f"🧠 AI Deep-Dive: '{selected_point}' kyun badha/ghata aur kaise manage karein?", key="btn_pt_ai"):
                    if not api_key:
                        st.warning("Sidebar me Gemini API key daalein.")
                    else:
                        with st.spinner(f"'{selected_point}' ka cross-statement FP&A analysis chal raha hai..."):
                            pt_prompt = f"""
                            You are a Senior FP&A Director. The user clicked on a specific financial line item: "{selected_point}".
                            Metrics for this item ({unit_choice}):
                            {pt_row.to_dict()}

                            Full Company Financial Table for Cross-Statement Context (P&L, BS, CF, Forecast):
                            {summary_df.to_markdown(index=False)}

                            Give a crisp, practical FP&A analysis in simple Hinglish/English with 3 clear headings:
                            1. **Root Cause (Yeh kyun badha/ghata?):** Connect it to other statements if relevant (e.g., COGS rise -> Inventory/Payables/Gross Margin; OpEx rise -> EBITDA/Cash Flow).
                            2. **Business & Cash Impact:** What happens if this trend continues into the Forecast?
                            3. **Actionable Management Plan:** 3 concrete steps a CFO/FP&A team should take right now to control or optimize it.
                            Do NOT invent numbers outside the table.
                            """
                            pt_ans = call_gemini(api_key, pt_prompt)
                            if pt_ans:
                                st.markdown(pt_ans)
                            else:
                                st.error("AI server busy hai, 5 second baad try karein.")

        # --- 5 TABS ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Executive 3-Statement + Forecast",
            "🧠 AI Root-Cause & Decisions",
            "📊 Custom Chart Explorer",
            "🎯 Break-Even & Auto Cut-Down",
            "🤖 AI CFO Chat & Recon"
        ])

        # ==================== TAB 1: EXECUTIVE 3-STATEMENT + FORECAST ====================
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
                rev_diff = round(((rev_a - rev_b) / abs(rev_b)) * 100, 1) if rev_b else 0.0
                cogs_diff = round(((cogs_a - cogs_b) / abs(cogs_b)) * 100, 1) if cogs_b else 0.0
                opex_diff = round(((opex_a - opex_b) / abs(opex_b)) * 100, 1) if opex_b else 0.0

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Total Revenue", fmt_val(rev_a, unit_suffix), f"{rev_diff}% vs {base_label}")
                c2.metric("COGS", fmt_val(cogs_a, unit_suffix), f"{cogs_diff}% vs {base_label}", delta_color="inverse")
                c3.metric("Gross Profit", fmt_val(gp_a, unit_suffix), f"GM: {gm_a}% ({base_label} {gm_b}%)")
                c4.metric("Operating Exp (OpEx)", fmt_val(opex_a, unit_suffix), f"{opex_diff}% vs {base_label}", delta_color="inverse")
                c5.metric("EBITDA / PAT", fmt_val(ebitda_a, unit_suffix), f"EBITDA {ebitda_m_a}% | PAT {net_m_a}%")

                ai_context_parts.append(
                    f"P&L ({unit_choice}): Revenue {fmt_val(rev_a, unit_suffix)} ({rev_diff}%), COGS {fmt_val(cogs_a, unit_suffix)} ({cogs_diff}%), "
                    f"Gross Margin {gm_a}% (vs {gm_b}%), OpEx {fmt_val(opex_a, unit_suffix)} ({opex_diff}%), EBITDA {fmt_val(ebitda_a, unit_suffix)} ({ebitda_m_a}%), Net Profit {fmt_val(net_a, unit_suffix)} ({net_m_a}%)."
                )
                if cogs_diff > rev_diff and cogs_a > 0:
                    decision_alerts.append(f"⚠️ **COGS Pressure:** COGS **{cogs_diff}%** badha hai jabki Revenue sirf **{rev_diff}%** badha — Gross Margin {gm_b}% se gir kar **{gm_a}%** aa gaya.")
                if opex_diff > rev_diff and opex_a > 0:
                    decision_alerts.append(f"⚠️ **OpEx Overrun:** OpEx **{opex_diff}%** badha hai (Revenue growth {rev_diff}% se tez) — EBITDA margin pe seedha pressure aa raha hai.")

                col_l, col_r = st.columns(2)
                with col_l:
                    fig_wf = go.Figure(go.Waterfall(
                        orientation="v",
                        measure=["relative", "relative", "total", "relative", "total", "relative", "total"],
                        x=["Revenue", "COGS", "Gross Profit", "OpEx", "EBITDA", "Int & Tax", "Net Profit"],
                        y=[rev_a, -cogs_a, 0, -opex_a, 0, -tax_a, 0],
                        textposition="outside"
                    ))
                    fig_wf.update_layout(title="P&L Waterfall Bridge (Revenue -> Net Profit)", showlegend=False)
                    st.plotly_chart(fig_wf, use_container_width=True)
                with col_r:
                    cost_df = summary_df[summary_df[head_col].astype(str).str.lower().apply(
                        lambda x: any(k in x for k in ["cogs", "opex", "operating", "expense"])
                    )].sort_values("Variance", ascending=True)
                    if not cost_df.empty:
                        fig_var = px.bar(
                            cost_df, x="Variance", y=cat_col, orientation="h",
                            color="Variance", color_continuous_scale="RdYlGn_r",
                            title="Top Cost Variance Drivers (COGS & OpEx Overruns)"
                        )
                        st.plotly_chart(fig_var, use_container_width=True)
                st.divider()

            if has_bs:
                st.subheader("2️⃣ Balance Sheet & Working Capital Health")
                tot_assets = ca_a + fa_a
                tot_liab = cl_a + ltd_a
                curr_ratio = round(ca_a / cl_a, 2) if cl_a > 0 else 0.0
                debt_to_eq = round(tot_liab / eq_a, 2) if eq_a > 0 else 0.0
                working_cap = ca_a - cl_a

                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Total Assets", fmt_val(tot_assets, unit_suffix))
                b2.metric("Net Working Capital", fmt_val(working_cap, unit_suffix), help="Current Assets minus Current Liabilities.")
                b3.metric("Current Ratio", f"{curr_ratio}x", "Healthy > 1.5x")
                b4.metric("Debt-to-Equity", f"{debt_to_eq}x", "Safe < 1.0x", delta_color="inverse")

                ai_context_parts.append(f"Balance Sheet: Assets {fmt_val(tot_assets, unit_suffix)}, Liabilities {fmt_val(tot_liab, unit_suffix)}, Working Capital {fmt_val(working_cap, unit_suffix)}, Current Ratio {curr_ratio}x, Debt-to-Equity {debt_to_eq}x.")
                if curr_ratio < 1.5 and curr_ratio > 0:
                    decision_alerts.append(f"⚠️ **Liquidity Alert:** Current Ratio **{curr_ratio}x** hai (safe benchmark 1.5x+) — Receivables recovery fast karein.")

                bs_only = summary_df[summary_df[head_col].astype(str).str.lower().apply(
                    lambda x: any(k in x for k in ["asset", "liab", "debt", "equity"])
                )]
                if not bs_only.empty:
                    fig_bs = px.bar(bs_only, x=head_col, y=actual_col, color=cat_col, title="Balance Sheet Structure (Assets vs Liabilities & Equity)")
                    st.plotly_chart(fig_bs, use_container_width=True)
                st.divider()

            if has_cf:
                st.subheader("3️⃣ Cash Flow & Liquidity Bridge")
                free_cf = ocf_a + icf_a
                net_cf = ocf_a + icf_a + fcf_fin_a
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Operating Cash Flow", fmt_val(ocf_a, unit_suffix))
                f2.metric("Investing CF (CapEx)", fmt_val(icf_a, unit_suffix))
                f3.metric("Free Cash Flow (FCF)", fmt_val(free_cf, unit_suffix))
                f4.metric("Net Cash Change", fmt_val(net_cf, unit_suffix))

                ai_context_parts.append(f"Cash Flow: Operating CF {fmt_val(ocf_a, unit_suffix)} (Prev {fmt_val(ocf_b, unit_suffix)}), Investing CF {fmt_val(icf_a, unit_suffix)}, Free Cash Flow {fmt_val(free_cf, unit_suffix)}, Net Cash Change {fmt_val(net_cf, unit_suffix)}.")
                if has_pnl and ocf_a < ebitda_a * 0.6 and ebitda_a > 0:
                    decision_alerts.append(f"⚠️ **Cash Conversion Gap:** EBITDA {fmt_val(ebitda_a, unit_suffix)} ke mukable Operating Cash Flow sirf {fmt_val(ocf_a, unit_suffix)} hai — paisa Receivables ya Inventory me atka ho sakta hai.")

                fig_cf = go.Figure(go.Waterfall(
                    orientation="v",
                    measure=["relative", "relative", "relative", "total"],
                    x=["Operating CF", "Investing CF (CapEx)", "Financing CF", "Net Cash Change"],
                    y=[ocf_a, icf_a, fcf_fin_a, 0],
                    textposition="outside"
                ))
                fig_cf.update_layout(title="Cash Flow Waterfall", showlegend=False)
                st.plotly_chart(fig_cf, use_container_width=True)
                st.divider()

            if has_forecast and has_pnl:
                st.subheader("4️⃣ Forecast vs Actual Outlook")
                fc_ebitda = rev_f - cogs_f - opex_f
                fc_df = pd.DataFrame({
                    "Metric": ["Revenue", "COGS", "OpEx", "EBITDA"],
                    base_label: [rev_b, cogs_b, opex_b, ebitda_b],
                    curr_label: [rev_a, cogs_a, opex_a, ebitda_a],
                    "Forecast": [rev_f, cogs_f, opex_f, fc_ebitda]
                })
                fig_fc = px.bar(fc_df, x="Metric", y=[base_label, curr_label, "Forecast"], barmode="group", title="Budget/Prev vs Actual vs Forecast Trajectory")
                st.plotly_chart(fig_fc, use_container_width=True)
                ai_context_parts.append(f"Forecast: Revenue {fmt_val(rev_f, unit_suffix)}, COGS {fmt_val(cogs_f, unit_suffix)}, OpEx {fmt_val(opex_f, unit_suffix)}, Projected EBITDA {fmt_val(fc_ebitda, unit_suffix)}.")
                st.divider()

            st.subheader(f"🚨 High Variance Alerts (Threshold: {threshold}%)")
            if not red_flags.empty:
                st.dataframe(red_flags, use_container_width=True, hide_index=True)
            else:
                st.success("Koi bhi line item threshold se bahar nahi gaya hai!")

            with st.expander("📋 View Full Unified Financial Table (All Statements)"):
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ==================== TAB 2: AI ROOT-CAUSE & DECISION ENGINE ====================
        with tab2:
            st.subheader("🧠 CFO Root-Cause Diagnosis & Management Decision Engine")
            st.caption("Python ke verified signals + Gemini AI ka cross-statement reasoning (COGS, OpEx, Working Capital, Cash Flow & Forecast).")

            if decision_alerts:
                with st.container(border=True):
                    st.markdown("#### ⚡ Automated Python Financial Signals (Zero-Hallucination)")
                    for al in decision_alerts:
                        st.markdown(f"- {al}")

            d_col1, d_col2, d_col3 = st.columns(3)
            run_full_diag = d_col1.button("🔍 Full COGS & OpEx Root-Cause + Fix", use_container_width=True)
            run_wc_diag = d_col2.button("💧 Working Capital & Cash Flow Decision", use_container_width=True)
            run_fc_diag = d_col3.button("🚀 Forecast Risk & Next-Quarter Plan", use_container_width=True)

            selected_diag_prompt = None
            if run_full_diag:
                selected_diag_prompt = """
                Analyze COGS increase and OpEx increase in detail using the verified data.
                Structure your answer in clear Hinglish/English:
                1. **COGS Increase Analysis:** Which exact COGS line items jumped, by how much, impact on Gross Margin %, and probable operational reasons (raw material inflation, vendor pricing, inventory buildup).
                2. **OpEx Increase Analysis:** Which exact OpEx departments overran budget/previous period, impact on EBITDA %, and whether spend is Discretionary or Core.
                3. **How to Manage (Actionable CFO Playbook):** Specific cost-control actions with target savings for both COGS and OpEx.
                """
            elif run_wc_diag:
                selected_diag_prompt = """
                Connect P&L, Balance Sheet, and Cash Flow together:
                1. **Cash Conversion Analysis:** Compare EBITDA vs Operating Cash Flow. Is cash stuck in Accounts Receivable or Inventory?
                2. **Liquidity & Debt Risk:** Evaluate Current Ratio, Working Capital, and Debt-to-Equity.
                3. **CFO Decisions:** Top 3 steps to unlock trapped cash immediately.
                """
            elif run_fc_diag:
                selected_diag_prompt = """
                Evaluate the Forecast vs Actual trajectory:
                1. **Forecast Realism Check:** Are Revenue, COGS, and OpEx forecasts achievable based on current Actual trends?
                2. **Biggest Risk to Forecast EBITDA:** What could derail the next quarter?
                3. **Management Decisions:** 3 proactive decisions to lock in target profitability.
                """

            if selected_diag_prompt:
                if not api_key:
                    st.warning("AI Decision Engine chalane ke liye sidebar me Gemini API key daalein.")
                else:
                    with st.spinner("🧠 AI CFO saare statements (P&L + BS + CF + Forecast) cross-check karke decision report bana raha hai..."):
                        full_diag_prompt = f"""
                        You are a Chief Financial Officer (CFO) & Head of FP&A.
                        Strictly use these Python-verified numbers ({unit_choice}). Do NOT invent numbers.

                        VERIFIED SUMMARY:
                        {chr(10).join(ai_context_parts)}

                        AUTOMATED SIGNALS:
                        {chr(10).join(decision_alerts)}

                        FULL FINANCIAL TABLE:
                        {summary_df.to_markdown(index=False)}

                        TASK:
                        {selected_diag_prompt}
                        """
                        diag_ans = call_gemini(api_key, full_diag_prompt)
                        if diag_ans:
                            st.session_state["last_diag_report"] = diag_ans
                        else:
                            st.error("AI server abhi busy hai. 5 second baad try karein.")

            if st.session_state.get("last_diag_report"):
                with st.container(border=True):
                    st.markdown(st.session_state["last_diag_report"])

        # ==================== TAB 3: CUSTOM CHART EXPLORER ====================
        with tab3:
            st.subheader("📊 Requirement-According Interactive Chart Builder")
            st.caption("Apni requirement ke hisaab se Statement, Metric, aur Chart Type chuno.")

            cc1, cc2, cc3 = st.columns(3)
            head_filter_opts = ["All Line Items"] + (summary_df[head_col].unique().tolist() if head_col != "None (Expense-Only Mode)" else [])
            chosen_head = cc1.selectbox("Filter by Account Head", head_filter_opts)
            chart_type = cc2.selectbox("Select Chart Type", ["Grouped Comparison Bar", "Variance Driver (Horizontal Bar)", "Treemap (Spend/Value Share)", "Donut / Pie Chart", "Line Trend (Prev -> Actual -> Forecast)"])
            metric_choice = cc3.selectbox("Primary Metric (for Pie/Treemap)", agg_cols, index=1 if len(agg_cols) > 1 else 0)

            plot_df = summary_df if chosen_head == "All Line Items" else summary_df[summary_df[head_col] == chosen_head]

            if not plot_df.empty:
                if chart_type == "Grouped Comparison Bar":
                    fig_c = px.bar(plot_df, x=cat_col, y=agg_cols, barmode="group", title=f"{chosen_head} — Comparison ({unit_choice})")
                elif chart_type == "Variance Driver (Horizontal Bar)":
                    fig_c = px.bar(plot_df.sort_values("Variance"), x="Variance", y=cat_col, orientation="h", color="Variance", color_continuous_scale="RdYlGn_r", title=f"{chosen_head} — Variance Drivers")
                elif chart_type == "Treemap (Spend/Value Share)":
                    pos_df = plot_df[plot_df[metric_choice] > 0]
                    path_cols = [head_col, cat_col] if head_col != "None (Expense-Only Mode)" else [cat_col]
                    fig_c = px.treemap(pos_df, path=path_cols, values=metric_choice, title=f"{chosen_head} — Treemap Breakdown ({metric_choice})")
                elif chart_type == "Donut / Pie Chart":
                    pos_df = plot_df[plot_df[metric_choice] > 0]
                    fig_c = px.pie(pos_df, names=cat_col, values=metric_choice, hole=0.45, title=f"{chosen_head} — Share Breakdown ({metric_choice})")
                else:
                    melted = plot_df.melt(id_vars=[cat_col], value_vars=agg_cols, var_name="Period", value_name="Amount")
                    fig_c = px.line(melted, x="Period", y="Amount", color=cat_col, markers=True, title=f"{chosen_head} — Period Trajectory")

                st.plotly_chart(fig_c, use_container_width=True)

        # ==================== TAB 4: BREAK-EVEN & AUTO CUT-DOWN ====================
        with tab4:
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
                k2.metric("Break-Even Revenue", fmt_val(break_even_rev, unit_suffix))
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

        # ==================== TAB 5: AI CFO CHAT & RECONCILIATION ====================
        with tab5:
            sub_chat, sub_recon = st.columns([3, 2])
            with sub_chat:
                st.subheader("💬 AI CFO Chat (All Statements Grounded)")
                if not api_key:
                    st.info("Sidebar me Gemini API key daalein.")
                else:
                    if "messages" not in st.session_state:
                        st.session_state.messages = []

                    q1, q2 = st.columns(2)
                    qp = None
                    if q1.button("📉 COGS & OpEx kyun badha?"):
                        qp = "COGS aur OpEx kyun badha hai? Kaunse specific items responsible hain aur inhe kaise control karein?"
                    if q2.button("📋 Full 3-Statement CFO Summary"):
                        qp = "P&L, Balance Sheet, Cash Flow, aur Forecast ko milakar ek crisp CFO executive summary bana do."

                    for msg in st.session_state.messages:
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["content"])

                    prompt = qp or st.chat_input("Kisi bhi statement ya line item ke baare me pucho...")
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
                            with st.spinner("Analyzing across all statements..."):
                                hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
                                ans = call_gemini(api_key, f"{data_context}\n\nHistory:\n{hist}\n\nAnswer clearly and concisely.")
                                if ans:
                                    st.markdown(ans)
                                    st.session_state.messages.append({"role": "assistant", "content": ans})
                                else:
                                    st.error("AI server abhi thoda busy hai. 5 second baad try karein.")

            with sub_recon:
                st.subheader("🔍 Quick Budget Reconciliation")
                q_rec = summary_df.copy()
                q_rec["Recon_Status"] = q_rec.apply(
                    lambda r: "🔴 Unbudgeted" if r[budget_col] == 0 and r[actual_col] != 0 else ("🟡 Unutilized" if r[actual_col] == 0 and r[budget_col] != 0 else "✅ Reconciled"), axis=1
                )
                st.dataframe(q_rec[[cat_col, budget_col, actual_col, "Variance", "Recon_Status"]], use_container_width=True, hide_index=True)
else:
    st.info("Sidebar se Sample Data tick karein ya apni P&L, Balance Sheet, Cash Flow, aur Forecast files ek saath upload karein.")
Planning financial application upgrades for multiple file uploads
