"""
Évaluation académique du modèle de détection.
==============================================
Fournit precision / recall / F1 / matrice de confusion / ROC-AUC
sur le dataset labellisé. Pour ton mémoire.

Prérequis : avoir lancé export_labeled_dataset.py (avec ATTACK_WINDOWS rempli).

Usage :
    python evaluate.py
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, precision_recall_fscore_support
)

CSV = "dataset_features.csv"

FEATURES = ["n_events", "n_failures", "n_distinct_users",
            "n_distinct_agents", "fail_ratio"]


def main():
    df = pd.read_csv(CSV)
    print(f"Dataset : {len(df)} lignes, {df['is_attack'].sum()} attaques\n")

    if df["is_attack"].sum() < 5:
        print("⚠️  Pas assez d'exemples positifs pour évaluer correctement.")
        print("   Lance plus de sessions d'attaque ou élargis ATTACK_WINDOWS.")
        return

    X = df[FEATURES].fillna(0).values
    y = df["is_attack"].astype(int).values

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    # On entraîne UNIQUEMENT sur les normaux (approche non supervisée réaliste)
    X_train_normal = X_train[y_train == 0]
    print(f"Train (uniquement normaux) : {len(X_train_normal)}")
    print(f"Test : {len(X_test)} dont {y_test.sum()} attaques\n")

    # Contamination ≈ proportion attendue d'anomalies dans le test
    contamination = max(0.01, y_test.mean())
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    model.fit(X_train_normal)

    # Prédictions
    y_pred = (model.predict(X_test) == -1).astype(int)
    y_score = -model.decision_function(X_test)  # plus haut = plus anormal

    # Métriques
    print("=" * 60)
    print("RÉSULTATS")
    print("=" * 60)
    print(classification_report(y_test, y_pred, target_names=["normal", "attaque"]))

    cm = confusion_matrix(y_test, y_pred)
    print("Matrice de confusion :")
    print(f"             Pred Normal  Pred Attaque")
    print(f"Vrai Normal      {cm[0,0]:5d}        {cm[0,1]:5d}")
    print(f"Vrai Attaque     {cm[1,0]:5d}        {cm[1,1]:5d}")
    print()

    try:
        auc = roc_auc_score(y_test, y_score)
        print(f"ROC-AUC : {auc:.3f}")
    except Exception as e:
        print(f"ROC-AUC : impossible ({e})")

    p, r, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary",
                                                  zero_division=0)
    print(f"Precision : {p:.3f}")
    print(f"Recall    : {r:.3f}")
    print(f"F1-score  : {f1:.3f}")

    # Sauvegarde JSON pour la comparaison avec CICIDS2017
    import json
    auc_val = None
    try:
        auc_val = float(roc_auc_score(y_test, y_score))
    except Exception:
        pass
    results = {
        "dataset": "Keycloak (interne)",
        "features_used": FEATURES,
        "n_train_normal": int(len(X_train_normal)),
        "n_test": int(len(X_test)),
        "metrics": {
            "precision": float(p),
            "recall":    float(r),
            "f1":        float(f1),
            "roc_auc":   auc_val,
            "confusion_matrix": cm.tolist(),
        },
    }
    with open("keycloak_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n[+] Résultats sauvegardés -> keycloak_results.json")


if __name__ == "__main__":
    main()
