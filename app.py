import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, date


APP_TITLE = "PV Assistant 4.0 – trendy + upust"
TARGET_HCT = 45.0
MAX_SINGLE_PHLEB_ML = 300


def to_float(value: str):
    value = value.strip().replace(",", ".")
    if not value:
        return None
    return float(value)


def to_int(value: str):
    value = value.strip()
    if not value:
        return None
    return int(value)


def to_date(value: str):
    value = value.strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def bmi_calc(weight_kg, height_cm):
    if weight_kg is None or height_cm is None or height_cm <= 0:
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


def parse_treatment_flags(text: str):
    t = (text or "").lower()
    flags = {
        "asa": any(x in t for x in ["asa", "acard", "aspir", "aspiryna"]),
        "hydroxyurea": any(x in t for x in ["hydroksy", "hydroxy", "hu"]),
        "interferon": any(x in t for x in ["interfer", "ropeg"]),
        "ruxolitinib": any(x in t for x in ["ruxo", "jakavi"]),
        "anticoagulant": any(x in t for x in ["apiks", "apix", "eliquis", "rivar", "xarelto", "dabig", "warf", "acenok"]),
    }
    flags["cytoreduction"] = flags["hydroxyurea"] or flags["interferon"] or flags["ruxolitinib"]
    return flags


def estimate_blood_volume_liters(sex: str, height_cm, weight_kg):
    """
    Wzór Nadlera.
    Height we wzorze w metrach.
    Wynik w litrach.
    """
    if height_cm is None or weight_kg is None:
        return None

    h = height_cm / 100.0
    w = weight_kg

    if sex == "M":
        return (0.3669 * (h ** 3)) + (0.03219 * w) + 0.6041
    elif sex == "K":
        return (0.3561 * (h ** 3)) + (0.03308 * w) + 0.1833
    else:
        # neutralne przybliżenie pośrednie
        return (0.3615 * (h ** 3)) + (0.03264 * w) + 0.3937


def collect_cbc_rows():
    rows = []
    widgets = [
        (entry_cbc1_date, entry_cbc1_hct, entry_cbc1_hb, entry_cbc1_wbc, entry_cbc1_plt),
        (entry_cbc2_date, entry_cbc2_hct, entry_cbc2_hb, entry_cbc2_wbc, entry_cbc2_plt),
        (entry_cbc3_date, entry_cbc3_hct, entry_cbc3_hb, entry_cbc3_wbc, entry_cbc3_plt),
        (entry_cbc4_date, entry_cbc4_hct, entry_cbc4_hb, entry_cbc4_wbc, entry_cbc4_plt),
    ]

    for d_e, hct_e, hb_e, wbc_e, plt_e in widgets:
        row = {
            "date": to_date(d_e.get()) if d_e.get().strip() else None,
            "hct": to_float(hct_e.get()) if hct_e.get().strip() else None,
            "hb": to_float(hb_e.get()) if hb_e.get().strip() else None,
            "wbc": to_float(wbc_e.get()) if wbc_e.get().strip() else None,
            "plt": to_float(plt_e.get()) if plt_e.get().strip() else None,
        }
        if any(v is not None for v in row.values()):
            rows.append(row)

    rows.sort(key=lambda x: x["date"] if x["date"] is not None else date.min)
    return rows


def collect_phleb_rows():
    rows = []
    widgets = [
        (entry_ph1_date, entry_ph1_ml),
        (entry_ph2_date, entry_ph2_ml),
        (entry_ph3_date, entry_ph3_ml),
        (entry_ph4_date, entry_ph4_ml),
    ]

    for d_e, ml_e in widgets:
        row = {
            "date": to_date(d_e.get()) if d_e.get().strip() else None,
            "ml": to_int(ml_e.get()) if ml_e.get().strip() else None,
        }
        if any(v is not None for v in row.values()):
            rows.append(row)

    rows.sort(key=lambda x: x["date"] if x["date"] is not None else date.min)
    return rows


def validate_inputs(cbc_rows, phleb_rows, age, weight, height, sex):
    if age is None:
        raise ValueError("Wiek jest wymagany.")
    if not (0 <= age <= 120):
        raise ValueError("Wiek poza zakresem.")

    if sex not in ["M", "K", "inna / niepodano"]:
        raise ValueError("Wybierz płeć.")

    if weight is not None and not (20 <= weight <= 300):
        raise ValueError("Masa ciała poza zakresem.")
    if height is not None and not (100 <= height <= 250):
        raise ValueError("Wzrost poza zakresem.")

    if len(cbc_rows) < 2:
        raise ValueError("Wpisz co najmniej 2 badania morfologii.")
    if cbc_rows[-1]["hct"] is None:
        raise ValueError("W ostatnim badaniu Hct jest wymagany.")

    for i, row in enumerate(cbc_rows, start=1):
        if row["date"] is None:
            raise ValueError(f"W badaniu {i} brakuje daty.")
        if row["hct"] is not None and not (20 <= row["hct"] <= 80):
            raise ValueError(f"Hct w badaniu {i} poza zakresem.")
        if row["hb"] is not None and not (5 <= row["hb"] <= 25):
            raise ValueError(f"Hb w badaniu {i} poza zakresem.")
        if row["wbc"] is not None and not (0 <= row["wbc"] <= 200):
            raise ValueError(f"WBC w badaniu {i} poza zakresem.")
        if row["plt"] is not None and not (0 <= row["plt"] <= 3000):
            raise ValueError(f"PLT w badaniu {i} poza zakresem.")

    for i, row in enumerate(phleb_rows, start=1):
        if row["date"] is None:
            raise ValueError(f"W upuście {i} brakuje daty.")
        if row["ml"] is not None and not (0 <= row["ml"] <= 1000):
            raise ValueError(f"Objętość w upuście {i} poza zakresem.")


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
    avg_phleb_interval
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


def assess_cytoreduction_need(age, treatment_flags, cbc_rows, avg_phleb_interval):
    reasons = []

    recent_hct = [r["hct"] for r in cbc_rows if r["hct"] is not None]
    recent_wbc = [r["wbc"] for r in cbc_rows if r["wbc"] is not None]
    recent_plt = [r["plt"] for r in cbc_rows if r["plt"] is not None]

    if age >= 60:
        reasons.append("wiek ≥60 lat")

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

    cyto_conclusion, cyto_reasons = assess_cytoreduction_need(
        age=data["age"],
        treatment_flags=treatment_flags,
        cbc_rows=cbc_rows,
        avg_phleb_interval=avg_interval,
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

    lines = []
    lines.append("PODSUMOWANIE LEKARSKIE")
    lines.append("=" * 78)
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

    lines.append("Leczenie")
    lines.append(data["treatment"] if data["treatment"] else "brak danych")
    if recognized:
        lines.append("Rozpoznane leczenie: " + ", ".join(recognized))
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
    lines.append(f"Tempo zmiany Hct z 2 ostatnich badań: {f'{hct_slope:.2f} % / mies.' if hct_slope is not None else 'za mało danych'}")
    lines.append(f"Tempo zmiany Hb z 2 ostatnich badań: {f'{hb_slope:.2f} g/dl / mies.' if hb_slope is not None else 'za mało danych'}")
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
    lines.append("-" * 78)
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
        f"Aktualny Hct: {current_hct:.1f}% | "
        f"kolejny upust do rozważenia: {next_ml} ml"
        if current_hct is not None else
        "Brak aktualnego Hct"
    )

    return "\n".join(lines), quick, current_hct


def calculate_bmi_label():
    try:
        weight = to_float(entry_weight.get())
        height = to_float(entry_height.get())
        bmi = bmi_calc(weight, height)
        if bmi is None:
            label_bmi.config(text="BMI: brak danych")
        else:
            label_bmi.config(text=f"BMI: {bmi:.1f} ({bmi_class(bmi)})")
    except Exception:
        label_bmi.config(text="BMI: błąd danych")


def set_quick_label_color(hct):
    if hct is None:
        label_quick.config(foreground="black")
    elif hct > TARGET_HCT:
        label_quick.config(foreground="red")
    else:
        label_quick.config(foreground="darkgreen")


def run_assessment():
    try:
        age = to_int(entry_age.get())
        weight = to_float(entry_weight.get())
        height = to_float(entry_height.get())
        sex = combo_sex.get().strip()

        cbc_rows = collect_cbc_rows()
        phleb_rows = collect_phleb_rows()

        validate_inputs(
            cbc_rows=cbc_rows,
            phleb_rows=phleb_rows,
            age=age,
            weight=weight,
            height=height,
            sex=sex,
        )

        data = {
            "patient_id": entry_patient.get().strip(),
            "age": age,
            "sex": sex,
            "weight": weight,
            "height": height,
            "treatment": text_treatment.get("1.0", tk.END).strip(),
            "cbc_rows": cbc_rows,
            "phleb_rows": phleb_rows,
        }

        summary, quick, current_hct = build_summary(data)
        output_text.config(state="normal")
        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, summary)
        output_text.config(state="disabled")
        label_quick.config(text=quick)
        set_quick_label_color(current_hct)
        calculate_bmi_label()

    except Exception as e:
        messagebox.showerror("Błąd", str(e))


def clear_form():
    widgets = [
        entry_patient, entry_age, entry_weight, entry_height,
        entry_cbc1_date, entry_cbc1_hct, entry_cbc1_hb, entry_cbc1_wbc, entry_cbc1_plt,
        entry_cbc2_date, entry_cbc2_hct, entry_cbc2_hb, entry_cbc2_wbc, entry_cbc2_plt,
        entry_cbc3_date, entry_cbc3_hct, entry_cbc3_hb, entry_cbc3_wbc, entry_cbc3_plt,
        entry_cbc4_date, entry_cbc4_hct, entry_cbc4_hb, entry_cbc4_wbc, entry_cbc4_plt,
        entry_ph1_date, entry_ph1_ml,
        entry_ph2_date, entry_ph2_ml,
        entry_ph3_date, entry_ph3_ml,
        entry_ph4_date, entry_ph4_ml,
    ]
    for w in widgets:
        w.delete(0, tk.END)

    combo_sex.set("M")
    text_treatment.delete("1.0", tk.END)

    output_text.config(state="normal")
    output_text.delete("1.0", tk.END)
    output_text.config(state="disabled")

    label_bmi.config(text="BMI: brak danych")
    label_quick.config(text="", foreground="black")


root = tk.Tk()
root.title(APP_TITLE)
root.geometry("1500x930")

main = ttk.Frame(root, padding=10)
main.pack(fill="both", expand=True)

left_outer = ttk.Frame(main)
left_outer.pack(side="left", fill="both", expand=True, padx=(0, 10))

right_outer = ttk.Frame(main)
right_outer.pack(side="right", fill="both", expand=True)

left_canvas = tk.Canvas(left_outer, highlightthickness=0)
left_scrollbar = ttk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
left_canvas.configure(yscrollcommand=left_scrollbar.set)
left_scrollbar.pack(side="right", fill="y")
left_canvas.pack(side="left", fill="both", expand=True)

left = ttk.Frame(left_canvas)
left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")


def _left_configure(event):
    left_canvas.configure(scrollregion=left_canvas.bbox("all"))


def _left_resize(event):
    left_canvas.itemconfig(left_window, width=event.width)


left.bind("<Configure>", _left_configure)
left_canvas.bind("<Configure>", _left_resize)

right_canvas = tk.Canvas(right_outer, highlightthickness=0)
right_scrollbar = ttk.Scrollbar(right_outer, orient="vertical", command=right_canvas.yview)
right_canvas.configure(yscrollcommand=right_scrollbar.set)
right_scrollbar.pack(side="right", fill="y")
right_canvas.pack(side="left", fill="both", expand=True)

right = ttk.Frame(right_canvas)
right_window = right_canvas.create_window((0, 0), window=right, anchor="nw")


def _right_configure(event):
    right_canvas.configure(scrollregion=right_canvas.bbox("all"))


def _right_resize(event):
    right_canvas.itemconfig(right_window, width=event.width)


right.bind("<Configure>", _right_configure)
right_canvas.bind("<Configure>", _right_resize)

active_canvas = None


def _bind_left(_event):
    global active_canvas
    active_canvas = left_canvas


def _bind_right(_event):
    global active_canvas
    active_canvas = right_canvas


def _unbind(_event):
    global active_canvas
    active_canvas = None


def _on_mousewheel(event):
    if active_canvas is not None:
        active_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


root.bind_all("<MouseWheel>", _on_mousewheel)
left_canvas.bind("<Enter>", _bind_left)
left_canvas.bind("<Leave>", _unbind)
right_canvas.bind("<Enter>", _bind_right)
right_canvas.bind("<Leave>", _unbind)

ttk.Label(left, text="PV Assistant 4.0 – trendy + upust", font=("Arial", 15, "bold")).pack(anchor="w", pady=(0, 8))

frame_basic = ttk.LabelFrame(left, text="Dane podstawowe", padding=8)
frame_basic.pack(fill="x", pady=(0, 8))

ttk.Label(frame_basic, text="Pacjent / ID").grid(row=0, column=0, sticky="w")
entry_patient = ttk.Entry(frame_basic, width=28)
entry_patient.grid(row=0, column=1, padx=5, pady=3, sticky="w")

ttk.Label(frame_basic, text="Wiek").grid(row=1, column=0, sticky="w")
entry_age = ttk.Entry(frame_basic, width=10)
entry_age.grid(row=1, column=1, padx=5, pady=3, sticky="w")

ttk.Label(frame_basic, text="Płeć").grid(row=2, column=0, sticky="w")
combo_sex = ttk.Combobox(frame_basic, values=["M", "K", "inna / niepodano"], state="readonly", width=16)
combo_sex.grid(row=2, column=1, padx=5, pady=3, sticky="w")
combo_sex.set("M")

ttk.Label(frame_basic, text="Masa ciała (kg)").grid(row=3, column=0, sticky="w")
entry_weight = ttk.Entry(frame_basic, width=10)
entry_weight.grid(row=3, column=1, padx=5, pady=3, sticky="w")

ttk.Label(frame_basic, text="Wzrost (cm)").grid(row=4, column=0, sticky="w")
entry_height = ttk.Entry(frame_basic, width=10)
entry_height.grid(row=4, column=1, padx=5, pady=3, sticky="w")

ttk.Button(frame_basic, text="Przelicz BMI", command=calculate_bmi_label).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
label_bmi = ttk.Label(frame_basic, text="BMI: brak danych")
label_bmi.grid(row=6, column=0, columnspan=2, sticky="w")

frame_treatment = ttk.LabelFrame(left, text="Leczenie", padding=8)
frame_treatment.pack(fill="x", pady=(0, 8))

text_treatment = ScrolledText(frame_treatment, height=5, wrap="word")
text_treatment.pack(fill="x")
ttk.Label(frame_treatment, text="Np. ASA, hydroksymocznik, interferon, ruxolitinib, antykoagulant").pack(anchor="w", pady=(5, 0))

frame_cbc = ttk.LabelFrame(left, text="4 kolejne badania morfologii", padding=8)
frame_cbc.pack(fill="x", pady=(0, 8))

headers = ["Data", "Hct", "Hb", "WBC", "PLT"]
for col, h in enumerate(headers):
    ttk.Label(frame_cbc, text=h).grid(row=0, column=col, sticky="w", padx=4, pady=2)

entry_cbc1_date = ttk.Entry(frame_cbc, width=12)
entry_cbc1_hct = ttk.Entry(frame_cbc, width=8)
entry_cbc1_hb = ttk.Entry(frame_cbc, width=8)
entry_cbc1_wbc = ttk.Entry(frame_cbc, width=8)
entry_cbc1_plt = ttk.Entry(frame_cbc, width=8)

entry_cbc2_date = ttk.Entry(frame_cbc, width=12)
entry_cbc2_hct = ttk.Entry(frame_cbc, width=8)
entry_cbc2_hb = ttk.Entry(frame_cbc, width=8)
entry_cbc2_wbc = ttk.Entry(frame_cbc, width=8)
entry_cbc2_plt = ttk.Entry(frame_cbc, width=8)

entry_cbc3_date = ttk.Entry(frame_cbc, width=12)
entry_cbc3_hct = ttk.Entry(frame_cbc, width=8)
entry_cbc3_hb = ttk.Entry(frame_cbc, width=8)
entry_cbc3_wbc = ttk.Entry(frame_cbc, width=8)
entry_cbc3_plt = ttk.Entry(frame_cbc, width=8)

entry_cbc4_date = ttk.Entry(frame_cbc, width=12)
entry_cbc4_hct = ttk.Entry(frame_cbc, width=8)
entry_cbc4_hb = ttk.Entry(frame_cbc, width=8)
entry_cbc4_wbc = ttk.Entry(frame_cbc, width=8)
entry_cbc4_plt = ttk.Entry(frame_cbc, width=8)

rows = [
    (entry_cbc1_date, entry_cbc1_hct, entry_cbc1_hb, entry_cbc1_wbc, entry_cbc1_plt),
    (entry_cbc2_date, entry_cbc2_hct, entry_cbc2_hb, entry_cbc2_wbc, entry_cbc2_plt),
    (entry_cbc3_date, entry_cbc3_hct, entry_cbc3_hb, entry_cbc3_wbc, entry_cbc3_plt),
    (entry_cbc4_date, entry_cbc4_hct, entry_cbc4_hb, entry_cbc4_wbc, entry_cbc4_plt),
]

for row_idx, row_widgets in enumerate(rows, start=1):
    for col_idx, widget in enumerate(row_widgets):
        widget.grid(row=row_idx, column=col_idx, padx=4, pady=2, sticky="w")

ttk.Label(frame_cbc, text="Format daty: YYYY-MM-DD").grid(row=5, column=0, columnspan=5, sticky="w", pady=(5, 0))

frame_phleb = ttk.LabelFrame(left, text="Daty upustów", padding=8)
frame_phleb.pack(fill="x", pady=(0, 8))

ttk.Label(frame_phleb, text="Data").grid(row=0, column=0, sticky="w", padx=4, pady=2)
ttk.Label(frame_phleb, text="ml").grid(row=0, column=1, sticky="w", padx=4, pady=2)

entry_ph1_date = ttk.Entry(frame_phleb, width=12)
entry_ph1_ml = ttk.Entry(frame_phleb, width=8)
entry_ph2_date = ttk.Entry(frame_phleb, width=12)
entry_ph2_ml = ttk.Entry(frame_phleb, width=8)
entry_ph3_date = ttk.Entry(frame_phleb, width=12)
entry_ph3_ml = ttk.Entry(frame_phleb, width=8)
entry_ph4_date = ttk.Entry(frame_phleb, width=12)
entry_ph4_ml = ttk.Entry(frame_phleb, width=8)

ph_rows = [
    (entry_ph1_date, entry_ph1_ml),
    (entry_ph2_date, entry_ph2_ml),
    (entry_ph3_date, entry_ph3_ml),
    (entry_ph4_date, entry_ph4_ml),
]

for row_idx, row_widgets in enumerate(ph_rows, start=1):
    for col_idx, widget in enumerate(row_widgets):
        widget.grid(row=row_idx, column=col_idx, padx=4, pady=2, sticky="w")

ttk.Label(frame_phleb, text="Format daty: YYYY-MM-DD").grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))

frame_buttons = ttk.Frame(left)
frame_buttons.pack(fill="x", pady=(6, 0))
ttk.Button(frame_buttons, text="Oceń pacjenta", command=run_assessment).pack(side="left")
ttk.Button(frame_buttons, text="Wyczyść", command=clear_form).pack(side="left", padx=8)

ttk.Label(right, text="Szybki wynik", font=("Arial", 10, "bold")).pack(anchor="w")
label_quick = ttk.Label(right, text="", font=("Arial", 11, "bold"))
label_quick.pack(anchor="w", pady=(0, 8))

ttk.Label(right, text="Podsumowanie", font=("Arial", 10, "bold")).pack(anchor="w")
output_text = ScrolledText(right, height=35, wrap="word")
output_text.pack(fill="both", expand=True)
output_text.config(state="disabled")

root.mainloop()
