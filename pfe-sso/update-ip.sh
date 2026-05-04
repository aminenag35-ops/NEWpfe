#!/bin/bash
# update-ip.sh — Met à jour l'IP partout depuis .env
cd "$(dirname "$0")"
source .env
sed -i "s|http://[0-9.]*:|http://${SERVER_IP}:|g" keycloak/realm-export.json
echo "✓ realm-export.json mis à jour vers ${SERVER_IP}"
