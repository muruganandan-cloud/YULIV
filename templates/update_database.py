from app import app, db, CartItem

def upgrade_database():
    print("🔄 Starting YuLiv database update...")
    
    with app.app_context():
        # 1. Safely drop the broken cart_items table if it exists
        print("Dropping outdated cart_items table...")
        CartItem.__table__.drop(db.engine, checkfirst=True)
        
        # 2. Rebuild the table with the new product_id column
        print("Rebuilding cart_items table with correct columns...")
        CartItem.__table__.create(db.engine)
        
        # 3. Safety net: Create any other missing tables that were added recently
        db.create_all()
        
    print("✅ Database update complete! Your tables are ready for production.")

if __name__ == '__main__':
    upgrade_database()