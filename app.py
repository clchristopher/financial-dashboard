import os
import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

db.execute("""
    CREATE TABLE  IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        symbol TEXT NOT NULL,
        price FLOAT,
        quantity FLOAT
    )
""")

db.execute("""
    CREATE TABLE  IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        symbol TEXT NOT NULL,
        price FLOAT,
        quantity FLOAT,
        date Text
    )
""")




@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response



@app.route("/")
@login_required
def index():
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", (session['user_id']))
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    total = cash[0]["cash"]
    for stock in portfolio:
        total += stock["quantity"] * stock["price"]

    return render_template("index.html", portfolio=portfolio, cash=cash, total=round(total, 2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = float(request.form.get("shares"))
        if (shares <= 0):
            return apology("Negative stock", 401)
        info = lookup(symbol)
        existing_stock = db.execute("SELECT * FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])

        cash_query = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        if not cash_query:
            return apology("User not found", 404)

        cash = cash_query[0]["cash"]
                

        if existing_stock:
            updated_quantity = existing_stock[0]["quantity"] + shares
            db.execute("UPDATE portfolio SET quantity = ? WHERE symbol = ? AND user_id = ?", updated_quantity, symbol, session['user_id'])
        else:
            db.execute("INSERT INTO portfolio (symbol, price, quantity, user_id) VALUES(?, ?, ?, ?)", symbol, info["price"], shares, session['user_id'])

        db.execute("INSERT INTO transactions (symbol, price, quantity, user_id, date) VALUES(?, ?, ?, ?, datetime('now', 'localtime'))",symbol, info["price"], shares, session['user_id'])

        
        cash -= (shares * info["price"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", (session['user_id']))
        total = cash
        for stock in portfolio:
            total += stock["quantity"] * stock["price"]
        flash("Bought!")
        return redirect("/")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", (session['user_id']))
    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        info = lookup(symbol)
        if info:
            return render_template("quoted.html", info=info)
        else:
            return apology("No stock exists", 400)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password does not match", 403)
        
        hashedPassword = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, HASH) VALUES(?, ?)", request.form.get('username'), hashedPassword)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", (session['user_id']))
    if request.method == "POST":
        symbol = request.form.get("stock").lower()
        shares = float(request.form.get("shares"))
        if (shares <= 0):
            return apology("Negative stock", 401)
        info = lookup(symbol)
        existing_stock = db.execute("SELECT * FROM portfolio WHERE symbol = ? AND user_id = ? LIMIT 1", symbol, session["user_id"])

        
        if (existing_stock[0]["quantity"] >= shares):
            updated_quantity = existing_stock[0]["quantity"] - shares
            if updated_quantity == 0:
                 db.execute("DELETE FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, session['user_id'])
            else:
                db.execute("UPDATE portfolio SET quantity = ? WHERE symbol = ? AND user_id = ?", updated_quantity, symbol, session['user_id'])

            shares *= -1
            db.execute("INSERT INTO transactions (symbol, price, quantity, user_id, date) VALUES(?, ?, ?, ?, datetime('now', 'localtime'))",symbol, info["price"], shares, session['user_id'])
            sellingPrice = info["price"]
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash[0]["cash"] = cash[0]["cash"] + (shares * sellingPrice)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"], session["user_id"])
            flash("Sold!")
            return redirect("/")
            
        else:
            return(apology("you don't have enough of this stock", 400))
    else:
        return render_template("sell.html", portfolio = portfolio)
