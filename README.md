# Fakey Store
#### Video Demo: https://youtu.be/Oe8g_rlVjN0
#### Description:

So this project is a web application using Flask, Python, JavaScript, HTML, Bootstrap, basic CSS, and an SQLite3 database.

It is a web store that fetches data from an API in the backend (Python/Flask). When retrieved, the API returns an array of dictionaries, where each dictionary represents a product. The app features a complete register, login, and logout system. Through the interface (HTML/CSS) and forms, users can maintain information while navigating the app—such as a shopping cart—and interact with the database. The database keeps track of the transactions (purchases and refunds) made by the user.

These actions are possible thanks to sections like Home, Refunds, Cart, History, and Add Funds (when a user is registered, they start with $1000.00 in cash by default). All of these sections are explained below.

### Disclaimer of Inspiration, API, and AI Usage
As stated in the guidelines for this final project, I used Gemini AI strictly for debugging purposes and for Bootstrap implementation guides. Most of the code has been typed by me. The structure is inspired by the "Finance" problem from CS50 Problem Set 9. I used the tools the course offered and added extra features like `flash` messages, sessions for cart features, advanced Bootstrap components, complex database tables, and new sections applied to a different field (e-commerce instead of stock finance).

The API used was `dummyjson.com`, specifically the data from: https://dummyjson.com/products

---

### Database (`final.db`)
This is the database that stores information across three tables:
1. **`users`**: Stores the username, hashed password, and the cash of each user, linking them to a unique ID.
2. **`products`**: Stores the title, category, and thumbnail of a product fetched from the API.
3. **`transactions`**: Stores the `user_id`, `product_id`, `quantity`, `price`, and `timestamp` of each transaction made.

---

### Backend (`app.py`)
This is the backend where communications with the database occur using `SQL` from the `cs50` library. It manages sessions using `flask_session` and uses hash functions from `werkzeug.security` to make user passwords as secure as possible. The most important functions and their related HTML templates are explained below.

#### Useful Helper Functions
* **`login_required(f)`**: Used as a decorator, it wraps a function to remember it. If no `user_id` is set in the session (meaning the user has not logged in), it redirects them to `/login`. Otherwise, it returns the function it takes. This decorator is applied to all addresses of the page that require the user to be logged in.
* **`retrieve_products()`**: This function doesn't take arguments. Through `requests`, it gets a response from the DummyJSON API. In a successful case, it returns the array of all the products the web store sells.

#### `@app.route("/register")` — `register.html`
* **CASE GET:** We render `register.html`, showing the form where the user can write their desired username, password, and the confirmation of the password to make sure they have typed it correctly. It uses a form with a `POST` method to register.
* **CASE POST:** It takes and validates the username, password, and confirmation to make sure they aren't blank, and checks that the password and confirmation match. After validation, it hashes the password, inserts the new user into the `users` table of the database, and redirects to the login page.
* *NOTE: This route, like the others, uses `flash` to send success or warning messages to the user.*

#### `@app.route("/login")` — `login.html`
* **CASE GET:** We render `login.html`, displaying the form where the user can write their registered username and password, using a `POST` method to log in.
* **CASE POST:** It validates the username and password to make sure they aren't blank, queries the database to check if the username exists, and verifies the password against the hashed one using a Werkzeug function. Once everything is verified, the session is cleared, the `user_id` key is updated, and the `cart` key is initialized as empty.

#### `@app.route("/logout")`
* **CASE GET:** The session is cleared, and the user is safely redirected to the home page.

#### `@app.route("/add")` — `add.html`
* **CASE GET:** Gets the `user_id` to retrieve the username and the current cash balance, which are sent to render `add.html`. It displays the current cash and features a form (using `POST`) that takes a monetary quantity and a button to add funds to the database.
* **CASE POST:** When the user submits the form, it validates the quantity of money submitted and updates the cash value in the `users` table. Afterward, it redirects to `/add` so the user can see their updated balance.

#### `@app.route("/")` — `index.html` (Home Page)
* **CASE GET:** Retrieves the products using the `retrieve_products()` function and sends them to render `index.html`. This is the most complex HTML file in the project. It contains:
  * **A Categories Container:** Using JavaScript, it gets the distinct categories from the product list and creates a checkbox input for each. When selected, a `fetchCertainProducts()` function filters the display using `displayProducts()`.
  * **A Products Container:** Using JavaScript, `displayProducts()` dynamically adds HTML strings for each product into the grid. Each product card includes a button that acts as a form (using `POST`) to send the desired quantity and product index to the `/cart` route.
  * **A Search Bar:** An input of type "search" allows the user to look for a product. JavaScript takes the value and matches it against product titles, descriptions, brands, or tags.
  * **A Load More Button:** Using a `fetchMoreProducts()` function, it dynamically displays 30 more products by adjusting the starting and ending index of the array.

#### `@app.route("/cart")`, `/delete`, and `/buy` — `cart.html`
* **CASE GET (`/cart`):** Gets the cart dictionary from the session, transforms it into a list, and calculates the grand total (price * quantity of all items). This data renders `cart.html`. Using Jinja, it displays the thumbnail, title, category, price, quantity, and total in a table. It also includes a `POST` form to delete a product.
* **CASE POST (`/cart`):** Gets the index and quantity, retrieves product data using `retrieve_products()`, and inserts the product into the `products` SQL table if it doesn't already exist. It then adds the item to `session["cart"]` (title, category, price, quantity, thumbnail, and total) and redirects back to `/cart`.
* **CASE POST (`/delete`):** When the user clicks the delete button, it sends the product index. The item is popped from the `session["cart"]` dictionary, and the page redirects to `/cart` to reflect the changes.
* **CASE POST (`/buy`):** Gets the cart and `user_id`, calculates the grand total, and checks the user's current cash. If the user has enough cash, it subtracts the cost, inserts a new transaction for each product into the `transactions` table, clears the session cart, and redirects to `/history`.

#### `@app.route("/refund")` — `refund.html`
* **CASE GET:** Gets the `user_id` and the user's "storage" (a subarray of products retrieved from a `JOIN` of the `transactions` and `products` tables). By grouping and summing quantities (positive for purchases, negative for refunds), it calculates how many of each item the user currently owns. It renders a select dropdown for the user to choose an item to refund, dynamically updating the max quantity via JavaScript.
* **CASE POST:** Validates the selected index and quantity. It calculates the total refund amount (price * quantity), adds this amount back to the user's cash in the database, and logs the refund as a new transaction with a *negative* quantity to differentiate it from a purchase. It then redirects to `/history`.

#### `@app.route("/history")` — `history.html`
* **CASE GET:** Retrieves all of the user's transactions from the database using their `user_id` and renders `history.html`. It displays the thumbnail, title, price, quantity, total, and timestamp in a table. It uses Jinja logic to show a green "Purchase" badge if the quantity is positive, or a blue "Refund" badge if the quantity is negative.
