"""
APP 1 : Admin User Management
=============================
- Login SSO via Keycloak
- CRUD users via l'Admin REST API de Keycloak
- Gestion des rôles (admin / user / support)
- Activation / blocage d'utilisateurs
"""
from flask import Flask, render_template, redirect, request, session, url_for, flash
import os

import keycloak_lib as kc

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev")


# ==========================================================
# Auth (login / callback / logout)
# ==========================================================
@app.route("/")
def index():
    if "user" not in session:
        return render_template("login.html")
    return redirect(url_for("users"))


@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return redirect(kc.login_url(redirect_uri))


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Pas de code", 400

    redirect_uri = url_for("callback", _external=True)
    tokens = kc.exchange_code(code, redirect_uri)
    info = kc.userinfo(tokens["access_token"])
    info["roles"] = kc.parse_roles_from_token(tokens)

    session["user"] = info
    session["access_token"] = tokens["access_token"]
    return redirect(url_for("users"))


@app.route("/logout")
def logout():
    session.clear()
    redirect_uri = url_for("index", _external=True)
    return redirect(kc.logout_url(redirect_uri))


# ==========================================================
# CRUD Users (réservé aux admins)
# ==========================================================
@app.route("/users")
@kc.role_required("admin")
def users():
    r = kc.admin_api("GET", "/users")
    users_list = r.json() if r.ok else []
    return render_template("users.html", users=users_list, me=session["user"])


@app.route("/users/create", methods=["POST"])
@kc.role_required("admin")
def create_user():
    payload = {
        "username":  request.form["username"],
        "email":     request.form["email"],
        "firstName": request.form.get("firstName", ""),
        "lastName":  request.form.get("lastName", ""),
        "enabled":   True,
        "credentials": [{
            "type":  "password",
            "value": request.form["password"],
            "temporary": False,
        }],
    }
    r = kc.admin_api("POST", "/users", json=payload)
    flash("Utilisateur créé" if r.status_code == 201 else f"Erreur : {r.text}")
    return redirect(url_for("users"))


@app.route("/users/<user_id>/toggle", methods=["POST"])
@kc.role_required("admin")
def toggle_user(user_id):
    """Bloque ou débloque un utilisateur."""
    r = kc.admin_api("GET", f"/users/{user_id}")
    if not r.ok:
        flash("Utilisateur introuvable")
        return redirect(url_for("users"))
    user = r.json()
    user["enabled"] = not user.get("enabled", True)
    kc.admin_api("PUT", f"/users/{user_id}", json=user)
    flash(f"Utilisateur {'activé' if user['enabled'] else 'bloqué'}")
    return redirect(url_for("users"))


@app.route("/users/<user_id>/delete", methods=["POST"])
@kc.role_required("admin")
def delete_user(user_id):
    kc.admin_api("DELETE", f"/users/{user_id}")
    flash("Utilisateur supprimé")
    return redirect(url_for("users"))


@app.route("/users/<user_id>/roles", methods=["GET", "POST"])
@kc.role_required("admin")
def user_roles(user_id):
    if request.method == "POST":
        # Récupère les rôles realm disponibles
        all_roles = kc.admin_api("GET", "/roles").json()
        # Rôles actuels de l'utilisateur
        current = kc.admin_api("GET", f"/users/{user_id}/role-mappings/realm").json()
        wanted_names = request.form.getlist("roles")

        # À ajouter
        to_add = [r for r in all_roles if r["name"] in wanted_names
                  and r["name"] not in [c["name"] for c in current]]
        if to_add:
            kc.admin_api("POST", f"/users/{user_id}/role-mappings/realm", json=to_add)

        # À retirer
        to_remove = [c for c in current if c["name"] not in wanted_names
                     and c["name"] in ("admin", "user", "support")]
        if to_remove:
            kc.admin_api("DELETE", f"/users/{user_id}/role-mappings/realm", json=to_remove)

        flash("Rôles mis à jour")
        return redirect(url_for("users"))

    # GET : afficher le formulaire
    user = kc.admin_api("GET", f"/users/{user_id}").json()
    current = kc.admin_api("GET", f"/users/{user_id}/role-mappings/realm").json()
    current_names = [r["name"] for r in current]
    return render_template("roles.html", user=user, current=current_names,
                           all_roles=["admin", "user", "support"], me=session["user"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
