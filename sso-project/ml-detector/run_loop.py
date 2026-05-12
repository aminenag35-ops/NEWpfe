"""
Boucle de détection en continu.
Lance detect() toutes les 60 secondes.
À utiliser une fois le modèle entraîné.
"""
import time
import logging
import detector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ml-loop")

INTERVAL = 60  # secondes

if __name__ == "__main__":
    log.info(f"Boucle de détection démarrée (intervalle = {INTERVAL}s)")
    while True:
        try:
            detector.detect()
        except Exception as e:
            log.error(f"Erreur détection : {e}")
        time.sleep(INTERVAL)
