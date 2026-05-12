"""
Comparaison des résultats : modèle sur Keycloak vs CICIDS2017
==============================================================
Génère un tableau de comparaison à inclure dans ton mémoire.

Prérequis :
  1. Avoir lancé evaluate.py (sur tes données Keycloak)
     -> sauvegarde keycloak_results.json
  2. Avoir lancé validate_on_cicids.py (sur CICIDS2017)
     -> sauvegarde cicids_results.json
"""

import json
import os

KEYCLOAK_JSON = "../keycloak_results.json"
CICIDS_JSON   = "cicids_results.json"


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def main():
    kc = load_json(KEYCLOAK_JSON)
    ci = load_json(CICIDS_JSON)

    if not kc:
        print(f"⚠️  {KEYCLOAK_JSON} introuvable. Lance d'abord evaluate.py")
    if not ci:
        print(f"⚠️  {CICIDS_JSON} introuvable. Lance d'abord validate_on_cicids.py")
    if not kc or not ci:
        return

    km = kc.get("metrics", kc)  # selon comment c'est sauvé
    cm = ci["metrics"]

    print("=" * 70)
    print("COMPARAISON : Keycloak (nos données) vs CICIDS2017 (référence)")
    print("=" * 70)
    print()
    print(f"{'Métrique':<15} {'Keycloak (perso)':>20} {'CICIDS2017':>20}")
    print("-" * 70)

    metrics = ["precision", "recall", "f1", "roc_auc", "pr_auc"]
    for m in metrics:
        v_kc = km.get(m, "N/A")
        v_ci = cm.get(m, "N/A")
        v_kc_str = f"{v_kc:.3f}" if isinstance(v_kc, (int, float)) else str(v_kc)
        v_ci_str = f"{v_ci:.3f}" if isinstance(v_ci, (int, float)) else str(v_ci)
        print(f"{m:<15} {v_kc_str:>20} {v_ci_str:>20}")

    print()
    print("=" * 70)
    print("Pour ton mémoire :")
    print("=" * 70)
    print("""
Tableau LaTeX prêt à copier :

\\begin{table}[h]
\\centering
\\caption{Comparaison des performances : dataset interne vs CICIDS2017}
\\label{tab:comparaison}
\\begin{tabular}{lcc}
\\toprule
Métrique & Keycloak (généré) & CICIDS2017 \\\\
\\midrule
""")
    for m in metrics:
        v_kc = km.get(m)
        v_ci = cm.get(m)
        if isinstance(v_kc, (int, float)) and isinstance(v_ci, (int, float)):
            print(f"{m.replace('_', '-').capitalize():<10} & {v_kc:.3f} & {v_ci:.3f} \\\\")
    print("""\\bottomrule
\\end{tabular}
\\end{table}
""")


if __name__ == "__main__":
    main()
