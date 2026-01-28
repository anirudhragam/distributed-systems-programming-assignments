-- Customer Database Schema

-- Sellers Table
CREATE TABLE sellers (
  seller_id SERIAL PRIMARY KEY,
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
  username VARCHAR(32) NOT NULL,
  passwd VARCHAR(32) NOT NULL, 
  items_purchased INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW() -- Move to Sessions table
);

-- Seller Sessions Table
CREATE TABLE seller_sessions (
  session_id UUID PRIMARY KEY,
  seller_id INTEGER NOT NULL,
  last_active_at TIMESTAMP DEFAULT NOW()
);

-- Buyer Sessions Table
CREATE TABLE buyer_sessions (
  session_id UUID PRIMARY KEY,
  buyer_id INTEGER NOT NULL,
  last_active_at TIMESTAMP DEFAULT NOW()
);

-- Add foreign key constraints to buyer and seller session tables
ALTER TABLE seller_sessions ADD CONSTRAINT fk_seller_session 
  FOREIGN KEY (seller_id) REFERENCES sellers(seller_id) 
  ON DELETE CASCADE;

ALTER TABLE buyer_sessions ADD CONSTRAINT fk_buyer_session 
  FOREIGN KEY (buyer_id) REFERENCES buyers(buyer_id) 
  ON DELETE CASCADE;

-- Indexes 
CREATE INDEX idx_sellers_username ON sellers(username);
CREATE INDEX idx_buyers_username ON buyers(username);
CREATE INDEX idx_sellers_last_accessed ON seller_sessions(last_active_at);
CREATE INDEX idx_buyers_last_accessed ON buyer_sessions(last_active_at);

-- Sample data for sellers
INSERT INTO sellers (username, passwd, thumbs_up, thumbs_down, items_sold)
VALUES 
  ('TechMart Store', 'password1', 0, 0, 0),
  ('Electronics Plus', 'password2', 0, 0, 0),
  ('Quality Goods', 'password3', 0, 0, 0),
  ('Daily Deals', 'password4', 0, 0, 0);

-- Sample data for buyers
INSERT INTO buyers (username, passwd, items_purchased)
VALUES 
  ('John Doe', 'password1', 0),
  ('Jane Smith', 'password2', 0),
  ('Bob Johnson', 'password3', 0),
  ('Alice Williams', 'password4', 0),
  ('Charlie Brown', 'password5', 0);

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