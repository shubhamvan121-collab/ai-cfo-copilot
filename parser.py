import io
import pandas as pd
from google import genai

def call_gemini(api_key: str, prompt_text: str):
    if not api_key:
        return None
    client = genai.Client(api_key=api_key)
    for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.5-flash-lite"]:
        try:
            resp = client.models.generate_content(model=m_name, contents=prompt_text)
            if resp and resp.text:
                return resp.text
        except Exception:
            continue
    return None

def read_raw_file(uploaded_file):
    """Reads CSV or Excel without assuming Row 1 is the header."""
    if uploaded_file.name.lower().endswith(".csv"):
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, header=None)
    else:
        uploaded_file.seek(0)
        xls = pd.ExcelFile(uploaded_file)
        return pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)

def parse_statement_with_ai(raw_df: pd.DataFrame, statement_type: str, source_name: str, api_key: str):
    """
    Uses Gemini to understand messy financial files (Screener, Tally, ERP)
    and return a clean, standardized DataFrame with Core vs Other classification.
    """
    raw_text = raw_df.head(75).to_csv(index=False, header=False)

    if statement_type == "P&L":
        allowed_cats = "Revenue, COGS, OpEx, Other Income, Other Expense, Depreciation, Interest, Tax, Exceptional Item"
    else:
        allowed_cats = "Current Assets, Fixed Assets, CWIP, Investments, Other Assets, Current Liabilities, Long-Term Debt, Other Liabilities, Equity"

    prompt = f"""
    You are a Senior FP&A Data Engineer. Understand and standardize this raw {statement_type} spreadsheet (file: "{source_name}") into a clean CSV with EXACTLY 5 columns:
    Line_Item,Category,Nature,Previous_Period,Latest_Period

    STRICT RULES:
    1. Drop all percentage, ratio, margin, or growth rows (e.g., Tax %, Margin %, Growth %, Employee Cost %, EPS, Dividend Payout).
    2. Drop all subtotal/total rows (e.g., Gross Profit, EBITDA, Operating Profit, Financing Profit, PBT, Profit before tax, Net Profit, Total Assets, Total Liabilities).
    3. Map Category strictly to one of: {allowed_cats}
    4. Set Nature strictly to "Core" (for core operating items like Revenue, COGS, OpEx, Current Assets, Fixed Assets, Current Liabilities, Equity) or "Other" (for Other Income, Other Expense, Exceptional Item, Investments, CWIP, Other Assets, Other Liabilities, Interest, Tax, Depreciation).
    5. If multiple years/periods exist, put the 2nd latest numeric period in Previous_Period and the latest numeric period in Latest_Period.
    6. Pure numbers only in Previous_Period and Latest_Period (no commas, no currency symbols, no %). Replace blanks with 0.
    7. Return ONLY raw CSV text starting with the header line. No markdown backticks, no explanation.

    RAW DATA:
    {raw_text}
    """
    resp = call_gemini(api_key, prompt)
    if not resp:
        return None
    try:
        clean_csv = resp.replace("```csv", "").replace("```", "").strip()
        df = pd.read_csv(io.StringIO(clean_csv))
        for col in ["Previous_Period", "Latest_Period"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        df["Source_File"] = source_name
        return df
    except Exception:
        return None

def load_sample_pnl():
    data = [
        ["Product Sales", "Revenue", "Core", 1200.0, 1280.0, "Sample_PnL.xlsx"],
        ["Service Revenue", "Revenue", "Core", 450.0, 510.0, "Sample_PnL.xlsx"],
        ["Raw Materials Consumed", "COGS", "Core", 520.0, 610.0, "Sample_PnL.xlsx"],
        ["Manufacturing & Direct Labor", "COGS", "Core", 180.0, 195.0, "Sample_PnL.xlsx"],
        ["Employee Salaries & Admin", "OpEx", "Core", 310.0, 330.0, "Sample_PnL.xlsx"],
        ["Marketing & Distribution", "OpEx", "Core", 150.0, 210.0, "Sample_PnL.xlsx"],
        ["Interest & Dividend Income", "Other Income", "Other", 25.0, 65.0, "Sample_PnL.xlsx"],
        ["Forex Loss & Misc Expenses", "Other Expense", "Other", 15.0, 28.0, "Sample_PnL.xlsx"],
        ["One-Time Asset Sale Gain", "Exceptional Item", "Other", 0.0, 45.0, "Sample_PnL.xlsx"],
        ["Depreciation & Amortization", "Depreciation", "Other", 65.0, 70.0, "Sample_PnL.xlsx"],
        ["Finance Cost (Interest)", "Interest", "Other", 85.0, 80.0, "Sample_PnL.xlsx"],
        ["Corporate Income Tax", "Tax", "Other", 90.0, 105.0, "Sample_PnL.xlsx"],
    ]
    return pd.DataFrame(data, columns=["Line_Item", "Category", "Nature", "Previous_Period", "Latest_Period", "Source_File"])

def load_sample_bs():
    data = [
        ["Cash & Bank Equivalents", "Current Assets", "Core", 320.0, 360.0, "Sample_BS.xlsx"],
        ["Accounts Receivable", "Current Assets", "Core", 280.0, 340.0, "Sample_BS.xlsx"],
        ["Inventory & Raw Stock", "Current Assets", "Core", 240.0, 310.0, "Sample_BS.xlsx"],
        ["Plant, Machinery & Buildings", "Fixed Assets", "Core", 1100.0, 1180.0, "Sample_BS.xlsx"],
        ["Capital Work in Progress (CWIP)", "CWIP", "Other", 80.0, 120.0, "Sample_BS.xlsx"],
        ["Long-Term Investments", "Investments", "Other", 190.0, 210.0, "Sample_BS.xlsx"],
        ["Other Non-Current Assets", "Other Assets", "Other", 90.0, 80.0, "Sample_BS.xlsx"],
        ["Accounts Payable", "Current Liabilities", "Core", 260.0, 310.0, "Sample_BS.xlsx"],
        ["Short-Term Borrowings", "Current Liabilities", "Core", 180.0, 200.0, "Sample_BS.xlsx"],
        ["Long-Term Bank Loans", "Long-Term Debt", "Core", 650.0, 610.0, "Sample_BS.xlsx"],
        ["Other Liabilities & Provisions", "Other Liabilities", "Other", 110.0, 130.0, "Sample_BS.xlsx"],
        ["Equity Share Capital", "Equity", "Core", 500.0, 500.0, "Sample_BS.xlsx"],
        ["Reserves & Surplus", "Equity", "Core", 600.0, 850.0, "Sample_BS.xlsx"],
    ]
    return pd.DataFrame(data, columns=["Line_Item", "Category", "Nature", "Previous_Period", "Latest_Period", "Source_File"])
