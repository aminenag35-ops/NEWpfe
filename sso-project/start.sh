#!/bin/bash
# ==========================================================
# Script de démarrage automatique du projet
# Usage : ./start.sh
# ==========================================================
set -e

cd "$(dirname "$0")"

echo "==> [1/4] Build du JAR Keycloak SPI..."
if [ ! -f "keycloak-kafka-listener/build/keycloak-kafka-listener.jar" ]; then
    cd keycloak-kafka-listener
    chmod +x build.sh
    ./build.sh
    cd ..
else
    echo "    JAR déjà présent, skip."
fi

echo ""
echo "==> [2/4] Lancement de la stack Docker..."
docker compose up -d

echo ""
echo "==> [3/4] Attente que les services soient prêts (60s)..."
sleep 60

echo ""
echo "==> [4/4] Vérification..."
docker compose ps

echo ""
echo "============================================================"
echo "✅ Stack démarrée."
echo ""
echo "Prochaines étapes manuelles :"
echo "  1. Importer le realm dans Keycloak :"
echo "     -> http://localhost:8080  (admin / admin)"
echo "     -> Create Realm > upload keycloak-realm-export.json"
echo ""
echo "  2. Tester les apps :"
echo "     -> http://localhost:5001  (admin app)"
echo "     -> http://localhost:5002  (tickets)"
echo "     -> http://localhost:5003  (dashboard)"
echo ""
echo "  3. Vérifier que les events arrivent :"
echo "     docker exec -it sso_kafka kafka-console-consumer \\"
echo "       --bootstrap-server kafka:9092 --topic keycloak-events"
echo "============================================================"
