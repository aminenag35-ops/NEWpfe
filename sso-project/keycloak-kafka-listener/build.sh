#!/bin/bash
# ==========================================================
# Build du JAR Keycloak Event Listener
# Utilise un conteneur Maven : pas besoin d'installer Maven
# sur l'hôte Ubuntu
# ==========================================================
set -e

cd "$(dirname "$0")"

echo "[+] Build du JAR Keycloak SPI via Docker Maven..."

docker run --rm \
  -v "$PWD":/app \
  -w /app \
  maven:3.9-eclipse-temurin-17 \
  mvn clean package -DskipTests

echo ""
echo "[+] OK - JAR généré dans : $PWD/build/keycloak-kafka-listener.jar"
echo "[+] Il sera monté automatiquement par docker-compose dans Keycloak."
