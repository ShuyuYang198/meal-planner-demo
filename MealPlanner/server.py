"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os

# accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, url_for, flash, make_response
from datetime import date, timedelta, datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
app = Flask(__name__, template_folder=tmpl_dir)
from local_database import get_engine
import secrets
from pathlib import Path
secret_file = Path(__file__).with_name(".session-key")
if not secret_file.exists():
    secret_file.write_text(secrets.token_hex(32))
    secret_file.chmod(0o600)
app.secret_key = secret_file.read_text().strip()
engine = get_engine()

@app.context_processor
def inject_user():
    return {"current_user": g.user}

@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.

    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()

    except:
        print("uh oh, problem connecting to database")
        import traceback

        traceback.print_exc()
        g.conn = None
    
    g.user = None
    username = request.cookies.get("currentUser")
    if username:
        g.user = get_user_by_name(username)

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass

""" Useful Constants """
DIET_OPTIONS = ('vegan','vegetarian','keto','pescatarian','gluten-free')


""" Helper functions used throughout our application. """
# ----------------------------------------------------------------------------

def require_login():
    if not g.user:
        flash("Please log in first.")
        return redirect(url_for("auth_page"))
    return None

def get_user_by_name(name):
    if not g.conn:
        return None
    
    return g.conn.execute( text('SELECT user_id, name, email FROM "user" WHERE name = :n LIMIT 1'), {"n": name},
    ).mappings().first()

def get_user_by_email(email):
    if not g.conn:
        return None
    
    return g.conn.execute(
        text('SELECT user_id, name, email FROM "user" WHERE email = :e LIMIT 1'), {"e": email},
    ).mappings().first()

def create_user(name, email):
    try:
        res = g.conn.execute(
                    text("""
                        INSERT INTO "user"(name, email)
                        VALUES (:n, :e)
                        RETURNING user_id, name, email
                    """), 
                    {"n": name, "e": email}
        )
        row = res.mappings().first()
        g.conn.commit()
        return row
    except Exception as e:
        print("Error creating user:", e)
        g.conn.rollback()
        return None

def _get_pref_row(user_id):
    return g.conn.execute(
        text("SELECT diet, allergies FROM user_pref WHERE user_id=:u"),
        {"u": user_id}
    ).mappings().first()

def _set_pref_row(user_id, diet, allergies):
    g.conn.execute(text("""
        INSERT INTO user_pref (user_id, diet, allergies)
        VALUES (:u, :d, :a)
        ON CONFLICT (user_id)
        DO UPDATE SET diet = EXCLUDED.diet, allergies = EXCLUDED.allergies
    """), {"u": user_id, "d": diet, "a": allergies})
    g.conn.commit()

def _tokenize_allergies(raw):
    if not raw: return []
    return [t.strip() for t in raw.split(",") if t.strip()]

def _week_monday(d):
 return d - timedelta(days=d.weekday())  # Monday
# ----------------------------------------------------------------------------



# PROTIP: (the trailing / in the path is important)
# see for routing: https://flask.palletsprojects.com/en/1.1.x/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/for_you")
def for_you():
    gate = require_login()
    if gate: 
        return gate

    pref = g.conn.execute(text("""
      SELECT diet, allergies 
      FROM user_pref 
      WHERE user_id = :u
    """), {"u": g.user["user_id"]}).mappings().first() or {"diet": None, "allergies": None}

    params = {}

    alerg_tokens = _tokenize_allergies(pref["allergies"])
    allergy_clause = ""
    if alerg_tokens:
        or_parts, dynamic = [], {}
        for idx, tok in enumerate(alerg_tokens):
            key = f"a{idx}"
            or_parts.append(f"i.name LIKE :{key}")
            dynamic[key] = f"%{tok}%"
        allergy_clause = (
            "AND NOT EXISTS ("
            "  SELECT 1"
            "  FROM recipe_ingredient ri"
            "  JOIN ingredient i ON i.ingredient_id = ri.ingredient_id"
            "  WHERE ri.recipe_id = r.recipe_id"
            "    AND (" + " OR ".join(or_parts) + ")"
            ")"
        )
        params.update(dynamic)

    diet_clause = ""
    sel_diet = (pref["diet"] or "").strip().lower()
    if sel_diet in DIET_OPTIONS:
        diet_clause = (
            "AND EXISTS ("
            "  SELECT 1 FROM recipe_diet rd"
            "  WHERE rd.recipe_id = r.recipe_id"
            "    AND lower(rd.diet) = :diet"
            ")"
        )
        params["diet"] = sel_diet

    sql = f"""
      WITH c AS (
        SELECT rc.recipe_id, COUNT(*) AS comments_30
        FROM recipe_comment rc
        WHERE rc.created_at >= datetime('now', '-30 days')
        GROUP BY rc.recipe_id
      ),
      m AS (
        SELECT mi.recipe_id, COUNT(*) AS adds_30
        FROM mealplan_item mi
        WHERE mi.meal_date >= date('now', '-30 days')
        GROUP BY mi.recipe_id
      )
      SELECT 
        r.recipe_id, 
        r.title, 
        u.name AS chef,
        COALESCE(c.comments_30, 0) AS comments_30,
        COALESCE(m.adds_30, 0)     AS adds_30
      FROM recipe r
      JOIN chef ch   ON ch.user_id = r.author_id
      JOIN "user" u  ON u.user_id  = ch.user_id
      LEFT JOIN c    ON c.recipe_id = r.recipe_id
      LEFT JOIN m    ON m.recipe_id = r.recipe_id
      WHERE 1=1
        {allergy_clause}
        {diet_clause}
      ORDER BY (COALESCE(c.comments_30,0)*2 + COALESCE(m.adds_30,0)) DESC,
               r.title ASC
      LIMIT 50
    """

    rows = g.conn.execute(text(sql), params).mappings().all()
    return render_template("for_you.html", rows=rows, pref=pref)


@app.route("/prefs", methods=["GET","POST"])
def prefs():
    gate = require_login()
    if gate: return gate

    uid = g.user["user_id"]

    if request.method == "POST":
        op = (request.form.get("op") or "save").strip()

        # Load current
        pref = _get_pref_row(uid) or {"diet": None, "allergies": None}
        cur_diet = (pref["diet"] or "").strip() or None
        cur_all = _tokenize_allergies(pref["allergies"])

        if op == "remove_allergy":
            tok = (request.form.get("token") or "").strip()
            new_list = [t for t in cur_all if t.lower() != tok.lower()]
            _set_pref_row(uid, cur_diet, ", ".join(new_list) if new_list else None)
            flash(f"Removed allergy: {tok}")
            return redirect(url_for("prefs"))

        if op == "add_allergy":
            tok = (request.form.get("token") or "").strip()
            if tok and tok.lower() not in [t.lower() for t in cur_all]:
                cur_all.append(tok)
            _set_pref_row(uid, cur_diet, ", ".join(cur_all) if cur_all else None)
            flash(f"Added allergy: {tok}")
            return redirect(url_for("prefs"))

        diet = (request.form.get("diet") or "").strip() or None
        allergies = (request.form.get("allergies") or "").strip() or None
        _set_pref_row(uid, diet, allergies)
        flash("Preferences saved.")
        return redirect(url_for("prefs"))

    pref = _get_pref_row(uid)
    return render_template("prefs.html", pref=pref)

@app.route("/trending")
def trending():
    try:
        days = max(1, min(3650, int(request.args.get("days", 30))))
    except ValueError:
        days = 30
    rows = g.conn.execute(text(f"""
      WITH c AS (
        SELECT recipe_id, COUNT(*) AS comments_30
        FROM recipe_comment
        WHERE created_at >= datetime('now', '-{days} days')
        GROUP BY recipe_id
      ),
      m AS (
        SELECT recipe_id, COUNT(*) AS adds_30
        FROM mealplan_item
        WHERE meal_date >= date('now', '-{days} days')
        GROUP BY recipe_id
      )
      SELECT r.recipe_id, r.title, u.name AS chef,
             COALESCE(c.comments_30,0) AS comments_30,
             COALESCE(m.adds_30,0)     AS adds_30,
             (COALESCE(c.comments_30,0)*2 + COALESCE(m.adds_30,0)) AS score
      FROM "recipe" r
      JOIN "user" u ON u.user_id = r.author_id
      LEFT JOIN c ON c.recipe_id = r.recipe_id
      LEFT JOIN m ON m.recipe_id = r.recipe_id
      ORDER BY score DESC, r.title
      LIMIT 100
    """)).mappings().all()
    return render_template("trending.html", rows=rows, days=days)

# Example of adding new data to the database
@app.route("/add", methods=["POST"])
def add():
    # accessing form inputs from user
    name = request.form["name"]

    # passing params in for each variable into query
    params = {}
    params["new_name"] = name
    g.conn.execute(text("INSERT INTO test(name) VALUES (:new_name)"), params)
    g.conn.commit()
    return redirect("/")


# Authentication routes (spoofed, no passwords)
# ----------------------------------------------------------------------------
@app.route("/auth", methods=["GET"])
def auth_page():
    return render_template("auth.html")

@app.route("/register", methods=["POST"])
def register():
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip()

    if not username or not email:
        flash("Please provide both username and email.")
        return redirect(url_for("auth_page"))
   
    if get_user_by_name(username):
       flash("Username already exists. Try logging in.")
       return redirect(url_for("auth_page"))
    
    if get_user_by_email(email):
       flash("Email already in use. Try logging in.")
       return redirect(url_for("auth_page"))
    
    user = create_user(username, email)
    if not user:
        flash("Could not create user (constraint violation?).")
        return redirect(url_for("auth_page"))
    
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("currentUser", username, httponly=True, samesite="Lax", max_age=60*60*24*30)
    flash(f"Registered and logged in as {username}.")
    return resp
   
@app.route("/login", methods=["POST"])
def login():
    username = (request.form.get("username") or "").strip()
    email    = (request.form.get("email") or "").strip()
    
    user = None
    if username:
        user = get_user_by_name(username)
    
    elif email:
        user = get_user_by_email(email)
        
        if user:
            username = user["name"]
    
    if not user:
        flash("No such user. Please register first.")
        return redirect(url_for("auth_page"))

    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("currentUser", username, httponly=True, samesite="Lax", max_age=60*60*24*30)
    flash(f"Logged in as {username}.")
    return resp

@app.route("/logout", methods=["POST"])
def logout():
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie("currentUser")
    flash("Logged out.")
    return resp

@app.route("/account", methods=["GET"])
def account():
    gate = require_login()
    if gate:
        return gate
    return render_template("account.html")

@app.route("/account/delete", methods=["GET", "POST"])
def delete_account():
    gate = require_login()
    if gate:
        return gate

    if request.method == "POST":
        # Require explicit confirmation
        confirm = (request.form.get("confirm") or "").strip().upper()
        if confirm != "DELETE":
            flash("Please type DELETE to confirm.", "warning")
            return redirect(url_for("delete_account"))

        try:
            uid = g.user["user_id"]  
            g.conn.execute(text('DELETE FROM "user" WHERE user_id = :uid'), {"uid": uid})
            g.conn.commit()

            # clear the auth cookie
            resp = make_response(redirect(url_for("goodbye")))
            resp.delete_cookie("currentUser")
            flash("Your account has been deleted.", "info")
            return resp

        except Exception as e:
            print("Error deleting account:", e)
            g.conn.rollback()
            flash("Could not delete your account. Please try again.", "danger")
            return redirect(url_for("account"))

    return render_template("delete_account_confirm.html")

@app.route("/goodbye", methods=["GET"])
def goodbye():
    return render_template("goodbye.html")
# ----------------------------------------------------------------------------

# Routes for recipes
# ----------------------------------------------------------------------------


@app.route("/recipes/new", methods=["GET", "POST"])
def recipes_new():
    gate = require_login()
    if gate:
        return gate
    
    if request.method == "POST":
        title    = (request.form.get("title") or "").strip()
        minutes  = request.form.get("total_minutes") or None
        servings = request.form.get("servings") or None
        cname    = (request.form.get("cuisine_name") or "").strip()
        creg     = (request.form.get("cuisine_region") or "").strip()
        uid      = g.user["user_id"] 

        if not title or not cname or not creg:
            flash("Title, cuisine name and region are required.")
            return redirect(url_for("recipes_new"))

        try:
            # first ensure constraint that user is a chef
            g.conn.execute(text('INSERT INTO "chef"(user_id) VALUES (:uid) ON CONFLICT DO NOTHING'), {"uid": uid})
            
            res = g.conn.execute(text("""
                                    INSERT INTO "recipe"(title, total_minutes, servings, author_id, cuisine_name, cuisine_region)
                                    VALUES (:t,:m,:s,:a,:cn,:cr)
                                    RETURNING recipe_id
                                """),
                                {"t": title, "m": minutes, "s": servings, "a": uid, "cn": cname, "cr": creg}
            )
            rid = res.scalar()
            
            diet_tags = request.form.getlist("diet[]")
            valid_tags = [d.lower() for d in diet_tags if d and d.lower() in DIET_OPTIONS]

            if valid_tags:
                g.conn.execute(
                    text("""
                        INSERT INTO recipe_diet (recipe_id, diet)
                        VALUES (:rid, :diet)
                        ON CONFLICT (recipe_id, diet) DO NOTHING
                    """),
                    [{"rid": rid, "diet": d} for d in valid_tags]  # executemany
                )
            g.conn.commit()
            flash("Recipe created.")
            return redirect(url_for("recipe_detail", recipe_id=rid))
            
        except Exception as e:
            print("Error creating recipe:", e)
            g.conn.rollback()
            flash("Could not create recipe.")
            return redirect(url_for("recipes_new"))
    
    # GET request
    # get names and regions separately to prevent duplicates in dropdown
    cuisine_names = g.conn.execute(text('SELECT DISTINCT name FROM "cuisine" ORDER BY name')).mappings().all()
    cuisine_regions = g.conn.execute(text('SELECT DISTINCT region FROM "cuisine" ORDER BY region')).mappings().all()

    return render_template("recipes_new.html", cuisine_names=cuisine_names, cuisine_regions=cuisine_regions, diet_options=DIET_OPTIONS)

@app.route("/recipes/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipe = g.conn.execute(text("""
        SELECT r.recipe_id, r.title, r.total_minutes, r.servings,
               u.name AS chef_name, r.author_id,
               r.cuisine_name, r.cuisine_region
        FROM "recipe" r
        JOIN "chef" ch ON ch.user_id = r.author_id
        JOIN "user" u ON u.user_id = ch.user_id
        WHERE r.recipe_id = :rid
    """), {"rid": recipe_id}).mappings().first()

    if not recipe:
        abort(404)

    ingredients = g.conn.execute(text("""
        SELECT i.ingredient_id, i.name, ri.quantity, ri.unit
        FROM recipe_ingredient ri
        JOIN "ingredient" i ON i.ingredient_id = ri.ingredient_id
        WHERE ri.recipe_id = :rid
        ORDER BY i.name
    """), {"rid": recipe_id}).mappings().all()

    comments = g.conn.execute(text("""
        SELECT rc.comment_id, rc.body, rc.created_at, rc.user_id, u.name AS author
        FROM recipe_comment rc
        JOIN "user" u ON u.user_id = rc.user_id
        WHERE rc.recipe_id = :rid
        ORDER BY rc.created_at DESC
    """), {"rid": recipe_id}).mappings().all()

    # for dropdown
    all_ingredients = g.conn.execute(text("""
        SELECT ingredient_id, name
        FROM "ingredient"
        ORDER BY name
        LIMIT 500
    """)).mappings().all()

    return render_template(
        "recipe_detail.html",
        r=recipe,
        ingredients=ingredients,
        comments=comments,
        all_ingredients=all_ingredients
    )


@app.route("/recipes/<int:recipe_id>/add_ingredient", methods=["POST"])
def recipe_add_ingredient(recipe_id):
    gate = require_login()
    if gate:
        return gate

    # Only the author can modify ingredients
    auth_row = g.conn.execute(text("""
        SELECT author_id FROM "recipe" WHERE recipe_id = :rid
    """), {"rid": recipe_id}).mappings().first()
    if not auth_row:
        abort(404)
    if auth_row["author_id"] != g.user["user_id"]:
        flash("Only the recipe author can modify ingredients.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    ing_name   = (request.form.get("ingredient_name") or "").strip()
    qty        = (request.form.get("quantity") or None)
    unit       = (request.form.get("unit") or None)
    ing_type   = (request.form.get("ingredient_type") or None)
    ing_flavor = request.form.get("ingredient_flavor")  # dropdown exact value (may be "")
    ing_color  = (request.form.get("ingredient_color") or None)

    if not ing_name:
        flash("Ingredient name is required.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    try:
        # Existing ingredient by case-insensitive name
        row = g.conn.execute(text("""
            SELECT ingredient_id
            FROM "ingredient"
            WHERE lower(name) = lower(:n)
            LIMIT 1
        """), {"n": ing_name}).first()

        if row:
            ing_id = row[0]
        else:
            # Create a new ingredient
            if ing_flavor is None or ing_flavor not in {"", "sweet", "sour", "salty", "bitter", "umami"}:
                flash("Please choose a valid flavor from the dropdown.")
                return redirect(url_for("recipe_detail", recipe_id=recipe_id))

            res = g.conn.execute(text("""
                INSERT INTO "ingredient"(name, type, flavor, color)
                VALUES (:n, :t, :f, :c)
                RETURNING ingredient_id
            """), {"n": ing_name, "t": ing_type, "f": ing_flavor, "c": ing_color})
            ing_id = res.scalar()

        g.conn.execute(text("""
            INSERT INTO recipe_ingredient(recipe_id, ingredient_id, quantity, unit)
            VALUES (:r, :i, :q, :u)
            ON CONFLICT (recipe_id, ingredient_id) DO UPDATE
            SET quantity = EXCLUDED.quantity, unit = EXCLUDED.unit
        """), {"r": recipe_id, "i": ing_id, "q": qty, "u": unit})

        g.conn.commit()
        flash("Ingredient saved.")
    except Exception as e:
        g.conn.rollback()
        print("Error adding ingredient:", e)
        flash("Failed to add ingredient.")

    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


# -----------------------------------------------------------------

# Follow / Unfollow Chefs and sort by ratings and followers
# -----------------------------------------------------------------
@app.route("/chefs/<int:chef_id>/follow", methods=["POST"])
def follow_chef(chef_id):
    gate = require_login()
    if gate:
        return gate
    
    try:
        g.conn.execute(text("""
                            INSERT INTO user_follows_chef(user_id, chef_id)
                            VALUES (:u, :c)
                            ON CONFLICT DO NOTHING
                            """), {"u": g.user["user_id"], "c": chef_id}
        )
        g.conn.commit()
        flash("Now following chef.")
    
    except Exception as e:
        g.conn.rollback()
        flash("Failed to follow chef.")
        print("Error following chef:", e)
    
    return redirect(url_for("chef_detail", user_id=chef_id))

@app.route("/chefs/<int:chef_id>/unfollow", methods=["POST"])
def unfollow_chef(chef_id):
    gate = require_login()
    if gate:
        return gate
    try:
        g.conn.execute(text("""
                        DELETE FROM user_follows_chef WHERE user_id=:u AND chef_id=:c
                        """), {"u": g.user["user_id"], "c": chef_id})
        g.conn.commit()
        flash("Unfollowed chef.")
        
    except Exception as e:
        g.conn.rollback()
        flash("Could not unfollow.")
    return redirect(url_for("chef_detail", user_id=chef_id))

@app.route("/chefs/following", methods=["GET"])
def followed_chefs():
    gate = require_login()
    if gate:
        return gate

    uid = g.user.user_id  # adapt if your current_user access is different

    rows = [dict(row) for row in g.conn.execute(text("""
        SELECT c.user_id AS chef_id, u.name AS chef_name, c.cuisine_type,
        (SELECT COUNT(*) FROM user_follows_chef f2 WHERE f2.chef_id=c.user_id) AS followers,
        (SELECT AVG(rating) FROM chef_rating cr WHERE cr.chef_id=c.user_id) AS rating,
        (SELECT COUNT(*) FROM recipe r WHERE r.author_id=c.user_id) AS recipe_count
        FROM user_follows_chef f JOIN chef c ON c.user_id=f.chef_id
        JOIN "user" u ON u.user_id=c.user_id
        WHERE f.user_id=:uid ORDER BY u.name
    """), {"uid": uid}).mappings()]
    for row in rows:
        row["recent"] = g.conn.execute(text('SELECT recipe_id,title FROM recipe WHERE author_id=:c ORDER BY recipe_id DESC LIMIT 5'), {"c":row["chef_id"]}).mappings().all()

    return render_template("followed_chefs.html", rows=rows)

# rate a chef from 1-5
@app.route("/chefs/<int:chef_id>/rate", methods=["POST"])
def rate_chef(chef_id):
    gate = require_login()
    if gate: 
        return gate

    rating = int(request.form["rating"])
    if rating < 1 or rating > 5:
        flash("Rating must be 1..5.")
        return redirect(url_for("chef_detail", user_id=chef_id))
    try:
        g.conn.execute(text("""
            INSERT INTO chef_rating(user_id, chef_id, rating)
            VALUES (:u,:c,:r)
            ON CONFLICT (user_id, chef_id) DO UPDATE SET rating = EXCLUDED.rating, rated_at = CURRENT_TIMESTAMP
        """), {"u": g.user["user_id"], "c": chef_id, "r": rating})
        g.conn.commit()
        flash("Rating saved.")
    except Exception:
        g.conn.rollback()
        flash("Could not save rating.")
    return redirect(url_for("chef_detail", user_id=chef_id))

@app.route("/chefs")
def chef_list():
    sort = request.args.get("sort", "rating")  # 'rating' or 'followers'
    order_by = """
      COALESCE(avg_r,0) DESC, COALESCE(fcount,0) DESC, u.name
    """ if sort == "rating" else """
      COALESCE(fcount,0) DESC, COALESCE(avg_r,0) DESC, u.name
    """
    rows = g.conn.execute(text(f"""
      WITH agg AS (
        SELECT c.user_id,
               (SELECT COUNT(*) FROM user_follows_chef f WHERE f.chef_id=c.user_id) AS fcount,
               (SELECT ROUND(AVG(rating),2) FROM chef_rating r WHERE r.chef_id=c.user_id) AS avg_r
        FROM "chef" c
      )
      SELECT c.user_id, u.name, a.fcount, a.avg_r
      FROM "chef" c
      JOIN "user" u ON u.user_id = c.user_id
      LEFT JOIN agg a ON a.user_id = c.user_id
      ORDER BY {order_by}
      LIMIT 200
    """)).mappings().all()
    return render_template("chef_list.html", chefs=rows, sort=sort)

# details about the chef with follow state
@app.route("/chefs/<int:user_id>")
def chef_detail(user_id):
    chef = g.conn.execute(text("""
      SELECT u.user_id, u.name,
             (SELECT ROUND(AVG(rating),2) FROM chef_rating r WHERE r.chef_id=u.user_id) AS avg_r,
             (SELECT COUNT(*) FROM user_follows_chef f WHERE f.chef_id=u.user_id) AS followers
      FROM "user" u JOIN "chef" c ON c.user_id=u.user_id
      WHERE u.user_id=:id
    """), {"id": user_id}).mappings().first()
    
    if not chef: 
        abort(404)
    
    recipes = g.conn.execute(text("""
      SELECT recipe_id, title, total_minutes, servings FROM "recipe"
      WHERE author_id=:id ORDER BY title
    """), {"id": user_id}).mappings().all()
    
    following = False
    
    if g.user:
        following = g.conn.execute(text("""
          SELECT 1 FROM user_follows_chef WHERE user_id=:u AND chef_id=:c
        """), {"u": g.user["user_id"], "c": user_id}).first() is not None
    
    return render_template("chef_detail.html", chef=chef, recipes=recipes, following=following)
# -----------------------------------------------------------------

# Comment routes
# -----------------------------------------------------------------
@app.route("/recipes/<int:recipe_id>/comments")
def recipe_comments(recipe_id):
    r = g.conn.execute(text("""
      SELECT r.recipe_id, r.title, r.author_id, u.name AS chef_name
      FROM recipe r
      JOIN "user" u ON u.user_id = r.author_id
      WHERE r.recipe_id = :rid
    """), {"rid": recipe_id}).mappings().first()
    if not r: 
        abort(404)

    comments = g.conn.execute(text("""
      SELECT rc.comment_id, rc.body, rc.created_at, rc.user_id, u.name AS author
      FROM recipe_comment rc
      JOIN "user" u ON u.user_id = rc.user_id
      WHERE rc.recipe_id = :rid
      ORDER BY rc.created_at DESC
    """), {"rid": recipe_id}).mappings().all()

    return redirect(url_for("recipe_detail", recipe_id=recipe_id))

@app.route("/recipes/<int:recipe_id>/comments/<int:comment_id>/delete", methods=["POST"])
def recipe_comment_delete(recipe_id, comment_id):
    gate = require_login()
    if gate: 
        return gate

    # Ensure permission: current user must own the comment OR be recipe author
    can_delete = g.conn.execute(text("""
      SELECT 1
      FROM recipe_comment rc
      JOIN recipe r ON r.recipe_id = rc.recipe_id
      WHERE rc.comment_id = :cid AND rc.recipe_id = :rid
        AND (rc.user_id = :me OR r.author_id = :me)
    """), {"cid": comment_id, "rid": recipe_id, "me": g.user["user_id"]}).first()

    if not can_delete:
      flash("You can’t delete this comment.")
      return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    try:
        g.conn.execute(text("""
          DELETE FROM recipe_comment WHERE comment_id = :cid AND recipe_id = :rid
        """), {"cid": comment_id, "rid": recipe_id})
        g.conn.commit()
        flash("Comment deleted.")
    except Exception:
        g.conn.rollback()
        flash("Failed to delete comment.")

    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


@app.route("/recipes/<int:recipe_id>/comment", methods=["POST"])
def recipe_comment_add(recipe_id):
    gate = require_login()
    if gate:
        return gate
    
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Comment cannot be empty.")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))
    
    try:
        g.conn.execute(text("""
                            INSERT INTO recipe_comment(recipe_id, user_id, body)
                            VALUES (:r, :u, :b)
                            """), {"r": recipe_id, "u": g.user["user_id"], "b": body})
        g.conn.commit()
        flash("Comment added.")
    
    except Exception as e:
        g.conn.rollback()
        flash("Could not add comment.")
    
    return redirect(url_for("recipe_detail", recipe_id=recipe_id))
# -----------------------------------------------------------------

# search for users or recipes by cuisine and region
# -----------------------------------------------------------------
@app.route("/search")
def search():
    quser = (request.args.get("user") or "").strip()
    cname = (request.args.get("cuisine") or "").strip()
    creg  = (request.args.get("region") or "").strip()

    users = []
    if quser:
        users = g.conn.execute(text("""
                    SELECT user_id, name, email FROM "user"
                    WHERE name LIKE :q
                    ORDER BY name LIMIT 50
                    """), {"q": f"%{quser}%"}).mappings().all()
        
    sql = """
        SELECT r.recipe_id, r.title, u.name AS chef, r.cuisine_name, r.cuisine_region
        FROM "recipe" r
        JOIN "user" u ON u.user_id = r.author_id
        WHERE 1=1
    """

    params = {}
    if cname:
        sql += " AND r.cuisine_name LIKE :cn"
        params["cn"] = f"%{cname}%"
    if creg:
        sql += " AND r.cuisine_region LIKE :cr"
        params["cr"] = f"%{creg}%"
    
    sql += " ORDER BY r.title LIMIT 100"
    recipes = g.conn.execute(text(sql), params).mappings().all()
    
    return render_template("search.html", users=users, recipes=recipes, quser=quser, cname=cname, creg=creg)

# -----------------------------------------------------------------

# mealplan and mealplan item routes
# -----------------------------------------------------------------

@app.route("/mealplans/<int:user_id>")
def mealplans_for_user(user_id):
    gate = require_login()
    if gate: return gate
    if user_id != g.user["user_id"]: abort(403)
    plans = g.conn.execute(text("""
        SELECT mealplan_id, title, start_date, end_date
        FROM "mealplan"
        WHERE user_id = :uid
        ORDER BY start_date DESC
    """), {"uid": user_id}).mappings().all()
    return render_template("mealplans_user.html", user_id=user_id, plans=plans)



@app.route("/mealplans/new", methods=["GET", "POST"])
def mealplan_new():
    gate = require_login()
    if gate: return gate

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        start = (request.form.get("start_date") or "").strip()   # yyyy-mm-dd
        end   = (request.form.get("end_date") or "").strip()     # yyyy-mm-dd
        uid   = g.user["user_id"]

        if not title or not start or not end:
            flash("Start and End dates are required.")
            return redirect(url_for("mealplan_new"))

        try:
            # overlap check
            overlap = g.conn.execute(text("""
                                SELECT 1
                                FROM "mealplan" 
                                WHERE user_id = :uid
                                AND NOT (
                                    end_date < date(:start)
                                    OR start_date > date(:end)
                                )
                                LIMIT 1
                            """), {"uid": uid, "start": start, "end": end}).first()
                                
           
            if overlap:
                flash("You already have a plan that overlaps these dates.")
                return redirect(url_for("mealplan_new"))
            
            pid = g.conn.execute(text("""
                            INSERT INTO "mealplan"(user_id, start_date, end_date, title)
                            VALUES (:uid, date(:start), date(:end), :title)
                            RETURNING mealplan_id
                            """), {"uid": uid, "start": start, "end": end, "title": title or None}).scalar()


            g.conn.commit()
            flash("Created meal plan.")
            return redirect(url_for("mealplan_detail", pid=pid))
        except Exception as e:
            g.conn.rollback()
            flash("Failed to create meal plan.")
            print("Error creating meal plan:", e)
            return redirect(url_for("mealplan_new"))

    return render_template("mealplan_new.html")

@app.route("/mealplans/<int:pid>/delete", methods=["POST"])
def mealplan_delete(pid):
    gate = require_login()
    if gate:
        return gate
    
    row = g.conn.execute(text("""
                        SELECT user_id FROM "mealplan" WHERE mealplan_id = :pid"""), {"pid": pid}).first()
    
    if not row:
        abort(404)
    
    if row[0] != g.user["user_id"]:
        flash("You do not have permission to delete that meal plan.")
        return redirect(url_for("mealplan_detail", pid=pid))
    
    try:
        g.conn.execute(text('DELETE FROM "mealplan" WHERE mealplan_id = :pid'), {"pid": pid})

        g.conn.commit()
        flash("Deleted meal plan.")
        
        return redirect(url_for("mealplans_for_user", user_id=g.user["user_id"]))
    
    except Exception as e:
        g.conn.rollback()
        flash("Could not delete meal plan.")
        print("Error deleting meal plan:", e)
        return redirect(url_for("mealplan_detail", pid=pid))

@app.route("/mealplans/<int:pid>/edit", methods=["GET","POST"])
def mealplan_edit(pid):
    gate = require_login()
    if gate: return gate

    plan = g.conn.execute(text("""
        SELECT mealplan_id, user_id, title, start_date, end_date
        FROM "mealplan" WHERE mealplan_id = :pid
    """), {"pid": pid}).mappings().first()
    if not plan: abort(404)
    if plan["user_id"] != g.user["user_id"]:
        flash("You do not have permission to edit this plan.")
        return redirect(url_for("mealplan_detail", pid=pid))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip() or None
        start = (request.form.get("start_date") or "").strip()
        end   = (request.form.get("end_date") or "").strip()

        if not start or not end:
            flash("Start and End dates are required.")
            return redirect(url_for("mealplan_edit", pid=pid))

        # overlap detection 
        overlap = g.conn.execute(text("""
            SELECT 1 FROM "mealplan"
            WHERE user_id = :uid
              AND mealplan_id != :pid
              AND NOT (end_date < date(:start) OR start_date > date(:end))
            LIMIT 1
        """), {"uid": g.user["user_id"], "pid": pid, "start": start, "end": end}).first()
        if overlap:
            flash("Another one of your plans overlaps these dates.")
            return redirect(url_for("mealplan_edit", pid=pid))

        try:
            # if shrinking range, drop out-of-range items
            g.conn.execute(text("""
                DELETE FROM mealplan_item
                WHERE mealplan_id = :pid
                  AND (meal_date < date(:start) OR meal_date > date(:end))
            """), {"pid": pid, "start": start, "end": end})

            g.conn.execute(text("""
                UPDATE "mealplan"
                SET title = :t, start_date = date(:start), end_date = date(:end)
                WHERE mealplan_id = :pid
            """), {"t": title, "start": start, "end": end, "pid": pid})

            g.conn.commit()
            flash("Meal plan updated.")
            return redirect(url_for("mealplan_detail", pid=pid))
        except Exception as e:
            print("Error editing mealplan:", e)
            g.conn.rollback()
            flash("Failed to update meal plan.")
            return redirect(url_for("mealplan_edit", pid=pid))

    return render_template("mealplan_edit.html", plan=plan)


MEAL_SLOTS = ("breakfast", "lunch", "dinner", "snack")

@app.route("/mealplans/view/<int:pid>/week")
def mealplan_week(pid):
    gate = require_login()
    if gate: return gate
    owner = g.conn.execute(text('SELECT user_id FROM mealplan WHERE mealplan_id=:p'), {"p": pid}).scalar()
    if owner != g.user["user_id"]: abort(403)
    plan = g.conn.execute(text("""
        SELECT mealplan_id, user_id, title, start_date, end_date
        FROM "mealplan" WHERE mealplan_id = :pid
    """), {"pid": pid}).mappings().first()
    if not plan: abort(404)

    qstart = request.args.get("start")
    if qstart:
        try:
            start_candidate = datetime.strptime(qstart, "%Y-%m-%d").date()
        except ValueError:
            start_candidate = plan["start_date"]
    else:
        start_candidate = plan["start_date"]

    week_start = _week_monday(start_candidate)
    week_end   = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    window_start = max(week_start, plan["start_date"])
    window_end   = min(week_end, plan["end_date"])

    items = g.conn.execute(text("""
        SELECT mi.mealplanitem_id, mi.meal_date, mi.meal_type, mi.servings,
               r.recipe_id, r.title
        FROM mealplan_item mi
        JOIN recipe r ON r.recipe_id = mi.recipe_id
        WHERE mi.mealplan_id = :pid
          AND mi.meal_date BETWEEN :ws AND :we
        ORDER BY mi.meal_date, mi.meal_type, r.title
    """), {"pid": pid, "ws": week_start, "we": week_end}).mappings().all()

    grid = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        grid[d] = {slot: [] for slot in MEAL_SLOTS}
    for it in items:
        grid[it["meal_date"]][it["meal_type"]].append(it)

    # Prev/next week links (stay within full plan range)
    prev_start = (week_start - timedelta(days=7))
    next_start = (week_start + timedelta(days=7))
    prev_link = url_for("mealplan_week", pid=pid, start=str(prev_start)) if prev_start <= plan["end_date"] else None
    next_link = url_for("mealplan_week", pid=pid, start=str(next_start)) if next_start <= plan["end_date"] else None

    return render_template(
        "mealplan_week.html",
        plan=plan,
        week_start=week_start,
        week_end=week_end,
        grid=grid,
        MEAL_SLOTS=MEAL_SLOTS,
        prev_link=prev_link,
        next_link=next_link,
        days=days
    )


@app.route("/mealplans/view/<int:pid>")
def mealplan_detail(pid):
    gate = require_login()
    if gate: return gate
    owner = g.conn.execute(text('SELECT user_id FROM mealplan WHERE mealplan_id=:p'), {"p": pid}).scalar()
    if owner != g.user["user_id"]: abort(403)
    plan = g.conn.execute(text("""
        SELECT m.mealplan_id, m.user_id, m.title, m.start_date, m.end_date, u.name
        FROM "mealplan" m LEFT JOIN "user" u ON u.user_id = m.user_id
        WHERE m.mealplan_id = :pid
    """), {"pid": pid}).mappings().first()
    if not plan: abort(404)

    items = g.conn.execute(text("""
        SELECT mi.mealplanitem_id, mi.meal_date, mi.meal_type, mi.servings,
               r.recipe_id, r.title
        FROM "mealplan_item" mi
        JOIN "recipe" r ON r.recipe_id = mi.recipe_id
        WHERE mi.mealplan_id = :pid
        ORDER BY mi.meal_date, mi.meal_type, r.title
    """), {"pid": pid}).mappings().all()

    recipes = g.conn.execute(text("""
        SELECT recipe_id, title FROM "recipe" ORDER BY title LIMIT 200
    """)).mappings().all()

    return render_template("mealplan_detail.html", plan=plan, items=items, recipes=recipes)

@app.route("/mealplans/<int:pid>/add_item", methods=["POST"])
def mealplan_add_item(pid):
    gate = require_login()
    if gate: 
        return gate

    owner = g.conn.execute(text('SELECT user_id FROM mealplan WHERE mealplan_id=:p'), {"p": pid}).scalar()
    if owner != g.user["user_id"]: abort(403)
    rid   = int(request.form["recipe_id"])
    d     = (request.form.get("meal_date") or "").strip()      
    slot  = (request.form.get("meal_type") or "").strip().lower()  # breakfast/lunch/...
    serv  = int(request.form.get("servings") or 1)

    try:
        rng = g.conn.execute(text("""
            SELECT start_date, end_date FROM "mealplan" WHERE mealplan_id = :pid
        """), {"pid": pid}).mappings().first()
        if not rng: abort(404)

        in_range = g.conn.execute(text("""
            SELECT (date(:d) BETWEEN :s AND :e) AS ok
        """), {"d": d, "s": rng["start_date"], "e": rng["end_date"]}).mappings().first()["ok"]
        if not in_range:
            flash("Item date must be within the plan's range.")
            return redirect(url_for("mealplan_detail", pid=pid))

        dup = g.conn.execute(text("""
            SELECT 1 FROM "mealplan_item"
            WHERE mealplan_id = :pid 
            AND meal_date = date(:d)
            AND meal_type = :slot
            AND recipe_id = :rid
            LIMIT 1
        """), {"pid": pid, "d": d, "slot": slot, "rid": rid}).first()
        if dup:
            flash("That recipe is already in this slot on that day.")
            return redirect(url_for("mealplan_detail", pid=pid))

        g.conn.execute(text("""
            INSERT INTO "mealplan_item"(mealplan_id, recipe_id, meal_date, meal_type, servings)
            VALUES (:pid, :rid, date(:d), :slot, :serv)
        """), {"pid": pid, "rid": rid, "d": d, "slot": slot, "serv": serv})
        g.conn.commit()
        flash("Added.")
    except Exception as e:
        print("Error adding mealplan item:", e)
        g.conn.rollback()
        flash("Failed to add item.")
    return redirect(url_for("mealplan_detail", pid=pid))

@app.route("/mealplans/item/<int:item_id>/delete", methods=["POST"])
def mealplan_item_delete(item_id):
    if not g.user: return redirect(url_for("auth_page"))
    owner = g.conn.execute(text('SELECT m.user_id FROM mealplan_item i JOIN mealplan m USING (mealplan_id) WHERE i.mealplanitem_id=:i'), {"i": item_id}).scalar()
    if owner != g.user["user_id"]: abort(403)
    gate = require_login()
    if gate: 
        return gate
    try:
        row = g.conn.execute(text("""
            DELETE FROM "mealplan_item"
            WHERE mealplanitem_id = :id
            RETURNING mealplan_id
        """), {"id": item_id}).first()
        g.conn.commit()
        flash("Removed item.")
        return redirect(url_for("mealplan_detail", pid=row[0] if row else None) or 0)
    except Exception:
        g.conn.rollback()
        flash("Failed to remove item.")
        return redirect(url_for("index"))

@app.route("/mealplans/<int:pid>/groceries")
def mealplan_groceries(pid):
    gate = require_login()
    if gate: return gate
    owner = g.conn.execute(text('SELECT user_id FROM mealplan WHERE mealplan_id=:p'), {"p": pid}).scalar()
    if owner != g.user["user_id"]: abort(403)
    plan = g.conn.execute(text("""
        SELECT mealplan_id, user_id, title, start_date, end_date
        FROM "mealplan" WHERE mealplan_id = :pid
    """), {"pid": pid}).mappings().first()
    if not plan: abort(404)

    rows = g.conn.execute(text("""
        SELECT i.name AS ingredient,
               ri.unit AS unit,
               ROUND(SUM(COALESCE(ri.quantity, 1) * COALESCE(mi.servings, 1)),2) AS total_qty
        FROM mealplan_item mi
        JOIN recipe_ingredient ri ON ri.recipe_id = mi.recipe_id
        JOIN ingredient i ON i.ingredient_id = ri.ingredient_id
        WHERE mi.mealplan_id = :pid
        GROUP BY i.name, ri.unit
        ORDER BY i.name, ri.unit
    """), {"pid": pid}).mappings().all()

    return render_template("mealplan_groceries.html", plan=plan, items=rows)
# -----------------------------------------------------------------
    
if __name__ == "__main__":
    import click

    @click.command()
    @click.option("--debug", is_flag=True)
    @click.option("--threaded", is_flag=True)
    @click.argument("HOST", default="127.0.0.1")
    @click.argument("PORT", default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using:

                python server.py

        Show the help text using:

                python server.py --help

        """

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


    run()
