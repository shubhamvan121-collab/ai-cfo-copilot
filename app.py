import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI CFO Copilot", page_icon="📊", layout="wide")

# --- SAMPLE DATA GENERATOR ---
@st.cache_data
def load_sample_data():
    data = {
        "Department": ["Marketing", "IT & Cloud", "Operations", "Sales", "HR & Admin", "Logistics", "R&D"],
        "Budget_INR": [1500000, 1200000, 2000000, 1800000, 800000, 1100000, 900000],
        "Actual_INR": [1850000, 1150000, 2380000, 1750000, 790000, 1390000, 920000]
    }
    return pd.DataFrame(data)

# --- SIDEBAR ---
st.sidebar.title("⚙️ Control Panel")
st.sidebar.caption("Demo Prototype: Upload anonymized or sample data only.")

api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key (Free from AI Studio)", type="password")

st.sidebar.divider()
use_sample = st.sidebar.checkbox("Try with Sample FP&A Data", value=True)
uploaded_file = st.sidebar.file_uploader("Ya apni Excel/CSV upload karo", type=["xlsx", "csv"])

# --- DATA LOADING ---
df = None
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        use_sample = False
    except Exception as e:
        st.error(f"File padhne me dikkat aayi. Ensure karein ki pehli row me clean column headers hon. Error: {e}")
elif use_sample:
    df = load_sample_data()

# --- MAIN APP ---
st.title("📊 AI CFO Copilot — Automated FP&A Analyzer")

if df is not None and not df.empty:
    text_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(text_cols) < 1 or len(num_cols) < 2:
        st.warning("Dashboard ke liye file me kam se kam 1 Category (text) aur 2 Numeric columns (jaise Budget aur Actual) hone chahiye.")
        st.dataframe(df.head())
    else:
        st.sidebar.subheader("🔗 Column Mapping")
        cat_col = st.sidebar.selectbox("Category / Department Column", text_cols, index=0)
        budget_col = st.sidebar.selectbox("Budget / Target Column", num_cols, index=0)
        actual_col = st.sidebar.selectbox("Actual / Spend Column", num_cols, index=1 if len(num_cols) > 1 else 0)
        threshold = st.sidebar.slider("Red Flag Variance Threshold (%)", 5, 50, 15)

        # --- PYTHON MATH ENGINE ---
        summary_df = df.groupby(cat_col, as_index=False)[[budget_col, actual_col]].sum()
        summary_df["Variance"] = summary_df[actual_col] - summary_df[budget_col]
        summary_df["Variance_%"] = summary_df.apply(
            lambda r: round((r["Variance"] / r[budget_col]) * 100, 2) if r[budget_col] != 0 else 0.0, axis=1
        )
        summary_df["Status"] = summary_df["Variance_%"].apply(
            lambda x: "🔴 Red Flag" if x > threshold else ("🟢 Under Budget" if x < 0 else "🟡 On Track")
        )

        total_budget = summary_df[budget_col].sum()
        total_actual = summary_df[actual_col].sum()
        net_variance = total_actual - total_budget
        net_var_pct = round((net_variance / total_budget) * 100, 2) if total_budget != 0 else 0.0
        red_flags = summary_df[summary_df["Variance_%"] > threshold]

        # --- TABS ---
        tab1, tab2 = st.tabs(["📈 Executive Dashboard", "🤖 AI CFO Chat"])

        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Budget", f"₹{total_budget:,.0f}")
            c2.metric("Total Actual", f"₹{total_actual:,.0f}")
            c3.metric("Net Variance", f"₹{net_variance:,.0f}", f"{net_var_pct}%", delta_color="inverse")
            c4.metric("Red Flag Areas", f"{len(red_flags)} / {len(summary_df)}")

            st.divider()

            col_left, col_right = st.columns(2)
            with col_left:
                fig_bar = px.bar(
                    summary_df, x=cat_col, y=[budget_col, actual_col],
                    barmode="group", title="Budget vs Actual Comparison"
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_right:
                fig_pie = px.pie(
                    summary_df, names=cat_col, values=actual_col,
                    hole=0.4, title="Actual Spend Breakdown"
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            st.subheader(f"🚨 High Variance Alerts (Over {threshold}%)")
            if not red_flags.empty:
                st.dataframe(red_flags, use_container_width=True, hide_index=True)
            else:
                st.success("Koi bhi category threshold se upar nahi gayi hai!")

            with st.expander("View Full Aggregated Table"):
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

        with tab2:
            st.subheader("💬 Apne Data Se Kuch Bhi Pucho")

            if not api_key:
                st.info("AI Chat use karne ke liye sidebar me apni free Gemini API key daalein.")
            else:
                if "messages" not in st.session_state:
                    st.session_state.messages = []

                q1, q2, q3 = st.columns(3)
                quick_prompt = None
                if q1.button("🔥 Sabse bada budget overrun kahan hai?"):
                    quick_prompt = "Sabse bada budget overrun kis category me hua hai aur kitna % hai?"
                if q2.button("💡 Cost bachane ke 3 tarike batao"):
                    quick_prompt = "Is data ke hisaab se cost optimize karne ke 3 practical corporate recommendations do."
                if q3.button("📋 Boardroom Summary banao"):
                    quick_prompt = "CFO aur Board meeting ke liye is financial data ka 4-bullet executive summary bana do."

                for msg in st.session_state.messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                user_input = st.chat_input("Example: Operations me variance kyun zyada dikh raha hai?")
                prompt = quick_prompt or user_input

                if prompt:
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    data_context = f"""
                    You are an expert Corporate CFO & FP&A Analyst.
                    Answer strictly based on this verified financial summary table. Do NOT invent numbers.
                    If something is not in the data, clearly state it is not available.
                    Always cite the exact Category name and numbers from the table.

                    Total Budget: {total_budget:,.2f}
                    Total Actual: {total_actual:,.2f}
                    Net Variance: {net_variance:,.2f} ({net_var_pct}%)

                    Category Breakdown Table:
                    {summary_df.to_markdown(index=False)}
                    """

                    with st.chat_message("assistant"):
                        with st.spinner("Analyzing numbers..."):
                            try:
                                client = genai.Client(api_key=api_key)
                                history_text = "\n".join(
                                    [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]]
                                )
                                full_prompt = f"{data_context}\n\nConversation History:\n{history_text}\n\nAnswer the latest user query clearly and concisely."

                                models_to_try = ["gemini-3.8-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash-lite"]
                                answer = None
                                last_err = None

                                for m_name in models_to_try:
                                    try:
                                        response = client.models.generate_content(
                                            model=m_name,
                                            contents=full_prompt
                                        )
                                        answer = response.text
                                        break
                                    except Exception as inner_e:
                                        last_err = inner_e
                                        continue

                                if answer:
                                    st.markdown(answer)
                                    st.session_state.messages.append({"role": "assistant", "content": answer})
                                else:
                                    st.error(f"Sabhi models abhi busy hain. Error: {last_err}")
                            except Exception as e:
                                st.error(f"Exact Error: {e}")
else:
    st.info("Shuru karne ke liye sidebar se 'Sample Data' tick karein ya apni Excel/CSV file upload karein.")
