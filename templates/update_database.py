import csv
import os
from app import app, db, CartItem, Products

CSV_FILENAME = 'inventory.csv'

def update_system():
    print("🔄 Starting YuLiv System Update...")
    
    with app.app_context():
        # --- PART 1: SCHEMA FIX (Cart Items) ---
        print("1. Rebuilding cart_items table...")
        CartItem.__table__.drop(db.engine, checkfirst=True)
        CartItem.__table__.create(db.engine)
        
        # --- PART 2: DUPLICATE CLEANUP ---
        # This acts as a vacuum cleaner to remove the existing 
        # clones from previous bugs before we run the upsert.
        print("2. Scanning for and removing existing duplicate products...")
        all_products = Products.query.all()
        seen_items = set()
        duplicates_removed = 0
        
        for item in all_products:
            # Identify uniqueness by EAN (if available) or product name
            identifier = item.ean_code if item.ean_code else item.product_name
            if identifier in seen_items:
                db.session.delete(item)
                duplicates_removed += 1
            else:
                seen_items.add(identifier)
        
        if duplicates_removed > 0:
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
                ean = row.get('ean_code', '').strip() if row.get('ean_code') else None
                name = row.get('product_name', '').strip()
                
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

                # Search for an existing match
                existing_product = None
                if ean:
                    existing_product = Products.query.filter_by(ean_code=ean).first()
                if not existing_product and name:
                    existing_product = Products.query.filter_by(product_name=name).first()

                if existing_product:
                    # Update the existing product safely
                    existing_product.product_name = name
                    existing_product.mrp = mrp
                    existing_product.selling_price = selling_price
                    existing_product.discount = discount
                    existing_product.stock = stock
                    if ean:
                        existing_product.ean_code = ean
                    updated_count += 1
                else:
                    # Insert it only if it is entirely new
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
        
        # Safety net: Create any other missing tables
        db.create_all()
        print("🚀 System update finished successfully!")

if __name__ == '__main__':
    update_system()