from flask import Flask, request, jsonify
from openai import OpenAI
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

app = Flask(__name__)
import os
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# CSV-bestanden in Replit uploaden via linker sidebar (Uploads)
df_intervallen = pd.read_csv("onderhoudsintervallen_per_kenteken.csv")
df_historie = pd.read_csv("onderhoudsbeurten_per_kenteken.csv")
huidige_datum = datetime(2025, 5, 20)

def bepaal_due_onderdelen(kenteken, huidige_km, laatste_onderhoudsdatum):
    relevant = df_intervallen[df_intervallen['Kenteken'] == kenteken]
    historie = df_historie[df_historie['Kenteken'] == kenteken]
    opmerkingen = []

    for _, row in relevant.iterrows():
        onderdeel = row['Onderdeel']
        interval_km = row['Interval_km']
        interval_maanden = row['Interval_maanden']

        laatst_vervangen = historie[historie['Vervangen Onderdelen'] == onderdeel]
        if not laatst_vervangen.empty:
            laatste_entry = laatst_vervangen.sort_values('Beurtdatum', ascending=False).iloc[0]
            laatst_vervangen_datum = laatste_entry['Beurtdatum']
            laatst_vervangen_km = int(laatste_entry['Km_stand'])
        else:
            laatst_vervangen_datum = laatste_onderhoudsdatum
            laatst_vervangen_km = 0

        maanden_geleden = relativedelta(huidige_datum, laatst_vervangen_datum).months + \
                          12 * (huidige_datum.year - laatst_vervangen_datum.year)
        km_sinds = max(huidige_km - laatst_vervangen_km, 0)

        if km_sinds >= interval_km or maanden_geleden >= interval_maanden:
            opmerkingen.append(
                f"{onderdeel}: vervangen {km_sinds} km en {maanden_geleden} maanden geleden, "
                f"interval is {interval_km} km / {interval_maanden} maanden"
            )

    return opmerkingen

@app.route("/onderhoudsadvies", methods=["POST"])
def onderhoudsadvies():
    data = request.json
    kenteken = data["kenteken"]
    km_per_jaar = int(data["km_per_jaar"])
    laatste_onderhoud = datetime.strptime(data["laatste_onderhoud"], "%Y-%m-%d")
    type_beurt = data["type_beurt"]
    garagebeleid = data["garagebeleid"]
    leeftijd = int(data["leeftijd_bestuurder"])

    maanden_sinds = relativedelta(huidige_datum, laatste_onderhoud).months + \
                    12 * (huidige_datum.year - laatste_onderhoud.year)
    km_schatting = int(km_per_jaar * (maanden_sinds / 12))

    due_onderdelen = bepaal_due_onderdelen(kenteken, km_schatting, laatste_onderhoud)
    onderdelen_tekst = "\n".join(due_onderdelen) if due_onderdelen else "Geen onderdelen zijn over hun interval."

    prompt = (
        f"Je bent een onderhoudsadviseur. De auto met kenteken {kenteken} rijdt {km_per_jaar} km per jaar. "
        f"De laatste onderhoudsbeurt was op {laatste_onderhoud.date()} (type: {type_beurt}). "
        f"Garagebeleid: {garagebeleid}. De bestuurder is {leeftijd} jaar oud. "
        f"Huidige km-stand is ongeveer {km_schatting} km. "
        f"Onderhoudscontrole:\n{onderdelen_tekst}\n"
        f"Welk onderhoud zou je adviseren? Geef 2-3 zinnen gericht advies."
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    advies = response.choices[0].message.content
    return jsonify({
        "kenteken": kenteken,
        "advies": advies
    })

app.run(host='0.0.0.0', port=81)
