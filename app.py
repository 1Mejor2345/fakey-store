import requests
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# Configure app
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure database
db = SQL("sqlite:///final.db")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def retrieve_products():
    """Retrieves products from the API"""
    try:
        response = requests.get("https://dummyjson.com/products?limit=194&skip=0")
        response.raise_for_status() # Raise an error for HTTP error responses
        data = response.json()
        return data["products"]
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None

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
    """Shows main page"""
    products = retrieve_products()
    return render_template("index.html", products=products)

@app.route("/cart", methods=["GET", "POST"])
@login_required
def cart():

    # Case of POST
    if request.method == "POST":

        products = retrieve_products()

        # Validate index
        index = request.form.get("index")
        if not index:
            flash("Index's input is blank.", "warning")
            return redirect("/cart")
        if not index.isdigit():
            flash("Index must be a positive integer.", "warning")
            return redirect("/cart")
        index = int(index)
        if not index in range(len(products)):
            flash("Index out of range.", "danger")
            return redirect("/cart")

        # Validate quantity
        quantity = request.form.get("quantity")
        if not quantity:
            flash("Quantity's input is blank.", "warning")
            return redirect("/cart")
        if not quantity.isdigit():
            flash("Quantity must be a positive integer.", "warning")
            return redirect("/cart")
        quantity = int(quantity)
        if quantity > products[index]["stock"]:
            flash("There is not sufficient stock for that quantity", "danger")
            return redirect("/cart")

        # Save data
        product_id = index
        title = products[product_id]["title"]
        category = products[product_id]["category"]
        thumbnail = products[product_id]["thumbnail"]
        price = products[product_id]["price"]
        total = quantity * price

        # Try to insert it into the products table
        existing = db.execute("SELECT id FROM products WHERE id = ?", product_id)
        if not existing:
            db.execute("INSERT INTO products (id, title, category, thumbnail) VALUES (?, ?, ? ,?);", product_id, title, category, thumbnail)

        # Add it to the cart
        if "cart" not in session:
            session["cart"] = {}

        product_id_str = str(product_id)
        if product_id_str in session["cart"]:
            session["cart"][product_id_str]["quantity"] += quantity
            session["cart"][product_id_str]["total"] = session["cart"][product_id_str]["quantity"] * price
        else:
            session["cart"][product_id_str] = {
                "product_id": product_id,
                "title": title,
                "category": category,
                "price": price,
                "quantity": quantity,
                "thumbnail": thumbnail,
                "total": total
            }

        # Success! Redirects to the cart
        return redirect("/cart")

    else:
        # Case of GET
        cart_dict = session.get("cart", {})
        cart_list = list(cart_dict.values())
        grand_total = sum(item["total"] for item in cart_list)
        return render_template("cart.html", cart=cart_list, grand_total=grand_total)

@app.route("/delete", methods=["POST"])
@login_required
def delete():
    """Remove an item from the cart"""

    # Validate id of the product to eliminate
    product_id_str = request.form.get("product_id")

    # Try to delete from cart
    if "cart" in session and product_id_str in session["cart"]:
        session["cart"].pop(product_id_str)
        session.modified = True
        flash("Item removed from cart.", "success")
    else:
        flash("Item not found.", "warning")

    # Success, redirects to cart
    return redirect("/cart")

@app.route("/buy", methods=["POST"])
@login_required
def buy():
    """Buys all the items from the cart"""

    # Get the cart, and user's id
    cart_dict = session.get("cart", {})
    cart_list = list(cart_dict.values())
    user_id = session.get("user_id")

    # Case the cart is empty
    if len(cart_list) == 0:
        flash("Cart is empty. You cannot buy.", "warning")
        return redirect("/cart")

    # Get the total to pay, and the user's current cash
    grand_total = sum(item["total"] for item in cart_list)

    # Fetch user's cash
    user_data = db.execute("SELECT cash FROM users WHERE id=?;", user_id)
    cash = user_data[0]["cash"]

    # Check if the user can afford it
    if cash < grand_total:
        flash("You don't have enough cash to buy.", "danger")
        return redirect("/cart")

    # Substract the cash from the user
    db.execute("UPDATE users SET cash = cash - ? WHERE id = ?;", grand_total, user_id)

    # Insert each item into the transactions table
    for item in cart_list:
        db.execute("INSERT INTO transactions (user_id, product_id, quantity, price) VALUES (?, ?, ?, ?)", user_id, item["product_id"], item["quantity"], item["price"])

    # Clear the cart
    session["cart"] = {}
    session.modified = True

    # Success, now redirects to history
    flash("Purchase successful! Thank you for shopping with us.", "success")
    return redirect("/history")

@app.route("/history", methods=["GET"])
@login_required
def history():
    """Shows all the transactions the user's has done"""

    # Get the user's id
    user_id = session.get("user_id")

    # Get the transactions, and return the history.html
    transactions = db.execute("SELECT transactions.quantity, transactions.price, transactions.timestamp, products.title, products.thumbnail, products.id FROM transactions JOIN products ON transactions.product_id = products.id WHERE transactions.user_id = ? ORDER BY transactions.timestamp DESC;", user_id)
    return render_template("history.html", transactions=transactions)

@app.route("/refund", methods=["GET", "POST"])
@login_required
def refund():

    # Case of POST
    if request.method == "POST":
        """Returns a product a get the money back"""

        # Get the user_id, storage, and valid indexes
        user_id = session.get("user_id")
        storage = db.execute("SELECT products.id, products.thumbnail, products.title, SUM(transactions.quantity) AS quantity, transactions.price FROM transactions JOIN products ON transactions.product_id = products.id WHERE transactions.user_id = ? GROUP BY transactions.product_id HAVING quantity > 0 ORDER BY transactions.timestamp DESC;", user_id)
        indexes = [item["id"] for item in storage]


        # Validate index
        index = request.form.get("index")
        if not index:
            flash("Index's input is blank.", "warning")
            return redirect("/refund")
        if not index.isdigit():
            flash("Index must be a positive integer.", "warning")
            return redirect("/refund")
        index = int(index)
        if not index in indexes:
            flash("Invalid index", "danger")
            return redirect("/refund")

        # Get the item, and the price for refund
        item = None
        for product in storage:
            if product['id'] == index:
                item = product
                break
        price = item["price"]

        # Validate quantity
        quantity = request.form.get("quantity")
        if not quantity:
            flash("Quantity's input is blank.", "warning")
            return redirect("/refund")
        if not quantity.isdigit():
            flash("Quantity must be a positive integer.", "warning")
            return redirect("/refund")
        quantity = int(quantity)
        if quantity > item["quantity"]:
            flash("You cannot refund more that you have in your storage.", "danger")
            return redirect("/refund")

        # Calculate the total to recieve
        total = quantity * price

        # Substract the cash from the user
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?;", total, user_id)

        # Insert the refund into transactions table
        db.execute("INSERT INTO transactions (user_id, product_id, quantity, price) VALUES (?, ?, ?, ?)", user_id, index, -quantity, price)

        # Success, now redirects to history
        flash("Refund successful! Thank you for shopping with us.", "success")
        return redirect("/history")

    else:
        # Case of GET

        # Get the list to show the storage
        user_id = session.get("user_id")
        storage = db.execute("SELECT products.id, products.thumbnail, products.title, SUM(transactions.quantity) AS quantity, transactions.price FROM transactions JOIN products ON transactions.product_id = products.id WHERE transactions.user_id = ? GROUP BY transactions.product_id HAVING SUM(transactions.quantity) > 0 ORDER BY transactions.timestamp DESC;", user_id)
        return render_template("refund.html", storage=storage)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """Add money to your cash"""

    # Case of POST
    if request.method == "POST":

        # Get user's id
        user_id = session.get("user_id")

        # Validate quantity
        quantity = request.form.get("quantity")
        if not quantity:
            flash("Quantity's input is blank.", "warning")
            return redirect("/refund")
        try:
            quantity = float(quantity)
            if quantity <= 0 or float('inf') == quantity:
                flash("Quantity must be a positive float.", "warning")
                return redirect("/add")
        except:
            flash("Quantity must be a positive float.", "warning")
            return redirect("/refund")

        # Try to update user's cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", quantity, user_id)

        flash("You have succesfully added funds to your current cash","success")
        return redirect("/add")
    else:
        # Case of GET
        user_id = session.get("user_id")
        username = db.execute("SELECT username FROM users WHERE id = ?;", user_id)[0]["username"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        return render_template("add.html", cash=cash, username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log the user in"""

    # Case of POST
    if request.method == "POST":

        # Get username and password and ensures they're not blank
        username = request.form.get("username")
        if not username:
            flash("Username's input is blank.", "warning")
            return redirect("/login")

        password = request.form.get("password")
        if not password:
            flash("Password's input is blank.", "warning")
            return redirect("/login")

        # Query the database for the username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Check if the username exists and the password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username and/or password", "danger")
            return redirect("/login")

        # Clear the user_id
        session.clear()

        # Save the user_id
        session["user_id"] = rows[0]["id"]
        session["cart"] = {}
        flash(f"You have succesfully logged. Welcome ${rows[0]["username"]}", "success")
        return redirect("/")

    else:
        # Case of GET
        return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register the user"""

    # Case of POST
    if request.method == "POST":

        # Validate username, password and confirmation
        username = request.form.get("username")
        if not username:
            flash("Username's input is blank.", "warning")
            return redirect("/register")

        password = request.form.get("password")
        if not password:
            flash("Password's input is blank.", "warning")
            return redirect("/register")

        confirmation = request.form.get("confirmation")
        if not confirmation:
            flash("Confirmation's input is blank.", "warning")
            return redirect("/register")

        # Check if password and confirmation match
        if password != confirmation:
            flash("Passwords do not match", "danger")
            return redirect("/register")

        # Hash the password
        hash_password = generate_password_hash(password)

        # Insert the user into the database
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)
        except:
            flash("Username already exists", "warning")
            return redirect("/register")

        # Success, redirects to the login page
        flash("User created succesfully, you can now log in", "success")
        return redirect("/login")

    else:
        # Case of GET
        return render_template("register.html")

@app.route("/logout")
def logout():
    """Log the user out"""

    # Clear user_id
    session.clear()

    # Success, redirects to home page
    flash("User has succesfully logged out", "success")
    return redirect("/")


