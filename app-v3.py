import streamlit as st
import pandas as pd
from parser import call_gemini, read_raw_file, parse_statement_with_ai, load_sample_pnl, load_sample_bs
from metrics import fmt_val, pct_change, compute_pnl_metrics, compute_bs_metrics
from charts import plot_pnl_waterfall, plot_core_vs_other_bar, plot_bs_structure, plot_item_xray

st.set_page_config(page_title="AI CFO Copilot — Modular FP&A", page_icon="📊", layout="wide")

# --- SIDEBAR: SEPARATE UPLOAD SLOTS ---
st.sidebar.title("⚙️ Modular FP&A Control")
st.sidebar.caption("Separate uploads • Anti-Double-Count AI • Click X-Ray • AI CFO Copilot.")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key (AI Studio)", type="password")

unit_choice = st.sidebar.selectbox("Currency Unit", ["Crores (₹ Cr)", "Lakhs (₹ L)", "INR (₹)"], index=0)
unit_suffix = " Cr" if "Crores" in unit_choice else (" L" if "Lakhs" in unit_choice else "")

st.sidebar.divider()
st.sidebar.subheader("📂 Separate Statement Uploads")
pnl_file = st.sidebar.file_uploader("1️⃣ Upload P&L Statement (Excel/CSV)", type=["xlsx", "csv"], key="up_pnl")
bs_file = st.sidebar.file_uploader("2️⃣ Upload Balance Sheet (Excel/CSV)", type=["xlsx", "csv"], key="up_bs")

any_uploaded = (pnl_file is not None) or (bs_file is not None)
use_sample = st.sidebar.checkbox(
    "Use Sample Data (jab koi file upload na ho)",
    value=not any_uploaded,
    disabled=any_uploaded
)

# --- LOAD & UNDERSTAND DATA ---
def get_statement_df(uploaded_file, stmt_type, sample_loader):
    if uploaded_file is not None:
        sig = f"{stmt_type}_{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get(f"sig_{stmt_type}") != sig:
            raw_df = read_raw_file(uploaded_file)
            if not api_key:
                st.sidebar.warning(f"{stmt_type} auto-understanding ke liye Gemini API key daalein.")
                return None
            with st.spinner(f"🤖 AI {stmt_type} ka structure, Core vs Other aur Tax samajh raha hai..."):
                parsed = parse_statement_with_ai(raw_df, stmt_type, uploaded_file.name, api_key)
                st.session_state[f"df_{stmt_type}"] = parsed
                st.session_state[f"sig_{stmt_type}"] = sig
        return st.session_state.get(f"df_{stmt_type}")
    elif use_sample and not any_uploaded:
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

# --- GLOBAL INTERACTIVE SEARCH BAR (SEARCH & INSTANT X-RAY ACROSS ALL LOADED STATEMENTS) ---
combined_list = []
if pnl_df is not None:
    tmp_p = pnl_df.copy()
    tmp_p["Statement"] = "P&L"
    combined_list.append(tmp_p)
if bs_df is not None:
    tmp_b = bs_df.copy()
    tmp_b["Statement"] = "Balance Sheet"
    combined_list.append(tmp_b)
all_df = pd.concat(combined_list, ignore_index=True)

with st.container(border=True):
    st.markdown("#### 🔍 Global Search & Instant Answer Bar")
    sc1, sc2 = st.columns([2, 2])
    search_txt = sc1.text_input(
        "Koi bhi line item ya category search karo (e.g., Sales, Tax, Interest, Cash, Debt)",
        placeholder="Type to search across loaded statements..."
    )
    if search_txt:
        mask = (
            all_df["Line_Item"].astype(str).str.contains(search_txt, case=False, na=False) |
            all_df["Category"].astype(str).str.contains(search_txt, case=False, na=False)
        )
        matched_df = all_df[mask]
    else:
        matched_df = all_df

    item_labels = [f"[{r['Statement']}] {r['Line_Item']} ({r['Category']})" for _, r in matched_df.iterrows()]
    chosen_label = sc2.selectbox("Select point for Instant X-Ray:", ["-- Select a Point --"] + item_labels)

    if chosen_label != "-- Select a Point --":
        chosen_idx = item_labels.index(chosen_label)
        row = matched_df.iloc[chosen_idx]
        chg = pct_change(row["Latest_Period"], row["Previous_Period"])
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Previous Period", fmt_val(row["Previous_Period"], unit_suffix))
        g2.metric("Latest Period", fmt_val(row["Latest_Period"], unit_suffix), f"{chg}%")
        g3.metric("Category / Nature", row["Category"], f"{row['Nature']} ({row['Statement']})")
        g4.metric("Audit Source", str(row["Source_File"]))
        st.plotly_chart(plot_item_xray(row, unit_suffix), use_container_width=True)

        if st.button(f"🤖 Ask AI CFO about '{row['Line_Item']}'", key="global_search_ai"):
            if not api_key:
                st.warning("Sidebar me Gemini API key daalein.")
            else:
                with st.spinner("AI CFO analyze kar raha hai..."):
                    q_prompt = f"""
                    You are a Corporate CFO. The user searched for '{row['Line_Item']}' ({row['Statement']}, {unit_choice}).
                    Row data: {row.to_dict()}
                    Full loaded financial data:
                    {all_df.to_markdown(index=False)}

                    Give a crisp Hinglish/English answer covering:
                    1. **Exact Meaning & Core vs Other Role**
                    2. **Why it moved ({chg}%) & Business Impact**
                    3. **Recommended Action (2-3 concrete steps)**
                    Do NOT invent numbers.
                    """
                    ans = call_gemini(api_key, q_prompt)
                    st.markdown(ans if ans else "AI server busy hai, 5 second baad try karein.")

# --- DYNAMIC TABS ---
tab_names = ["🔎 Step 1: Verify Data"]
if pnl_df is not None:
    tab_names.append("📈 P&L Analysis (Core vs Other)")
if bs_df is not None:
    tab_names.append("🏦 Balance Sheet Health")
tab_names.append("🤖 AI CFO Copilot Chat")

tabs = st.tabs(tab_names)
tab_idx = 0

# ==================== TAB 0: DATA UNDERSTANDING & VERIFICATION ====================
with tabs[tab_idx]:
    st.subheader("🔎 Step 1: Verify What the Model Understood")
    st.caption("Koi bhi number ya Core/Other tag edit kar sakte ho — saare KPIs aur AI CFO turant update ho jayenge.")

    if pnl_df is not None:
        st.markdown("##### 📄 P&L Statement Structure")
        pnl_df = st.data_editor(pnl_df, use_container_width=True, num_rows="dynamic", key="edit_pnl")
    if bs_df is not None:
        st.markdown("##### 📄 Balance Sheet Structure")
        bs_df = st.data_editor(bs_df, use_container_width=True, num_rows="dynamic", key="edit_bs")

ai_summary_blocks = []

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

        ai_summary_blocks.append(
            f"P&L ({unit_choice}): Revenue {m['rev_c']} ({m['rev_chg']}%), COGS {m['cogs_c']}, OpEx {m['opex_c']}, "
            f"Core EBITDA {m['core_ebitda_c']} ({m['core_ebitda_m']}%), Net Other/Exceptional {m['net_other_c']}, "
            f"Dep {m['dep_c']}, Interest {m['int_c']}, Tax {m['tax_c']}, Net Profit (PAT) {m['pat_c']} ({m['pat_m']}%)."
        )

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

        ai_summary_blocks.append(
            f"Balance Sheet ({unit_choice}): Assets {b['tot_assets_c']}, Liabilities {b['tot_liab_c']}, Equity {b['eq_c']}, "
            f"Working Capital {b['working_cap_c']}, Current Ratio {b['curr_ratio_c']}x, Debt-to-Equity {b['debt_to_eq_c']}x."
        )

# ==================== AI CFO COPILOT CHAT TAB ====================
tab_idx += 1
with tabs[tab_idx]:
    st.subheader("🤖 AI CFO Copilot — Ask Anything About Your Financials")
    if not api_key:
        st.info("Sidebar me apni Gemini API key daalein taaki AI CFO Copilot activate ho sake.")
    else:
        if "cfo_messages" not in st.session_state:
            st.session_state.cfo_messages = []

        q1, q2, q3 = st.columns(3)
        qp = None
        if q1.button("📉 Full Core vs Other Review", use_container_width=True):
            qp = "Company ki Core operating performance vs Other Income/Exceptional items ka detailed CFO review do."
        if q2.button("✂️ Cost & Risk Action Plan", use_container_width=True):
            qp = "Sabse bade cost drivers aur financial risks kaunse hain, aur management ko unhe kaise control karna chahiye?"
        if q3.button("📋 4-Bullet Board Summary", use_container_width=True):
            qp = "Board meeting ke liye 4-bullet executive summary bana do verified numbers ke saath."

        for msg in st.session_state.cfo_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_q = qp or st.chat_input("Apne financials ke baare me koi bhi sawal pucho (e.g., PAT kyun gira, Tax kitna laga, Liquidity kaisi hai?)...")
        if user_q:
            st.session_state.cfo_messages.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            # Rebuild latest edited all_df for grounded context
            fresh_list = []
            if pnl_df is not None:
                tp = pnl_df.copy(); tp["Statement"] = "P&L"; fresh_list.append(tp)
            if bs_df is not None:
                tb = bs_df.copy(); tb["Statement"] = "Balance Sheet"; fresh_list.append(tb)
            fresh_all = pd.concat(fresh_list, ignore_index=True)

            hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.cfo_messages[-6:]])
            chat_prompt = f"""
            You are an expert Corporate CFO & FP&A Head.
            Answer strictly using the Python-verified metrics and table below ({unit_choice}). NEVER invent numbers.

            VERIFIED SUMMARY:
            {chr(10).join(ai_summary_blocks)}

            COMPLETE VERIFIED TABLE:
            {fresh_all.to_markdown(index=False)}

            CONVERSATION HISTORY:
            {hist}

            Answer clearly, directly, and practically in Hinglish/English.
            """
            with st.chat_message("assistant"):
                with st.spinner("AI CFO analyze kar raha hai..."):
                    ans = call_gemini(api_key, chat_prompt)
                    if ans:
                        st.markdown(ans)
                        st.session_state.cfo_messages.append({"role": "assistant", "content": ans})
                    else:
                        st.error("AI server busy hai, 5 second baad try karein.")
