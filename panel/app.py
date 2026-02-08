from flask import Flask, request, render_template, redirect, url_for, session, flash
import os
import subprocess

app = Flask(__name__)
app.secret_key = os.urandom(24)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
HTPASSWD_FILE = "/auth/.htpasswd"

def check_auth(username, password):
    return username == "admin" and password == ADMIN_PASSWORD

@app.route("/panel/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if check_auth(request.form["username"], request.form["password"]):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid credentials")
    return render_template("login.html")

@app.route("/panel/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/panel/")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    users = []
    if os.path.exists(HTPASSWD_FILE):
        with open(HTPASSWD_FILE, "r") as f:
            for line in f:
                if ":" in line:
                    users.append(line.split(":")[0])
    return render_template("dashboard.html", users=users)

@app.route("/panel/add", methods=["POST"])
def add_user():
    if not session.get("logged_in"): return redirect(url_for("login"))
    username = request.form["username"]
    password = request.form["password"]
    if username and password:
        if not os.path.exists(HTPASSWD_FILE):
            subprocess.run(["touch", HTPASSWD_FILE])
        subprocess.run(["htpasswd", "-b", "-B", HTPASSWD_FILE, username, password])
        flash(f"User {username} added")
    return redirect(url_for("dashboard"))

@app.route("/panel/delete", methods=["POST"])
def delete_user():
    if not session.get("logged_in"): return redirect(url_for("login"))
    username = request.form["username"]
    if username:
        subprocess.run(["htpasswd", "-D", HTPASSWD_FILE, username])
        flash(f"User {username} deleted")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
