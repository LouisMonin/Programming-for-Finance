import streamlit as st
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import random

# === Fonction principale de stratégie ===
def appliquer_strategie_stoploss(params):
    if params["mode_simulation"]:
        N = 1000
        dates = pd.date_range(start="2019-01-01", periods=N, freq="B")
        rendement_risque = np.cumprod(1 + np.random.normal(0.0004, 0.01, N))
        rendement_sans_risque = np.cumprod(1 + np.random.normal(0.0001, 0.002, N))
    else:
        vbisx = yf.download("VBISX", start="2019-01-01")
        sp500 = yf.download("^GSPC", start="2019-01-01")

        data = vbisx[['Close']].rename(columns={'Close': 'VBISX'}).join(
            sp500[['Close']].rename(columns={'Close': 'S&P500'}),
            how='inner'
        )

        prix_risque = data["S&P500"].values
        prix_sans_risque = data["VBISX"].values
        dates = data.index

        rendement_risque = prix_risque / prix_risque[0]
        rendement_sans_risque = prix_sans_risque / prix_sans_risque[0]

    N = len(rendement_risque)
    plancher = np.zeros(N)
    valeur_portefeuille = np.ones(N)
    valeur_nette = np.ones(N)

    max_rendement = rendement_risque[0]
    plancher[0] = params["gain_protege"] * max_rendement
    dans_actif_risque = True
    lock_in = params["lock_in"]
    latence = params["latence"]
    attente = 0

    for t in range(1, N):
        max_rendement = max(max_rendement, rendement_risque[t])
        plancher[t] = params["gain_protege"] * max_rendement

        r_risk_prev = rendement_risque[t-1] if rendement_risque[t-1] != 0 else 1
        r_safe_prev = rendement_sans_risque[t-1] if rendement_sans_risque[t-1] != 0 else 1

        if t < lock_in:
            changement_possible = False
        elif attente > 0:
            changement_possible = False
            attente -= 1
        else:
            changement_possible = True

        if dans_actif_risque:
            if changement_possible and rendement_risque[t] < plancher[t]:
                dans_actif_risque = False
                attente = latence
                croissance = rendement_sans_risque[t] / r_safe_prev
                croissance *= (1 - params["frais_transaction"])
            else:
                croissance = rendement_risque[t] / r_risk_prev
        else:
            if changement_possible and rendement_risque[t] > plancher[t]:
                dans_actif_risque = True
                attente = latence
                croissance = rendement_risque[t] / r_risk_prev
                croissance *= (1 - params["frais_transaction"])
            else:
                croissance = rendement_sans_risque[t] / r_safe_prev

        if not dans_actif_risque:
            croissance *= (1 - params["frais_gestion"] / 252)

        croissance *= (1 - params["inflation_journaliere"])

        if params["stress"] and random.random() < 0.01:
            croissance *= random.uniform(0.90, 0.97)

        valeur_portefeuille[t] = valeur_portefeuille[t - 1] * croissance

        gain_brut = valeur_portefeuille[t] - 1
        impot = params["taux_imposition"] * gain_brut if gain_brut > 0 else 0
        valeur_nette[t] = valeur_portefeuille[t] - impot

    return dates, rendement_risque, rendement_sans_risque, plancher, valeur_portefeuille, valeur_nette

# === Interface Streamlit ===
st.set_page_config(layout="wide")
st.title("Simulateur de stratégie Stop-Loss dynamique")

# === Sidebar: paramètres utilisateur ===
st.sidebar.header("Paramètres de simulation")
gain_protege = st.sidebar.slider("% de gain protégé (plancher)", 0.5, 1.0, 0.9, step=0.05)
taux_imposition = st.sidebar.slider("Taux d'imposition sur plus-values (%)", 0, 50, 30, step=5) / 100
frais_transaction = st.sidebar.slider("Frais de transaction (%)", 0.0, 1.0, 0.2, step=0.1) / 100
frais_gestion = st.sidebar.slider("Frais de gestion annuel sur actif sans risque (%)", 0.0, 2.0, 0.5, step=0.1) / 100
inflation_annuelle = st.sidebar.slider("Taux d'inflation annuel (%)", 0.0, 10.0, 2.0, step=0.1) / 100
lock_in = st.sidebar.slider("Période de blocage initiale (jours)", 0, 365, 30, step=5)
latence = st.sidebar.slider("Latence comportementale (jours)", 0, 10, 1, step=1)
stress = st.sidebar.checkbox("Activer les chocs de marché aléatoires (stress)", value=False)
mode_simulation = st.sidebar.checkbox("Mode simulation hors ligne (aléatoire)", value=False)

inflation_journaliere = inflation_annuelle / 252

params = {
    "gain_protege": gain_protege,
    "taux_imposition": taux_imposition,
    "frais_transaction": frais_transaction,
    "frais_gestion": frais_gestion,
    "inflation_journaliere": inflation_journaliere,
    "lock_in": lock_in,
    "latence": latence,
    "stress": stress,
    "mode_simulation": mode_simulation
}

if st.sidebar.button("Lancer la simulation"):
    with st.spinner("Simulation en cours..."):
        try:
            dates, r_risque, r_safe, plancher, val_brute, val_nette = appliquer_strategie_stoploss(params)
            st.success("Simulation réussie ✅")

            st.subheader("Évolution de la valeur du portefeuille")
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(dates, val_brute, label="Valeur brute", color="green")
            ax.plot(dates, val_nette, label="Valeur nette après impôt", linestyle="--", color="purple")
            ax.plot(dates, plancher, label="Plancher garanti", linestyle=":", color="red")
            ax.set_xlabel("Date")
            ax.set_ylabel("Valeur du portefeuille")
            ax.legend()
            ax.grid(True)
            st.pyplot(fig)

            st.subheader("Résumé des résultats")
            st.write("**Valeur finale brute :** {:.3f}".format(val_brute[-1]))
            st.write("**Valeur finale nette après impôt :** {:.3f}".format(val_nette[-1]))
            st.write("**Plancher garanti final :** {:.3f}".format(plancher[-1]))
            st.write("**Gain brut :** {:.3f}".format(val_brute[-1] - 1))
            st.write("**Impôt payé :** {:.3f}".format((val_brute[-1] - 1) * taux_imposition if val_brute[-1] > 1 else 0))
            st.write("**Surperformance nette vs plancher :** {:.3f}".format(val_nette[-1] - plancher[-1]))
        except Exception as e:
            st.error(f"❌ Erreur pendant la simulation : {e}")
            st.info("💡 Essayez le mode simulation hors ligne si vous êtes sans connexion Internet.")