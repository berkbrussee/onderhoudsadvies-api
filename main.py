from flask import Flask, request, jsonify
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import openai
import os

# Zet je OpenAI key via Render (environment variable)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Laad de onderhoudsdata
intervalen_df = pd.read_csv("onderhoudsintervallen_per_kenteken.csv")
historie_df = pd.read_csv("onderhoudsbeurten_per_kenteken.csv")

app = Flask(__name__)

def bepaal_due_onderdelen(kenteken, km_stand_huidig, laatst_onderhoud):
    relevant = intervalen_df[intervalen_df["Kenteken"] == kenteken]
    historie = historie_df[historie_df["Kenteken"] == kenteken]
    opmerkingen = []

    for _, row in relevant.iterrows():
        onderdeel = row["Onderdeel"]
        interval_km = row["Interval_km"]
        interval_mnd = row["Interval_maanden"]

        vervangingen = historie[historie["Vervangen Onderdelen"] == onderdeel]
        if vervangingen.empty:
            laatst_vervangen_datum = laatst_onderhoud
            laatst_vervangen_km = 0
        else:
            laatste = vervangingen.sort_values("Beurtdatum", ascending=False).iloc[0]
            laatst_vervangen_datum = datetime.strptime(laatste["Beurtdatum"].split(" ")[0], "%Y-%m-%d")
            laatst_vervangen_km = int(laatste["Km_stand"])

        maanden_geleden = relativedelta(datetime.now(), laatst_vervangen_datum).months + \
                          12 * (datetime.now().year - laatst_vervangen_datum.year)
        km_geleden = km_stand_huidig - laatst_vervangen_km

        if km_geleden >= interval_km or maanden_geleden >= interval_mnd:
            opmerkingen.append(
                f"{onderdeel}: vervangen {km_geleden} km en {maanden_geleden} maanden geleden, "
                f"interval is {interval_km} km / {interval_mnd} maanden"
            )

    return opmerkingen

@app.route("/onderhoudsadvies", methods=["POST"])
def onderhoudsadvies():
    data = request.json
    kenteken = data.get("kenteken")
    huidige_km = data.get("huidige_km")

    if not kenteken or not huidige_km:
        return jsonify({"error": "kenteken of huidige_km ontbreekt"}), 400

    try:
        km_per_jaar = int(data.get("km_per_jaar", 10000))
        huidige_km = int(huidige_km)
    except ValueError:
        return jsonify({"error": "km-waarden moeten getallen zijn"}), 400

    laatste_onderhoud = historie_df[historie_df["Kenteken"] == kenteken]["Beurtdatum"].max()
    if pd.isna(laatste_onderhoud):
        laatste_onderhoud_datum = datetime.now()
    else:
        laatste_onderhoud_datum = datetime.strptime(laatste_onderhoud.split(" ")[0], "%Y-%m-%d")

    due = bepaal_due_onderdelen(kenteken, huidige_km, laatste_onderhoud_datum)
    onderdelen_tekst = "\n".join(due) if due else "Geen onderdelen over hun interval."

    prompt = (
        f"Kenteken: {kenteken}\n"
        f"Laatst onderhoud: {laatste_onderhoud_datum.date()}\n"
        f"Huidige km-stand: {huidige_km}\n"
        f"Onderhoudscontrole:\n{onderdelen_tekst}\n"
        f"Welk onderhoud zou je adviseren? Antwoord in 2-3 zinnen."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        advies = response["choices"][0]["message"]["content"]
    except Exception as e:
        return jsonify({"error": f"AI-fout: {str(e)}"}), 500

    return jsonify({"advies": advies})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
