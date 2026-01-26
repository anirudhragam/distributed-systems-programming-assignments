-- Product Database Schema

CREATE TABLE products (
  item_id SERIAL PRIMARY KEY,
  seller_id VARCHAR(10) NOT NULL,
  item_name VARCHAR(32) NOT NULL,
  category INTEGER NOT NULL,
  keywords VARCHAR(8)[] DEFAULT ARRAY[]::VARCHAR(8)[],
  condition VARCHAR(10) CHECK (condition IN ('New', 'Used')) NOT NULL,
  sale_price DECIMAL(10, 2) NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 0,
  thumbs_up INTEGER DEFAULT 0,
  thumbs_down INTEGER DEFAULT 0,
);

-- Indexes for better query performance
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_name ON products(item_name);
CREATE INDEX idx_products_condition ON products(condition);

-- Sample data (optional)
INSERT INTO products (seller_id, item_name, category, keywords, condition, sale_price, quantity, thumbs_up, thumbs_down)
VALUES 
  (1, 'Laptop Computer', 1, ARRAY['laptop', 'pc', 'intel'], 'New', 999.99, 50, 0, 0),
  (1, 'Wireless Mouse', 2, ARRAY['mouse', 'usb', 'wifi'], 'New', 29.99, 200, 0, 0),
  (2, 'Keyboard', 3, ARRAY['board', 'mech', 'rgb'], 'Used', 79.99, 15, 0, 0),
  (3, 'USB-C Cable', 4, ARRAY['cable', 'usb-c'], 'New', 12.99, 500, 0, 0),
  (4, 'Monitor Stand', 5, ARRAY['stand', 'mount'], 'Used', 35.00, 8, 0, 0);