from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import os, csv
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "replace_this_with_a_real_secret"

# Config
RESUMES_FOLDER = os.path.join(app.root_path, "resumes")
USERS_CSV = os.path.join(app.root_path, "users.csv")
SUBMISSIONS_CSV = os.path.join(app.root_path, "submissions.csv")
ALLOWED_EXT = {".pdf"}

# Ensure folders & CSVs exist
os.makedirs(RESUMES_FOLDER, exist_ok=True)

if not os.path.exists(USERS_CSV):
    with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Email", "Password", "IsAdmin"])  # IsAdmin = "1" for admin, else "0" or blank
        # create default admin (email: admin@admin.com, password: admin123)
        writer.writerow(["admin@admin.com", "admin123", "1"])

if not os.path.exists(SUBMISSIONS_CSV):
    with open(SUBMISSIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Email", "Skills", "Filename"])

# ---------- Helpers ----------
def calc_score(skills_text: str) -> int:
    if not skills_text:
        return 0
    count = len([s for s in skills_text.split(",") if s.strip()])
    return min(count * 10, 100)

def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXT

def user_is_admin(email: str) -> bool:
    if not os.path.exists(USERS_CSV):
        return False
    with open(USERS_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("Email") == email and row.get("IsAdmin") == "1":
                return True
    return False

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if not email or not password:
            flash("Provide email and password", "danger")
            return redirect(url_for("signup"))

        # check duplicate
        with open(USERS_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Email") == email:
                    flash("Account already exists. Please login.", "warning")
                    return redirect(url_for("login"))

        with open(USERS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([email, password, "0"])

        flash("Account created. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        found = False
        is_admin = False
        with open(USERS_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Email") == email and row.get("Password") == password:
                    found = True
                    is_admin = (row.get("IsAdmin") == "1")
                    break
        if found:
            session["user"] = email
            session["is_admin"] = bool(is_admin)
            flash("Logged in successfully", "success")
            # redirect admin to admin page, others to upload
            if is_admin:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("upload"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("is_admin", None)
    flash("Logged out", "info")
    return redirect(url_for("home"))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user" not in session:
        flash("Please login to upload resume", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        resume = request.files.get("resume")

        if not (name and email and skills and resume):
            flash("All fields required", "danger")
            return redirect(url_for("upload"))

        if not allowed_file(resume.filename):
            flash("Only PDF resumes are allowed", "danger")
            return redirect(url_for("upload"))

        filename = secure_filename(resume.filename)
        save_path = os.path.join(RESUMES_FOLDER, filename)

        # avoid overwriting: add numeric suffix if exists
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(save_path):
            filename = f"{base}_{counter}{ext}"
            save_path = os.path.join(RESUMES_FOLDER, filename)
            counter += 1

        resume.save(save_path)

        with open(SUBMISSIONS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([name, email, skills, filename])

        flash("Resume uploaded successfully", "success")
        return redirect(url_for("upload"))

    return render_template("upload.html")

@app.route("/admin")
def admin_dashboard():
    # Only admin allowed
    if not session.get("is_admin"):
        flash("Admin access required", "danger")
        return redirect(url_for("login"))

    search_skill = (request.args.get("skill") or "").lower().strip()
    rows = []
    if os.path.exists(SUBMISSIONS_CSV):
        with open(SUBMISSIONS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                skills = row.get("Skills", "") or ""
                if not search_skill or search_skill in skills.lower():
                    # attach dynamic Score as integer
                    row["Score"] = calc_score(skills)
                    rows.append(row)
    # sort by Score descending
    rows.sort(key=lambda r: r["Score"], reverse=True)
    return render_template("admin.html", data=rows, skill=search_skill)

@app.route("/resumes/<path:filename>")
def serve_resume(filename):
    # Serve from resumes folder
    return send_from_directory(RESUMES_FOLDER, filename, as_attachment=False)

# Run app
if __name__ == "__main__":
    app.run(debug=True)
