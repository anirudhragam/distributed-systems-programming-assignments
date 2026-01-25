-- Customer Database Schema

-- Sellers Table
CREATE TABLE sellers (
  seller_id SERIAL PRIMARY KEY,
  seller_name VARCHAR(32) NOT NULL,
  username VARCHAR(32) NOT NULL,
  passwd VARCHAR(32) NOT NULL, 
  thumbs_up INTEGER DEFAULT 0,
  thumbs_down INTEGER DEFAULT 0,
  items_sold INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW() -- Move to Sessions table
);

-- Buyers Table
CREATE TABLE buyers (
  buyer_id SERIAL PRIMARY KEY,
  buyer_name VARCHAR(32) NOT NULL,
  username VARCHAR(32) NOT NULL,
  passwd VARCHAR(32) NOT NULL, 
  items_purchased INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW() -- Move to Sessions table
);

-- Indexes 
CREATE INDEX idx_sellers_name ON sellers(seller_name);
CREATE INDEX idx_buyers_name ON buyers(buyer_name);

-- Sample data for sellers
INSERT INTO sellers (seller_name, thumbs_up, thumbs_down, items_sold)
VALUES 
  ('TechMart Store', 0, 0, 0),
  ('Electronics Plus', 0, 0, 0),
  ('Quality Goods', 0, 0, 0),
  ('Daily Deals', 0, 0, 0);

-- Sample data for buyers
INSERT INTO buyers (buyer_name, items_purchased)
VALUES 
  ('John Doe', 0),
  ('Jane Smith', 0),
  ('Bob Johnson', 0),
  ('Alice Williams', 0),
  ('Charlie Brown', 0);

/*
Table: carts
This table links the shopping journey to a specific user.
| Column | Type | Description |
| :--- | :--- | :--- |
| id | UUID | Primary Key. |
| user_id | UUID | Foreign Key to the User Profile Table. |
| created_at | Timestamp | Initial creation time. |
| updated_at | Timestamp | Used for tracking session activity. | 

Table: cart_items 
This table manages the individual products and their persistence status.
| Column | Type | Description |
| :--- | :--- | :--- |
| id | UUID | Primary Key. |
| cart_id | UUID | Foreign Key to the carts table (with ON DELETE CASCADE). |
| product_id | UUID | Reference to the product. |
| quantity | Integer | Number of units. |
| is_saved | Boolean | Requirement Logic: TRUE if the SaveCart API was called; FALSE by default. |
| added_at | Timestamp | Essential for automated cleanup of old sessions. | 

item_feedback
Column 	Type	Description
user_id	UUID	Foreign Key to the User table.
item_id	UUID	Foreign Key to the Item/Product table.
vote	SmallInt	1 for Thumbs Up, -1 for Thumbs Down (or use a boolean).
created_at	Timestamp	Allows you to track when the feedback was given for analytics.
*/