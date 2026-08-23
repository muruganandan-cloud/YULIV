import csv
import os
from app import app, db, CartItem, Products

CSV_FILENAME = 'inventory.csv'

def update_system():
    print("🔄 Starting YuLiv System Update (Clean Slate Mode)...")
    
    with app.app_context():
        # --- PART 1: THE COMPLETE WIPE ---
        print("1. Vaporizing old tables to guarantee zero duplicates...")
        # We must drop CartItem first because it relies on the Products table
        CartItem.__table__.drop(db.engine, checkfirst=True)
        Products.__table__.drop(db.engine, checkfirst=True)
        
        # --- PART 2: THE REBUILD ---
        print("2. Rebuilding fresh, perfectly empty tables...")
        db.create_all()
        
        # --- PART 3: THE CLEAN IMPORT ---
        print("3. Importing exactly one fresh copy of your inventory...")
        if not os.path.exists(CSV_FILENAME):
            print(f"   ❌ Error: {CSV_FILENAME} not found.")
            return

        added_count = 0

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

                # Because we wiped the table, we don't even need to check for duplicates!
                # We just insert the fresh data directly.
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
        print(f"✅ Clean Slate Import complete: Exactly {added_count} products loaded.")
        print("🚀 System update finished successfully!")

if __name__ == '__main__':
    update_system()