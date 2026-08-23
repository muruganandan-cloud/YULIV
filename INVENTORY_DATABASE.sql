CREATE DATABASE IF NOT EXISTS yuliv_db;
USE yuliv_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    pincode VARCHAR(10)
);

-- Add the admin column if it doesn't exist
-- (Moved this up here so all table modifications happen before loading data)
-- ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS inventory;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE inventory (
    id int AUTO_INCREMENT PRIMARY KEY,
    EAN_CODE VARCHAR(100) NOT NULL,
    PRODUCT_NAME VARCHAR(100),
    PRODUCT_PRICE INT,
    SELLING_PRICE INT,
    DISCOUNT FLOAT,
    INVENTORY_QTY INT
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id),
    -- FIXED: Changed medicine_id to product_id to match the column above
    FOREIGN KEY (product_id) REFERENCES inventory(id) 
);

-- Enable local file uploads on the server
SET GLOBAL local_infile = 1;

-- Load the CSV Data
LOAD DATA LOCAL INFILE '/Users/muruganandan/Documents/programs/inventory.csv'
INTO TABLE inventory
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n' -- If this still imports 0 rows, change this to '\r\n' or '\r'
IGNORE 1 ROWS
(EAN_CODE, PRODUCT_NAME, PRODUCT_PRICE, SELLING_PRICE, DISCOUNT, INVENTORY_QTY);

-- Verify the upload
SELECT EAN_CODE, PRODUCT_NAME, INVENTORY_QTY FROM inventory WHERE INVENTORY_QTY <= 100 OR INVENTORY_QTY IS NULL;