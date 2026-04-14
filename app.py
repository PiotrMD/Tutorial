import io
import os
from datetime import date, timedelta
from typing import List

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

APP_TITLE = "Asystent kliniczny – czerwienica prawdziwa"
DATA_FILE = "patients.csv"
TARGET_HCT = 45.0
MAX_SINGLE_PHLEB_ML = 300
PDF_FONT_FILE = "DejaVuSans.ttf"
PDF_FONT_NAME = "DejaVuSans"

st.set_page_config(
    page_title=APP_TITLE,
    layout="centered",
    initial_sidebar_state="collapsed",
)

try:
    st.set_option("client.showErrorDetails", False)
except Exception:
    pass


# =========================
# STYLE
# =========================

st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1000px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .ak-card {
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid rgba(120,120,120,0.25);
        background: rgba(250,250,250,0.03);
        margin-bottom: 12px;
    }
    .ak-kpi-title {
        font-size: 0.9rem;
        opacity: 0.8;
        margin-bottom: 4px;
    }
    .ak-kpi-value {
        font-size: 1.35rem;
        font-weight: 700;
    }
    .ak-section {
        margin-top: 1.2rem;
        margin-bottom: 0.6rem;
        font-size: 1.2rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# DOMYŚLNE WARTOŚCI
# =========================

DEFAULTS = {
    "patient_id": "",
    "age": 55,
    "sex": "M",
    "weight": 80.0,
    "height": 175.0,
    "diagnoses_text": "",
    "history_text": "",
    "treatment_text": "",
    "hx_thrombosis": False,
    "hx_bleeding": False,
    "hx_spleen": False,
    "hx_smoking": False,
    "other_events_text": "",
    "symptom_itch": False,
    "symptom_headache": False,
    "symptom_erythromelalgia": False,
    "symptom_dizziness": False,
    "symptom_micro": False,
    "symptom_nightsweats": False,
    "symptom_weightloss": False,
    "other_symptoms_text": "",
    "labs_n": 4,
    "phleb_n": 4,
}

for i in range(10):
    DEFAULTS[f"cbc_date_{i}"] = date.today()
    DEFAULTS[f"cbc_hct_{i}"] = 45.0
    DEFAULTS[f"cbc_hb_{i}"] = 15.0
    DEFAULTS[f"cbc_wbc_{i}"] = 10.0
    DEFAULTS[f"cbc_plt_{i}"] = 400.0
    DEFAULTS[f"cbc_ldh_{i}"] = 250.0
    DEFAULTS[f"cbc_uric_{i}"] = 6.0
    DEFAULTS[f"cbc_ferr_{i}"] = 50.0
    DEFAULTS[f"cbc_creat_{i}"] = 1.0
    DEFAULTS[f"cbc_rdw_{i}"] = 13.0
    DEFAULTS[f"cbc_b2m_{i}"] = 2.0
    DEFAULTS[f"cbc_glu_{i}"] = 90.0
    DEFAULTS[f"cbc_alt_{i}"] = 25.0
    DEFAULTS[f"cbc_ast_{i}"] = 25.0
    DEFAULTS[f"cbc_ggtp_{i}"] = 30.0
    DEFAULTS[f"cbc_bili_{i}"] = 0.8

for i in range(12):
    DEFAULTS[f"ph_date_{i}"] = date.today()
    DEFAULTS[f"ph_ml_{i}"] = 300


# =========================
# SESSION STATE
# =========================

def init_state():
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_form():
    for key, value in DEFAULTS.items():
        st.session_state[key] = value

    for key in [
        "analysis_ready",
        "last_summary",
        "last_note",
        "last_flags",
        "last_drug_alerts",
        "last_next_ml",
        "last_current_hct",
        "last_current_status",
        "last_compare_rows",
        "last_phleb_table",
        "last_phleb_count_year",
        "last_phleb_ml_year",
        "last_phleb_avg_interval",
        "last_data",
    ]:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()


# =========================
# HELPERS
# =========================

def safe_float(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def text_lines(text: str) -> List[str]:
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def numbered_lines(text: str) -> List[str]:
    lines = text_lines(text)
    return [f"{i+1}. {line}" for i, line in enumerate(lines)]


def bmi_calc(weight_kg, height_cm):
    if not weight_kg or not height_cm or height_cm <= 0:
        return None
    return weight_kg / ((height_cm / 100.0) ** 2)


def bmi_class(bmi):
    if bmi is None:
        return "brak danych"
    if bmi < 18.5:
        return "niedowaga"
    if bmi < 25:
        return "masa ciała prawidłowa"
    if bmi < 30:
        return "nadwaga"
    if bmi < 35:
        return "otyłość I°"
    if bmi < 40:
        return "otyłość II°"
    return "otyłość III°"


def round_to_25(value):
    return int(round(value / 25.0) * 25)


def estimate_blood_volume_liters(sex: str, height_cm, weight_kg):
    if height_cm is None or weight_kg is None:
        return None

    h = height_cm / 100.0
    w = weight_kg

    if sex == "M":
        return (0.3669 * (h ** 3)) + (0.03219 * w) + 0.6041
    if sex == "K":
        return (0.3561 * (h ** 3)) + (0.03308 * w) + 0.1833
    return (0.3615 * (h ** 3)) + (0.03264 * w) + 0.3937


def trend_label(values):
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return "za mało danych"
    if vals[-1] > vals[0]:
        return "trend wzrostowy"
    if vals[-1] < vals[0]:
        return "trend spadkowy"
    return "bez wyraźnej zmiany"


def last_two_monthly_slope(values, dates):
    paired = [(d, v) for d, v in zip(dates, values) if d is not None and v is not None]
    if len(paired) < 2:
        return None
    d1, v1 = paired[-2]
    d2, v2 = paired[-1]
    delta_days = (d2 - d1).days
    if delta_days <= 0:
        return None
    return (v2 - v1) / delta_days * 30.0


def linear_projection_days_to_target(current_value, slope_per_month, target_value):
    if current_value is None or slope_per_month is None:
        return None
    if slope_per_month <= 0:
        return None
    if current_value >= target_value:
        return 0
    delta = target_value - current_value
    months = delta / slope_per_month
    if months < 0:
        return None
    return int(round(months * 30))


def average_phleb_interval_days(phleb_rows):
    valid_dates = [r["date"] for r in phleb_rows if r["date"] is not None]
    if len(valid_dates) < 2:
        return None
    valid_dates.sort()
    intervals = []
    for i in range(1, len(valid_dates)):
        intervals.append((valid_dates[i] - valid_dates[i - 1]).days)
    return sum(intervals) / len(intervals) if intervals else None


def phleb_frequency_text(avg_days):
    if avg_days is None:
        return "za mało danych"
    if avg_days <= 21:
        return f"bardzo częste upusty, średnio co ok. {avg_days:.0f} dni"
    if avg_days <= 42:
        return f"częste upusty, średnio co ok. {avg_days:.0f} dni"
    return f"średnio co ok. {avg_days:.0f} dni"


def persistent_above_target(values, n_needed=2):
    vals = [v for v in values if v is not None]
    if len(vals) < n_needed:
        return False
    return all(v > TARGET_HCT for v in vals[-n_needed:])


def parse_treatment_flags(text: str):
    t = (text or "").lower()
    flags = {
        "asa": any(x in t for x in ["asa", "acard", "aspir", "aspiryna", "polopiryna"]),
        "hydroxyurea": any(x in t for x in ["hydroksy", "hydroxy", "hydrea", "hu"]),
        "interferon": any(x in t for x in ["interfer", "ropeg", "peginterfer"]),
        "ruxolitinib": any(x in t for x in ["ruxo", "jakavi", "ruxolitinib"]),
        "anticoagulant": any(
            x in t for x in [
                "apiks", "apix", "eliquis", "rivar", "xarelto",
                "dabig", "pradaxa", "warf", "warfar", "acenok", "syncumar"
            ]
        ),
        "allopurinol": "allopur" in t,
        "statin": any(x in t for x in ["statyn", "atorwa", "rosuwa", "simwa", "atorvast", "rosuvast"]),
    }
    flags["cytoreduction"] = (
        flags["hydroxyurea"] or flags["interferon"] or flags["ruxolitinib"]
    )
    return flags


def build_drug_alerts(treatment_flags, current_plt):
    alerts = []

    if treatment_flags["asa"] and treatment_flags["anticoagulant"]:
        alerts.append("ASA + antykoagulant: zwiększone ryzyko krwawienia.")
    if treatment_flags["ruxolitinib"]:
        alerts.append("Ruxolitinib: sprawdź interakcje z silnymi inhibitorami CYP3A4.")
    if treatment_flags["anticoagulant"]:
        alerts.append("Antykoagulant: sprawdź interakcje z inhibitorami i induktorami CYP3A4/P-gp.")
    if current_plt is not None and current_plt >= 1000 and treatment_flags["asa"]:
        alerts.append("PLT ≥1000 i ASA: rozważ ocenę ryzyka nabytego vWD.")

    return alerts


def estimate_next_phleb_ml(
    current_hct,
    current_hb,
    current_wbc,
    current_plt,
    hct_slope_month,
    ebv_liters,
    bmi,
    age,
    treatment_flags,
    avg_phleb_interval,
):
    if current_hct is None or current_hct <= TARGET_HCT or ebv_liters is None:
        return 0

    ebv_ml = ebv_liters * 1000.0
    raw_ml = ebv_ml * ((current_hct - TARGET_HCT) / current_hct)

    factor = 1.0

    if current_hb is not None and current_hb >= 18:
        factor += 0.10
    elif current_hb is not None and current_hb < 14:
        factor -= 0.15

    if current_wbc is not None and current_wbc > 15:
        factor += 0.05

    if current_plt is not None and current_plt >= 1000:
        factor += 0.05

    if hct_slope_month is not None and hct_slope_month > 2:
        factor += 0.10
    elif hct_slope_month is not None and hct_slope_month < 0:
        factor -= 0.05

    if avg_phleb_interval is not None and avg_phleb_interval <= 21:
        factor -= 0.10
    elif avg_phleb_interval is not None and avg_phleb_interval <= 42:
        factor -= 0.05

    if bmi is not None and bmi < 20:
        factor -= 0.15
    elif bmi is not None and bmi >= 30:
        factor += 0.05

    if age >= 75:
        factor -= 0.15
    elif age >= 65:
        factor -= 0.05

    if treatment_flags["cytoreduction"]:
        factor -= 0.05

    estimated = raw_ml * factor
    estimated = max(100, estimated)
    estimated = round_to_25(estimated)
    return min(estimated, MAX_SINGLE_PHLEB_ML)


def assess_cytoreduction_need(age, hx_thrombosis, treatment_flags, cbc_rows, avg_phleb_interval, symptom_burden):
    reasons = []

    recent_hct = [r["hct"] for r in cbc_rows if r["hct"] is not None]
    recent_wbc = [r["wbc"] for r in cbc_rows if r["wbc"] is not None]
    recent_plt = [r["plt"] for r in cbc_rows if r["plt"] is not None]

    if age >= 60:
        reasons.append("wiek ≥60 lat")
    if hx_thrombosis:
        reasons.append("przebyta zakrzepica")
    if len(recent_hct) >= 2 and all(v > TARGET_HCT for v in recent_hct[-2:]):
        reasons.append("utrzymywanie Hct >45%")
    if len(recent_hct) >= 3 and all(v > TARGET_HCT for v in recent_hct[-3:]):
        reasons.append("utrwalony brak kontroli Hct")
    if avg_phleb_interval is not None and avg_phleb_interval <= 42:
        reasons.append("częsta potrzeba upustów")
    if len(recent_wbc) >= 2 and max(recent_wbc[-2:]) > 15:
        reasons.append("utrzymująca się leukocytoza >15")
    if len(recent_plt) >= 2 and max(recent_plt[-2:]) >= 1000:
        reasons.append("bardzo wysokie PLT")
    if symptom_burden >= 2:
        reasons.append("istotne obciążenie objawami")

    reasons = list(dict.fromkeys(reasons))

    if treatment_flags["cytoreduction"]:
        if reasons:
            conclusion = "obraz przemawia za oceną skuteczności lub optymalizacji cytoredukcji"
        else:
            conclusion = "brak silnych przesłanek do zmiany cytoredukcji"
    else:
        if reasons:
            conclusion = "obraz przemawia za rozważeniem cytoredukcji"
        else:
            conclusion = "brak wyraźnych przesłanek do cytoredukcji"

    return conclusion, reasons


# =========================
# HISTORIA I PLIKI
# =========================

def visit_to_record(data, summary, next_ml):
    current = data["cbc_rows"][-1]
    return {
        "patient_id": data["patient_id"],
        "visit_date": date.today().isoformat(),
        "age": data["age"],
        "sex": data["sex"],
        "weight": data["weight"],
        "height": data["height"],
        "diagnoses_text": data["diagnoses_text"],
        "history_text": data["history_text"],
        "treatment_text": data["treatment_text"],
        "hx_thrombosis": data["hx_thrombosis"],
        "hx_bleeding": data["hx_bleeding"],
        "hx_spleen": data["hx_spleen"],
        "hx_smoking": data["hx_smoking"],
        "symptom_itch": data["symptoms"]["świąd"],
        "symptom_headache": data["symptoms"]["ból_głowy"],
        "symptom_erythromelalgia": data["symptoms"]["erytromelalgia"],
        "symptom_dizziness": data["symptoms"]["zawroty"],
        "symptom_micro": data["symptoms"]["mikrokrążenie"],
        "symptom_nightsweats": data["symptoms"]["nocne_poty"],
        "symptom_weightloss": data["symptoms"]["spadek_masy"],
        "other_symptoms_text": data["other_symptoms_text"],
        "other_events_text": data["other_events_text"],
        "hct": current["hct"],
        "hb": current["hb"],
        "wbc": current["wbc"],
        "plt": current["plt"],
        "ldh": current["ldh"],
        "uric_acid": current["uric_acid"],
        "ferritin": current["ferritin"],
        "creatinine": current["creatinine"],
        "rdw": current["rdw"],
        "beta2m": current["beta2m"],
        "glucose": current["glucose"],
        "alt": current["alt"],
        "ast": current["ast"],
        "ggtp": current["ggtp"],
        "bilirubin": current["bilirubin"],
        "next_ml": next_ml,
        "summary": summary,
    }


def append_visit_to_csv(record):
    df = pd.DataFrame([record])
    if os.path.exists(DATA_FILE):
        old = pd.read_csv(DATA_FILE)
        all_df = pd.concat([old, df], ignore_index=True)
        all_df.to_csv(DATA_FILE, index=False)
    else:
        df.to_csv(DATA_FILE, index=False)


def load_patient_history(patient_id):
    if not patient_id or not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    df = pd.read_csv(DATA_FILE)
    if "patient_id" not in df.columns:
        return pd.DataFrame()
    df = df[df["patient_id"].astype(str) == str(patient_id)]
    if not df.empty and "visit_date" in df.columns:
        df = df.sort_values("visit_date")
    return df


def compare_with_previous_visit(history_df):
    if history_df.empty or len(history_df) < 2:
        return []
    last = history_df.iloc[-1]
    prev = history_df.iloc[-2]

    lines = []
    for col, label in [
        ("hct", "Hct"),
        ("hb", "Hb"),
        ("wbc", "WBC"),
        ("plt", "PLT"),
        ("ldh", "LDH"),
        ("uric_acid", "Kwas moczowy"),
        ("ferritin", "Ferrytyna"),
        ("glucose", "Glukoza"),
        ("alt", "ALT"),
        ("ast", "AST"),
        ("ggtp", "GGTP"),
        ("bilirubin", "Bilirubina"),
    ]:
        try:
            diff = float(last[col]) - float(prev[col])
            lines.append(f"{label}: {diff:+.2f}")
        except Exception:
            pass
    return lines


# =========================
# PDF
# =========================

def prepare_pdf_font():
    if os.path.exists(PDF_FONT_FILE):
        try:
            pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, PDF_FONT_FILE))
            return PDF_FONT_NAME
        except Exception:
            return "Helvetica"
    return "Helvetica"


def wrap_text(text, width, font_name="Helvetica", font_size=10):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            test = current + " " + word
            if stringWidth(test, font_name, font_size) <= width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def make_pdf_bytes(title, body):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    margin = 40
    y = page_height - 40

    font_name = prepare_pdf_font()

    pdf.setFont(font_name, 14)
    pdf.drawString(margin, y, title)
    y -= 24

    pdf.setFont(font_name, 10)
    max_width = page_width - 2 * margin
    lines = wrap_text(body, max_width, font_name, 10)

    for line in lines:
        if y < 50:
            pdf.showPage()
            pdf.setFont(font_name, 10)
            y = page_height - 40
        pdf.drawString(margin, y, line)
        y -= 14

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


# =========================
# ANALIZA
# =========================

def build_compare_four_entered(cbc_rows):
    rows = []
    last_four = sorted(cbc_rows, key=lambda x: x["date"])[-4:]

    for key, label in [
        ("hct", "Hct"),
        ("hb", "Hb"),
        ("wbc", "WBC"),
        ("plt", "PLT"),
        ("ldh", "LDH"),
        ("uric_acid", "Kwas moczowy"),
        ("ferritin", "Ferrytyna"),
        ("creatinine", "Kreatynina"),
        ("rdw", "RDW"),
        ("beta2m", "Beta-2-mikroglobulina"),
        ("glucose", "Glukoza"),
        ("alt", "ALT"),
        ("ast", "AST"),
        ("ggtp", "GGTP"),
        ("bilirubin", "Bilirubina"),
    ]:
        row = {"Parametr": label}
        for i, item in enumerate(last_four, start=1):
            row[f"{i} ({item['date'].isoformat()})"] = item.get(key)
        rows.append(row)

    return pd.DataFrame(rows)


def build_phleb_year_stats(phleb_rows):
    if not phleb_rows:
        return 0, 0, None, pd.DataFrame()

    current_year = date.today().year
    year_rows = [r for r in phleb_rows if r["date"] is not None and r["date"].year == current_year]

    count_year = len(year_rows)
    total_ml_year = sum(int(r["ml"]) for r in year_rows if r["ml"] is not None)

    avg_interval = average_phleb_interval_days(phleb_rows)

    table_rows = []
    valid_sorted = sorted([r for r in phleb_rows if r["date"] is not None], key=lambda x: x["date"])

    prev_date = None
    for row in valid_sorted:
        interval = None
        if prev_date is not None:
            interval = (row["date"] - prev_date).days
        table_rows.append({
            "Data upustu": row["date"].isoformat(),
            "Objętość (ml)": row["ml"],
            "Odstęp od poprzedniego (dni)": interval
        })
        prev_date = row["date"]

    return count_year, total_ml_year, avg_interval, pd.DataFrame(table_rows)


def build_analysis(data):
    bmi = bmi_calc(data["weight"], data["height"])
    treatment_flags = parse_treatment_flags(data["treatment_text"])
    cbc_rows = sorted(data["cbc_rows"], key=lambda x: x["date"])
    phleb_rows = sorted(data["phleb_rows"], key=lambda x: x["date"])

    current = cbc_rows[-1]
    current_hct = current["hct"]
    current_hb = current["hb"]
    current_wbc = current["wbc"]
    current_plt = current["plt"]
    current_ldh = current["ldh"]
    current_uric = current["uric_acid"]
    current_ferritin = current["ferritin"]

    dates = [r["date"] for r in cbc_rows]
    hct_vals = [r["hct"] for r in cbc_rows]
    hb_vals = [r["hb"] for r in cbc_rows]
    wbc_vals = [r["wbc"] for r in cbc_rows]
    plt_vals = [r["plt"] for r in cbc_rows]

    hct_trend = trend_label(hct_vals)
    hb_trend = trend_label(hb_vals)
    wbc_trend = trend_label(wbc_vals)
    plt_trend = trend_label(plt_vals)

    hct_slope = last_two_monthly_slope(hct_vals, dates)
    avg_interval = average_phleb_interval_days(phleb_rows)
    ebv_liters = estimate_blood_volume_liters(data["sex"], data["height"], data["weight"])

    next_ml = estimate_next_phleb_ml(
        current_hct=current_hct,
        current_hb=current_hb,
        current_wbc=current_wbc,
        current_plt=current_plt,
        hct_slope_month=hct_slope,
        ebv_liters=ebv_liters,
        bmi=bmi,
        age=data["age"],
        treatment_flags=treatment_flags,
        avg_phleb_interval=avg_interval,
    )

    days_to_recross = linear_projection_days_to_target(current_hct, hct_slope, TARGET_HCT)

    symptom_burden = sum([
        1 if data["symptoms"].get("świąd") else 0,
        1 if data["symptoms"].get("ból_głowy") else 0,
        1 if data["symptoms"].get("erytromelalgia") else 0,
        1 if data["symptoms"].get("zawroty") else 0,
        1 if data["symptoms"].get("mikrokrążenie") else 0,
        1 if data["symptoms"].get("nocne_poty") else 0,
        1 if data["symptoms"].get("spadek_masy") else 0,
    ])
    if data["other_symptoms_text"].strip():
        symptom_burden += 1

    cyto_conclusion, cyto_reasons = assess_cytoreduction_need(
        age=data["age"],
        hx_thrombosis=data["hx_thrombosis"],
        treatment_flags=treatment_flags,
        cbc_rows=cbc_rows,
        avg_phleb_interval=avg_interval,
        symptom_burden=symptom_burden,
    )

    drug_alerts = build_drug_alerts(treatment_flags, current_plt)

    flags = []
    reasons = []

    if data["hx_thrombosis"]:
        flags.append("Przebyta zakrzepica")
        reasons.append("obciążający wywiad zakrzepowy")
    if data["age"] >= 60:
        flags.append("Wiek ≥60 lat")
        reasons.append("wiek zwiększający ryzyko zakrzepowe")
    if persistent_above_target(hct_vals, 2):
        flags.append("Kolejne Hct >45%")
        reasons.append("brak pełnej kontroli Hct")
    if avg_interval is not None and avg_interval <= 42:
        flags.append("Częsta potrzeba upustów")
        reasons.append("nawracająca potrzeba flebotomii")
    if current_wbc is not None and current_wbc > 15:
        flags.append("WBC >15 x10^9/l")
        reasons.append("utrzymująca się leukocytoza")
    if current_plt is not None and current_plt >= 1000:
        flags.append("PLT ≥1000 x10^9/l")
        reasons.append("bardzo wysokie PLT")
    if symptom_burden >= 2:
        flags.append("Istotne obciążenie objawami")
        reasons.append("objawy zgłaszane przez pacjenta")
    if current_ferritin is not None and current_ferritin < 30:
        flags.append("Niska ferrytyna")
        reasons.append("możliwy niedobór żelaza")
    if current_uric is not None and current_uric > 7:
        flags.append("Podwyższony kwas moczowy")
        reasons.append("hiperurykemia")
    if data["hx_bleeding"]:
        flags.append("Wywiad krwawienia")
        reasons.append("wywiad krwawienia")

    recommendations = []
    if current_hct is not None and current_hct > TARGET_HCT:
        recommendations.append("Rozważyć intensyfikację kontroli Hct do celu <45%.")
    if next_ml > 0:
        recommendations.append(f"Orientacyjny pojedynczy kolejny upust do rozważenia: {next_ml} ml.")
    if current_ferritin is not None and current_ferritin < 30:
        recommendations.append("Ocenić niedobór żelaza w kontekście częstych upustów.")
    if current_uric is not None and current_uric > 7:
        recommendations.append("Rozważyć kontrolę hiperurykemii.")
    if current_ldh is not None and current_ldh > 250:
        recommendations.append("Podwyższone LDH ocenić w kontekście aktywności choroby.")
    if data["hx_spleen"]:
        recommendations.append("Uwzględnić ocenę śledziony i obciążenia objawami.")
    if cyto_reasons:
        recommendations.append(cyto_conclusion)

    phleb_count_year, phleb_ml_year, phleb_avg_interval, phleb_table = build_phleb_year_stats(phleb_rows)
    compare_four = build_compare_four_entered(cbc_rows)

    diagnosis_lines = numbered_lines(data["diagnoses_text"])
    history_lines = text_lines(data["history_text"])
    treatment_lines = numbered_lines(data["treatment_text"])

    summary_lines = []
    summary_lines.append("PODSUMOWANIE KLINICZNE")
    summary_lines.append("=" * 72)
    summary_lines.append("")
    summary_lines.append("Dane podstawowe")
    summary_lines.append(f"ID pacjenta: {data['patient_id'] or 'brak'}")
    summary_lines.append(f"Wiek: {data['age']}")
    summary_lines.append(f"Płeć: {data['sex']}")
    summary_lines.append(
        f"Masa / wzrost: {data['weight']} kg / {data['height']} cm | "
        f"BMI: {bmi:.1f} ({bmi_class(bmi)})" if bmi is not None else "BMI: brak danych"
    )
    summary_lines.append("")

    summary_lines.append("Rozpoznania")
    if diagnosis_lines:
        for line in diagnosis_lines:
            summary_lines.append(line)
    else:
        summary_lines.append("brak danych")
    summary_lines.append("")

    summary_lines.append("Historia choroby")
    if history_lines:
        for line in history_lines:
            summary_lines.append(f"• {line}")
    else:
        summary_lines.append("brak danych")
    summary_lines.append("")

    summary_lines.append("Aktualne leczenie")
    if treatment_lines:
        for line in treatment_lines:
            summary_lines.append(line)
    else:
        summary_lines.append("brak danych")
    summary_lines.append("")

    summary_lines.append("Wywiad / zdarzenia")
    summary_lines.append(
        f"Zakrzepica: {'tak' if data['hx_thrombosis'] else 'nie'} | "
        f"Krwawienie: {'tak' if data['hx_bleeding'] else 'nie'} | "
        f"Śledziona / splenomegalia: {'tak' if data['hx_spleen'] else 'nie'} | "
        f"Palenie: {'tak' if data['hx_smoking'] else 'nie'}"
    )
    if data["other_events_text"].strip():
        summary_lines.append(f"Inne zdarzenia: {data['other_events_text'].strip()}")
    summary_lines.append("")

    summary_lines.append("Objawy")
    symptom_names = [k.replace("_", " ") for k, v in data["symptoms"].items() if v]
    summary_lines.append(", ".join(symptom_names) if symptom_names else "brak zaznaczonych objawów")
    if data["other_symptoms_text"].strip():
        summary_lines.append(f"Inne objawy: {data['other_symptoms_text'].strip()}")
    summary_lines.append("")

    summary_lines.append("Ocena aktualna")
    summary_lines.append(
        f"Hct {current_hct}, Hb {current_hb}, WBC {current_wbc}, PLT {current_plt}, "
        f"LDH {current_ldh}, kwas moczowy {current_uric}, ferrytyna {current_ferritin}"
    )
    summary_lines.append("")
    summary_lines.append("Komentarz")
    if reasons:
        summary_lines.append("Obraz kliniczny zwraca uwagę na: " + ", ".join(reasons) + ".")
    else:
        summary_lines.append("Brak istotnych dodatkowych czynników alarmowych w bieżącym modelu.")
    summary_lines.append(f"Trendy: Hct {hct_trend}, Hb {hb_trend}, WBC {wbc_trend}, PLT {plt_trend}.")
    if hct_slope is not None:
        summary_lines.append(f"Szacowane tempo zmiany Hct: {hct_slope:.2f}% / miesiąc.")
    if days_to_recross is not None:
        if current_hct < TARGET_HCT and days_to_recross > 0:
            est_date = date.today() + timedelta(days=days_to_recross)
            summary_lines.append(
                f"Przy obecnym tempie zmian Hct może ponownie przekroczyć 45% za około {days_to_recross} dni, około {est_date.isoformat()}."
            )
        elif current_hct >= TARGET_HCT:
            summary_lines.append("Hct aktualnie pozostaje co najmniej na poziomie 45%.")
    summary_lines.append("")

    summary_lines.append("Upusty")
    summary_lines.append(phleb_frequency_text(avg_interval))
    summary_lines.append(f"Liczba upustów w bieżącym roku: {phleb_count_year}")
    summary_lines.append(f"Łączna objętość upustów w bieżącym roku: {phleb_ml_year} ml")
    if phleb_avg_interval is not None:
        summary_lines.append(f"Średni odstęp między upustami: {phleb_avg_interval:.1f} dni")
    summary_lines.append("")

    summary_lines.append("Czerwone flagi")
    if flags:
        for item in flags:
            summary_lines.append(f"• {item}")
    else:
        summary_lines.append("brak istotnych flag")
    summary_lines.append("")

    summary_lines.append("Ostrzeżenia lekowe")
    if drug_alerts:
        for item in drug_alerts:
            summary_lines.append(f"• {item}")
    else:
        summary_lines.append("brak istotnych ostrzeżeń wykrytych lokalnie")
    summary_lines.append("")

    summary_lines.append("Wnioski i zalecenia robocze")
    if recommendations:
        for item in recommendations:
            summary_lines.append(f"• {item}")
    else:
        summary_lines.append("• utrzymać bieżący nadzór")
    summary_lines.append("")
    summary_lines.append("Ocena cytoredukcji")
    summary_lines.append(cyto_conclusion)

    summary = "\n".join(summary_lines)

    note_lines = []
    note_lines.append("NOTATKA DO DOKUMENTACJI")
    note_lines.append("")
    note_lines.append(f"Pacjent ID: {data['patient_id'] or 'brak'}")
    note_lines.append(f"Wiek: {data['age']} lat, płeć: {data['sex']}")
    note_lines.append("")
    note_lines.append("Rozpoznania:")
    if diagnosis_lines:
        note_lines.extend(diagnosis_lines)
    else:
        note_lines.append("brak danych")
    note_lines.append("")
    note_lines.append("Historia choroby:")
    if history_lines:
        for line in history_lines:
            note_lines.append(f"• {line}")
    else:
        note_lines.append("brak danych")
    note_lines.append("")
    note_lines.append("Aktualne leczenie:")
    if treatment_lines:
        note_lines.extend(treatment_lines)
    else:
        note_lines.append("brak danych")
    note_lines.append("")
    note_lines.append(
        f"Wywiad / zdarzenia: zakrzepica {'tak' if data['hx_thrombosis'] else 'nie'}, "
        f"krwawienie {'tak' if data['hx_bleeding'] else 'nie'}, "
        f"śledziona {'tak' if data['hx_spleen'] else 'nie'}, "
        f"palenie {'tak' if data['hx_smoking'] else 'nie'}."
    )
    if data["other_events_text"].strip():
        note_lines.append(f"Inne zdarzenia: {data['other_events_text'].strip()}")
    note_lines.append("")
    symptom_names_text = ", ".join([k.replace("_", " ") for k, v in data["symptoms"].items() if v])
    note_lines.append(f"Objawy: {symptom_names_text if symptom_names_text else 'brak zaznaczonych objawów'}.")
    if data["other_symptoms_text"].strip():
        note_lines.append(f"Inne objawy: {data['other_symptoms_text'].strip()}")
    note_lines.append("")
    note_lines.append(
        f"Aktualne badania: Hct {current_hct}, Hb {current_hb}, WBC {current_wbc}, "
        f"PLT {current_plt}, LDH {current_ldh}, kwas moczowy {current_uric}, ferrytyna {current_ferritin}, "
        f"glukoza {current['glucose']}, ALT {current['alt']}, AST {current['ast']}, GGTP {current['ggtp']}, bilirubina {current['bilirubin']}."
    )
    note_lines.append(f"Upusty w bieżącym roku: {phleb_count_year}, łącznie {phleb_ml_year} ml.")
    note_lines.append(f"Orientacyjny kolejny upust do rozważenia: {next_ml} ml.")
    note_lines.append(f"Ocena cytoredukcji: {cyto_conclusion}.")
    if flags:
        note_lines.append(f"Flagi: {', '.join(flags)}.")
    if drug_alerts:
        note_lines.append(f"Ostrzeżenia lekowe: {'; '.join(drug_alerts)}.")

    note = "\n".join(note_lines)
    current_status = "poza celem" if current_hct is not None and current_hct > TARGET_HCT else "w celu"

    return {
        "summary": summary,
        "note": note,
        "flags": flags,
        "drug_alerts": drug_alerts,
        "next_ml": next_ml,
        "current_hct": current_hct,
        "current_status": current_status,
        "compare_four": compare_four,
        "phleb_count_year": phleb_count_year,
        "phleb_ml_year": phleb_ml_year,
        "phleb_avg_interval": phleb_avg_interval,
        "phleb_table": phleb_table,
    }


# =========================
# START
# =========================

init_state()

st.title(APP_TITLE)
st.caption("Analiza badań, historia choroby i wsparcie decyzji klinicznych")

st.text_input("Pacjent / ID", key="patient_id")
st.button("Wyczyść cały formularz", on_click=clear_form, use_container_width=True)

history_df = load_patient_history(st.session_state["patient_id"])
if not history_df.empty:
    st.success(f"Zapisane wizyty tego pacjenta: {len(history_df)}")
else:
    st.info("Brak zapisanych wizyt dla tego ID")

st.markdown('<div class="ak-section">Dane podstawowe</div>', unsafe_allow_html=True)
st.number_input("Wiek", min_value=0, max_value=120, key="age")
st.selectbox("Płeć", ["M", "K", "inna / niepodano"], key="sex")
st.number_input("Masa ciała (kg)", min_value=20.0, max_value=300.0, key="weight")
st.number_input("Wzrost (cm)", min_value=100.0, max_value=250.0, key="height")

bmi = bmi_calc(st.session_state["weight"], st.session_state["height"])
st.info(f"BMI: {bmi:.1f} ({bmi_class(bmi)})" if bmi is not None else "BMI: brak danych")

st.markdown('<div class="ak-section">Rozpoznania</div>', unsafe_allow_html=True)
st.text_area(
    "Rozpoznania",
    key="diagnoses_text",
    height=110,
    label_visibility="collapsed",
    placeholder="Każde rozpoznanie wpisz w nowej linii"
)

st.markdown('<div class="ak-section">Historia choroby</div>', unsafe_allow_html=True)
st.text_area(
    "Historia choroby",
    key="history_text",
    height=130,
    label_visibility="collapsed",
    placeholder="Najważniejsze informacje o przebiegu choroby"
)

st.markdown('<div class="ak-section">Aktualne leczenie</div>', unsafe_allow_html=True)
st.text_area(
    "Aktualne leczenie",
    key="treatment_text",
    height=120,
    label_visibility="collapsed",
    placeholder="Każdy lek i dawkowanie wpisz w nowej linii"
)

st.markdown("Sprawdzenie interakcji lekowych:")
st.markdown("[Medscape Interaction Checker](https://reference.medscape.com/drug-interactionchecker)")
st.markdown("[Drugs.com Interaction Checker](https://www.drugs.com/drug_interactions.html)")

st.markdown('<div class="ak-section">Wywiad / zdarzenia</div>', unsafe_allow_html=True)
st.checkbox("Przebyta zakrzepica", key="hx_thrombosis")
st.checkbox("Przebyte krwawienie", key="hx_bleeding")
st.checkbox("Splenomegalia / objawy śledzionowe", key="hx_spleen")
st.checkbox("Palenie", key="hx_smoking")
st.text_area(
    "Inne zdarzenia",
    key="other_events_text",
    height=80,
    placeholder="Wpisz inne ważne zdarzenia"
)

st.markdown('<div class="ak-section">Objawy</div>', unsafe_allow_html=True)
st.checkbox("Świąd", key="symptom_itch")
st.checkbox("Ból głowy", key="symptom_headache")
st.checkbox("Erytromelalgia", key="symptom_erythromelalgia")
st.checkbox("Zawroty głowy", key="symptom_dizziness")
st.checkbox("Objawy mikrokrążeniowe", key="symptom_micro")
st.checkbox("Nocne poty", key="symptom_nightsweats")
st.checkbox("Spadek masy ciała", key="symptom_weightloss")
st.text_area(
    "Inne objawy",
    key="other_symptoms_text",
    height=80,
    placeholder="Wpisz inne objawy"
)

st.markdown('<div class="ak-section">Ostatnie badania</div>', unsafe_allow_html=True)
r1, r2 = st.columns(2)
with r1:
    if st.button("➕ Dodaj badanie"):
        if st.session_state["labs_n"] < 10:
            st.session_state["labs_n"] += 1
            st.rerun()
with r2:
    if st.button("➖ Usuń badanie"):
        if st.session_state["labs_n"] > 1:
            st.session_state["labs_n"] -= 1
            st.rerun()

cbc_rows = []
for i in range(st.session_state["labs_n"]):
    st.markdown(f"**Badanie {i+1}**")
    st.date_input("Data", key=f"cbc_date_{i}")
    st.number_input("Hct", min_value=0.0, max_value=100.0, key=f"cbc_hct_{i}")
    st.number_input("Hb", min_value=0.0, max_value=30.0, key=f"cbc_hb_{i}")
    st.number_input("WBC", min_value=0.0, max_value=300.0, key=f"cbc_wbc_{i}")
    st.number_input("PLT", min_value=0.0, max_value=5000.0, key=f"cbc_plt_{i}")
    st.number_input("LDH", min_value=0.0, max_value=5000.0, key=f"cbc_ldh_{i}")
    st.number_input("Kwas moczowy", min_value=0.0, max_value=50.0, key=f"cbc_uric_{i}")
    st.number_input("Ferrytyna", min_value=0.0, max_value=5000.0, key=f"cbc_ferr_{i}")
    st.number_input("Kreatynina", min_value=0.0, max_value=20.0, key=f"cbc_creat_{i}")
    st.number_input("RDW", min_value=0.0, max_value=100.0, key=f"cbc_rdw_{i}")
    st.number_input("Beta-2-mikroglobulina", min_value=0.0, max_value=50.0, key=f"cbc_b2m_{i}")
    st.number_input("Glukoza", min_value=0.0, max_value=1000.0, key=f"cbc_glu_{i}")
    st.number_input("ALT", min_value=0.0, max_value=5000.0, key=f"cbc_alt_{i}")
    st.number_input("AST", min_value=0.0, max_value=5000.0, key=f"cbc_ast_{i}")
    st.number_input("GGTP", min_value=0.0, max_value=5000.0, key=f"cbc_ggtp_{i}")
    st.number_input("Bilirubina", min_value=0.0, max_value=50.0, key=f"cbc_bili_{i}")

    cbc_rows.append({
        "date": st.session_state[f"cbc_date_{i}"],
        "hct": safe_float(st.session_state[f"cbc_hct_{i}"]),
        "hb": safe_float(st.session_state[f"cbc_hb_{i}"]),
        "wbc": safe_float(st.session_state[f"cbc_wbc_{i}"]),
        "plt": safe_float(st.session_state[f"cbc_plt_{i}"]),
        "ldh": safe_float(st.session_state[f"cbc_ldh_{i}"]),
        "uric_acid": safe_float(st.session_state[f"cbc_uric_{i}"]),
        "ferritin": safe_float(st.session_state[f"cbc_ferr_{i}"]),
        "creatinine": safe_float(st.session_state[f"cbc_creat_{i}"]),
        "rdw": safe_float(st.session_state[f"cbc_rdw_{i}"]),
        "beta2m": safe_float(st.session_state[f"cbc_b2m_{i}"]),
        "glucose": safe_float(st.session_state[f"cbc_glu_{i}"]),
        "alt": safe_float(st.session_state[f"cbc_alt_{i}"]),
        "ast": safe_float(st.session_state[f"cbc_ast_{i}"]),
        "ggtp": safe_float(st.session_state[f"cbc_ggtp_{i}"]),
        "bilirubin": safe_float(st.session_state[f"cbc_bili_{i}"]),
    })
    st.markdown("---")

st.markdown('<div class="ak-section">Upusty</div>', unsafe_allow_html=True)
u1, u2 = st.columns(2)
with u1:
    if st.button("➕ Dodaj upust"):
        if st.session_state["phleb_n"] < 12:
            st.session_state["phleb_n"] += 1
            st.rerun()
with u2:
    if st.button("➖ Usuń upust"):
        if st.session_state["phleb_n"] > 1:
            st.session_state["phleb_n"] -= 1
            st.rerun()

phleb_rows = []
for i in range(st.session_state["phleb_n"]):
    st.markdown(f"**Upust {i+1}**")
    st.date_input("Data upustu", key=f"ph_date_{i}")
    st.number_input("Objętość ml", min_value=0, max_value=1000, step=25, key=f"ph_ml_{i}")
    phleb_rows.append({
        "date": st.session_state[f"ph_date_{i}"],
        "ml": st.session_state[f"ph_ml_{i}"],
    })
    st.markdown("---")

if st.button("Analizuj wizytę", type="primary", use_container_width=True):
    data = {
        "patient_id": st.session_state["patient_id"],
        "age": int(st.session_state["age"]),
        "sex": st.session_state["sex"],
        "weight": float(st.session_state["weight"]),
        "height": float(st.session_state["height"]),
        "diagnoses_text": st.session_state["diagnoses_text"],
        "history_text": st.session_state["history_text"],
        "treatment_text": st.session_state["treatment_text"],
        "hx_thrombosis": st.session_state["hx_thrombosis"],
        "hx_bleeding": st.session_state["hx_bleeding"],
        "hx_spleen": st.session_state["hx_spleen"],
        "hx_smoking": st.session_state["hx_smoking"],
        "other_events_text": st.session_state["other_events_text"],
        "other_symptoms_text": st.session_state["other_symptoms_text"],
        "cbc_rows": cbc_rows,
        "phleb_rows": phleb_rows,
        "symptoms": {
            "świąd": st.session_state["symptom_itch"],
            "ból_głowy": st.session_state["symptom_headache"],
            "erytromelalgia": st.session_state["symptom_erythromelalgia"],
            "zawroty": st.session_state["symptom_dizziness"],
            "mikrokrążenie": st.session_state["symptom_micro"],
            "nocne_poty": st.session_state["symptom_nightsweats"],
            "spadek_masy": st.session_state["symptom_weightloss"],
        },
    }

    result = build_analysis(data)

    st.session_state["analysis_ready"] = True
    st.session_state["last_summary"] = result["summary"]
    st.session_state["last_note"] = result["note"]
    st.session_state["last_flags"] = result["flags"]
    st.session_state["last_drug_alerts"] = result["drug_alerts"]
    st.session_state["last_next_ml"] = result["next_ml"]
    st.session_state["last_current_hct"] = result["current_hct"]
    st.session_state["last_current_status"] = result["current_status"]
    st.session_state["last_compare_rows"] = result["compare_four"]
    st.session_state["last_phleb_count_year"] = result["phleb_count_year"]
    st.session_state["last_phleb_ml_year"] = result["phleb_ml_year"]
    st.session_state["last_phleb_avg_interval"] = result["phleb_avg_interval"]
    st.session_state["last_phleb_table"] = result["phleb_table"]
    st.session_state["last_data"] = data

if st.session_state.get("analysis_ready", False):
    st.markdown('<div class="ak-section">Analiza</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    with c1:
        st.markdown(
            f'<div class="ak-card"><div class="ak-kpi-title">Hct aktualnie</div><div class="ak-kpi-value">{st.session_state["last_current_hct"]:.1f}%</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="ak-card"><div class="ak-kpi-title">Kolejny upust do rozważenia</div><div class="ak-kpi-value">{st.session_state["last_next_ml"]} ml</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="ak-card"><div class="ak-kpi-title">Status kontroli</div><div class="ak-kpi-value">{st.session_state["last_current_status"]}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="ak-card"><div class="ak-kpi-title">Upusty w roku</div><div class="ak-kpi-value">{st.session_state["last_phleb_count_year"]}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="ak-card"><div class="ak-kpi-title">Łączna objętość upustów w roku</div><div class="ak-kpi-value">{st.session_state["last_phleb_ml_year"]} ml</div></div>',
        unsafe_allow_html=True,
    )

    if st.session_state["last_phleb_avg_interval"] is not None:
        st.markdown(
            f'<div class="ak-card"><div class="ak-kpi-title">Średni odstęp między upustami</div><div class="ak-kpi-value">{st.session_state["last_phleb_avg_interval"]:.1f} dni</div></div>',
            unsafe_allow_html=True,
        )

    if st.session_state["last_flags"]:
        st.markdown("### Czerwone flagi")
        for f in st.session_state["last_flags"]:
            st.error(f)

    st.markdown("### Interakcje lekowe i ostrzeżenia")
    if st.session_state["last_drug_alerts"]:
        for a in st.session_state["last_drug_alerts"]:
            st.warning(a)
    else:
        st.info("Brak istotnych ostrzeżeń wykrytych lokalnie.")

    st.markdown("[Medscape Interaction Checker](https://reference.medscape.com/drug-interactionchecker)")
    st.markdown("[Drugs.com Interaction Checker](https://www.drugs.com/drug_interactions.html)")

    st.markdown("### Porównanie 4 ostatnich badań")
    compare_df = st.session_state["last_compare_rows"]
    if isinstance(compare_df, pd.DataFrame) and not compare_df.empty:
        st.dataframe(compare_df, use_container_width=True)

    st.markdown("### Tabela upustów")
    phleb_table = st.session_state["last_phleb_table"]
    if isinstance(phleb_table, pd.DataFrame) and not phleb_table.empty:
        st.dataframe(phleb_table, use_container_width=True)

    st.markdown("### Podsumowanie wizyty")
    st.text_area(
        "summary_box",
        value=st.session_state["last_summary"],
        height=520,
        label_visibility="collapsed",
    )

    st.markdown("### Notatka do wydruku / dokumentacji")
    st.text_area(
        "note_box",
        value=st.session_state["last_note"],
        height=340,
        label_visibility="collapsed",
    )

    if st.button("Zapisz wizytę do historii", use_container_width=True):
        if st.session_state["last_data"]["patient_id"]:
            record = visit_to_record(
                st.session_state["last_data"],
                st.session_state["last_summary"],
                st.session_state["last_next_ml"],
            )
            append_visit_to_csv(record)
            st.success("Wizyta zapisana.")
        else:
            st.error("Najpierw wpisz ID pacjenta.")

    pdf_bytes = make_pdf_bytes("Asystent kliniczny - podsumowanie", st.session_state["last_summary"])
    st.download_button(
        "Pobierz PDF",
        data=pdf_bytes,
        file_name="podsumowanie_czerwienica_prawdziwa.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.download_button(
        "Pobierz TXT",
        data=st.session_state["last_summary"].encode("utf-8"),
        file_name="podsumowanie_czerwienica_prawdziwa.txt",
        mime="text/plain",
        use_container_width=True,
    )

if st.session_state["patient_id"]:
    st.markdown("---")
    st.markdown('<div class="ak-section">Historia zapisanych wizyt tego pacjenta</div>', unsafe_allow_html=True)

    if history_df.empty:
        st.info("Brak zapisanych wizyt dla tego ID.")
    else:
        st.dataframe(history_df.tail(10), use_container_width=True)

        st.markdown("### Porównanie z poprzednią zapisaną wizytą")
        compare_prev = compare_with_previous_visit(history_df)
        if compare_prev:
            for line in compare_prev:
                st.write(line)
        else:
            st.write("Za mało zapisanych wizyt do porównania.")

        if "visit_date" in history_df.columns:
            plot_df = history_df.copy()
            plot_df["visit_date"] = pd.to_datetime(plot_df["visit_date"])
            plot_df = plot_df.set_index("visit_date")
            cols_to_plot = [
                c for c in [
                    "hct", "hb", "wbc", "plt", "ldh", "uric_acid",
                    "ferritin", "glucose", "alt", "ast", "ggtp", "bilirubin"
                ] if c in plot_df.columns
            ]
            if cols_to_plot:
                st.markdown("### Trendy zapisanych wizyt")
                st.line_chart(plot_df[cols_to_plot])
