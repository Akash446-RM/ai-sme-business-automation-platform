"""Reference data used by the synthetic data generator.

Keeping the catalogue definition separate from the generation logic makes it
easy to swap in a real product master later without touching the simulation.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# category -> (price range, base popularity weight, seasonality profile)
CATEGORY_PROFILES: Dict[str, dict] = {
    "Groceries": {
        "price_range": (25, 450),
        "margin": (0.14, 0.26),
        "popularity": 3.0,
        "seasonality": "steady",
        "basket_affinity": 0.9,
    },
    "Beverages": {
        "price_range": (20, 350),
        "margin": (0.18, 0.34),
        "popularity": 2.4,
        "seasonality": "summer",
        "basket_affinity": 0.8,
    },
    "Personal Care": {
        "price_range": (45, 900),
        "margin": (0.22, 0.40),
        "popularity": 1.8,
        "seasonality": "steady",
        "basket_affinity": 0.6,
    },
    "Home Care": {
        "price_range": (35, 700),
        "margin": (0.20, 0.36),
        "popularity": 1.6,
        "seasonality": "festival",
        "basket_affinity": 0.6,
    },
    "Electronics": {
        "price_range": (450, 42000),
        "margin": (0.10, 0.22),
        "popularity": 0.9,
        "seasonality": "festival",
        "basket_affinity": 0.25,
    },
    "Mobile Accessories": {
        "price_range": (99, 3500),
        "margin": (0.28, 0.52),
        "popularity": 1.5,
        "seasonality": "festival",
        "basket_affinity": 0.45,
    },
    "Stationery": {
        "price_range": (10, 600),
        "margin": (0.25, 0.45),
        "popularity": 1.4,
        "seasonality": "school",
        "basket_affinity": 0.5,
    },
    "Apparel": {
        "price_range": (250, 4500),
        "margin": (0.30, 0.55),
        "popularity": 1.1,
        "seasonality": "festival",
        "basket_affinity": 0.3,
    },
    "Footwear": {
        "price_range": (350, 5500),
        "margin": (0.28, 0.50),
        "popularity": 0.7,
        "seasonality": "festival",
        "basket_affinity": 0.2,
    },
    "Kitchenware": {
        "price_range": (120, 4200),
        "margin": (0.24, 0.44),
        "popularity": 0.8,
        "seasonality": "festival",
        "basket_affinity": 0.3,
    },
    "Health & Wellness": {
        "price_range": (60, 2200),
        "margin": (0.20, 0.38),
        "popularity": 1.2,
        "seasonality": "winter",
        "basket_affinity": 0.4,
    },
    "Toys & Games": {
        "price_range": (150, 3200),
        "margin": (0.30, 0.52),
        "popularity": 0.6,
        "seasonality": "festival",
        "basket_affinity": 0.2,
    },
}

PRODUCT_NOUNS: Dict[str, List[str]] = {
    "Groceries": [
        "Basmati Rice", "Wheat Flour", "Toor Dal", "Moong Dal", "Sunflower Oil",
        "Mustard Oil", "Sugar", "Iodised Salt", "Tea Leaves", "Instant Coffee",
        "Turmeric Powder", "Chilli Powder", "Coriander Powder", "Garam Masala",
        "Peanut Butter", "Mixed Jam", "Honey", "Corn Flakes", "Oats", "Poha",
        "Semolina", "Vermicelli", "Chickpeas", "Kidney Beans", "Cashew Nuts",
        "Almonds", "Raisins", "Ghee", "Paneer", "Butter",
    ],
    "Beverages": [
        "Cola Bottle", "Orange Soda", "Lemon Drink", "Mango Juice", "Apple Juice",
        "Mixed Fruit Juice", "Energy Drink", "Iced Tea", "Green Tea Bags",
        "Coconut Water", "Mineral Water", "Soda Water", "Cold Coffee",
        "Buttermilk Pack", "Lassi Pack", "Health Drink Powder",
    ],
    "Personal Care": [
        "Shampoo", "Conditioner", "Hair Oil", "Body Lotion", "Face Wash",
        "Sunscreen Lotion", "Bath Soap", "Hand Wash", "Toothpaste", "Toothbrush",
        "Mouthwash", "Shaving Gel", "Razor Pack", "Deodorant", "Talcum Powder",
        "Lip Balm", "Face Cream", "Hair Serum",
    ],
    "Home Care": [
        "Floor Cleaner", "Toilet Cleaner", "Glass Cleaner", "Dishwash Liquid",
        "Dishwash Bar", "Detergent Powder", "Detergent Liquid", "Fabric Softener",
        "Air Freshener", "Mosquito Repellent", "Garbage Bags", "Scrub Pad",
        "Broom", "Mop Refill", "Phenyl",
    ],
    "Electronics": [
        "LED Television", "Bluetooth Speaker", "Soundbar", "Microwave Oven",
        "Mixer Grinder", "Electric Kettle", "Induction Cooktop", "Air Fryer",
        "Vacuum Cleaner", "Table Fan", "Room Heater", "Water Purifier",
        "Smart Watch", "Wireless Earbuds", "Laptop Cooling Pad", "Webcam",
        "Wireless Mouse", "Mechanical Keyboard", "External Hard Drive", "Printer",
    ],
    "Mobile Accessories": [
        "Fast Charger", "USB Cable", "Type C Cable", "Power Bank", "Phone Case",
        "Screen Guard", "Car Mount", "Selfie Stick", "OTG Adapter", "Memory Card",
        "Wired Earphones", "Neckband Headset", "Phone Stand", "Ring Holder",
    ],
    "Stationery": [
        "Ball Pen Pack", "Gel Pen Pack", "Pencil Box", "Eraser Pack", "Sharpener",
        "Notebook 200 Pages", "Spiral Notepad", "A4 Paper Ream", "File Folder",
        "Sticky Notes", "Highlighter Set", "Whiteboard Marker", "Glue Stick",
        "Stapler", "Scissors", "Geometry Box", "Drawing Book", "Crayon Set",
    ],
    "Apparel": [
        "Cotton T-Shirt", "Formal Shirt", "Denim Jeans", "Chino Trousers",
        "Kurta", "Saree", "Leggings", "Track Pants", "Hooded Sweatshirt",
        "Winter Jacket", "Socks Pack", "Innerwear Pack", "Scarf", "Cap",
    ],
    "Footwear": [
        "Running Shoes", "Casual Sneakers", "Formal Shoes", "Sandals",
        "Flip Flops", "Sports Slides", "Loafers", "Kids Shoes", "Rain Boots",
    ],
    "Kitchenware": [
        "Steel Pressure Cooker", "Non Stick Pan", "Steel Tiffin Box",
        "Water Bottle", "Dinner Plate Set", "Glass Set", "Storage Container Set",
        "Chopping Board", "Knife Set", "Serving Bowl", "Casserole", "Tawa",
        "Kadai", "Spoon Set",
    ],
    "Health & Wellness": [
        "Multivitamin Tablets", "Vitamin C Tablets", "Protein Powder",
        "Digital Thermometer", "Blood Pressure Monitor", "Pain Relief Spray",
        "Antiseptic Liquid", "First Aid Kit", "Face Mask Pack", "Hand Sanitizer",
        "Glucose Powder", "Immunity Booster", "Weighing Scale",
    ],
    "Toys & Games": [
        "Building Blocks", "Remote Car", "Puzzle Set", "Board Game",
        "Soft Toy", "Doll House", "Card Game", "Kids Cycle", "Water Gun",
        "Art and Craft Kit", "Musical Toy",
    ],
}

BRANDS = [
    "Sunrise", "GreenLeaf", "UrbanNest", "PrimeChoice", "Nova", "Everyday",
    "Sparkle", "TrueValue", "Metro", "Aster", "Kanchan", "Zenith", "Orbit",
    "Kaveri", "Sahara", "Lotus", "Pioneer", "Vertex", "Harmony", "Signature",
]

GENERIC_VARIANTS = [
    "Pack of 2", "Pack of 4", "Pack of 6", "Family Pack", "Value Pack",
    "Premium", "Classic", "Standard",
]

# Variant vocabulary per category so product names stay believable
# (a beverage is measured in millilitres, never in kilograms).
CATEGORY_VARIANTS: Dict[str, List[str]] = {
    "Groceries": ["250 g", "500 g", "1 kg", "2 kg", "5 kg", "Family Pack", "Value Pack"],
    "Beverages": ["200 ml", "330 ml", "500 ml", "750 ml", "1 L", "2 L", "Pack of 6"],
    "Personal Care": ["100 ml", "200 ml", "400 ml", "Travel Size", "Family Pack", "Premium"],
    "Home Care": ["500 ml", "1 L", "2 L", "1 kg", "Refill Pack", "Value Pack"],
    "Electronics": ["Standard", "Pro", "Plus", "Max", "Compact", "Premium"],
    "Mobile Accessories": ["1 m", "1.5 m", "2 m", "Fast Charge", "Pack of 2", "Premium"],
    "Stationery": ["Pack of 5", "Pack of 10", "Pack of 12", "Single", "Jumbo Pack"],
    "Apparel": ["Small", "Medium", "Large", "X-Large", "XX-Large"],
    "Footwear": ["UK 6", "UK 7", "UK 8", "UK 9", "UK 10", "UK 11"],
    "Kitchenware": ["Small", "Medium", "Large", "Set of 2", "Set of 4", "Set of 6"],
    "Health & Wellness": ["30 Tablets", "60 Tablets", "90 Tablets", "250 g", "500 g", "1 Unit"],
    "Toys & Games": ["Age 3+", "Age 5+", "Age 8+", "Small", "Large", "Deluxe"],
}

SUPPLIERS = [
    "Metro Wholesale Distributors", "Sunrise Trading Co", "Nandi Supply Chain",
    "Everest Distributors", "BlueRiver Logistics", "Kaveri Enterprises",
    "National FMCG Partners", "Skyline Traders", "Deccan Distribution House",
    "Orbit Retail Supply",
]

CITIES = [
    "Bengaluru", "Mysuru", "Hubballi", "Mangaluru", "Belagavi", "Davangere",
    "Ballari", "Tumakuru", "Shivamogga", "Vijayapura", "Hassan", "Udupi",
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Rohan", "Karthik", "Manoj", "Suresh", "Ramesh",
    "Prakash", "Ananya", "Diya", "Aadhya", "Saanvi", "Pari", "Anika", "Navya",
    "Kavya", "Meera", "Lakshmi", "Divya", "Pooja", "Sneha", "Nisha", "Rekha",
    "Vinod", "Girish", "Harish", "Naveen", "Deepak", "Sunil", "Anil", "Vikram",
]

LAST_NAMES = [
    "Sharma", "Verma", "Reddy", "Naidu", "Rao", "Gowda", "Shetty", "Hegde",
    "Kulkarni", "Desai", "Patil", "Joshi", "Nair", "Menon", "Iyer", "Pillai",
    "Bhat", "Kamath", "Prabhu", "Acharya", "Singh", "Chauhan", "Mehta", "Shah",
]

EMPLOYEE_ROLES: List[Tuple[str, str, int]] = [
    ("Store Manager", "Operations", 1),
    ("Assistant Manager", "Operations", 2),
    ("Inventory Manager", "Inventory", 2),
    ("Cashier", "Billing", 4),
    ("Sales Executive", "Sales", 7),
    ("Customer Support", "Support", 2),
    ("Delivery Coordinator", "Logistics", 2),
]

# Indian festival/holiday periods that lift retail demand (month, day, spread, lift)
FESTIVAL_WINDOWS: List[Tuple[int, int, int, float]] = [
    (1, 14, 3, 1.25),   # Sankranti
    (3, 8, 2, 1.15),    # Holi
    (4, 14, 2, 1.20),   # Ugadi / New Year
    (8, 15, 2, 1.18),   # Independence Day sales
    (9, 7, 4, 1.30),    # Ganesh Chaturthi
    (10, 20, 8, 1.55),  # Dussehra to Diwali build up
    (11, 12, 6, 1.70),  # Diwali peak
    (12, 24, 7, 1.35),  # Year end
]
