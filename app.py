from itertools import product
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_, func
from sqlalchemy import text
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)  # Load environment variables from .env file
raw_key = os.getenv("GEMINI_API_KEY")

if raw_key:
    # .strip() completely removes any invisible spaces, tabs, or newlines
    clean_key = raw_key.strip()
    print(f"✅ DEBUG: AI Key loaded! Starts with: {clean_key[:7]}... Length: {len(clean_key)}")
    client = genai.Client(api_key=clean_key)
else:
    print("🚨 CRITICAL ERROR: API Key is None! The .env file is completely missing or empty.")
    # Fallback to prevent immediate crash, though AI will still fail
    client = genai.Client(api_key="MISSING_KEY")

# This fixes the "name 'client' is not defined" error for Gemini
# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 1. Define the exact path to your project folder FIRST
basedir = os.path.abspath(os.path.dirname(__file__))

# 2. Tell Python exactly where the .env file is hiding
load_dotenv(os.path.join(basedir, '.env'))

# 3. NOW it is safe to pull your hidden keys
raw_key = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

# Fetch the secret key from the environment. 
# The second argument is a fallback just in case the .env fails to load.
app.secret_key = os.getenv('SECRET_KEY', 'fallback_default_secret_key_if_missing')

import os

# Check if we are running on the live PythonAnywhere server
import os
basedir = os.path.abspath(os.path.dirname(__file__))

if 'PYTHONANYWHERE_DOMAIN' in os.environ:
    # --- LIVE DATABASE CONNECTION (Free SQLite Workaround) ---
    # This creates a file named 'live_yuliv.db' inside your project folder
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'live_yuliv.db')
else:
    # Format: mysql+pymysql://username:password@127.0.0.1:3306/database_name
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Hanish5^611@127.0.0.1:3306/yuliv_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_default_secret_key_if_missing')

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    pincode = db.Column(db.String(10), nullable=True)
    is_admin = db.Column(db.Boolean, default=False) # <--- ADD THIS LINE
    cart_items = db.relationship('CartItem', backref='owner', cascade="all, delete-orphan")

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        # If the database is missing a column, rollback the error and log the user out safely
        db.session.rollback()
        return None

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    
    # This line MUST exist for the HTML to fetch the product name and price!
    product = db.relationship('Products')

@app.context_processor
def inject_user():
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return dict(current_user=current_user, cart_count=cart_count)

class Products(db.Model):
    __tablename__ = 'inventory' # Matches your table name
    id = db.Column(db.Integer, primary_key=True)
    ean_code = db.Column(db.String(100))
    product_name = db.Column(db.String(200))
    product_price = db.Column(db.Float)
    selling_price = db.Column(db.Float)
    discount = db.Column(db.Float)
    inventory_qty = db.Column(db.Integer)

@app.route('/test-db')
def test_db():
    try:
        count = Products.query.count()
        return f"Success! Connected to database. Total items: {count}"
    except Exception as e:
        return f"Connection Failed: {str(e)}"

@app.route('/fix-db')
def fix_db():
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN pincode VARCHAR(10);"))
        db.session.commit()
        return "Success! The 'pincode' column was added to the database. You can go back and login/signup now."
    except Exception as e:
        return f"Database update failed (the column might already exist, or there's another error): {str(e)}"

#medicines = [
#    {"name": "Paracetamol", "use": "Pain relief and fever", "date": "2025-01-01"},
#    {"name": "Amoxicillin", "use": "Antibiotic for infections", "date": "2024-12-15"},
#   {"name": "Ibuprofen", "use":
#        "Anti-inflammatory painkiller", "date": "2025-06-30"},
#    {"name": "Cetirizine", "use": "Allergy relief", "date": "2024-10-10"},
 #   {"name": "Vitamin C", "use": "Immune system support", "date": "2025-03-20"}
#]

@app.route('/')
def home():
    # This looks for index.html inside the 'templates' folder automatically
    return render_template('index.html')

@app.route('/search')
def search():
    raw_query = request.args.get('q', '').lower().strip()
    if not raw_query:
        return render_template('search_results.html', query=raw_query, results=[], ai_top=None, ai_bottom=None)

    # 1. CLEAN THE QUERY
    # Turn hyphens/commas into spaces so "sali-cinamide" becomes "sali cinamide"
    clean_query = raw_query.replace('-', ' ').replace(',', ' ')

    # 2. STRICTER INVENTORY SEARCH
    stop_words = {'i', 'need', 'want', 'some', 'medicine', 'for', 'a', 'an', 'my', 'have', 'the', 'is', 'in', 'with', 'to'}
    # Split the clean query into individual words
    words = [word for word in clean_query.split() if word not in stop_words] or [clean_query.replace(' ', '')]
    
    # 3. CRUSH THE DATABASE STRING (The Magic)
    # This temporarily removes spaces and hyphens from the database column just for this search
    crushed_db_name = func.replace(func.replace(Products.product_name, ' ', ''), '-', '')
    
    # Must match ALL keywords in the crushed product name
    name_conditions = [crushed_db_name.ilike(f"%{word}%") for word in words]
    
    # Combine: Match ALL words in name, OR match the exact EAN code
    results = Products.query.filter(
        or_(
            and_(*name_conditions),
            Products.ean_code.ilike(f"%{raw_query}%")
        )
    ).all()
    
    print(f"Inventory search: Query='{raw_query}', Found={len(results)}")
    
    # ... (Keep the rest of your AI code exactly as it is below this line) ...

    # 2. Extract in-stock names to prevent AI from duplicating them
    in_stock_names = ", ".join([item.product_name for item in results]) if results else "None"

    # 3. Ask AI for Insights & Alternatives
    try:
        from google import genai
        # 1. Check if a specific model is forced via .env
        configured_model = os.getenv("GEMINI_MODEL")

        if configured_model:
            model_name = configured_model.strip()
        else:
            # 2. Desired priority list (from newest/best to reliable standard)
            PREFERRED_MODELS = [
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-3.5-flash",
                "gemini-3.1-flashlite",
            ]

            # 3. Normalize available model strings (stripping 'models/' prefix safely)
            normalized_available = [
                (m.name if hasattr(m, "name") else str(m)).replace("models/", "").strip()
                for m in available_models
            ]

            # 4. Pick the highest-priority model that exists in available_models
            model_name = next(
                (m for m in PREFERRED_MODELS if m in normalized_available),
                normalized_available[0] if normalized_available else "gemini-3.5-flash"
            )

        print(f"🤖 Active Gemini Model: {model_name}")

        prompt = f"""You are an expert pharmacist at YuLiv Pharmacy. Analyze this customer search query: '{raw_query}'.
        
       CRITICAL INSTRUCTIONS: 
        1. Determine if it is a SYMPTOM or a PRODUCT/BRAND.
        2. We ALREADY have these items in stock: [{in_stock_names}]. DO NOT suggest these exact products in your alternatives. Suggest DIFFERENT substitute brands.
        3. Return ONLY raw HTML code. Do not use markdown blocks.
        4. You MUST separate the top Insights section and the bottom Alternatives section using exactly this text: <!-- SPLIT -->
        
        IF IT IS A SYMPTOM, format exactly like this:
        <div class="ai-card">
            <h4 class="card-title">🩺 Understanding Your Symptoms</h4>
            <p style="margin-bottom: 12px; line-height: 1.5;"><strong>Possible Causes:</strong> [Detailed explanation]</p>
            <p style="margin-bottom: 0; line-height: 1.5;"><strong>Lifestyle Advice:</strong> [Practical tips]</p>
        </div>
        <!-- SPLIT -->
        <div class="ai-card">
            <h4 class="card-title">💊 Other Over-the-Counter Options</h4>
            <div class="product-item">...</div>
        </div>
        
        IF IT IS A PRODUCT OR BRAND, format exactly like this:
        <div class="ai-card">
            <h4 class="card-title">📦 Product Insights</h4>
            <p style="margin-bottom: 12px; line-height: 1.5;"><strong>About this Search:</strong> [Explanation]</p>
            <p style="margin-bottom: 0; line-height: 1.5;"><strong>Key Ingredients:</strong> [List ingredients]</p>
        </div>
        <!-- SPLIT -->
        <div class="ai-card">
            <h4 class="card-title">🔄 Alternative Brands to Consider</h4>
            <div class="product-item">...</div>
        </div>
        """

        response = client.models.generate_content(model=model_name, contents=prompt)
        ai_solution = response.text.replace('```html', '').replace('```', '').strip()
        
        # Split the AI HTML into Top (Insights) and Bottom (Alternatives)
        if "<!-- SPLIT -->" in ai_solution:
            ai_top, ai_bottom = ai_solution.split("<!-- SPLIT -->", 1)
        else:
            ai_top = ai_solution
            ai_bottom = ""
        
    except Exception as e:
        print(f"AI Error: {e}")
        error_string = str(e)
        if "429" in error_string or "RESOURCE_EXHAUSTED" in error_string:
            # FIXED: Assigning to ai_top and ai_bottom so the return statement doesn't crash
            ai_top = """
            <div class="ai-card">
                <h4 class="card-title">⏳ AI is Catching Its Breath</h4>
                <p style="margin-bottom: 0; line-height: 1.5;">Our AI pharmacist is currently assisting other customers. Please wait about 30 seconds and click search again!</p>
            </div>
            """
            ai_bottom = ""
        else:
            # FIXED: Assigning to ai_top and ai_bottom here as well
            ai_top = f"<strong style='color:red;'>AI Error:</strong> {error_string}"
            ai_bottom = ""

# --- ENHANCED: Fetch Detailed Cart Data & Calculate Savings ---
    cart_items = []
    cart_qtys = {}
    cart_details = []  
    cart_total = 0     
    total_savings = 0  # NEW: Tracks the customer's total savings
    checkout_mode = request.args.get('checkout') == 'true'
    
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        for item in cart_items:
            cart_qtys[item.product_id] = item.quantity
            
            product = Products.query.get(item.product_id)
            if product:
                # 1. Grab MRP and Discount, default to 0 if missing
                mrp = product.mrp if product.mrp else 0
                discount_pct = product.discount if product.discount else 0
                
                # 2. Calculate the exact YuLiv Price
                discount_amount = mrp * (discount_pct / 100)
                yuliv_price = mrp - discount_amount
                
                # 3. Calculate line totals
                item_total = yuliv_price * item.quantity
                item_savings = discount_amount * item.quantity
                
                # 4. Add to Grand Totals
                cart_total += item_total
                total_savings += item_savings
                
                # 5. Pass it all to the HTML
                cart_details.append({
                    'name': product.product_name,
                    'mrp': mrp,
                    'yuliv_price': round(yuliv_price, 2),
                    'qty': item.quantity,
                    'total': round(item_total, 2)
                })

    return render_template('search_results.html', 
                           query=raw_query, 
                           results=results, 
                           ai_top=ai_top, 
                           ai_bottom=ai_bottom,
                           cart_items=cart_items,
                           cart_qtys=cart_qtys,
                           cart_details=cart_details,
                           cart_total=round(cart_total, 2),
                           total_savings=round(total_savings, 2),
                           checkout_mode=checkout_mode)

    # 4. Final Step: Send BOTH the database 'results' AND the 'ai_solution' to the HTML template
    # return render_template('search_results.html', query=raw_query, results=results, ai_top=ai_top, ai_bottom=ai_bottom)
    # -------------------------------

    print(f"Inventory search: Query='{query}', Found=0. Showing AI context.")
    return render_template('search_results.html', query=query, results=[], ai_solution=ai_solution)

@app.route('/api/recommend', methods=['POST'])
def ai_recommend():
    data = request.json
    preferences = data.get('preferences', [])
    if not preferences:
        return {"html": "<p>Click on categories to get personalized AI suggestions!</p>"}

    try:
        import google.generativeai as genai
        # Change this on lines 114 and 198 for git bit secret key usage
        api_key = os.getenv("OPENAI_API_KEY")
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        pref_str = ', '.join(preferences)
        prompt = f"""You are a Gen-Z wellness and pharmacy AI assistant. The user recently clicked on these categories: {pref_str}.
        Suggest 3 trendy, related product categories, quick wellness tips, or specific items they might like in a highly visual, modern HTML format. 
        Use emojis. Keep it extremely brief. Return ONLY valid HTML (no markdown backticks, no ```html).
        Example format: 
        <div style="display:flex;gap:15px;flex-wrap:wrap;justify-content:center;">
           <div style="background:#fff;padding:15px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.05);flex:1;min-width:200px;">
              <h4 style="margin:0 0 10px;color:#ff6600;">✨ Glowing Skin</h4><p style="margin:0;color:#555;">Try a Vitamin C serum for that natural glow!</p>
           </div>
        </div>
        """
        response = model.generate_content(prompt)
        return {"html": response.text}
    except Exception as e:
        print(f"AI Recommend Error: {e}")
        return {"html": "<p>AI is taking a quick nap 😴. Check back later!</p>"}

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/home')
def home_page():
    # This looks for index.html inside the 'templates' folder automatically
    return render_template('index.html')

@app.route('/googleYOUR_FILE_NAME.html')
def google_verify():
    return render_template('googleYOUR_FILE_NAME.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', category='error')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        pincode = request.form.get('pincode')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists.', category='error')
        else:
            # We use pbkdf2:sha256 for password hashing
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, password=hashed_password, pincode=pincode)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            return redirect(url_for('home'))
            
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/orders')
@login_required
def orders():
    return render_template('orders.html')

@app.route('/history')
@login_required
def browsing_history():
    return render_template('history.html')

@app.route('/recommendations')
@login_required
def recommendations():
    return render_template('recommendations.html')

@app.route('/category/<category_name>')
def shop_by_category(category_name):
    # We redirect the category click directly into your powerful AI search logic!
    return redirect(url_for('search', q=category_name))

@app.route('/add_to_cart/<int:product_id>', methods=['GET', 'POST'])
@login_required
def add_to_cart(product_id):
    user_id = current_user.id
    added_qty = 1
    
    # We will track which button they clicked ('cart' is default)
    action = 'cart'
    
    if request.method == 'POST':
        try:
            added_qty = int(request.form.get('quantity', 1))
        except ValueError:
            added_qty = 1
            
        # Grab the value of the button they clicked
        action = request.form.get('action', 'cart')
    
    existing_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    
    if existing_item:
        existing_item.quantity += added_qty
    else:
        new_item = CartItem(user_id=user_id, product_id=product_id, quantity=added_qty)
        db.session.add(new_item)
        
    db.session.commit()
    
   # THE NEW ROUTING LOGIC:
    if action == 'buy':
        flash('Proceeding to checkout!', 'success')
        # Redirect back to search, but turn on the checkout pane
        return redirect(url_for('search', checkout='true')) 
    else:
        flash('Item added to cart!', 'success')
        return redirect(request.referrer or url_for('search'))
    
@app.route('/cart')
@login_required
def view_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.selling_price * item.quantity for item in items if item.product.selling_price)
    return render_template('cart.html', items=items, total=total)

@app.route('/remove_from_cart/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    item = CartItem.query.get_or_404(cart_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('view_cart'))
# ==========================================
# ADMIN INVENTORY UPLOAD SYSTEM
# ==========================================

def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        # Check if the user is logged in AND has the admin flag set to True
        if current_user.is_authenticated and current_user.is_admin:
            return f(*args, **kwargs)
        flash("Unauthorized access! Admin privileges required.", "error")
        return redirect(url_for('home'))
    return wrap

@app.route('/admin/upload-inventory', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_inventory():
    if request.method == 'POST':
        if 'inventory_file' not in request.files:
            flash('No file part selected', 'error')
            return redirect(request.url)
            
        file = request.files['inventory_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file:
            filename = secure_filename(file.filename)
            file_ext = os.path.splitext(filename)[1].lower()
            
            try:
                # 1. Read the file into a Pandas DataFrame
                if file_ext == '.csv':
                    df = pd.read_csv(file)
                elif file_ext in ['.xls', '.xlsx']:
                    df = pd.read_excel(file)
                else:
                    flash('Unsupported format! Use .csv, .xls, or .xlsx', 'error')
                    return redirect(request.url)

                # 2. Clean column names to prevent matching errors
                df.columns = [str(col).strip().upper() for col in df.columns]

                # 3. Loop through the spreadsheet and update the database safely via SQLAlchemy
                for index, row in df.iterrows():
                    ean = str(row['EAN_CODE']).strip()
                    
                    # Search if this exact medicine already exists
                    item = Medicine.query.filter_by(ean_code=ean).first()
                    
                    if item:
                        # It exists! Just update the prices and stock levels
                        item.product_name = str(row['PRODUCT_NAME'])
                        item.product_price = float(row['PRODUCT_PRICE'])
                        item.selling_price = float(row['SELLING_PRICE'])
                        item.discount = float(row['DISCOUNT'])
                        item.inventory_qty = int(row['INVENTORY_QTY'])
                    else:
                        # It's a new product! Create a fresh entry
                        new_item = Medicine(
                            ean_code=ean,
                            product_name=str(row['PRODUCT_NAME']),
                            product_price=float(row['PRODUCT_PRICE']),
                            selling_price=float(row['SELLING_PRICE']),
                            discount=float(row['DISCOUNT']),
                            inventory_qty=int(row['INVENTORY_QTY'])
                        )
                        db.session.add(new_item)
                
                # Save all the changes to the database
                db.session.commit()
                flash(f'Successfully processed {len(df)} inventory items!', 'success')
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error processing file: {str(e)}', 'error')
                return redirect(request.url)

    # Loads the frontend UI we created earlier
    return render_template('admin_upload.html')
if __name__ == '__main__':
    app.run(debug=True, port=8080)
