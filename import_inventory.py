import csv
import os
from app import Products, app, db, Products # Ensure 'Products' matches your model name in app.py

def import_csv():
    csv_file_path = os.path.join(os.path.dirname(__file__), 'inventory.csv')
    
    if not os.path.exists(csv_file_path):
        print(f"❌ Error: Could not find '{csv_file_path}'")
        return

    with app.app_context():
        # Clear existing rows if restocking freshly
        # Products.query.delete()

        count = 0
        with open(csv_file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map CSV column headers to your SQLAlchemy model fields
                item = Products(
                    ean_code=row.get('EAN_CODE', '').strip(),
                    product_name=row.get('PRODUCT_NAME', '').strip(),
                    product_price=float(row.get('PRODUCT_PRICE', 0) or 0),
                    selling_price=float(row.get('SELLING_PRICE', 0) or 0),
                    discount=float(row.get('DISCOUNT', 0) or 0),
                    inventory_qty=int(row.get('INVENTORY_QTY', 0) or 0)
                )
                db.session.add(item)
                count += 1

        db.session.commit()
        print(f"✅ Successfully imported {count} items into the database!")

if __name__ == '__main__':
    import_csv()