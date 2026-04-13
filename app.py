import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import math

TARGET_HCT = 45.0
MAX_SINGLE_PHLEB_ML = 300

st.set_page_config(page_title="PV Assistant PRO", layout="wide")


def safe_float(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


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
    """
    Wzór Nadlera.
    """
    if height_cm is None or weight_kg is None:
        return None

    h = height_cm / 100.0
    w = weight_kg

    if sex == "M":
        return (0.3669 * (h ** 3)) + (0.03219 * w) + 0.6041
    if sex == "K":
        return (0.3561 * (h ** 3)) + (0.03308 * w) + 0.1833
    return (0.3615 * (h ** 3)) + (0.03264 * w) + 0.3937


def parse_treatment_flags(text: str):
    t = (text or "").lower()
    flags = {
        "asa": any(x in t for x in ["asa", "acard", "aspir", "aspiryna"]),
        "hydroxyurea": any(x in t for x in ["hydroksy", "hydroxy", "hu"]),
        "interferon": any(x in t for x in ["interfer", "ropeg"]),
        "ruxolitinib": any(x in t for x in ["ruxo", "jakavi"]),
        "anticoagulant": any(
            x in t for x in ["apiks", "apix", "eliquis", "rivar", "xarelto", "dabig", "warf", "acenok"]
        ),
    }
    flags["cytoreduction"] = (
        flags["hydroxyurea"] or flags["interferon"] or flags["ruxolitinib"]
    )
    return flags


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
    """
    Dodatni slope_per_month = narastanie parametru.
    Zwraca dni do przekroczenia target_value, jeśli ma to sens.
    """
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
    """
    Model roboczy:
    objętość do osiągnięcia Hct 45% liczona z EBV:
    V = EBV * (Hct_i - Hct_target) / Hct_i
    potem korekty kliniczne i limit 300 ml.
    """
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


def assess_cytoreduction_need(age, thrombosis_history, treatment_flags, cbc_rows, avg_phleb_interval, symptom_burden):
    reasons = []

    recent_hct = [r["hct"] for r in cbc_rows if r["hct"] is not None]
    recent_wbc = [r["wbc"] for r in cbc_rows if r["wbc"] is not None]
    recent_plt = [r["plt"] for r in cbc_rows if r["plt"] is not None]

    if age >= 60:
        reasons.append("wiek ≥60 lat")
    if thrombosis_history == "tak":
        reasons.append("przebyta zakrzepica")

    if len(recent_hct) >= 2 and all(v > TARGET_HCT for v in recent_hct[-2:]):
        reasons.append("utrzymywanie Hct >45% w kolejnych badaniach")

    if len(recent_hct) >= 3 and all(v > TARGET_HCT for v in recent_hct[-3:]):
        reasons.append("utrwalony brak kontroli Hct w serii badań")

    if avg_phleb_interval is not None and avg_phleb_interval <= 42:
        reasons.append("częsta potrzeba upustów")

    if len(recent_wbc) >= 2 and max(recent_wbc[-2:]) > 15:
        reasons.append("utrzymująca się leukocytoza >15 x10^9/l")

    if len(recent_plt) >= 2 and max(recent_plt[-2:]) >= 1000:
        reasons.append("bardzo wysokie PLT")

    if symptom_burden >= 2:
        reasons.append("istotne obciążenie objawami")

    reasons = list(dict.fromkeys(reasons))

    if treatment_flags["cytoreduction"]:
        if reasons:
            conclusion = "obraz przemawia za oceną skuteczności lub optymalizacji leczenia cytoredukcyjnego"
        else:
            conclusion = "brak silnych przesłanek do zmiany cytoredukcji w tym uproszczonym modelu"
    else:
        if reasons:
            conclusion = "obraz przemawia za rozważeniem leczenia cytoredukcyjnego"
        else:
            conclusion = "brak wyraźnych przesłanek do cytoredukcji w tym uproszczonym modelu"

    return conclusion, reasons


def build_summary(data):
    bmi = bmi_calc(data["weight"], data["height"])
    treatment_flags = parse_treatment_flags(data["treatment"])
    cbc_rows = data["cbc_rows"]
    phleb_rows = data["phleb_rows"]

    current = cbc_rows[-1]
    current_hct = current["hct"]
    current_hb = current["hb"]
    current_wbc = current["wbc"]
    current_plt = current["plt"]

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
    hb_slope = last_two_monthly_slope(hb_vals, dates)

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
    ])

    cyto_conclusion, cyto_reasons = assess_cytoreduction_need(
        age=data["age"],
        thrombosis_history=data["thrombosis_history"],
        treatment_flags=treatment_flags,
        cbc_rows=cbc_rows,
        avg_phleb_interval=avg_interval,
        symptom_burden=symptom_burden,
    )

    recognized = []
    if treatment_flags["asa"]:
        recognized.append("ASA")
    if treatment_flags["hydroxyurea"]:
        recognized.append("hydroksymocznik")
    if treatment_flags["interferon"]:
        recognized.append("interferon")
    if treatment_flags["ruxolitinib"]:
        recognized.append("ruxolitinib")
    if treatment_flags["anticoagulant"]:
        recognized.append("antykoagulant")

    flags = []
    if data["thrombosis_history"] == "tak":
        flags.append("przebyta zakrzepica")
    if data["age"] >= 60:
        flags.append("wiek ≥60 lat")
    if persistent_above_target(hct_vals, 2):
        flags.append("kolejne Hct >45%")
    if avg_interval is not None and avg_interval <= 42:
        flags.append("częsta potrzeba upustów")
    if current_wbc is not None and current_wbc > 15:
        flags.append("WBC >15 x10^9/l")
    if current_plt is not None and current_plt >= 1000:
        flags.append("PLT ≥1000 x10^9/l")
    if symptom_burden >= 2:
        flags.append("istotne obciążenie objawami")

    lines = []
    lines.append("PODSUMOWANIE LEKARSKIE")
    lines.append("=" * 72)
    lines.append("")
    lines.append("Dane podstawowe")
    lines.append(f"Pacjent / ID: {data['patient_id'] or 'brak danych'}")
    lines.append(f"Wiek: {data['age']}")
    lines.append(f"Płeć: {data['sex']}")
    lines.append(
        f"Masa / wzrost: "
        f"{data['weight'] if data['weight'] is not None else 'brak'} kg / "
        f"{data['height'] if data['height'] is not None else 'brak'} cm"
    )
    lines.append(
        f"BMI: {f'{bmi:.1f}' if bmi is not None else 'brak danych'} "
        f"({bmi_class(bmi)})"
    )
    lines.append(
        f"Szacowana objętość krwi: "
        f"{f'{ebv_liters:.2f} l' if ebv_liters is not None else 'brak danych'}"
    )
    lines.append("")
    lines.append("Ryzyko klasyczne")
    if data["thrombosis_history"] == "tak" or data["age"] >= 60:
        lines.append("Pacjent spełnia klasyczne kryteria wysokiego ryzyka zakrzepowego.")
    else:
        lines.append("Pacjent nie spełnia klasycznych kryteriów wysokiego ryzyka zakrzepowego.")
    lines.append(f"Zakrzepica w wywiadzie: {data['thrombosis_history']}")
    lines.append("")
    lines.append("Leczenie")
    lines.append(data["treatment"] if data["treatment"] else "brak danych")
    if recognized:
        lines.append("Rozpoznane leczenie: " + ", ".join(recognized))
    lines.append("")
    lines.append("Objawy")
    symptom_labels = [k.replace("_", " ") for k, v in data["symptoms"].items() if v]
    lines.append(", ".join(symptom_labels) if symptom_labels else "brak zaznaczonych objawów")
    lines.append(f"Obciążenie objawami w uproszczonym modelu: {symptom_burden}")
    lines.append("")
    lines.append("Kolejne badania")
    for i, row in enumerate(cbc_rows, start=1):
        lines.append(
            f"{i}) {row['date'].isoformat()} | "
            f"Hct: {row['hct'] if row['hct'] is not None else 'brak'} | "
            f"Hb: {row['hb'] if row['hb'] is not None else 'brak'} | "
            f"WBC: {row['wbc'] if row['wbc'] is not None else 'brak'} | "
            f"PLT: {row['plt'] if row['plt'] is not None else 'brak'}"
        )
    lines.append("")
    lines.append("Ocena trendów")
    lines.append(f"Hct: {hct_trend}")
    lines.append(f"Hb: {hb_trend}")
    lines.append(f"WBC: {wbc_trend}")
    lines.append(f"PLT: {plt_trend}")
    lines.append(
        f"Tempo zmiany Hct z 2 ostatnich badań: "
        f"{f'{hct_slope:.2f} % / mies.' if hct_slope is not None else 'za mało danych'}"
    )
    lines.append(
        f"Tempo zmiany Hb z 2 ostatnich badań: "
        f"{f'{hb_slope:.2f} g/dl / mies.' if hb_slope is not None else 'za mało danych'}"
    )
    lines.append("")
    lines.append("Daty upustów")
    if phleb_rows:
        for i, row in enumerate(phleb_rows, start=1):
            lines.append(
                f"{i}) {row['date'].isoformat()} | "
                f"objętość: {row['ml'] if row['ml'] is not None else 'brak'} ml"
            )
        lines.append(f"Ocena częstości upustów: {phleb_frequency_text(avg_interval)}")
    else:
        lines.append("Brak danych o upustach.")
    lines.append("")
    lines.append("WNIOSKI")
    lines.append("-" * 72)
    if current_hct is not None and current_hct <= TARGET_HCT:
        lines.append(f"Aktualny Hct {current_hct:.1f}% jest w celu terapeutycznym <45%.")
    elif current_hct is not None:
        lines.append(f"Aktualny Hct {current_hct:.1f}% pozostaje powyżej celu terapeutycznego <45%.")

    if current_hb is not None:
        lines.append(f"Aktualny Hb: {current_hb:.1f} g/dl.")
    if current_wbc is not None:
        lines.append(f"Aktualny WBC: {current_wbc:.1f} x10^9/l.")
    if current_plt is not None:
        lines.append(f"Aktualny PLT: {current_plt:.0f} x10^9/l.")
    lines.append("")

    if next_ml > 0:
        lines.append(
            f"Orientacyjna objętość jednego kolejnego upustu do rozważenia: {next_ml} ml "
            f"(maks. {MAX_SINGLE_PHLEB_ML} ml w tym modelu)."
        )
    else:
        lines.append("Na podstawie aktualnego Hct orientacyjny kolejny upust do rozważenia: 0 ml.")

    if days_to_recross is not None:
        if current_hct < TARGET_HCT and days_to_recross > 0:
            est_date = date.today() + timedelta(days=days_to_recross)
            lines.append(
                f"Przy utrzymaniu obecnego tempa wzrostu Hct próg 45% może zostać przekroczony "
                f"za około {days_to_recross} dni, orientacyjnie około {est_date.isoformat()}."
            )
        elif current_hct >= TARGET_HCT:
            lines.append("Hct już pozostaje na poziomie co najmniej 45%.")
    else:
        lines.append("Nie udało się wiarygodnie oszacować czasu do ponownego przekroczenia 45%.")
    lines.append("")

    lines.append("Flagi")
    if flags:
        for flag in flags:
            lines.append(f"• {flag}")
    else:
        lines.append("• brak dodatkowych flag w tym modelu")
    lines.append("")

    lines.append("Ocena cytoredukcji")
    lines.append(cyto_conclusion)
    if cyto_reasons:
        for r in cyto_reasons:
            lines.append(f"• {r}")
    else:
        lines.append("• brak dodatkowych przesłanek w tym uproszczonym modelu")
    lines.append("")
    lines.append("Uwagi końcowe")
    lines.append("• To narzędzie ma charakter wspomagający dla lekarza.")
    lines.append("• Nie zastępuje pełnej oceny hematologicznej.")
    lines.append("• Objętość upustu jest tylko szacunkiem roboczym.")
    lines.append("• Ostateczna decyzja należy do lekarza prowadzącego.")

    quick = (
        f"Aktualny Hct: {current_hct:.1f}% | kolejny upust do rozważenia: {next_ml} ml"
        if current_hct is not None
        else "Brak aktualnego Hct"
    )

    return "\n".join(lines), quick, current_hct, next_ml


st.title("PV Assistant PRO")
st.caption("Wersja webowa dla lekarza")

st.warning(
    "To narzędzie ma charakter wspomagający dla lekarza. "
    "Nie zastępuje pełnej oceny klinicznej ani decyzji terapeutycznej."
)

left, right = st.columns([1.05, 1.25])

with left:
    st.subheader("Dane podstawowe")

    patient_id = st.text_input("Pacjent / ID", value="")
    age = st.number_input("Wiek", min_value=0, max_value=120, value=55, step=1)
    sex = st.selectbox("Płeć", ["M", "K", "inna / niepodano"])
    weight = st.number_input("Masa ciała (kg)", min_value=20.0, max_value=300.0, value=80.0, step=1.0)
    height = st.number_input("Wzrost (cm)", min_value=100.0, max_value=250.0, value=175.0, step=1.0)
    thrombosis_history = st.selectbox("Zakrzepica w wywiadzie", ["nie", "tak"])

    bmi = bmi_calc(weight, height)
    st.info(f"BMI: {bmi:.1f} ({bmi_class(bmi)})" if bmi is not None else "BMI: brak danych")

    treatment = st.text_area(
        "Leczenie",
        value="",
        height=120,
        placeholder="Np. ASA, hydroksymocznik, interferon, ruxolitinib, antykoagulant",
    )

    st.subheader("Objawy")
    s1, s2 = st.columns(2)
    symptoms = {
        "świąd": s1.checkbox("Świąd"),
        "ból_głowy": s1.checkbox("Ból głowy"),
        "erytromelalgia": s1.checkbox("Erytromelalgia"),
        "zawroty": s2.checkbox("Zawroty głowy"),
        "mikrokrążenie": s2.checkbox("Objawy mikrokrążeniowe"),
    }

    st.subheader("4 kolejne badania morfologii")
    cbc_rows = []
    for i in range(4):
        st.markdown(f"**Badanie {i+1}**")
        c1, c2, c3, c4, c5 = st.columns(5)

        row_date = c1.date_input(f"Data {i+1}", value=date.today(), key=f"cbc_date_{i}")
        row_hct = c2.number_input(f"Hct {i+1}", min_value=20.0, max_value=80.0, value=45.0, step=0.1, key=f"cbc_hct_{i}")
        row_hb = c3.number_input(f"Hb {i+1}", min_value=5.0, max_value=25.0, value=15.0, step=0.1, key=f"cbc_hb_{i}")
        row_wbc = c4.number_input(f"WBC {i+1}", min_value=0.0, max_value=200.0, value=10.0, step=0.1, key=f"cbc_wbc_{i}")
        row_plt = c5.number_input(f"PLT {i+1}", min_value=0.0, max_value=3000.0, value=400.0, step=1.0, key=f"cbc_plt_{i}")

        cbc_rows.append(
            {
                "date": row_date,
                "hct": safe_float(row_hct),
                "hb": safe_float(row_hb),
                "wbc": safe_float(row_wbc),
                "plt": safe_float(row_plt),
            }
        )

    st.subheader("4 ostatnie upusty")
    phleb_rows = []
    for i in range(4):
        p1, p2 = st.columns(2)
        ph_date = p1.date_input(f"Data upustu {i+1}", value=date.today(), key=f"ph_date_{i}")
        ph_ml = p2.number_input(f"Objętość ml {i+1}", min_value=0, max_value=1000, value=300, step=25, key=f"ph_ml_{i}")
        phleb_rows.append({"date": ph_date, "ml": ph_ml})

with right:
    st.subheader("Analiza")

    if st.button("Oceń pacjenta", type="primary"):
        cbc_rows = sorted(cbc_rows, key=lambda x: x["date"])
        phleb_rows = sorted(phleb_rows, key=lambda x: x["date"])

        data = {
            "patient_id": patient_id,
            "age": int(age),
            "sex": sex,
            "weight": float(weight),
            "height": float(height),
            "thrombosis_history": thrombosis_history,
            "treatment": treatment,
            "cbc_rows": cbc_rows,
            "phleb_rows": phleb_rows,
            "symptoms": symptoms,
        }

        summary, quick, current_hct, next_ml = build_summary(data)

        if current_hct is not None and current_hct > TARGET_HCT:
            st.error(quick)
        else:
            st.success(quick)

        st.metric("Orientacyjny kolejny upust do rozważenia", f"{next_ml} ml")

        st.text_area("Podsumowanie", value=summary, height=560)

        df = pd.DataFrame(cbc_rows)
        if not df.empty:
            df_chart = df.copy()
            df_chart["date"] = pd.to_datetime(df_chart["date"])
            df_chart = df_chart.set_index("date")

            st.subheader("Trend Hct")
            st.line_chart(df_chart[["hct"]])

            st.subheader("Trend Hb / WBC / PLT")
            st.line_chart(df_chart[["hb", "wbc", "plt"]])

            csv_data = df.reset_index().to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Pobierz badania jako CSV",
                data=csv_data,
                file_name="pv_badania.csv",
                mime="text/csv",
            )

        st.download_button(
            "Pobierz podsumowanie jako TXT",
            data=summary.encode("utf-8"),
            file_name="pv_podsumowanie.txt",
            mime="text/plain",
        )
    else:
        st.info("Wprowadź dane i kliknij „Oceń pacjenta”.")
