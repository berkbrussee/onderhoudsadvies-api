from flask import Flask, request, jsonify
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import os

app = Flask(__name__)

# API-key ophalen uit environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# CSV-bestanden inlezen
df_intervallen = pd.read_csv("onderhoudsintervallen_per_kenteken.csv")
df_historie = pd.read_csv("onderhoudsbeurten_per_kenteken.csv")

def bepaal_due_onderdelen(kenteken, huidige_km, huidige_datum):
    opmerkingen = []
    relevant = df_intervallen[df_intervallen["Kenteken"] == kenteken]
    historie = df_historie[df_historie["Kenteken"] == kenteken]

    for _, row in relevant.iterrows():
        onderdeel = row["Onderdeel"]
        interval_km = row["Interval_km"]
        interval_maanden = row["Interval_maanden"]

        laatst_vervangen = historie[historie["Vervangen Onderdelen"] == onderdeel]

        if not laatst_vervangen.empty:
            laatste_entry = laatst_vervangen.sort_values("Beurtdatum", ascending=False).iloc[0]
            laatste_datum = datetime.strptime(laatste_entry["Beurtdatum"], "%Y-%m-%d")
            laatste_km = int(laatste_entry["Km_stand"])
        else:
            laatste_datum = huidige_datum - relativedelta(months=interval_maanden + 1)
            laatste_km = 0

        maanden_geleden = relativedelta(huidige_datum, laatste_datum).months + \
                          12 * (huidige_datum.year - laatste_datum.year)
        km_sinds = max(huidige_km - laatste_km, 0)

        if km_sinds >= interval_km or maanden_geleden >= interval_maanden:
            opmerkingen.append(
                f"{onderdeel}: vervangen {km_sinds} km of {maanden_geleden} maanden geleden, "
                f"interval is {interval_km} km / {interval_maanden} maanden"
            )

    return opmerkingen

@app.route("/onderhoudsadvies", methods=["POST"])
def onderhoudsadvies():
    data = request.json
    try:
        kenteken = data["kenteken"]
        huidige_km = int(data["huidige_km"])
    except (KeyError, ValueError):
        return jsonify({"error": "Vul een geldig kenteken en kilometerstand in."}), 400

    huidige_datum = datetime.now()
    due_onderdelen = bepaal_due_onderdelen(kenteken, huidige_km, huidige_datum)

    onderdelen_tekst = "\n".join(due_onderdelen) if due_onderdelen else "Geen onderdelen zijn over hun interval."

    prompt = (
        f"De auto met kenteken {kenteken} heeft een huidige kilometerstand van {huidige_km} km.\n"
        f"Onderhoudscontrole:\n{onderdelen_tekst}\n"
        f"Welk onderhoud zou je adviseren? Geef 2-3 zinnen gericht advies."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        advies = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": f"AI-service fout: {str(e)}"}), 500

    return jsonify({
        "kenteken": kenteken,
        "advies": advies,
        "onderdelen_check": onderdelen_tekst
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)
