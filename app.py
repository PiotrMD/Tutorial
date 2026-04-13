import streamlit as st
from datetime import datetime

st.set_page_config(layout="wide")

st.title("PV Assistant – wersja lekarska (web)")

TARGET_HCT = 45
MAX_VOLUME = 300

# ----------------------
# FUNKCJE
# ----------------------

def to_float(x):
    try:
        return float(x)
    except:
        return None

def days_between(d1, d2):
    try:
        d1 = datetime.strptime(d1, "%Y-%m-%d")
        d2 = datetime.strptime(d2, "%Y-%m-%d")
        return (d2 - d1).days
    except:
        return None

# ----------------------
# LAYOUT
# ----------------------

col1, col2 = st.columns(2)

# ======================
# LEWA STRONA – DANE
# ======================
with col1:
    st.header("Dane pacjenta")

    wiek = st.number_input("Wiek", 18, 100, 60)
    plec = st.selectbox("Płeć", ["M", "K"])
    masa = st.number_input("Masa (kg)", 40.0, 150.0, 70.0)
    wzrost = st.number_input("Wzrost (cm)", 140.0, 210.0, 175.0)

    bmi = masa / ((wzrost / 100) ** 2)
    st.write(f"BMI: {round(bmi,1)}")

    st.header("4 ostatnie badania")

    badania = []

    for i in range(4):
        st.subheader(f"Badanie {i+1}")
        data = st.text_input(f"Data (YYYY-MM-DD) {i}", key=f"d{i}")
        hct = to_float(st.text_input(f"Hct (%) {i}", key=f"h{i}"))
        hb = to_float(st.text_input(f"Hb (g/dl) {i}", key=f"hb{i}"))
        wbc = to_float(st.text_input(f"WBC {i}", key=f"w{i}"))
        plt = to_float(st.text_input(f"PLT {i}", key=f"p{i}"))

        badania.append({
            "data": data,
            "hct": hct,
            "hb": hb,
            "wbc": wbc,
            "plt": plt
        })

    st.header("3 ostatnie upusty")

    upusty = []

    for i in range(3):
        data = st.text_input(f"Data upustu {i}", key=f"u{i}")
        vol = to_float(st.text_input(f"Objętość (ml) {i}", key=f"v{i}"))

        upusty.append({
            "data": data,
            "vol": vol
        })

    zakrzepica = st.selectbox("Zakrzepica w wywiadzie", ["nie", "tak"])
    cytoredukcja = st.selectbox("Leczenie cytoredukcyjne", ["nie", "tak"])

# ======================
# PRAWA STRONA – ANALIZA
# ======================
with col2:
    st.header("Analiza")

    if st.button("Oblicz"):

        tekst = ""

        # aktualny wynik
        aktualny = badania[0]["hct"]

        if aktualny:
            tekst += f"Aktualny Hct: {aktualny}%\n"

            if aktualny > TARGET_HCT:
                tekst += "Powyżej celu terapeutycznego (<45%)\n"
            else:
                tekst += "W zakresie celu terapeutycznego\n"

        # trend
        hcts = [b["hct"] for b in badania if b["hct"]]

        if len(hcts) >= 2:
            trend = hcts[0] - hcts[-1]

            if trend > 0:
                tekst += f"Trend wzrostowy (+{round(trend,1)}%)\n"
            else:
                tekst += f"Trend spadkowy ({round(trend,1)}%)\n"

        # odstępy między upustami
        if upusty[0]["data"] and upusty[1]["data"]:
            dni = days_between(upusty[1]["data"], upusty[0]["data"])
            if dni:
                tekst += f"Odstęp ostatnich upustów: {dni} dni\n"

        # propozycja objętości
        if aktualny:
            nadwyzka = aktualny - TARGET_HCT

            if nadwyzka > 0:
                sugerowana = min(MAX_VOLUME, int(nadwyzka * 40))
                tekst += f"\nProponowana objętość (do rozważenia): {sugerowana} ml (max 300 ml)\n"

        # ryzyko
        if wiek >= 60 or zakrzepica == "tak":
            tekst += "\nPacjent wysokiego ryzyka zakrzepowego\n"

            if cytoredukcja == "nie":
                tekst += "→ rozważyć leczenie cytoredukcyjne\n"

        else:
            tekst += "\nPacjent niskiego ryzyka\n"

        # PLT
        plt = badania[0]["plt"]
        if plt and plt > 1000:
            tekst += "UWAGA: bardzo wysokie PLT – rozważyć pilną modyfikację leczenia\n"

        tekst += "\n---\nDecyzja ostateczna należy do lekarza."

        st.text_area("Wynik", tekst, height=400)
