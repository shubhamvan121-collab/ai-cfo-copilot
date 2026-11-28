import pandas as pd

def fmt_val(val: float, unit_suffix: str = "") -> str:
    return f"₹{val:,.1f}{unit_suffix}" if abs(val) < 1000 else f"₹{val:,.0f}{unit_suffix}"

def pct_change(curr: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return round(((curr - prev) / abs(prev)) * 100, 1)

def compute_pnl_metrics(df: pd.DataFrame) -> dict:
    def cat_sum(cat_name, col):
        return float(df.loc[df["Category"] == cat_name, col].sum())

    rev_c, rev_p = cat_sum("Revenue", "Latest_Period"), cat_sum("Revenue", "Previous_Period")
    cogs_c, cogs_p = cat_sum("COGS", "Latest_Period"), cat_sum("COGS", "Previous_Period")
    opex_c, opex_p = cat_sum("OpEx", "Latest_Period"), cat_sum("OpEx", "Previous_Period")

    other_inc_c = cat_sum("Other Income", "Latest_Period")
    other_exp_c = cat_sum("Other Expense", "Latest_Period")
    excep_c = cat_sum("Exceptional Item", "Latest_Period")
    dep_c = cat_sum("Depreciation", "Latest_Period")
    int_c = cat_sum("Interest", "Latest_Period")
    tax_c = cat_sum("Tax", "Latest_Period")

    gp_c, gp_p = rev_c - cogs_c, rev_p - cogs_p
    core_ebitda_c, core_ebitda_p = gp_c - opex_c, gp_p - opex_p
    net_other_c = other_inc_c + excep_c - other_exp_c
    pbt_c = core_ebitda_c + net_other_c - dep_c - int_c
    pat_c = pbt_c - tax_c

    return {
        "rev_c": rev_c, "rev_p": rev_p, "rev_chg": pct_change(rev_c, rev_p),
        "cogs_c": cogs_c, "cogs_p": cogs_p, "cogs_chg": pct_change(cogs_c, cogs_p),
        "gp_c": gp_c, "gm_c": round((gp_c / rev_c) * 100, 1) if rev_c else 0.0,
        "opex_c": opex_c, "opex_p": opex_p, "opex_chg": pct_change(opex_c, opex_p),
        "core_ebitda_c": core_ebitda_c,
        "core_ebitda_m": round((core_ebitda_c / rev_c) * 100, 1) if rev_c else 0.0,
        "other_inc_c": other_inc_c, "other_exp_c": other_exp_c, "excep_c": excep_c,
        "net_other_c": net_other_c,
        "dep_c": dep_c, "int_c": int_c, "tax_c": tax_c,
        "pbt_c": pbt_c, "pat_c": pat_c,
        "pat_m": round((pat_c / rev_c) * 100, 1) if rev_c else 0.0,
    }

def compute_bs_metrics(df: pd.DataFrame) -> dict:
    def cat_sum(cat_name, col):
        return float(df.loc[df["Category"] == cat_name, col].sum())

    ca_c, ca_p = cat_sum("Current Assets", "Latest_Period"), cat_sum("Current Assets", "Previous_Period")
    fa_c = cat_sum("Fixed Assets", "Latest_Period")
    cwip_c = cat_sum("CWIP", "Latest_Period")
    inv_c = cat_sum("Investments", "Latest_Period")
    oa_c = cat_sum("Other Assets", "Latest_Period")
    tot_assets_c = ca_c + fa_c + cwip_c + inv_c + oa_c

    cl_c, cl_p = cat_sum("Current Liabilities", "Latest_Period"), cat_sum("Current Liabilities", "Previous_Period")
    ltd_c = cat_sum("Long-Term Debt", "Latest_Period")
    ol_c = cat_sum("Other Liabilities", "Latest_Period")
    eq_c = cat_sum("Equity", "Latest_Period")
    tot_liab_c = cl_c + ltd_c + ol_c

    working_cap_c = ca_c - cl_c
    curr_ratio_c = round(ca_c / cl_c, 2) if cl_c > 0 else 0.0
    debt_to_eq_c = round(tot_liab_c / eq_c, 2) if eq_c > 0 else 0.0
    balance_diff = round(tot_assets_c - (tot_liab_c + eq_c), 2)

    return {
        "ca_c": ca_c, "fa_c": fa_c, "cwip_c": cwip_c, "inv_c": inv_c, "oa_c": oa_c,
        "tot_assets_c": tot_assets_c,
        "cl_c": cl_c, "ltd_c": ltd_c, "ol_c": ol_c, "tot_liab_c": tot_liab_c,
        "eq_c": eq_c,
        "working_cap_c": working_cap_c,
        "curr_ratio_c": curr_ratio_c,
        "debt_to_eq_c": debt_to_eq_c,
        "balance_diff": balance_diff,
    }
