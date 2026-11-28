import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def plot_pnl_waterfall(m: dict, unit_suffix: str):
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "total", "relative", "total", "relative", "relative", "total"],
        x=["Core Revenue", "COGS", "Gross Profit", "Core OpEx", "Core EBITDA", "Net Other & Excep.", "Dep / Int / Tax", "Net Profit (PAT)"],
        y=[
            m["rev_c"], -m["cogs_c"], 0, -m["opex_c"], 0,
            m["net_other_c"], -(m["dep_c"] + m["int_c"] + m["tax_c"]), 0
        ],
        textposition="outside"
    ))
    fig.update_layout(title=f"P&L Bridge: Core Operations vs Other Factors ({unit_suffix.strip() or '₹'})", showlegend=False)
    return fig

def plot_core_vs_other_bar(df: pd.DataFrame, title: str):
    agg = df.groupby(["Nature", "Category"], as_index=False)[["Previous_Period", "Latest_Period"]].sum()
    fig = px.bar(
        agg, x="Category", y=["Previous_Period", "Latest_Period"],
        color_discrete_sequence=["#636EFA", "#00CC96"],
        barmode="group", title=title
    )
    return fig

def plot_bs_structure(df: pd.DataFrame):
    asset_cats = ["Current Assets", "Fixed Assets", "CWIP", "Investments", "Other Assets"]
    bs_df = df.copy()
    bs_df["Side"] = bs_df["Category"].apply(lambda c: "Assets" if c in asset_cats else "Liabilities & Equity")
    fig = px.bar(
        bs_df, x="Side", y="Latest_Period", color="Category",
        title="Balance Sheet Structure: Assets vs Liabilities & Equity",
        text_auto=".2s"
    )
    return fig

def plot_item_xray(row: pd.Series, unit_suffix: str):
    fig = px.bar(
        x=["Previous Period", "Latest Period"],
        y=[row["Previous_Period"], row["Latest_Period"]],
        color=["Previous Period", "Latest Period"],
        title=f"X-Ray Trend: {row['Line_Item']} ({unit_suffix.strip() or '₹'})",
        height=240
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="")
    return fig
