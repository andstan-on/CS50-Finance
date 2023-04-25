import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, passwordContainNumbers

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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
    """Show portfolio of stocks"""
    # User's available money
    userCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # User's transactions
    transactions = db.execute("SELECT * FROM shares WHERE user_id = ?", session["user_id"])

    # make a list containing all info for each stock
    stockInfo = []
    symbolList = []
    for transaction in transactions:
        if transaction["symbol"] not in symbolList:
            symbolList.append(transaction["symbol"])
    for symbol in symbolList:
        stockInfo.append(lookup(symbol))
    totalStockValue = 0
    for stock in stockInfo:
        count = 0
        for transaction in transactions:
            if stock["symbol"] == transaction["symbol"]:
                count += transaction["shares"]
        stock.update({"shares": count})
        totalStockValue += count*stock["price"]

    for stock in stockInfo:
        stockTotal = stock["shares"] * stock["price"]
        stock.update({"total": stockTotal})
        stock["price"] = usd(stock["price"])
        stock["total"] = usd(stock["total"])
    superTotal = usd(totalStockValue + userCash[0]["cash"])
    totalStockValue = usd(totalStockValue)
    userCash = usd(userCash[0]["cash"])

    return render_template("index.html", userCash=userCash, stockInfo=stockInfo, totalStockValue=totalStockValue, superTotal=superTotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure symbol exists
        elif lookup(request.form.get("symbol")) == None:
            return apology("symbol is not valid", 400)

        # Ensure number of shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide number of shares", 400)

         # Ensure number of shares is int
        elif not request.form.get("shares").isdigit():
            return apology("must provide integer", 400)

        # Ensure number of shares is positive
        elif int(request.form.get("shares")) <= 0:
            return apology("must provide valid number of shares", 400)

        # Stock's details and current price
        stockInfo = lookup(request.form.get("symbol"))
        # User's available money
        userCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Ensure user has enough money for the shares
        if userCash[0]["cash"] < stockInfo["price"] * int(request.form.get("shares")):
            return apology("not enough cash", 400)

        # Add transaction in db
        db.execute("INSERT INTO history (user_id, symbol, action, price, shares, total_price) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], stockInfo["symbol"], "buy", stockInfo["price"], int(request.form.get("shares")), stockInfo["price"] * int(request.form.get("shares")))

        check_symbol = db.execute("SELECT * FROM shares WHERE user_id = ? AND symbol = ?", session["user_id"], stockInfo["symbol"])
        if len(check_symbol) == 1:
            db.execute("UPDATE shares SET shares = ? WHERE user_id = ? and symbol = ?",
                       check_symbol[0]["shares"]+int(request.form.get("shares")), session["user_id"], stockInfo["symbol"])
        else:
            db.execute("INSERT INTO shares(user_id, symbol, shares) VALUES(?, ?, ?)",
                       session["user_id"], stockInfo["symbol"], int(request.form.get("shares")))

        # Substract cash from user
        db.execute("UPDATE users SET cash = ? WHERE id = ?",
                   userCash[0]["cash"] - stockInfo["price"]*int(request.form.get("shares")), session["user_id"])
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # User's history
    userHistory = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])

    for item in userHistory:
        item["price"] = usd(item["price"])
        item["total_price"] = usd(item["total_price"])

    print(userHistory)

    return render_template("history.html", userHistory=userHistory)


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
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if lookup(request.form.get("symbol")) == None:
            return apology("invalid symbol", 400)
        else:
            info = lookup(request.form.get("symbol"))
            price = usd(info["price"])
            return render_template("quoted.html", info=info, price=price)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Ensure password meets criteria
        elif len(request.form.get("password")) < 6:
            return apology("password too weak", 400)

        # Ensure passwords match
        elif not (request.form.get("password") == request.form.get("confirmation")):
            return apology("passwords do not match", 400)

        # Ensure user is not already registered
        elif not rows == []:
            return apology("user already exists", 400)

        # Ensure password contains numbers
        if passwordContainNumbers(request.form.get("password")) == False:
            return apology("must have numbers", 400)

        # register account
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
                   request.form.get("username"), generate_password_hash(request.form.get("password")))
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    userShares = db.execute("SELECT * FROM shares WHERE user_id = ?", session["user_id"])
    userShareList = []
    for share in userShares:
        userShareList.append(share["symbol"])
    verifyShares = db.execute("SELECT * FROM shares WHERE user_id = ? and symbol = ?",
                              session["user_id"], request.form.get("symbol"))

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure symbol is vaid
        elif request.form.get("symbol") not in userShareList:
            return apology("symbol is not valid", 400)

        # Ensure number of shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # Ensure number of shares is positive
        elif int(request.form.get("shares")) <= 0:
            return apology("must provide valid number of shares", 400)

        # Ensure that the user has enough shares
        elif int(request.form.get("shares")) > verifyShares[0]["shares"]:
            return apology("don't have that amount in account", 400)

        # Stock's details and current price
        stockInfo = lookup(request.form.get("symbol"))
        # User's available money
        userCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        userCash = userCash[0]["cash"] + stockInfo["price"]*int(request.form.get("shares"))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", userCash, session["user_id"])

        # Add transaction in db
        db.execute("INSERT INTO history (user_id, symbol, action, price, shares, total_price) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], stockInfo["symbol"], "sell", stockInfo["price"], int(request.form.get("shares")), stockInfo["price"] * int(request.form.get("shares")))

        # update shares table

        if verifyShares[0]["shares"] - int(request.form.get("shares")) == 0:
            db.execute("DELETE FROM shares WHERE user_id = ? and symbol = ?",
                       session["user_id"], stockInfo["symbol"])
        else:
            db.execute("UPDATE shares SET shares = ? WHERE user_id = ? and symbol = ?",
                       verifyShares[0]["shares"] - int(request.form.get("shares")), session["user_id"], stockInfo["symbol"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:

        return render_template("sell.html", userShares=userShares)

