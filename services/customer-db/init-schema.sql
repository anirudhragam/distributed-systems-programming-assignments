-- Customer Database Schema

-- Sellers Table
CREATE TABLE sellers (
  seller_id SERIAL PRIMARY KEY,
  seller_name VARCHAR(32) NOT NULL,
  thumbs_up INTEGER DEFAULT 0,
  thumbs_down INTEGER DEFAULT 0,
  items_sold INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Buyers Table
CREATE TABLE buyers (
  buyer_id SERIAL PRIMARY KEY,
  buyer_name VARCHAR(32) NOT NULL,
  items_purchased INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
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
