"""
=============================================================
  Productivity Dashboard — Unified Model
  Modelos:
    · Galderma  → More is Best (Points)
    · AMS       → Less is Best (Effort)
    · ITIS      → Less is Best (Ticket Duration / Effort)
=============================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(layout="wide", page_title="Productivity Analysis")

# ─── WINDOW SIZES (Default) ──────────────────────────────────
CURRENT_SIZE  = 3
BASELINE_SIZE = 3
GAP_SIZE      = 3

COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

XAXIS_STYLE = dict(title="Period", tickformat="%b %Y", dtick="M1", tickangle=45)

st.title("📊 Productivity Analysis")


# ════════════════════════════════════════════════════════════
#  DIALOGS
# ════════════════════════════════════════════════════════════
@st.dialog("📖 Documentación", width="large")
def show_docs():
    readme_path = Path("README.md")
    if readme_path.exists():
        st.markdown(readme_path.read_text(encoding="utf-8"))
    else:
        st.warning("README.md no encontrado en el directorio raíz.")


# ════════════════════════════════════════════════════════════
#  DATA LOAD FOR GALDERMA MODEL (Points / More is Best)
# ════════════════════════════════════════════════════════════
def load_galderma(uploaded_file):

    xls  = pd.ExcelFile(uploaded_file)
    sname = "RawData" if "RawData" in xls.sheet_names else xls.sheet_names[0]
    df   = pd.read_excel(uploaded_file, sheet_name=sname)
    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)

    df["Points"] = pd.to_numeric(df["Points"], errors="coerce")
    df["Period"] = pd.to_datetime(df["Period"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    df = df[df["Status"].isin(["Ready to Deploy", "Closed"])].copy()
    df["Grupo"] = "Grupo"

    has_dev = None
    if "Developer" in df.columns:
        has_dev = df["Developer"].notna() & (df["Developer"].astype(str).str.strip() != "") & (df["Developer"].astype(str).str.lower() != "nan")
        
    has_qa = None
    if "QA Tester" in df.columns:
        has_qa = df["QA Tester"].notna() & (df["QA Tester"].astype(str).str.strip() != "") & (df["QA Tester"].astype(str).str.lower() != "nan")
        
    if has_dev is not None and has_qa is not None:
        df = df[has_dev | has_qa].copy()
    elif has_dev is not None:
        df = df[has_dev].copy()
    elif has_qa is not None:
        df = df[has_qa].copy()

    if "Developer" in df.columns:
        df["Developer"] = df["Developer"].astype(str).str.replace("-", "/", regex=False)
        
        def safe_split(x):
            val = str(x).strip()
            if val.lower() in ["unassigned", "nan", "none", "<na>", ""]:
                return ["Unassigned"]
            return val.split("/")
            
        df["Developer_List"] = df["Developer"].apply(safe_split)
        df["Dev_Count"] = df["Developer_List"].apply(len)
        df["Points"] = df["Points"] / df["Dev_Count"]
        
        df["Developer"] = df["Developer_List"]
        df = df.explode("Developer")
        df["Developer"] = df["Developer"].astype(str).str.strip()
        df = df.drop(columns=["Dev_Count", "Developer_List"])

    config = {
        "metric_col":   "Points",
        "more_is_best": True,
        "dimensions":   [c for c in ["Developer", "QA Tester", "Grupo"] if c in df.columns],
        "label_real":   "Real Points",
        "label_exp":    "Expected Points",
    }
    return df, config


# ════════════════════════════════════════════════════════════
#  DATA LOAD FOR AMS MODEL (Effort / Less is Best)
# ════════════════════════════════════════════════════════════
def detect_columns_ams(df: pd.DataFrame) -> dict:
    
    col_map = {
        "Assigned To": None, "IS": None, "Group": None, "WBS": None,
        "Category": None, "Service Type": None, "EndDate": None,
        "Effort": None, "Points": None, "Developer": None,
        "Status": None, "Period": None, "QA Tester": None,
        "Issue Type": None, "Priority": None,
    }
    for col in df.columns:
        c = col.lower().strip()
        if   c in ["assigned to", "assignee", "resource"]:         col_map["Assigned To"]  = col
        elif c == "is":                                             col_map["IS"]           = col
        elif c == "group":                                          col_map["Group"]        = col
        elif c == "wbs":                                            col_map["WBS"]          = col
        elif c == "category":                                       col_map["Category"]     = col
        elif c in ["service type", "servicetype"]:                  col_map["Service Type"] = col
        elif c in ["enddate", "end date"]:                         col_map["EndDate"]      = col
        elif c == "effort":                                         col_map["Effort"]       = col
        elif c == "points":                                         col_map["Points"]       = col
        elif c == "developer":                                      col_map["Developer"]    = col
        elif c == "status":                                         col_map["Status"]       = col
        elif c == "period":                                         col_map["Period"]       = col
        elif c in ["qa tester", "qatester"]:                       col_map["QA Tester"]    = col
        elif c in ["issue type", "issuetype"]:                     col_map["Issue Type"]   = col
        elif c == "priority":                                       col_map["Priority"]     = col
    return col_map


def load_ams(uploaded_file):
   
    xls   = pd.ExcelFile(uploaded_file)
    sname = "RawData" if "RawData" in xls.sheet_names else xls.sheet_names[0]
    df    = pd.read_excel(uploaded_file, sheet_name=sname)
    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)

    col_map = detect_columns_ams(df)

    required = ["Assigned To", "Group", "WBS", "EndDate", "Effort"]
    missing  = [k for k in required if col_map[k] is None]
    if missing:
        return None, f"Missing required columns for AMS model: {missing}"

    df = df.rename(columns={v: k for k, v in col_map.items() if v is not None}).copy()

    df["EndDate"] = pd.to_datetime(df["EndDate"], errors="coerce")
    df["Period"]  = df["EndDate"].dt.to_period("M").dt.to_timestamp()
    df["Effort"]  = pd.to_numeric(df["Effort"], errors="coerce")

    config = {
        "metric_col":   "Effort",
        "more_is_best": False,
        "dimensions":   [c for c in ["Assigned To", "IS", "Group", "WBS", "Category", "Service Type"]
                         if c in df.columns],
        "label_real":   "Real Effort",
        "label_exp":    "Expected Effort",
    }
    return df, config


# ════════════════════════════════════════════════════════════
#  DATA LOAD FOR ITIS MODEL (Effort / Less is Best)
# ════════════════════════════════════════════════════════════
def load_itis(uploaded_file):
    
    xls   = pd.ExcelFile(uploaded_file)
    sname = "Data Template" if "Data Template" in xls.sheet_names else xls.sheet_names[0]
    df    = pd.read_excel(uploaded_file, sheet_name=sname)
    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)

    required_cols = ["Ticket Closed/Resolved Date", "Ticket Duration", "Assignee", "Ticket Type"]
    missing = [c for c in required_cols if c not in df.columns]
    
    if missing:
        return None, f"Missing required columns for ITIS model: {missing}"

    df["Date_Temp"] = pd.to_datetime(df["Ticket Closed/Resolved Date"], errors="coerce")
    df["Period"] = df["Date_Temp"].dt.to_period("M").dt.to_timestamp()
    
    df["Ticket Duration"] = pd.to_numeric(df["Ticket Duration"], errors="coerce")
    df["Effort"] = df["Ticket Duration"] / 60.0
    
    df["Grupo"] = "Grupo"
    df = df[df["Period"].notna() & df["Effort"].notna()].copy()

    config = {
        "metric_col":   "Effort",
        "more_is_best": False, 
        "dimensions":   [c for c in ["Assignee", "Ticket Type", "Grupo"] if c in df.columns],
        "label_real":   "Real Effort",
        "label_exp":    "Expected Effort",
    }
    return df, config


# ════════════════════════════════════════════════════════════
#  MONTHLY AGGREGATION
# ════════════════════════════════════════════════════════════
def aggregate_monthly(df: pd.DataFrame, dimension: str, metric_col: str) -> pd.DataFrame:
    agg = (
        df.groupby(["Period", dimension], dropna=False)
        .agg(n=(metric_col, "size"),
             Sum=(metric_col, "sum"), 
             Mean=(metric_col, "mean")) 
        .reset_index()
        .sort_values(["Period", dimension])
        .reset_index(drop=True)
    )
    return agg


# ════════════════════════════════════════════════════════════
#  PRODUCTIVITY CALCULATION
# ════════════════════════════════════════════════════════════
def fx_productivity_v3(db_agg, dimension, more_is_best, selected_values=None,
                       current_size=CURRENT_SIZE, gap_size=GAP_SIZE, baseline_size=BASELINE_SIZE):

    signo = 1 if more_is_best else -1
    if selected_values is not None:
        db_agg = db_agg[db_agg[dimension].isin(selected_values)].copy()

    fechas = sorted(db_agg["Period"].unique())
    rows   = []

    for current_period in fechas:
        subset_all = db_agg[db_agg["Period"] <= current_period].copy()
        services   = subset_all[dimension].unique()

        period_effort_data = 0.0
        period_base_equiv  = 0.0
        any_calc = False

        for svc in services:
            svc_data = (
                subset_all[subset_all[dimension] == svc]
                .sort_values("Period", ascending=False)
                .reset_index(drop=True)
            )
            n         = len(svc_data)
            max_fecha = svc_data["Period"].max()

            if n < current_size or current_period > max_fecha:
                continue

            has_baseline_full = n >= (current_size + gap_size + baseline_size)
            cur_s, cur_e = 0, current_size

            if has_baseline_full:
                bl_s = current_size + gap_size
                bl_e = current_size + gap_size + baseline_size
            else:
                bl_s = max(0, n - baseline_size)
                bl_e = n

            cw = svc_data.iloc[cur_s:cur_e]
            bw = svc_data.iloc[bl_s:bl_e]

            effort_data     = cw["Sum"].sum()
            units_data      = cw["n"].sum()
            effort_baseline = bw["Sum"].sum()
            units_baseline  = bw["n"].sum()

            if units_baseline == 0 or units_data == 0:
                continue

            epu_bl     = effort_baseline / units_baseline
            base_equiv = epu_bl * units_data

            period_effort_data += effort_data
            period_base_equiv  += base_equiv
            any_calc = True

        if not any_calc or period_base_equiv == 0:
            continue

        productivity = ((period_effort_data - period_base_equiv) / period_base_equiv) * signo
        rows.append({
            "ActualPeriod":   current_period,
            "EffortData":     period_effort_data,
            "BaseEfforEquiv": period_base_equiv,
            "Value":          productivity,
        })

    return pd.DataFrame(rows)


def calc_individual_productivity(db_agg, dimension, more_is_best, selected_values, **kwargs):
    results = []
    for val in selected_values:
        res = fx_productivity_v3(db_agg, dimension, more_is_best, [val], **kwargs)
        if not res.empty:
            res[dimension] = str(val)
            results.append(res)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def calc_global_productivity(db_agg, dimension, more_is_best, selected_values, **kwargs):
    res = fx_productivity_v3(db_agg, dimension, more_is_best, selected_values, **kwargs)
    if not res.empty:
        res[dimension] = "Group Total"
    return res


# ════════════════════════════════════════════════════════════
#  GRAFICS
# ════════════════════════════════════════════════════════════
def make_count_chart(db_agg, dimension, selected_values):
    fig = go.Figure()
    for i, val in enumerate(selected_values):
        sub = db_agg[db_agg[dimension] == str(val)].sort_values("Period")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["Period"], y=sub["n"],
            mode="lines+markers+text",
            name=str(val),
            text=[f"{v:.0f}" for v in sub["n"]],
            textposition="top center",
            line=dict(color=COLORS[i % len(COLORS)], width=2),
            marker=dict(size=6),
        ))
    fig.update_layout(
        title=f"{dimension} — Ticket Count Over Time",
        xaxis=XAXIS_STYLE, yaxis_title="Count (n)",
        height=420, hovermode="x unified",
    )
    return fig


def make_mean_chart(db_agg, dimension, metric_col, selected_values):
    fig = go.Figure()
    for i, val in enumerate(selected_values):
        sub = db_agg[db_agg[dimension] == str(val)].sort_values("Period")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["Period"], y=sub["Mean"],
            mode="lines+markers+text",
            name=str(val),
            text=[f"{v:.2f}" for v in sub["Mean"]],
            textposition="top center",
            line=dict(color=COLORS[i % len(COLORS)], width=2),
            marker=dict(size=6),
        ))
    fig.update_layout(
        title=f"{dimension} — Mean {metric_col} Over Time",
        xaxis=XAXIS_STYLE, yaxis_title=f"Mean {metric_col}",
        height=420, hovermode="x unified",
    )
    return fig


def make_productivity_chart(prod_df, dimension, label_real, label_exp):
    fig = go.Figure()
    vals = prod_df[dimension].unique() if dimension in prod_df.columns else ["Group Total"]
    for i, val in enumerate(vals):
        sub = (prod_df[prod_df[dimension] == str(val)]
               if dimension in prod_df.columns else prod_df).sort_values("ActualPeriod")
        prod_pct = sub["Value"] * 100
        fig.add_trace(go.Scatter(
            x=sub["ActualPeriod"], y=prod_pct,
            mode="lines+markers+text",
            name=str(val),
            text=[f"{v:.1f}%" if pd.notna(v) else "" for v in prod_pct],
            textposition="top center",
            line=dict(color=COLORS[i % len(COLORS)], width=2),
            marker=dict(size=6),
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1.5)
    fig.update_layout(
        title=f"Productivity Over Time by {dimension}",
        xaxis=XAXIS_STYLE, yaxis_title="Productivity (%)",
        height=420, hovermode="x unified",
    )
    return fig


def make_velocity_chart(prod_df, dimension, metric_col, label_real, label_exp, chart_title="Velocity: Real vs Expected"):
    fig = go.Figure()
    vals   = prod_df[dimension].unique() if dimension in prod_df.columns else ["Group Total"]
    styles = [("EffortData", label_real, "solid"), ("BaseEfforEquiv", label_exp, "dash")]
    for i, val in enumerate(vals):
        sub = (prod_df[prod_df[dimension] == str(val)]
               if dimension in prod_df.columns else prod_df).sort_values("ActualPeriod")
        base_color = COLORS[i % len(COLORS)]
        for col, lbl, dash in styles:
            fig.add_trace(go.Scatter(
                x=sub["ActualPeriod"], y=sub[col],
                mode="lines+markers",
                name=f"{val} — {lbl}",
                line=dict(color=base_color, width=2, dash=dash),
                marker=dict(size=5),
            ))
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1.5)
    fig.update_layout(
        title=chart_title,
        xaxis=XAXIS_STYLE, yaxis_title=metric_col,
        height=420, hovermode="x unified",
    )
    return fig


# ════════════════════════════════════════════════════════════
#  UI PRINCIPAL
# ════════════════════════════════════════════════════════════

st.sidebar.header("⚙️ Model")
model_choice = st.sidebar.radio(
    "Select productivity model",
    [
        "🟢  Galderma · Points  (More is Best)", 
        "🔵  AMS · Effort  (Less is Best)",
        "🟠  ITIS · Duration  (Less is Best)"
    ],
    help=(
        "Galderma: Tracks story points delivered by developers.\n"
        "AMS: Tracks effort (hours) consumed per ticket — lower is better.\n"
        "ITIS: Tracks ticket duration (converted to hours) — lower is better."
    ),
)
is_galderma = model_choice.startswith("🟢")
is_ams      = model_choice.startswith("🔵")
is_itis     = model_choice.startswith("🟠")

st.sidebar.markdown("---")
st.sidebar.header("📂 Data")

if is_galderma:
    uploader_text = "Upload Galderma Excel file (.xlsx)"
elif is_ams:
    uploader_text = "Upload AMS Excel file (.xlsx)"
else:
    uploader_text = "Upload ITIS 'Account Ticket Analysis' (.xlsx)"
    
uploaded_file = st.file_uploader(uploader_text, type=["xlsx"])

# ── Documentación & Templates ──────────────────────────────
st.sidebar.markdown("---")

if st.sidebar.button("📖 Documentación", use_container_width=True):
    show_docs()

with st.sidebar.expander("📁 Templates"):
    templates_dir = Path("Templates")
    if templates_dir.exists():
        templates = sorted(templates_dir.glob("*.xlsx"))
        if templates:
            for tpl in templates:
                with open(tpl, "rb") as f:
                    tpl_bytes = f.read()
                st.download_button(
                    label=f"⬇️ {tpl.name}",
                    data=tpl_bytes,
                    file_name=tpl.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{tpl.stem}",
                    use_container_width=True,
                )
        else:
            st.info("No hay templates disponibles.")
    else:
        st.info("Carpeta Templates no encontrada.")


# ── Data Load ──────────────────────────────
df, config = None, None

if uploaded_file:
    if is_ams:
        result = load_ams(uploaded_file)
    elif is_itis:
        result = load_itis(uploaded_file)
    else:
        result = load_galderma(uploaded_file)
        
    if isinstance(result, tuple) and result[0] is None:
        st.error(result[1])
        st.stop()
    elif isinstance(result, tuple):
        df, config = result
    else:
        df, config = result
else:
    # Local Files Fallbacks
    galderma_path = Path("Galderma_12-01-24_to_03-31-26.xlsx")
    ams_path      = Path("DataForPythonAMS.xlsx")
    itis_path     = Path("Account Ticket Analysis.xlsx")

    if is_galderma and galderma_path.exists():
        df, config = load_galderma(str(galderma_path))
        st.info(f"📄 Usando archivo local: {galderma_path.name}  —  {len(df):,} filas")
    elif is_ams and ams_path.exists():
        result = load_ams(str(ams_path))
        if result[0] is None:
            st.error(result[1])
            st.stop()
        df, config = result
        st.info(f"📄 Local File: {ams_path.name}  —  {len(df):,} filas")
    elif is_itis and itis_path.exists():
        result = load_itis(str(itis_path))
        if result[0] is None:
            st.error(result[1])
            st.stop()
        df, config = result
        st.info(f"📄 Local File: {itis_path.name}  —  {len(df):,} filas")
    else:
        st.info("⬆️  Upload an Excel file to begin.")
        st.stop()

# ── Badge de modelo activo ───────────────────────────────────
if is_galderma:
    st.markdown(
        "🟢 **GALDERMA MODEL** — MORE IS BEST (POINTS) &nbsp;|&nbsp; "
        f"Metric: `{config['metric_col']}`"
    )
elif is_ams:
    st.markdown(
        "🔵 **AMS MODEL** — LESS IS BEST (EFFORT) &nbsp;|&nbsp; "
        f"Metric: `{config['metric_col']}`"
    )
else:
    st.markdown(
        "🟠 **ITIS MODEL** — LESS IS BEST (EFFORT / HRS) &nbsp;|&nbsp; "
        f"Metric: `{config['metric_col']}`"
    )

# ── Controls  ────────────────────────────────────────
st.sidebar.header("Controls")

dimension = st.sidebar.selectbox("Analyze by", config["dimensions"])

df[dimension] = df[dimension].astype(str)
values = sorted(df[dimension].dropna().unique().tolist())

default_sel = [v for v in values if v != "Unassigned"][:3] if len(values) >= 3 else values
selected_values = st.sidebar.multiselect("Select values", values, default=default_sel)

analysis_mode = st.sidebar.radio(
    "Analysis mode",
    ["Individual (one series per value)", "Global (combined into one series)"],
    help="Individual = R Recursive mode.  Global = R Single mode.",
)

show_charts = st.sidebar.multiselect(
    "Charts to show",
    ["Productivity", "Velocity 3M", "Velocity per Month", "Count over Time", "Mean over Time"],
    default=["Productivity", "Velocity 3M", "Velocity per Month"],
)

# ── RANGO DE FECHAS (UI) ──────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.header("📅 Rango de Fechas")

# Obtener las fechas mínima y máxima disponibles en los datos
min_date = df["Period"].min().to_pydatetime().date()
max_date = df["Period"].max().to_pydatetime().date()

# Slider para que el usuario seleccione el rango a visualizar
date_range = st.sidebar.slider(
    "Selecciona el rango a visualizar",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="MMM YYYY"
)

# Extraer el inicio y fin del rango seleccionado
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date


if not selected_values:
    st.warning("Select at least one value.")
    st.stop()

# ── Agregación ────────────────────────────────────────────────
df_filtered = df[df[dimension].isin(selected_values)].copy()
db_agg = aggregate_monthly(df_filtered, dimension, config["metric_col"])
db_agg[dimension] = db_agg[dimension].astype(str)

# ── Productividad (Cálculo Paralelo para 3M y 1M) ─────────────
if "Individual" in analysis_mode:
    prod_df_3m = calc_individual_productivity(
        db_agg, dimension, config["more_is_best"], selected_values,
        current_size=3, gap_size=3, baseline_size=3
    )
    prod_df_1m = calc_individual_productivity(
        db_agg, dimension, config["more_is_best"], selected_values,
        current_size=1, gap_size=3, baseline_size=3
    )
else:
    prod_df_3m = calc_global_productivity(
        db_agg, dimension, config["more_is_best"], selected_values,
        current_size=3, gap_size=3, baseline_size=3
    )
    prod_df_1m = calc_global_productivity(
        db_agg, dimension, config["more_is_best"], selected_values,
        current_size=1, gap_size=3, baseline_size=3
    )

# ── APLICAR FILTRO DE FECHAS PARA VISUALIZACIÓN ───────────────
# Es clave hacerlo aquí (DESPUÉS del cálculo) para mantener los históricos matemáticos
db_agg = db_agg[(db_agg["Period"].dt.date >= start_date) & (db_agg["Period"].dt.date <= end_date)]

if not prod_df_3m.empty:
    prod_df_3m = prod_df_3m[(prod_df_3m["ActualPeriod"].dt.date >= start_date) & (prod_df_3m["ActualPeriod"].dt.date <= end_date)]
    
if not prod_df_1m.empty:
    prod_df_1m = prod_df_1m[(prod_df_1m["ActualPeriod"].dt.date >= start_date) & (prod_df_1m["ActualPeriod"].dt.date <= end_date)]


# ── Gráficas ──────────────────────────────────────────────────
if prod_df_3m.empty and prod_df_1m.empty:
    st.warning(
        f"⚠️ No hay datos suficientes o el rango de fecha seleccionado no contiene métricas calculables. "
    )
else:
    if "Productivity" in show_charts and not prod_df_3m.empty:
        st.subheader("📈 Productivity Over Time (3M Base)")
        st.caption(
            "Positive = better than baseline  |  Negative = worse than baseline  |  "
            "Zero line = baseline level"
        )
        st.plotly_chart(
            make_productivity_chart(prod_df_3m, dimension, config["label_real"], config["label_exp"]),
            use_container_width=True,
        )

    if "Velocity 3M" in show_charts and not prod_df_3m.empty:
        st.subheader("⚡ Velocity 3M: Real vs Expected")
        st.caption(
            f"{config['label_real']} = sum of {config['metric_col']} in current 3-month window  |  "
            f"{config['label_exp']} = what baseline EpU predicts for current 3-month volume"
        )
        st.plotly_chart(
            make_velocity_chart(
                prod_df_3m, dimension, config["metric_col"],
                config["label_real"], config["label_exp"],
                chart_title=f"Velocity 3M: {config['label_real']} vs {config['label_exp']}"
            ),
            use_container_width=True,
        )
        
    if "Velocity per Month" in show_charts and not prod_df_1m.empty:
        st.subheader("⚡ Velocity per Month: Real vs Expected")
        st.caption(
            f"{config['label_real']} = sum of {config['metric_col']} in current 1-month window  |  "
            f"{config['label_exp']} = what baseline EpU predicts for current 1-month volume"
        )
        st.plotly_chart(
            make_velocity_chart(
                prod_df_1m, dimension, config["metric_col"],
                config["label_real"], config["label_exp"],
                chart_title=f"Velocity per Month: {config['label_real']} vs {config['label_exp']}"
            ),
            use_container_width=True,
        )

if "Count over Time" in show_charts:
    st.subheader("🔢 Ticket Count Over Time")
    st.plotly_chart(
        make_count_chart(db_agg, dimension, selected_values),
        use_container_width=True,
    )

if "Mean over Time" in show_charts:
    st.subheader(f"📊 Mean {config['metric_col']} Over Time")
    st.plotly_chart(
        make_mean_chart(db_agg, dimension, config["metric_col"], selected_values),
        use_container_width=True,
    )

# ── Tablas (expanders) ────────────────────────────────────────
with st.expander("📋 Aggregated Monthly Data (db_agg)", expanded=False):
    st.dataframe(db_agg.sort_values(["Period", dimension]), use_container_width=True)

if not prod_df_3m.empty or not prod_df_1m.empty:
    with st.expander("📋 Productivity Results", expanded=False):
        tab1, tab2 = st.tabs(["3-Month Window", "1-Month Window"])
        with tab1:
            if not prod_df_3m.empty:
                display_3m = prod_df_3m.copy()
                display_3m["Productivity %"] = (display_3m["Value"] * 100).map(
                    lambda x: f"{x:.4f}%" if pd.notna(x) else ""
                )
                st.dataframe(display_3m.sort_values("ActualPeriod"), use_container_width=True)
            else:
                st.info("No hay datos calculados para mostrar en este rango.")
                
        with tab2:
            if not prod_df_1m.empty:
                display_1m = prod_df_1m.copy()
                display_1m["Productivity %"] = (display_1m["Value"] * 100).map(
                    lambda x: f"{x:.4f}%" if pd.notna(x) else ""
                )
                st.dataframe(display_1m.sort_values("ActualPeriod"), use_container_width=True)
            else:
                st.info("No hay datos calculados para mostrar en este rango.")

# ── Footer ─────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="text-align: right;">
        © 2026 Softtek. All rights reserved.<br>
        Developed by the Softtek - Maritz Team
    </div>
    """,
    unsafe_allow_html=True
)