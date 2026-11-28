import streamlit as st
import pandas as pd
from parser import call_gemini, read_raw_file, parse_statement_with_ai, load_sample_pnl, load_sample_bs
from metrics import fmt_val, pct_change, compute_pnl_metrics, compute_bs_metrics
from charts import plot_pnl_waterfall, plot_core_vs_other_bar, plot_bs_structure, plot_item_xray

st.set_page_config(page_title="AI CFO Copilot — Modular FP&A", page_icon="📊", layout="wide")

# --- SIDEBAR: SEPARATE UPLOAD SLOTS ---
st.sidebar.title("⚙️ Modular FP&A Control")
st.sidebar.caption("Separate uploads • Data Understanding first • Click-to-Inspect X-Ray.")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key (AI Studio)", type="password")

unit_choice = st.sidebar.selectbox("Currency Unit", ["Crores (₹ Cr)", "Lakhs (₹ L)", "INR (₹)"], index=0)
unit_suffix = " Cr" if "Crores" in unit_choice else (" L" if "Lakhs" in unit_choice else "")

st.sidebar.divider()
st.sidebar.subheader("📂 Separate Statement Uploads")
use_sample = st.sidebar.checkbox("Use Sample Data (P&L + Balance Sheet)", value=True)
pnl_file = st.sidebar.file_uploader("1️⃣ Upload P&L Statement (Excel/CSV)", type=["xlsx", "csv"], key="up_pnl")
bs_file = st.sidebar.file_uploader("2️⃣ Upload Balance Sheet (Excel/CSV)", type=["xlsx", "csv"], key="up_bs")

# --- LOAD & UNDERSTAND DATA ---
def get_statement_df(uploaded_file, stmt_type, sample_loader):
    if uploaded_file is not None:
        sig = f"{stmt_type}_{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get(f"sig_{stmt_type}") != sig:
            raw_df = read_raw_file(uploaded_file)
            if not api_key:
                st.sidebar.warning(f"{stmt_type} auto-understanding ke liye Gemini API key daalein.")
                return None
            with st.spinner(f"🤖 AI {stmt_type} ka structure aur Core vs Other items samajh raha hai..."):
                parsed = parse_statement_with_ai(raw_df, stmt_type, uploaded_file.name, api_key)
                st.session_state[f"df_{stmt_type}"] = parsed
                st.session_state[f"sig_{stmt_type}"] = sig
        return st.session_state.get(f"df_{stmt_type}")
    elif use_sample:
        return sample_loader()
    return None

pnl_df = get_statement_df(pnl_file, "P&L", load_sample_pnl)
bs_df = get_statement_df(bs_file, "Balance Sheet", load_sample_bs)

# --- HEADER ---
st.title("📊 AI CFO Copilot — Human-to-Model FP&A Workspace")

loaded_stmts = []
if pnl_df is not None and not pnl_df.empty:
    loaded_stmts.append("P&L Statement")
if bs_df is not None and not bs_df.empty:
    loaded_stmts.append("Balance Sheet")

if not loaded_stmts:
    st.info("Sidebar se **P&L** ya **Balance Sheet** upload karein (ya testing ke liye **Use Sample Data** tick karein).")
    st.stop()

st.caption(f"✅ **Active Workspace:** {'  •  '.join(loaded_stmts)}  |  **Unit:** {unit_choice}")

# --- DYNAMIC TABS (ONLY SHOW WHAT IS LOADED) ---
tab_names = ["🔎 Step 1: Data Understanding & Verify"]
if pnl_df is not None:
    tab_names.append("📈 P&L Analysis (Core vs Other)")
if bs_df is not None:
    tab_names.append("🏦 Balance Sheet Health")

tabs = st.tabs(tab_names)
tab_idx = 0

# ==================== TAB 0: DATA UNDERSTANDING & VERIFICATION ====================
with tabs[tab_idx]:
    st.subheader("🔎 Step 1: Verify What the Model Understood")
    st.caption("Koi bhi number ya Core/Other tag galat lage toh seedha table me edit kar sakte ho — dashboard turant update ho jayega.")

    if pnl_df is not None:
        st.markdown("##### 📄 P&L Statement Structure")
        pnl_df = st.data_editor(pnl_df, use_container_width=True, num_rows="dynamic", key="edit_pnl")
    if bs_df is not None:
        st.markdown("##### 📄 Balance Sheet Structure")
        bs_df = st.data_editor(bs_df, use_container_width=True, num_rows="dynamic", key="edit_bs")

# --- REUSABLE CLICK-TO-INSPECT X-RAY PANEL ---
def render_xray_panel(df: pd.DataFrame, stmt_type: str, context_summary: str):
    with st.container(border=True):
        st.markdown(f"#### 🔬 Click-to-Inspect: {stmt_type} Data Background (X-Ray)")
        items = df["Line_Item"].astype(str).tolist()
        selected = st.selectbox(f"Kisi bhi {stmt_type} point ko select karo uska pura background dekhne ke liye:", ["-- Select a Line Item --"] + items, key=f"xray_{stmt_type}")
        if selected != "-- Select a Line Item --":
            row = df[df["Line_Item"] == selected].iloc[0]
            chg = pct_change(row["Latest_Period"], row["Previous_Period"])
            x1, x2, x3, x4 = st.columns(4)
            x1.metric("Previous Period", fmt_val(row["Previous_Period"], unit_suffix))
            x2.metric("Latest Period", fmt_val(row["Latest_Period"], unit_suffix), f"{chg}%")
            x3.metric("Classification", f"{row['Category']}", f"Nature: {row['Nature']}")
            x4.metric("Audit Source", str(row["Source_File"]))

            st.plotly_chart(plot_item_xray(row, unit_suffix), use_container_width=True)

            if st.button(f"🧠 Ask AI CFO: '{selected}' ka Root-Cause & Action Plan", key=f"ai_btn_{stmt_type}_{selected}"):
                if not api_key:
                    st.warning("Sidebar me Gemini API key daalein.")
                else:
                    with st.spinner("AI CFO background analyze kar raha hai..."):
                        prompt = f"""
                        You are a Corporate CFO. The user clicked on '{selected}' in the {stmt_type} ({unit_choice}).
                        Item Details: {row.to_dict()}
                        Statement Summary: {context_summary}
                        Full Table:
                        {df.to_markdown(index=False)}

                        Explain in crisp Hinglish/English:
                        1. **What this means & Core vs Other Impact:**
                        2. **Why it likely changed ({chg}%):**
                        3. **Recommended CFO Action (2-3 concrete steps):**
                        Do NOT invent numbers.
                        """
                        ans = call_gemini(api_key, prompt)
                        st.markdown(ans if ans else "AI server busy hai, 5 second baad try karein.")

# ==================== P&L TAB ====================
if pnl_df is not None:
    tab_idx += 1
    with tabs[tab_idx]:
        m = compute_pnl_metrics(pnl_df)
        st.subheader("📈 Profit & Loss — Core Operations vs. Other Factors")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Core Revenue", fmt_val(m["rev_c"], unit_suffix), f"{m['rev_chg']}% YoY")
        k2.metric("Gross Profit", fmt_val(m["gp_c"], unit_suffix), f"GM: {m['gm_c']}%")
        k3.metric("Core EBITDA", fmt_val(m["core_ebitda_c"], unit_suffix), f"Margin: {m['core_ebitda_m']}%")
        k4.metric("Net Other & Excep.", fmt_val(m["net_other_c"], unit_suffix), f"Inc {m['other_inc_c']:.0f} | Excep {m['excep_c']:.0f} | Exp -{m['other_exp_c']:.0f}")
        k5.metric("Net Profit (PAT)", fmt_val(m["pat_c"], unit_suffix), f"Net Margin: {m['pat_m']}%")

        c_left, c_right = st.columns(2)
        with c_left:
            st.plotly_chart(plot_pnl_waterfall(m, unit_suffix), use_container_width=True)
        with c_right:
            st.plotly_chart(plot_core_vs_other_bar(pnl_df, "P&L Category Comparison (Previous vs Latest)"), use_container_width=True)

        pnl_summary = f"Revenue {m['rev_c']}, COGS {m['cogs_c']}, Core EBITDA {m['core_ebitda_c']} ({m['core_ebitda_m']}%), Net Other/Exceptional {m['net_other_c']}, PAT {m['pat_c']} ({m['pat_m']}%)."
        render_xray_panel(pnl_df, "P&L", pnl_summary)

# ==================== BALANCE SHEET TAB ====================
if bs_df is not None:
    tab_idx += 1
    with tabs[tab_idx]:
        b = compute_bs_metrics(bs_df)
        st.subheader("🏦 Balance Sheet — Liquidity, Leverage & Asset Structure")

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Total Assets", fmt_val(b["tot_assets_c"], unit_suffix))
        b2.metric("Total Liabilities", fmt_val(b["tot_liab_c"], unit_suffix))
        b3.metric("Net Working Capital", fmt_val(b["working_cap_c"], unit_suffix))
        b4.metric("Current Ratio", f"{b['curr_ratio_c']}x", "Healthy > 1.5x")
        b5.metric("Debt-to-Equity", f"{b['debt_to_eq_c']}x", "Safe < 1.0x", delta_color="inverse")

        if abs(b["balance_diff"]) > 1:
            st.warning(f"⚠️ Balance Sheet Check: Assets aur (Liabilities + Equity) me **{fmt_val(b['balance_diff'], unit_suffix)}** ka difference hai. Step 1 me verify karein.")
        else:
            st.success("✅ Balance Sheet Tally: Total Assets = Total Liabilities + Equity.")

        c_left, c_right = st.columns(2)
        with c_left:
            st.plotly_chart(plot_bs_structure(bs_df), use_container_width=True)
        with c_right:
            st.plotly_chart(plot_core_vs_other_bar(bs_df, "Balance Sheet YoY Movement"), use_container_width=True)

        bs_summary = f"Assets {b['tot_assets_c']}, Liabilities {b['tot_liab_c']}, Equity {b['eq_c']}, Working Capital {b['working_cap_c']}, Current Ratio {b['curr_ratio_c']}x, Debt-to-Equity {b['debt_to_eq_c']}x."
        render_xray_panel(bs_df, "Balance Sheet", bs_summary)
