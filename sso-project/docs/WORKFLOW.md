# 🎯 Workflow complet — Approche "Hydra/Burp + CICIDS2017"

Ce guide t'explique **dans quel ordre** lancer les choses pour produire un mémoire de PFE solide.

## Vue d'ensemble du processus

```
Phase 1 - Setup                    [1 jour]
   ↓
Phase 2 - Génération de trafic     [1-2 jours]
   ↓
Phase 3 - Entraînement ML          [1 jour]
   ↓
Phase 4 - Évaluation interne       [1 jour]
   ↓
Phase 5 - Validation externe       [2 jours]   ← C'est CICIDS2017
   ↓
Phase 6 - Rédaction mémoire        [reste du temps]
```

---

## Phase 1 — Setup (jour 1)

### A. Démarrer la stack
```bash
cd sso-project
./start.sh
# Importer le realm via http://<ip>:8080
```

### B. Installer les outils d'attaque
**Sur ta machine d'attaque (Kali en VM ou Windows + WSL) :**
```bash
sudo apt install hydra
# OU
choco install hydra        # Windows
```

**Burp Suite Community** : télécharger depuis portswigger.net

### C. Vérifier le pipeline
```bash
# Test rapide : connexion via app tickets
# http://<ip>:5002/login
# Tu dois voir des events dans Postgres :
docker exec -it sso_postgres psql -U postgres -d logsdb \
  -c "SELECT count(*) FROM auth_events;"
```

---

## Phase 2 — Génération de trafic (jours 2-3)

### A. Trafic légitime (BASELINE - INDISPENSABLE)

```bash
# Sur ta machine d'attaque, en arrière-plan :
python attack-scripts/normal_traffic.py http://192.168.1.50:8080 60  # 60 minutes
```

**Pourquoi 60 min minimum ?** Le modèle ML a besoin d'au moins quelques centaines d'événements normaux pour apprendre la baseline. Plus tu en as, mieux c'est.

### B. Sessions d'attaque ESPACÉES dans le temps

Le piège classique : lancer toutes tes attaques en 5 min. Le modèle voit alors un seul gros pic et fait du mauvais apprentissage. Il faut des sessions **espacées** :

```bash
# JOUR 2 - Session 1 (matin)
START=$(date '+%Y-%m-%d %H:%M:%S') ; echo "DEBUT: $START"
./attack-scripts/hydra/run_hydra_bruteforce.sh 192.168.1.50 alice
END=$(date '+%Y-%m-%d %H:%M:%S') ; echo "FIN: $END"
# -> Note les horodatages !

# Pause d'au moins 30 min : laisse le trafic légitime "respirer"
sleep 1800

# JOUR 2 - Session 2 (après-midi)
./attack-scripts/hydra/run_hydra_spraying.sh 192.168.1.50 "Password123!"

# JOUR 3 - Session 3 (matin)
# Burp Suite Pitchfork attack (cf. attack-scripts/burp/README.md)

# JOUR 3 - Session 4 (après-midi)
python attack-scripts/credential_stuffing.py http://192.168.1.50:8080
```

### C. Construire le ground truth

À la fin, tu as une liste précise de fenêtres d'attaque. Édite le fichier :

```python
# ml-detector/export_labeled_dataset.py
ATTACK_WINDOWS = [
    ("2024-12-15 09:00:00", "2024-12-15 09:08:00", "hydra_bruteforce",     None),
    ("2024-12-15 14:30:00", "2024-12-15 14:42:00", "hydra_spraying",       None),
    ("2024-12-16 10:00:00", "2024-12-16 10:15:00", "burp_pitchfork",       None),
    ("2024-12-16 15:00:00", "2024-12-16 15:05:00", "credential_stuffing",  None),
]
```

---

## Phase 3 — Entraînement ML (jour 4)

### A. Construire le dataset labellisé

```bash
cd ml-detector
python export_labeled_dataset.py
# -> dataset_events.csv  (1 ligne = 1 event)
# -> dataset_features.csv (1 ligne = 1 IP × fenêtre 5 min, AVEC label)
```

### B. Vérifier le dataset

```bash
head dataset_features.csv
# Dois voir des lignes avec is_attack=True ET False
# Compte des attaques :
grep -c "True" dataset_features.csv
```

### C. Entraîner le modèle de détection en ligne

```bash
python detector.py train
# -> model.pkl
```

### D. Lancer la détection en continu

```bash
nohup python run_loop.py > ml.log 2>&1 &
# -> les alertes apparaissent dans le dashboard temps réel
```

---

## Phase 4 — Évaluation interne (jour 5)

```bash
python evaluate.py
```

**Sortie type** :
```
=== RÉSULTATS ===
Precision : 0.870
Recall    : 0.910
F1-score  : 0.890
ROC-AUC   : 0.940

[+] Résultats sauvegardés -> keycloak_results.json
```

**Interprétation pour le mémoire :**
- Precision = sur les alertes émises, combien sont de vraies attaques
- Recall = sur toutes les attaques, combien on a détectées
- F1 = harmonique des deux
- ROC-AUC > 0.9 = excellent pouvoir discriminant

---

## Phase 5 — Validation externe sur CICIDS2017 (jours 6-7)

### A. Télécharger CICIDS2017

Voir `ml-detector/cicids/README.md` (formulaire CIC, gratuit, instantané).

### B. Lancer la validation

```bash
cd ml-detector/cicids
python validate_on_cicids.py
# -> cicids_results.json
# -> roc_curve.png
```

### C. Générer le tableau comparatif

```bash
python compare_results.py
# -> tableau ASCII + LaTeX prêt à coller dans ton mémoire
```

---

## Phase 6 — Rédaction du mémoire

### Structure recommandée du chapitre "Évaluation"

**Chapitre X : Évaluation expérimentale**

```
X.1  Génération du jeu de données
     X.1.1  Trafic légitime (générateur Python)
     X.1.2  Trafic malveillant
            - Hydra (T1110.001 Brute Force)
            - Hydra (T1110.003 Password Spraying)
            - Burp Suite Intruder (Pitchfork strategy)
            - Script custom (T1110.004 Credential Stuffing)
     X.1.3  Procédure de labellisation

X.2  Métriques d'évaluation
     X.2.1  Métriques retenues : precision, recall, F1, ROC-AUC
     X.2.2  Justification du choix de F1 (datasets déséquilibrés)

X.3  Évaluation sur le dataset interne (Keycloak)
     X.3.1  Protocole : split 70/30 stratifié
     X.3.2  Résultats : [tableau]
     X.3.3  Analyse des erreurs : faux positifs / faux négatifs

X.4  Validation externe sur CICIDS2017
     X.4.1  Présentation du dataset
     X.4.2  Adaptation du modèle aux features réseau
     X.4.3  Résultats : [tableau]
     X.4.4  Discussion comparative

X.5  Synthèse
     X.5.1  Forces de l'approche
     X.5.2  Limites identifiées
     X.5.3  Pistes d'amélioration
```

### Limites à mentionner (te fait gagner des points)

> *Les principales limites de cette évaluation sont :*
> - *Volume de trafic légitime relativement faible (quelques milliers d'événements vs millions dans des SOC réels)*
> - *Diversité limitée des comportements légitimes simulés (3 utilisateurs uniquement)*
> - *Absence d'attaques sophistiquées : slow brute force réparti sur des semaines, attaques distribuées via Tor, evasion par variation des User-Agents*
> - *Contexte limité à OAuth2/HTTP : la validation sur CICIDS2017 (FTP/SSH) ne couvre pas tous les protocoles d'authentification existants*

---

## Récap calendrier suggéré (2 semaines)

| Semaine | Jour | Tâche |
|---------|------|-------|
| 1 | L | Setup stack + tests SSO |
| 1 | Ma | Installation outils attaque + tests Hydra |
| 1 | Me | Génération trafic légitime + 2 sessions attaque |
| 1 | J | 2 autres sessions + entraînement modèle |
| 1 | V | Évaluation interne |
| 2 | L | Téléchargement et exploration CICIDS2017 |
| 2 | Ma | Adaptation script + premières validations |
| 2 | Me | Génération graphiques + tableau comparatif |
| 2 | J-V | Rédaction chapitre évaluation |

---

## En cas de problème

**Le ML n'apprend rien** → tu n'as pas assez de trafic légitime. Lance `normal_traffic.py 120` (2h) avant de relancer les attaques.

**Trop de faux positifs** → ajuste `contamination` dans `detector.py` (par défaut 0.1, essaie 0.05).

**CICIDS donne F1 très bas (< 0.3)** → c'est normal en non supervisé sur ce dataset. Compare avec Isolation Forest dans la littérature, tu seras dans la fourchette.

**ROC-AUC sur Keycloak = 1.0** → suspicieux. Probablement un leak entre train et test. Vérifie que tu fais bien `train_test_split(stratify=y)` et que tu n'entraînes que sur les normaux.
