"""
Validation externe du modèle sur CICIDS2017
============================================
Ce script ENTRAÎNE et ÉVALUE un modèle Isolation Forest sur le dataset
public CICIDS2017, en isolant la partie "Brute Force" (FTP-Patator, SSH-Patator).

Objectif : démontrer que NOTRE APPROCHE (Isolation Forest + features
agrégées par flux) fonctionne aussi sur un dataset reconnu de la
recherche académique. Cela complète l'évaluation sur nos données
Keycloak en montrant la généralisation.

PROCESSUS SCIENTIFIQUE :
  1. Charger CICIDS2017 - jour avec brute force (Tuesday)
  2. Filtrer : trafic BENIGN + attaques FTP-Patator + SSH-Patator
  3. Sélectionner des features comparables à celles utilisées sur Keycloak
  4. Train Isolation Forest UNIQUEMENT sur le trafic BENIGN
     (approche non supervisée réaliste)
  5. Évaluer sur un test set mixte
  6. Reporter precision / recall / F1 / ROC-AUC

Prérequis :
    pip install pandas numpy scikit-learn matplotlib

Téléchargement CICIDS2017 :
    https://www.unb.ca/cic/datasets/ids-2017.html
    (formulaire avec email, gratuit, instantané)
    -> récupérer "MachineLearningCSV.zip"
    -> dézipper, garder Tuesday-WorkingHours.pcap_ISCX.csv
"""

import os
import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve,
    precision_recall_fscore_support, average_precision_score
)

# ==========================================================
# Config
# ==========================================================
CICIDS_FILE = os.getenv("CICIDS_FILE", "Tuesday-WorkingHours.pcap_ISCX.csv")

# Features choisies (présentes dans CICIDS et conceptuellement
# proches de celles qu'on utilise pour Keycloak)
# Note : CICIDS a parfois des espaces en début/fin de noms
FEATURES = [
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Fwd Packet Length Mean",
    "Bwd Packet Length Mean",
    "Flow IAT Mean",          # inter arrival time : pertinent pour brute force
    "Fwd PSH Flags",
    "ACK Flag Count",
]


# ==========================================================
# Étape 1 : Chargement et nettoyage
# ==========================================================
def load_dataset(path: str) -> pd.DataFrame:
    """Charge CICIDS2017 et nettoie les noms de colonnes."""
    if not os.path.exists(path):
        print(f"❌ Fichier introuvable : {path}")
        print("   Télécharge CICIDS2017 sur https://www.unb.ca/cic/datasets/ids-2017.html")
        print("   et place Tuesday-WorkingHours.pcap_ISCX.csv dans ce dossier.")
        sys.exit(1)

    print(f"[+] Chargement {path}...")
    df = pd.read_csv(path, low_memory=False)

    # CICIDS a souvent des espaces en début de colonnes
    df.columns = df.columns.str.strip()
    print(f"    {len(df):,} flux chargés")
    print(f"    Colonnes : {len(df.columns)}")
    return df


def filter_relevant(df: pd.DataFrame) -> pd.DataFrame:
    """Garde uniquement BENIGN + attaques par brute force."""
    print(f"\n[+] Distribution des labels :")
    print(df["Label"].value_counts())

    # On garde le trafic normal et les 2 types de brute force
    # (équivalent fonctionnel de nos attaques sur Keycloak)
    keep = ["BENIGN", "FTP-Patator", "SSH-Patator"]
    df = df[df["Label"].isin(keep)].copy()

    print(f"\n[+] Après filtrage (BENIGN + brute force) : {len(df):,} flux")
    return df


def clean_features(df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    """Sélectionne les features et nettoie inf/NaN."""
    # Vérifie que les colonnes existent
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        print(f"⚠️  Colonnes manquantes : {missing}")
        print(f"   Colonnes disponibles : {list(df.columns)[:20]}...")
        feature_cols = [c for c in feature_cols if c in df.columns]
        print(f"   On continue avec : {feature_cols}")

    X = df[feature_cols].copy()
    # Remplacer inf et NaN
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    return X, feature_cols


# ==========================================================
# Étape 2 : Entraînement (non supervisé, sur trafic normal uniquement)
# ==========================================================
def train_model(X_train_normal: np.ndarray, contamination: float = 0.05):
    """
    Approche non supervisée réaliste :
    on entraîne UNIQUEMENT sur du trafic légitime, le modèle apprend
    la "normalité" et flagge tout ce qui s'en écarte.
    """
    print(f"\n[+] Entraînement Isolation Forest")
    print(f"    Échantillons normaux : {len(X_train_normal):,}")
    print(f"    Contamination        : {contamination}")

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_normal)
    return model


# ==========================================================
# Étape 3 : Évaluation
# ==========================================================
def evaluate(model, X_test, y_test, scaler=None):
    """Calcule toutes les métriques académiques attendues."""
    if scaler is not None:
        X_test = scaler.transform(X_test)

    # Predict : -1 = anomalie/attaque, 1 = normal
    y_pred = (model.predict(X_test) == -1).astype(int)
    # Score continu : plus haut = plus anormal
    y_score = -model.decision_function(X_test)

    print("\n" + "=" * 60)
    print("RÉSULTATS - Validation externe sur CICIDS2017")
    print("=" * 60)

    # Classification report
    print("\nClassification report :")
    print(classification_report(
        y_test, y_pred, target_names=["BENIGN", "ATTACK"], digits=3
    ))

    # Matrice de confusion
    cm = confusion_matrix(y_test, y_pred)
    print("Matrice de confusion :")
    print(f"                Pred BENIGN   Pred ATTACK")
    print(f"Vrai BENIGN         {cm[0,0]:7d}      {cm[0,1]:7d}")
    print(f"Vrai ATTACK         {cm[1,0]:7d}      {cm[1,1]:7d}")

    # Métriques individuelles
    p, r, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="binary", zero_division=0
    )
    try:
        auc_roc = roc_auc_score(y_test, y_score)
    except Exception:
        auc_roc = None
    auc_pr = average_precision_score(y_test, y_score)

    print(f"\nMétriques :")
    print(f"  Precision : {p:.3f}")
    print(f"  Recall    : {r:.3f}")
    print(f"  F1-score  : {f1:.3f}")
    if auc_roc is not None:
        print(f"  ROC-AUC   : {auc_roc:.3f}")
    print(f"  PR-AUC    : {auc_pr:.3f}")

    return {
        "precision": p, "recall": r, "f1": f1,
        "roc_auc": auc_roc, "pr_auc": auc_pr,
        "confusion_matrix": cm.tolist(),
    }


# ==========================================================
# Étape 4 : Visualisation (optionnelle, pour le mémoire)
# ==========================================================
def plot_roc(model, X_test, y_test, scaler=None, output="roc_curve.png"):
    """Sauvegarde la courbe ROC en image (pour le mémoire)."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib non installé, skip plot")
        return

    if scaler is not None:
        X_test = scaler.transform(X_test)
    y_score = -model.decision_function(X_test)

    fpr, tpr, _ = roc_curve(y_test, y_score)
    auc = roc_auc_score(y_test, y_score)

    plt.figure(figsize=(7, 6))
    plt.plot(fpr, tpr, label=f"Isolation Forest (AUC = {auc:.3f})", linewidth=2)
    plt.plot([0, 1], [0, 1], "--", color="gray", label="Random")
    plt.xlabel("Taux de faux positifs")
    plt.ylabel("Taux de vrais positifs")
    plt.title("Courbe ROC - Détection d'anomalies sur CICIDS2017")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()
    print(f"\n[+] Courbe ROC sauvegardée -> {output}")


# ==========================================================
# Pipeline principal
# ==========================================================
def main():
    # 1. Charger et préparer
    df = load_dataset(CICIDS_FILE)
    df = filter_relevant(df)
    X, used_features = clean_features(df, FEATURES)
    y = (df["Label"] != "BENIGN").astype(int).values  # 1 = attaque

    print(f"\n[+] Features utilisées ({len(used_features)}) : {used_features}")
    print(f"[+] Distribution : {y.sum():,} attaques / {len(y):,} total "
          f"({y.mean()*100:.1f}%)")

    # 2. Standardisation (importante pour Isolation Forest avec features hétérogènes)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 3. Split train/test stratifié
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.3, random_state=42, stratify=y
    )

    # 4. Train uniquement sur le trafic BENIGN du train set
    X_train_normal = X_train[y_train == 0]

    # On limite à 50k pour la rapidité (CICIDS a des millions de flux)
    if len(X_train_normal) > 50000:
        idx = np.random.RandomState(42).choice(
            len(X_train_normal), 50000, replace=False
        )
        X_train_normal = X_train_normal[idx]

    # contamination ≈ proportion d'attaques attendue
    contamination = max(0.01, min(0.5, y_test.mean()))
    model = train_model(X_train_normal, contamination=contamination)

    # 5. Évaluation
    metrics = evaluate(model, X_test, y_test)

    # 6. Plot ROC
    plot_roc(model, X_test, y_test)

    # 7. Sauvegarde JSON pour le mémoire
    import json
    with open("cicids_results.json", "w") as f:
        json.dump({
            "dataset": "CICIDS2017",
            "features_used": used_features,
            "n_train_normal": len(X_train_normal),
            "n_test": len(X_test),
            "metrics": metrics,
        }, f, indent=2, default=str)
    print("\n[+] Résultats sauvegardés -> cicids_results.json")


if __name__ == "__main__":
    main()
