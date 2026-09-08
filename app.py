import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SHOPORA_SECRET_KEY", "shopora-local-development-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.root_path, "shopora.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), default="")
    address = db.Column(db.Text, default="")
    profile_image = db.Column(db.String(255), default="")
    role = db.Column(db.String(20), default="customer", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviews = db.relationship("Review", back_populates="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")
    products = db.relationship("Product", back_populates="category", cascade="all, delete-orphan")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    brand = db.Column(db.String(100), default="Shopora")
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(500), default="")
    rating = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.relationship("Category", back_populates="products")
    reviews = db.relationship("Review", back_populates="product", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    order_items = db.relationship("OrderItem", back_populates="product")

    @property
    def current_price(self):
        return self.discount_price if self.discount_price is not None else self.price

    @property
    def discount_percent(self):
        if self.discount_price and self.price:
            return round((1 - self.discount_price / self.price) * 100)
        return 0

    def refresh_rating(self):
        values = [review.rating for review in self.reviews if review.approved]
        self.rating = round(sum(values) / len(values), 1) if values else 0


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="reviews")
    product = db.relationship("Product", back_populates="reviews")


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product", back_populates="cart_items")


class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product = db.relationship("Product")
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="unique_wishlist"),)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    shipping_cost = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), default="Pending")
    payment_method = db.Column(db.String(30), default="cod")
    shipping_address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(30), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    product_name = db.Column(db.String(180), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    cart_count = 0
    wishlist_count = 0
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        cart_count = sum(item.quantity for item in cart.items) if cart else 0
        wishlist_count = WishlistItem.query.filter_by(user_id=current_user.id).count()
    return {"cart_count": cart_count, "wishlist_count": wishlist_count, "year": datetime.utcnow().year}


@app.before_request
def csrf_protection():
    session.setdefault("csrf_token", secrets.token_hex(16))
    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if token != session.get("csrf_token"):
            abort(400, description="Invalid or missing security token.")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def get_cart():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    return cart


def seed_database():
    if User.query.first():
        return
    categories = {
        name: Category(name=name, description=description)
        for name, description in [
            ("Audio", "Immersive sound for every day."),
            ("Workspace", "Thoughtful tools for focused work."),
            ("Travel", "Carry less. Go further."),
            ("Wellness", "Small upgrades for better routines."),
        ]
    }
    db.session.add_all(categories.values())
    admin = User(name="Shopora Admin", email="admin@shopora.local", role="admin")
    admin.set_password("Admin123!")
    demo = User(name="Demo Customer", email="demo@shopora.local", role="customer", phone="+91 90000 00000")
    demo.set_password("Demo123!")
    db.session.add_all([admin, demo])
    products = [
        ("AeroTune Wireless Headphones", "Audio", "Aero", 8999, 6999, 18, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=900"),
        ("Orbit Mechanical Keyboard", "Workspace", "Orbit", 7499, 5999, 24, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=900"),
        ("Terra Everyday Backpack", "Travel", "Terra", 4999, 3999, 31, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=900"),
        ("Halo Desk Lamp", "Workspace", "Halo", 3299, None, 12, "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=900"),
        ("Pulse Smart Bottle", "Wellness", "Pulse", 2499, 1999, 42, "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=900"),
        ("Mori Ceramic Mug", "Wellness", "Mori", 1299, None, 55, "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?w=900"),
        ("Nova Portable Speaker", "Audio", "Nova", 5999, 4499, 9, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=900"),
        ("Cove Travel Organizer", "Travel", "Cove", 1899, 1499, 36, "https://images.unsplash.com/photo-1622560480605-d83c853bc5c3?w=900"),
    ]
    for name, category, brand, price, sale, stock, image in products:
        db.session.add(Product(name=name, description=f"Meet {name}, a considered everyday essential designed with premium materials, simple controls, and a calm, modern feel.", category=categories[category], brand=brand, price=price, discount_price=sale, stock=stock, image=image, rating=4.4))
    db.session.commit()


def product_query():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    brand = request.args.get("brand", "").strip()
    sort = request.args.get("sort", "newest")
    products = Product.query
    category_joined = False
    if query:
        term = f"%{query}%"
        products = products.join(Category).filter(or_(Product.name.ilike(term), Product.brand.ilike(term), Product.description.ilike(term), Category.name.ilike(term)))
        category_joined = True
    if category:
        if not category_joined:
            products = products.join(Category)
        products = products.filter(Category.name == category)
    if brand:
        products = products.filter(Product.brand == brand)
    if request.args.get("min_price"):
        products = products.filter(Product.price >= float(request.args["min_price"]))
    if request.args.get("max_price"):
        products = products.filter(Product.price <= float(request.args["max_price"]))
    if request.args.get("rating"):
        products = products.filter(Product.rating >= float(request.args["rating"]))
    if request.args.get("available") == "1":
        products = products.filter(Product.stock > 0)
    if request.args.get("discount") == "1":
        products = products.filter(Product.discount_price.isnot(None))
    ordering = {"price_low": Product.discount_price.asc(), "price_high": Product.discount_price.desc(), "rating": Product.rating.desc(), "best": Product.stock.asc(), "newest": Product.created_at.desc()}
    return products.order_by(ordering.get(sort, Product.created_at.desc())).all()


@app.route("/")
def index():
    featured = Product.query.order_by(Product.rating.desc()).limit(4).all()
    newest = Product.query.order_by(Product.created_at.desc()).limit(4).all()
    categories = Category.query.all()
    return render_template("index.html", featured=featured, newest=newest, categories=categories)


@app.route("/products")
def products():
    return render_template("products.html", products=product_query(), categories=Category.query.all(), brands=db.session.query(Product.brand).distinct().order_by(Product.brand).all())


@app.route("/api/products/suggestions")
def suggestions():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify([])
    matches = Product.query.filter(Product.name.ilike(f"%{term}%")).limit(6).all()
    return jsonify([{"name": p.name, "url": url_for("product_detail", product_id=p.id)} for p in matches])


@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    if request.method == "POST":
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        rating = int(request.form.get("rating", 0))
        comment = request.form.get("comment", "").strip()
        if rating not in range(1, 6) or len(comment) < 3:
            flash("Please provide a rating and a useful comment.", "error")
        else:
            review = Review.query.filter_by(user_id=current_user.id, product_id=product.id).first()
            if review:
                review.rating, review.comment = rating, comment
            else:
                db.session.add(Review(user=current_user, product=product, rating=rating, comment=comment))
            db.session.flush()
            product.refresh_rating()
            db.session.commit()
            flash("Your review is live. Thanks for sharing!", "success")
        return redirect(url_for("product_detail", product_id=product.id))
    session.setdefault("recently_viewed", [])
    session["recently_viewed"] = [product.id] + [x for x in session["recently_viewed"] if x != product.id]
    session["recently_viewed"] = session["recently_viewed"][:5]
    related = Product.query.filter(Product.category_id == product.category_id, Product.id != product.id).limit(4).all()
    reviews = Review.query.filter_by(product_id=product.id, approved=True).order_by(Review.created_at.desc()).all()
    return render_template("product_detail.html", product=product, related=related, reviews=reviews)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        name, email, password = request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not name or "@" not in email or len(password) < 8:
            flash("Use a name, a valid email, and a password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to Shopora!", "success")
            return redirect(url_for("index"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user and user.verify_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(request.args.get("next") or (url_for("admin_dashboard") if user.role == "admin" else url_for("index")))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    reset_url = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user:
            token = secrets.token_urlsafe(24)
            session["reset_token"] = token
            session["reset_user"] = user.id
            reset_url = url_for("reset_password", token=token, _external=True)
        else:
            flash("If that account exists, a reset link has been prepared.", "success")
    return render_template("auth.html", mode="forgot", reset_url=reset_url)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if token != session.get("reset_token"):
        abort(404)
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            user = db.session.get(User, session.get("reset_user"))
            user.set_password(password)
            db.session.commit()
            session.pop("reset_token", None)
            session.pop("reset_user", None)
            flash("Password updated. You can sign in now.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="reset")


@app.route("/cart")
@login_required
def cart():
    current_cart = get_cart()
    subtotal = sum(item.product.current_price * item.quantity for item in current_cart.items)
    discount = sum((item.product.price - item.product.current_price) * item.quantity for item in current_cart.items)
    shipping = 0 if subtotal >= 5000 or subtotal == 0 else 149
    tax = round((subtotal - discount) * 0.05, 2)
    return render_template("cart.html", cart=current_cart, subtotal=subtotal, discount=discount, shipping=shipping, tax=tax, total=subtotal + shipping + tax)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = db.get_or_404(Product, product_id)
    if product.stock < 1:
        flash("That product is currently out of stock.", "error")
    else:
        item = CartItem.query.filter_by(cart_id=get_cart().id, product_id=product.id).first()
        if item:
            item.quantity = min(item.quantity + int(request.form.get("quantity", 1)), product.stock)
        else:
            db.session.add(CartItem(cart_id=get_cart().id, product_id=product.id, quantity=min(int(request.form.get("quantity", 1)), product.stock)))
        db.session.commit()
        flash(f"{product.name} added to your cart.", "success")
    return redirect(request.form.get("next") or url_for("cart"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    item = db.get_or_404(CartItem, item_id)
    if item.cart.user_id != current_user.id:
        abort(403)
    item.quantity = max(0, min(int(request.form.get("quantity", 1)), item.product.stock))
    if item.quantity == 0:
        db.session.delete(item)
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_cart_item(item_id):
    item = db.get_or_404(CartItem, item_id)
    if item.cart.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/wishlist")
@login_required
def wishlist():
    return render_template("wishlist.html", items=WishlistItem.query.filter_by(user_id=current_user.id).all())


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
@login_required
def toggle_wishlist(product_id):
    db.get_or_404(Product, product_id)
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        message = "Removed from wishlist."
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
        message = "Saved to wishlist."
    db.session.commit()
    flash(message, "success")
    return redirect(request.form.get("next") or url_for("wishlist"))


@app.route("/wishlist/move/<int:item_id>", methods=["POST"])
@login_required
def move_wishlist(item_id):
    item = db.get_or_404(WishlistItem, item_id)
    if item.user_id != current_user.id:
        abort(403)
    cart_item = CartItem.query.filter_by(cart_id=get_cart().id, product_id=item.product_id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        db.session.add(CartItem(cart_id=get_cart().id, product_id=item.product_id, quantity=1))
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    current_cart = get_cart()
    if not current_cart.items:
        return redirect(url_for("cart"))
    subtotal = sum(item.product.current_price * item.quantity for item in current_cart.items)
    discount = sum((item.product.price - item.product.current_price) * item.quantity for item in current_cart.items)
    shipping = 0 if subtotal >= 5000 else 149
    tax = round(subtotal * 0.05, 2)
    total = round(subtotal + shipping + tax, 2)
    if request.method == "POST":
        address = request.form.get("shipping_address", "").strip()
        phone = request.form.get("phone", "").strip()
        if len(address) < 10 or len(phone) < 7:
            flash("Please provide a complete shipping address and phone number.", "error")
        elif any(item.quantity > item.product.stock for item in current_cart.items):
            flash("One of your items no longer has enough stock.", "error")
        else:
            order = Order(user_id=current_user.id, subtotal=subtotal, discount=discount, shipping_cost=shipping, tax=tax, total_amount=total, payment_method=request.form.get("payment_method", "cod"), shipping_address=address, phone=phone, status="Confirmed")
            db.session.add(order)
            for item in current_cart.items:
                item.product.stock -= item.quantity
                db.session.add(OrderItem(order=order, product_id=item.product.id, product_name=item.product.name, quantity=item.quantity, price=item.product.current_price))
            current_cart.items.clear()
            db.session.commit()
            flash("Order placed successfully.", "success")
            return redirect(url_for("order_detail", order_id=order.id))
    return render_template("checkout.html", cart=current_cart, subtotal=subtotal, discount=discount, shipping=shipping, tax=tax, total=total)


@app.route("/orders")
@login_required
def orders():
    return render_template("orders.html", orders=Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all())


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    if order.user_id != current_user.id and current_user.role != "admin":
        abort(403)
    return render_template("order_detail.html", order=order)


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    order = db.get_or_404(Order, order_id)
    if order.user_id != current_user.id or order.status not in ("Pending", "Confirmed"):
        abort(403)
    order.status = "Cancelled"
    for item in order.items:
        if item.product:
            item.product.stock += item.quantity
    db.session.commit()
    flash("Your order has been cancelled.", "success")
    return redirect(url_for("orders"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", "").strip() or current_user.name
        current_user.phone = request.form.get("phone", "").strip()
        current_user.address = request.form.get("address", "").strip()
        new_password = request.form.get("new_password", "")
        if new_password:
            if len(new_password) < 8:
                flash("New password must be at least 8 characters.", "error")
                return render_template("profile.html")
            current_user.set_password(new_password)
        db.session.commit()
        flash("Profile updated.", "success")
    return render_template("profile.html")


@app.route("/about")
def about():
    return render_template("info.html", title="About Shopora", heading="Objects with a point of view.", content="Shopora is a small, independent edit of useful things for calmer workdays, lighter travel, and better rituals.")


@app.route("/faq")
def faq():
    return render_template("info.html", title="FAQ", heading="Questions, answered.", content="Orders typically leave our studio within two working days. Shipping is free above ₹5,000. Cash on Delivery and mock online payment are available in this local demo.")


@app.route("/contact")
def contact():
    return render_template("info.html", title="Contact", heading="A real person is listening.", content="For this demo, reach us at hello@shopora.local. In a production deployment, connect this form to your preferred email provider.")


@app.route("/admin")
@admin_required
def admin_dashboard():
    revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(Order.status != "Cancelled").scalar()
    return render_template("admin/dashboard.html", users=User.query.count(), product_count=Product.query.count(), order_count=Order.query.count(), revenue=revenue, recent_orders=Order.query.order_by(Order.created_at.desc()).limit(6).all(), low_stock=Product.query.filter(Product.stock < 10).order_by(Product.stock).all())


@app.route("/admin/products")
@admin_required
def admin_products():
    return render_template("admin/products.html", products=Product.query.order_by(Product.created_at.desc()).all())


@app.route("/admin/products/new", methods=["GET", "POST"])
@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_form(product_id=None):
    product = db.session.get(Product, product_id) if product_id else Product()
    if product_id and not product:
        abort(404)
    if request.method == "POST":
        try:
            product.name = request.form["name"].strip()
            product.description = request.form["description"].strip()
            product.category_id = int(request.form["category_id"])
            product.brand = request.form["brand"].strip()
            product.price = float(request.form["price"])
            sale = request.form.get("discount_price", "").strip()
            product.discount_price = float(sale) if sale else None
            product.stock = max(0, int(request.form["stock"]))
            product.image = request.form.get("image", "").strip()
            if not product_id:
                db.session.add(product)
            db.session.commit()
            flash("Product saved.", "success")
            return redirect(url_for("admin_products"))
        except (KeyError, ValueError):
            flash("Please fill every product field correctly.", "error")
    return render_template("admin/product_form.html", product=product, categories=Category.query.all())


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_product_delete(product_id):
    product = db.get_or_404(Product, product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin/users.html", users=User.query.order_by(User.created_at.desc()).all())


@app.route("/admin/orders")
@admin_required
def admin_orders():
    return render_template("admin/orders.html", orders=Order.query.order_by(Order.created_at.desc()).all())


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id):
    order = db.get_or_404(Order, order_id)
    order.status = request.form.get("status", "Pending")
    db.session.commit()
    flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/reviews")
@admin_required
def admin_reviews():
    return render_template("admin/reviews.html", reviews=Review.query.order_by(Review.created_at.desc()).all())


@app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
@admin_required
def admin_review_delete(review_id):
    review = db.get_or_404(Review, review_id)
    product = review.product
    db.session.delete(review)
    db.session.flush()
    product.refresh_rating()
    db.session.commit()
    flash("Review removed.", "success")
    return redirect(url_for("admin_reviews"))


@app.errorhandler(404)
def not_found(error):
    return render_template("info.html", title="Page not found", heading="That page wandered off.", content="The link may be old, or the product may have moved."), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template("info.html", title="Access denied", heading="This area is private.", content="You do not have permission to view this page."), 403


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    app.run(debug=True)
