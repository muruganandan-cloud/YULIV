from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from sqlalchemy import text
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv
from google import genai

load_dotenv()

# This fixes the "name 'client' is not defined" error for Gemini
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

# Format: mysql+pymysql://username:password@127.0.0.1:3306/database_name
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Hanish5^611@127.0.0.1:3306/yuliv_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'yuliv_pharmacy_secret_key_123' # Change this to a secure key

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
    medicine_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    medicine = db.relationship('Medicine', backref='cart_entries')

@app.context_processor
def inject_user():
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return dict(current_user=current_user, cart_count=cart_count)

class Medicine(db.Model):
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
        count = Medicine.query.count()
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
    query = request.args.get('q', '').lower().strip()
    if not query:
        return render_template('search_results.html', query=query, results=[], ai_solution=None)

    # --- EXTERNAL AI INTEGRATION ---
    ai_solution = None
    
    # To activate real AI: 
    # 1. Run in terminal: pip install google-generativeai
    # 2. Uncomment the code below and add your API key from Google AI Studio.
    
    try:
        from google import genai
        
    
         # Change this on lines 114 and 198
        api_key = os.getenv("OPENAI_API_KEY")
  
        # Dynamically find modern available models your API key has clearance to use
        available_models = [m.name for m in client.models.list()]
        
        if not available_models:
            raise Exception("No AI models are available. Please check if your API key has 'Generative Language API' enabled.")
            
        # Standard fallback sequence checking for current operational models
        if 'gemini-2.5-flash' in available_models:
            model_name = 'gemini-2.5-flash'
        elif 'gemini-2.5-pro' in available_models:
            model_name = 'gemini-2.5-pro'
        elif 'gemini-1.5-flash' in available_models:
            model_name = 'gemini-1.5-flash'
        else:
            # Use the first available returned fallback model string cleanly
            model_name = available_models[0]

        print(f"Successfully loaded model: {model_name}")

        prompt = f"""You are a helpful expert pharmacy assistant. A customer is asking: '{query}'. 
        First, provide a detailed overview of possible root causes and comprehensive lifestyle advice for this issue.
        Then, suggest 5 to 6 real-world over-the-counter medicines (commonly available in India) for this issue.
        Return ONLY raw HTML code (no markdown backticks, no ```html). Use this exact structure:
        
        <div class="ai-card">
            <h4 class="card-title">🩺 Understanding Your Symptoms</h4>
            <p style="margin-bottom: 12px; line-height: 1.5;"><strong>Possible Causes:</strong> [Provide a detailed 3-4 sentence explanation of root causes]</p>
            <p style="margin-bottom: 0; line-height: 1.5;"><strong>Lifestyle Advice:</strong> [Provide 3-4 detailed practical home remedies or lifestyle tips]</p>
        </div>
        
        <div class="ai-card">
            <h4 class="card-title">💊 Suggested Medication</h4>
            <!-- Repeat the div below 5 to 6 times for different medicines -->
            <div class="product-item">
                <h5>[Brand Name]</h5>
                <p><strong>Active Ingredient:</strong> [Ingredient]</p>
                <p><strong>Pack Size:</strong> [Size]</p>
                <p><strong>Estimated Price:</strong> [Price]</p>
                <p><strong>Use:</strong> [Brief description]</p>
            </div>
        </div>
        <p style="grid-column: 1 / -1; color: #dc2626; font-size: 0.9em; font-style: italic; text-align: center; margin-top: 15px;">Disclaimer: Please consult a healthcare professional before taking any medication. Prices are estimates.</p>"""
        
        response = client.models.generate_content(model=model_name, contents=prompt)
        ai_solution = response.text
        
    except ImportError:
        ai_solution = "<strong style='color:red;'>Setup Required:</strong> You need to install the AI library. Run <code>pip install google-genai</code> in your terminal and restart the server."
    except Exception as e:
        print(f"AI Error: {e}")
        ai_solution = f"<strong style='color:red;'>AI Error:</strong> {str(e)}<br><br><em>(Please ensure your API key is valid. Create a new key at <a href='https://aistudio.google.com/app/apikey' target='_blank'>Google AI Studio</a>.)</em>"
    # -------------------------------

    # "AI-Lite" NLP: Remove conversational stop-words to parse natural language
    # Example: "I need medicine for a headache" -> keywords: ["headache"]
    stop_words = {'i', 'need', 'want', 'some', 'medicine', 'for', 'a', 'an', 'my', 'have', 'the', 'is', 'in', 'with', 'to'}
    words = [word for word in query.split() if word not in stop_words]
    
    if not words:
        words = [query] # Fallback if they only typed stop words

    # Build a search condition that looks for ANY of the extracted keywords
    search_conditions = [Medicine.product_name.ilike(f"%{word}%") for word in words]
    
    # Always allow an exact EAN code match just in case
    search_conditions.append(Medicine.ean_code.ilike(f"%{query}%"))

    results = Medicine.query.filter(or_(*search_conditions)).all()
    
    print(f"DEBUG: Query='{query}', AI-Tokens={words}, Found={len(results)}")
    return render_template('search_results.html', query=query, results=results, ai_solution=ai_solution)

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

@app.route('/add_to_cart/<int:medicine_id>')
@login_required
def add_to_cart(medicine_id):
    item = CartItem.query.filter_by(user_id=current_user.id, medicine_id=medicine_id).first()
    if item:
        item.quantity += 1
    else:
        new_item = CartItem(user_id=current_user.id, medicine_id=medicine_id)
        db.session.add(new_item)
    db.session.commit()
    flash('Added to cart!', 'success')
    return redirect(request.referrer or url_for('home'))

@app.route('/cart')
@login_required
def view_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.medicine.selling_price * item.quantity for item in items if item.medicine.selling_price)
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