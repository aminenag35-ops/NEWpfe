#!/bin/bash
# ==========================================================
# ORCHESTRATEUR D'ATTAQUES
# =========== ===============================================
# Lance toutes les attaques dans le bon ordre, avec des pauses,
# et génère automatiquement le fichier ATTACK_WINDOWS pour la
# labellisation du dataset ML.
#
# Usage : ./run_all_attacks.sh <ip-keycloak>
# Exemple : ./run_all_attacks.sh 192.168.1.16
# ==========================================================
set -e

IP=${1:-192.168.1.16}
LOG=attacks_timeline.log
WINDOWS_FILE=attack_windows.py

# Pause entre attaques (secondes). Mets 60-120 pour des tests rapides,
# 600-1800 pour un protocole scientifique propre.
PAUSE=${PAUSE:-300}

cd "$(dirname "$0")"

# Init fichiers
> $LOG
echo "# Généré automatiquement par run_all_attacks.sh" > $WINDOWS_FILE
echo "# Copie cette liste dans ml-detector/export_labeled_dataset.py" >> $WINDOWS_FILE
echo "" >> $WINDOWS_FILE
echo "ATTACK_WINDOWS = [" >> $WINDOWS_FILE

# Helper : enregistre une attaque dans le timeline
log_attack() {
    local name=$1
    local start=$2
    local end=$3
    echo "[$name] $start -> $end" | tee -a $LOG
    echo "    (\"$start\", \"$end\", \"$name\", None)," >> $WINDOWS_FILE
}

run_attack() {
    local name=$1
    shift
    local start=$(date '+%Y-%m-%d %H:%M:%S')
    echo ""
    echo "============================================================"
    echo " ATTAQUE: $name"
    echo " DÉBUT: $start"
    echo "============================================================"
    "$@" || echo "[!] Attaque $name terminée avec une erreur (ok)"
    local end=$(date '+%Y-%m-%d %H:%M:%S')
    log_attack "$name" "$start" "$end"
    echo " FIN: $end"
}

pause() {
    echo ""
    echo ">>> Pause de $PAUSE secondes (laisse le trafic légitime respirer)..."
    sleep $PAUSE
}

# ==========================================================
# DÉBUT
# ==========================================================
SESSION_START=$(date '+%Y-%m-%d %H:%M:%S')
echo ""
echo "=================================================================="
echo "  CAMPAGNE D'ATTAQUES - DÉBUT $SESSION_START"
echo "  Cible : http://$IP:8080"
echo "  Pause entre attaques : ${PAUSE}s"
echo "=================================================================="
echo "[INFO] Assure-toi qu'un trafic légitime tourne en parallèle :"
echo "       python normal_traffic.py http://$IP:8080 180"
echo ""
read -p "Appuie sur Entrée pour démarrer..."

# ==========================================================
# ATTAQUE 1 : Brute force Hydra ciblé sur alice
# ==========================================================
run_attack "hydra_bruteforce_alice" \
    bash hydra/run_hydra_bruteforce.sh "$IP" alice
pause

# ==========================================================
# ATTAQUE 2 : Password spraying Hydra
# ==========================================================
run_attack "hydra_password_spraying" \
    bash hydra/run_hydra_spraying.sh "$IP" "Password123!"
pause

# ==========================================================
# ATTAQUE 3 : Credential stuffing (couples user/pwd + IPs simulées)
# ==========================================================
run_attack "credential_stuffing" \
    python credential_stuffing.py "http://$IP:8080"
pause

# ==========================================================
# ATTAQUE 4 : Account enumeration (découverte usernames)
# ==========================================================
run_attack "account_enumeration" \
    python account_enumeration.py "http://$IP:8080"
pause

# ==========================================================
# ATTAQUE 5 : Bot rapide (cadence inhumaine)
# ==========================================================
run_attack "bot_rapide" \
    python bot_rapide.py "http://$IP:8080" 30 5
pause

# ==========================================================
# ATTAQUE 6 : Login distribué (proxies simulés)
# ==========================================================
run_attack "login_distribue" \
    python login_distribue.py "http://$IP:8080" alice 50

# ==========================================================
# FIN
# ==========================================================
echo "]" >> $WINDOWS_FILE

SESSION_END=$(date '+%Y-%m-%d %H:%M:%S')
echo ""
echo "=================================================================="
echo "  CAMPAGNE TERMINÉE"
echo "  Début : $SESSION_START"
echo "  Fin   : $SESSION_END"
echo "=================================================================="
echo ""
echo "📋 Timeline complet : $LOG"
echo "📋 Liste pour labellisation : $WINDOWS_FILE"
echo ""
echo "Prochaines étapes :"
echo "  1. cat $WINDOWS_FILE"
echo "  2. Copie le contenu dans ml-detector/export_labeled_dataset.py"
echo "  3. cd ../ml-detector && python export_labeled_dataset.py"
echo "  4. python detector.py train"
echo "  5. python evaluate.py"
