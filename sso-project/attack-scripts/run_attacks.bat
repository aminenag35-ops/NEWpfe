@echo off
REM ==========================================================
REM Lancement automatique de scenarios d'attaque
REM Usage : run_attacks.bat <ip_ubuntu>
REM Exemple : run_attacks.bat 192.168.1.50
REM ==========================================================

if "%1"=="" (
    echo Usage: run_attacks.bat ^<ip_ubuntu^>
    exit /b 1
)

set TARGET=http://%1:8080

echo ============================================================
echo  Scenarios d'attaque sur %TARGET%
echo ============================================================
echo.

echo [1/4] Trafic legitime (5 min en arriere-plan)...
start /b python normal_traffic.py %TARGET% 5

echo [2/4] Brute force sur alice (attendre 10s pour creer un ecart)...
timeout /t 10 /nobreak >nul
python brute_force.py %TARGET% alice

echo [3/4] Credential stuffing...
timeout /t 5 /nobreak >nul
python credential_stuffing.py %TARGET%

echo [4/4] Password spraying...
timeout /t 5 /nobreak >nul
python password_spraying.py %TARGET% Password123!

echo.
echo ============================================================
echo  Termine. Verifie le dashboard : http://%1:5003
echo ============================================================
pause
