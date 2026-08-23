import csv
import os
from app import app, db, CartItem, Products

CSV_FILENAME = 'inventory.csv'

def update_system():
    print("🔄 Starting YuLiv System Update...")
    
    with app.app_context():
        # --- PART 1: SCHEMA FIX ---
        print("1. Rebuilding cart_items table...")
        CartItem.__table__.drop(db.engine, checkfirst=True)
        CartItem.__table__.create(db.engine)
        
        # --- PART 2: AGGRESSIVE DUPLICATE CLEANUP ---
        print("2. Scanning for and removing existing duplicate products...")
        all_products = Products.query.all()
        seen_items = set()
        duplicates_removed = 0
        
        for item in all_products:
            # Create a bulletproof identifier: all lowercase, absolutely no spaces
            if item.ean_code and str(item.ean_code).strip():
                identifier = str(item.ean_code).strip().lower()
            else:
                identifier = str(item.product_name).strip().lower().replace(' ', '')
                
            if identifier in seen_items:
                db.session.delete(item)
                duplicates_removed += 1
            else:
                seen_items.add(identifier)
        
        db.session.commit()
        print(f"   🗑️ Removed {duplicates_removed} duplicate clones!")

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
                # Clean the CSV inputs aggressively
                ean = str(row.get('ean_code', '')).strip()
                name = str(row.get('product_name', '')).strip()
                
                if not name and not ean:
                    continue
                    
                # Parse numbers safely
                try:
                    mrp = float(row.get('mrp', 0) or 0)
                    selling_price = float(row.get('selling_price', 0) or 0)
                    discount = float(row.get('discount', 0) or 0)
                    stock = int(row.get('stock', 0) or 0)
                except ValueError:
                    continue

                # Aggressive Matching Strategy
                existing_product = None
                
                # 1. Match by exact EAN
                if ean:
                    existing_product = Products.query.filter_by(ean_code=ean).first()
                
                # 2. Match by exact Name
                if not existing_product and name:
                    existing_product = Products.query.filter_by(product_name=name).first()
                    
                # 3. Last Resort: Loop through and match by squished, lowercase name
                if not existing_product and name:
                    clean_csv_name = name.lower().replace(' ', '')
                    for p in Products.query.all():
                        db_name = str(p.product_name).lower().replace(' ', '')
                        if db_name == clean_csv_name:
                            existing_product = p
                            break

                if existing_product:
                    # Update existing
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