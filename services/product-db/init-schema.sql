-- Product Database Schema

CREATE TABLE products (
  item_id SERIAL PRIMARY KEY,
  seller_id INTEGER NOT NULL,
  item_name VARCHAR(32) NOT NULL,
  category INTEGER NOT NULL,
  keywords VARCHAR(8)[] DEFAULT ARRAY[]::VARCHAR(8)[],
  condition VARCHAR(10) CHECK (condition IN ('New', 'Used')) NOT NULL,
  sale_price DECIMAL(10, 2) NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 0,
  thumbs_up INTEGER DEFAULT 0,
  thumbs_down INTEGER DEFAULT 0
);

-- Indexes for better query performance
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_name ON products(item_name);
CREATE INDEX idx_products_condition ON products(condition);
-- Generalized Inverted Index (GIN) for keywords array for efficient searching
CREATE INDEX idx_products_keywords ON products USING GIN (keywords);

-- Sample data
INSERT INTO products (seller_id, item_name, category, keywords, condition, sale_price, quantity, thumbs_up, thumbs_down)
VALUES 
  (1, 'Laptop Computer', 1, ARRAY['laptop', 'pc', 'intel'], 'New', 999.99, 500, 0, 0),
  (1, 'Wireless Mouse', 2, ARRAY['mouse', 'usb', 'wifi'], 'New', 29.99, 200, 0, 0),
  (2, 'Keyboard', 3, ARRAY['board', 'mech', 'rgb'], 'Used', 79.99, 350, 0, 0),
  (2, 'Personal Computer', 1, ARRAY['computer', 'pc', 'desktop'], 'New', 499.99, 300, 0, 0),
  (3, 'Gaming Computer', 1, ARRAY['gaming', 'pc', 'high-end'], 'New', 1499.99, 200, 0, 0);