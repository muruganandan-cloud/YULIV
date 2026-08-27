import csv
import os
from app import app, db, Products

# 1. ABSOLUTE PATHS: Forces terminal to use the exact same files as the live website
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CSV_FILENAME = os.path.join(BASE_DIR, 'inventory.csv')

def sync_inventory():
    print("🔄 Starting YuLiv Intelligent Sync...")
    
    if not os.path.exists(CSV_FILENAME):
        print(f"❌ Error: Could not find {CSV_FILENAME}")
        return

    with app.app_context():
        # 2. PRE-FILTER: Read CSV and keep ONLY the latest row for each product name
        csv_products = {}
        with open(CSV_FILENAME, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = str(row.get('product_name', '')).strip()
                if name:
                    # Overwrites any duplicate rows hiding inside the CSV itself
                    csv_products[name.lower()] = row 
                    
        # 3. UPSERT: Update existing or Insert new
        added_count = 0
        updated_count = 0
        
        for lower_name, row in csv_products.items():
            name = str(row.get('product_name', '')).strip()
            ean = str(row.get('ean_code', '')).strip() or None
            
            try:
                mrp = float(row.get('mrp', 0) or 0)
                selling_price = float(row.get('selling_price', 0) or 0)
                discount = float(row.get('discount', 0) or 0)
                stock = int(row.get('stock', 0) or 0)
            except ValueError:
                continue
            
            # Check the live database
            existing_product = Products.query.filter(Products.product_name.ilike(name)).first()
            
            if existing_product:
                existing_product.mrp = mrp
                existing_product.selling_price = selling_price
                existing_product.discount = discount
                existing_product.stock = stock
                if ean: 
                    existing_product.ean_code = ean
                updated_count += 1
            else:
                new_item = Products(
                    product_name=name, ean_code=ean, mrp=mrp, 
                    selling_price=selling_price, discount=discount, stock=stock
                )
                db.session.add(new_item)
                added_count += 1
                
        db.session.commit()
        print(f"✅ Sync complete! Added: {added_count} new items. Updated: {updated_count} existing items.")

if __name__ == '__main__':
    sync_inventory()