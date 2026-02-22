CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    series TEXT NOT NULL,
    model TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,
    price_inr INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    region TEXT NOT NULL DEFAULT 'India',
    product_url TEXT NOT NULL,
    image_url TEXT,
    cpu_brand TEXT NOT NULL,
    cpu_tier TEXT NOT NULL,
    cpu_model TEXT NOT NULL,
    ram_gb INTEGER NOT NULL,
    storage_type TEXT NOT NULL,
    storage_gb INTEGER NOT NULL,
    gpu_type TEXT NOT NULL,
    gpu_model TEXT NOT NULL,
    screen_size REAL NOT NULL,
    resolution TEXT NOT NULL,
    refresh_hz INTEGER NOT NULL,
    panel TEXT NOT NULL,
    weight_kg REAL,
    battery_hours REAL,
    battery_capacity_wh INTEGER,
    battery_type TEXT,
    rating REAL DEFAULT 0,
    use_cases_json TEXT NOT NULL,
    ports_json TEXT NOT NULL,
    specs_json TEXT NOT NULL,
    benchmarks_json TEXT NOT NULL,
    buy_links_json TEXT NOT NULL,
    srgb_100 INTEGER NOT NULL DEFAULT 0,
    dci_p3 INTEGER NOT NULL DEFAULT 0,
    good_cooling INTEGER NOT NULL DEFAULT 0,
    ram_upgradable INTEGER NOT NULL DEFAULT 0,
    extra_ssd_slot INTEGER NOT NULL DEFAULT 0,
    backlit_keyboard INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_brand ON products (brand);
CREATE INDEX IF NOT EXISTS idx_products_gpu_model ON products (gpu_model);
CREATE INDEX IF NOT EXISTS idx_products_price ON products (price_inr);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    pros TEXT NOT NULL,
    cons TEXT NOT NULL,
    experience TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reviews_product_created ON reviews (product_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews (status);
