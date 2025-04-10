import os

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
    l = db.execute(f"select distinct symbol from symbols where user_id = {session["user_id"]}")
    symbol_list = []
    for i in l:
        symbol_list.append(i["symbol"])
    aggregate = []
    for s in symbol_list:
        d = {"symbol": s}
        d["shares"] = db.execute(
            f"select sum(shares) from transactions where user_id = {session['user_id']} and symbol = \"{s}\"")[0]["sum(shares)"]
        d["price"] = lookup(s)["price"]
        d["total"] = d["shares"] * d["price"]
        aggregate.append(d)
    cash = db.execute(f"select cash from users where id = {session['user_id']}")[0]["cash"]
    total = cash + sum(i["total"] for i in aggregate)
    return render_template("layout.html", aggregate=aggregate, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        print(lookup(request.form.get("symbol")))
        if not request.form.get("symbol") or not lookup(request.form.get("symbol")):
            return apology("Invalid symbol.")
        if not request.form.get("shares") or not request.form.get("shares").isnumeric():
            return apology("Enter a number.")
        cash = db.execute(f"select cash from users where id = {session['user_id']}")[0]["cash"]
        amount = lookup(request.form.get("symbol"))["price"] * int(request.form.get("shares"))

        if amount > cash:
            return apology("Not enough money.")
        db.execute(f"update users set cash = {cash - amount} where id = {session['user_id']}")
        db.execute(
            f"insert into transactions (user_id, symbol, shares, date, amount) values ({session['user_id']}, \"{lookup(request.form.get('symbol'))['symbol']}\", {int(request.form.get('shares'))}, CURRENT_TIMESTAMP, -{amount})")
        if lookup(request.form.get('symbol'))['symbol'] not in map(lambda x: x["symbol"], db.execute(f"select symbol from symbols where user_id = {session["user_id"]}")):
            db.execute(
                f"insert into symbols (user_id, symbol, shares) values (\"{session["user_id"]}\", \"{lookup(request.form.get('symbol'))['symbol']}\", {request.form.get("shares")})")
        else:
            db.execute(
                f"update symbols set shares = shares + {request.form.get("shares")} where user_id = \"{session["user_id"]}\" and symbol = \"{lookup(request.form.get('symbol'))['symbol']}\"")
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    return render_template("history.html", transactions=db.execute(f"select * from transactions where user_id = {session["user_id"]}"))


@app.template_filter('abs_round')
def abs_round(value):
    return "{:.2f}".format(abs(value))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Provide username.")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Provide password.")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Enter a symbol.")
        if lookup(request.form.get("symbol")):
            return render_template("quoted.html", items=lookup(request.form.get("symbol")))
        return apology("Invalid symbol.")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            if not request.form.get("username"):
                return apology("Provide username.")
            if not request.form.get("password"):
                return apology("Provide password.")
            if not request.form.get("confirmation"):
                return apology("Type your password again.")
            if request.form.get("password") != request.form.get("confirmation"):
                return apology("Enter the same password twice.")
            db.execute(
                f"INSERT INTO users (username, hash) VALUES (\"{request.form.get("username")}\", \"{generate_password_hash(request.form.get("password"))}\")")
            return render_template("login.html")
        except ValueError:
            return apology("No duplicate usernames.")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    symbols = [x["symbol"] for x in db.execute(
        f"select symbol from symbols where user_id = {session["user_id"]}")]
    if request.method == "GET":
        return render_template("sell.html", symbols=symbols)
    else:
        try:
            symbol = lookup(request.form.get("symbol"))["symbol"]
        except AttributeError:
            return apology("Please enter a valid symbol.")
        shares = int(request.form.get("shares"))
        curr_shares = db.execute(
            f"select shares from symbols where user_id = {session["user_id"]} and symbol = \"{symbol}\"")[0]["shares"]
        curr_cash = db.execute(f"select cash from users where id = {session["user_id"]}")[0]["cash"]
        if symbol not in symbols:
            return apology("You don't own this symbol.")
        if curr_shares < shares:
            return apology("You don't own enough shares.")
        price = lookup(symbol)["price"]
        profit = price * shares
        if curr_shares == shares:
            db.execute(
                f"delete from symbols where user_id = {session["user_id"]} and symbol = \"{symbol}\"")
        else:
            db.execute(
                f"update symbols set shares = {curr_shares - shares} where user_id = {session["user_id"]}")
        db.execute(f"update users set cash = {curr_cash + profit} where id = {session["user_id"]}")
        db.execute(
            f"insert into transactions (symbol, shares, date, amount, user_id) values (\"{symbol}\", -{shares}, CURRENT_TIMESTAMP, {profit}, {session["user_id"]})")
        return redirect("/")


@app.route("/changepwd", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("changepwd.html")
    else:
        curr_pwd = request.form.get("current password")
        if not check_password_hash(db.execute(f"select hash from users where id = {session["user_id"]}")[0]["hash"], curr_pwd):
            return apology("Wrong password.", 403)
        new_pwd = request.form.get("password")
        conf = request.form.get("confirmation")
        if new_pwd != conf:
            return apology("The passwords do no match.", 403)
        if new_pwd == curr_pwd:
            return apology("You may not use your previous password.", 403)
        db.execute(
            f"update users set hash = \"{generate_password_hash(new_pwd)}\" where id = {session["user_id"]}")
        return redirect("/")
