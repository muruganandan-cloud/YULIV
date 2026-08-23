import csv
import os
from sqlalchemy import text
from app import app, db, CartItem, Products

CSV_FILENAME = 'inventory.csv'

def update_system():
    print("🔄 Starting YuLiv System Update...")
    
    with app.app_context():
        # --- PART 1: SCHEMA FIX ---
        print("1. Rebuilding cart_items table...")
        CartItem.__table__.drop(db.engine, checkfirst=True)
        CartItem.__table__.create(db.engine)
        
        # --- PART 2: RAW SQL DEDUPLICATION (The Nuclear Option) ---
        # This bypasses Python and forces the SQLite database to delete 
        # all clones, keeping only the absolute oldest entry for each product name.
        print("2. Destroying all duplicate clones in the database...")
        try:
            db.session.execute(text("""
                DELETE FROM inventory 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM inventory 
                    GROUP BY product_name
                )
            """))
            db.session.commit()
            print("   🗑️ Duplicates vaporized successfully!")
        except Exception as e:
            print(f"   ⚠️ Cleanup note: {e}")

        # --- PART 3: SMART UPSERT ---
        print("3. Starting Intelligent Inventory Sync (Upsert)...")
        if not os.path.exists(CSV_FILENAME):
            print(f"   ❌ Error: {CSV_FILENAME} not found.")
            return

        added_count = 0
        updated_count = 0

        with open(CSV_FILENAME, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                ean = str(row.get('ean_code', '')).strip() if row.get('ean_code') else None
                name = str(row.get('product_name', '')).strip()
                
                if not name:
                    continue
                    
                # Parse numbers safely
                try:
                    mrp = float(row.get('mrp', 0) or 0)
                    selling_price = float(row.get('selling_price', 0) or 0)
                    discount = float(row.get('discount', 0) or 0)
                    stock = int(row.get('stock', 0) or 0)
                except ValueError:
                    continue

                # Use ILIKE to ignore all uppercase/lowercase differences
                existing_product = Products.query.filter(Products.product_name.ilike(name)).first()

                if existing_product:
                    # Update existing item
                    existing_product.product_name = name
                    existing_product.mrp = mrp
                    existing_product.selling_price = selling_price
                    existing_product.discount = discount
                    existing_product.stock = stock
                    if ean:
                        existing_product.ean_code = ean
                    updated_count += 1
                else:
                    # Insert truly new item
                    new_product = Products(
                        ean_code=ean,
                        product_name=name,
                        mrp=mrp,
                        selling_price=selling_price,
                        discount=discount,
                        stock=stock
                    )
                    db.session.add(new_product)
                    added_count += 1

        db.session.commit()
        print(f"✅ Inventory sync complete: {added_count} newly added, {updated_count} updated.")
        
        db.create_all()
        print("🚀 System update finished successfully!")

if __name__ == '__main__':
    update_system()