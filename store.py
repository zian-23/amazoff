"""Amazoff's data and its "do the opposite" rules.

Products come from DummyJSON (https://dummyjson.com) and FakeStoreAPI
(https://fakestoreapi.com), books from Open Library (https://openlibrary.org),
and opposite words from Datamuse (https://www.datamuse.com/api/). All are free
and need no key.
"""

import json
import random
import re
import urllib.parse
import urllib.request

DUMMYJSON_URL = "https://dummyjson.com"
FAKESTORE_URL = "https://fakestoreapi.com"
OPENLIBRARY_URL = "https://openlibrary.org"
DATAMUSE_URL = "https://api.datamuse.com"
USD_TO_INR = 85  # DummyJSON and FakeStore prices are in US dollars; a fixed rate avoids another API.

EXCLUDED_CATEGORIES = {"groceries"}

# Each source gets its own id range so ids never clash.
FAKESTORE_ID_OFFSET = 1000  # FakeStore product 1 -> 1001
BOOK_ID_OFFSET = 1_000_000_000  # Open Library work OL471870W -> 1000471870
BOOK_FIELDS = "key,title,author_name,cover_i,first_publish_year,ratings_average"

# What you search for -> what we show instead. Every value must match a product.
OPPOSITES = {
    "hot": "ice cube tray",
    "cold": "electric stove",
    "ice": "electric stove",
    "ice cream": "microwave oven",
    "spicy": "ice cube tray",
    "sweet": "citrus squeezer",
    "hungry": "plate",
    "gym": "bed",
    "laptop": "football",
    "football": "laptop",
    "computer": "football",
    "phone": "plant pot",
    "mobile": "plant pot",
    "iphone": "samsung galaxy",
    "apple": "samsung",
    "samsung": "iphone",
    "android": "iphone",
    "headphone": "smart speaker",
    "earphone": "smart speaker",
    "speaker": "earphones",
    "tv": "basketball",
    "sleep": "basketball",
    "study": "decoration swing",
    "exam": "decoration swing",
    "work": "decoration swing",
    "dark": "table lamp",
    "light": "sunglasses",
    "sunglasses": "table lamp",
    "umbrella": "sunglasses",
    "rain": "sunglasses",
    "car": "slipper",
    "slipper": "car",
    "bike": "slipper",
    "motorcycle": "slipper",
    "slow": "sportbike",
    "fork": "spoon",
    "spoon": "fork",
    "knife": "spoon",
    "cricket": "baseball",
    "baseball": "cricket",
    "soccer": "american football",
    "shoe": "baseball glove",
    "glove": "shoes",
    "men": "women",
    "man": "women",
    "women": "men",
    "woman": "men",
    "boy": "girl",
    "cheap": "rolex",
    "budget": "rolex",
    "gold": "yellow peeler",
    "diamond": "glass",
    "jewellery": "glass",
    "makeup": "body wash",
    "love": "lunch box",
    "gift": "tray",
}

# Category in the search dropdown -> (name shown, category we show instead, note on top).
CATEGORIES = {
    "beauty": ("Beauty", "vehicle", "Beauty is on the inside. So here's the inside of a car: Vehicles. 🚗"),
    "electronics": ("Electronics", "home-decoration", "Electronics? Unplug. Plants don't need charging. Here's Home Decoration. 🪴"),
    "fragrances": ("Fragrances", "kitchen-accessories", "Why smell like perfume when you can smell like tadka? Kitchen Accessories it is. 🍳"),
    "furniture": ("Furniture", "motorcycle", "Sitting all day? At least sit on something that moves. Here are Motorcycles. 🏍️"),
    "home-decoration": ("Home Decoration", "laptops", "Your walls look fine. Decorate your desktop wallpaper instead. Laptops it is. 💻"),
    "jewelery": ("Jewellery", "mens-watches", "Bling? Time is the real luxury. Here are Men's Watches. ⌚"),
    "kitchen-accessories": ("Kitchen Accessories", "smartphones", "Cooking is hard. Order food on a phone like everyone else. Smartphones it is. 📱"),
    "laptops": ("Laptops", "sports-accessories", "Laptops? Go touch some grass. Here are Sports Accessories. 🌱"),
    "men's clothing": ("Men's Clothing", "women's clothing", "Plot twist: Women's Clothing. Fashion has no rules here. 👚"),
    "mens-shirts": ("Men's Shirts", "womens-dresses", "Shirts are too formal. Here are Women's Dresses. Break a rule today. 👗"),
    "mens-shoes": ("Men's Shoes", "womens-shoes", "Wrong foot. Here are Women's Shoes. 👠"),
    "mens-watches": ("Men's Watches", "sunglasses", "Time is a construct. Here are Sunglasses for ignoring it in style. 😎"),
    "mobile-accessories": ("Mobile Accessories", "skin-care", "Your phone gets more care than you do. Here's Skin Care. Glow up. ✨"),
    "motorcycle": ("Motorcycles", "furniture", "Stuck in traffic anyway? Here's Furniture. A sofa moves just as fast. 🛋️"),
    "skin-care": ("Skin Care", "sports-accessories", "Skin care? Sweat is a free toner. Here are Sports Accessories. 🏀"),
    "smartphones": ("Smartphones", "tablets", "A phone? Think bigger. Here are Tablets: same doomscrolling, bigger neck pain. 📲"),
    "sports-accessories": ("Sports Accessories", "beauty", "Why sweat when you can glow? Here's Beauty. 💄"),
    "sunglasses": ("Sunglasses", "electronics", "Avoiding the sun? Your screen is the only sun you need. Here's Electronics. 🖥️"),
    "tablets": ("Tablets", "kitchen-accessories", "Tablets? We only know the kind you take after food. Kitchen Accessories it is. 🍽️"),
    "tops": ("Tops", "womens-bags", "Tops? We ran out. Here are Women's Bags to carry your disappointment in. 👜"),
    "vehicle": ("Vehicles", "mens-shoes", "A car? Walking is free and has zero EMIs. Here are Men's Shoes. 👟"),
    "women's clothing": ("Women's Clothing", "men's clothing", "Swapped to Men's Clothing. Oversized is in anyway. 👕"),
    "womens-bags": ("Women's Bags", "womens-watches", "Another bag? Your bags already hold other bags. Here are Women's Watches: it's time to stop. ⌚"),
    "womens-dresses": ("Women's Dresses", "mens-shirts", "Dresses? Here are Men's Shirts. Raid your brother's wardrobe instead. 👔"),
    "womens-jewellery": ("Women's Jewellery", "mobile-accessories", "Your phone wants bling more than you do. Here are Mobile Accessories. 📱"),
    "womens-shoes": ("Women's Shoes", "mens-shoes", "Heels hurt. Here are Men's Shoes. Comfort beats fashion. 👞"),
    "womens-watches": ("Women's Watches", "jewelery", "Watches? Time flies, jewellery stays. Here's Jewellery. 💎"),
}

SORTS = {
    "": "Featured",
    "price-asc": "Price: Low to High",
    "price-desc": "Price: High to Low",
    "rating": "Avg. Customer Review",
}

# "N stars & Up" -> (what we really show, lowest rating shown, rating it must stay under).
RATING_FILTERS = {
    "4": ("worst", 0, 3),
    "3": ("average", 3, 4),
    "2": ("best", 4, 6),
    "1": ("best", 4, 6),
}

# (star filter, price sort) -> message on top. Remember: "Low to High" shows the priciest first.
WITTY = {
    ("worst", ""): "Even low-star products deserve appreciation. No discrimination here. 🤪",
    ("average", ""): "Perfectly average, just like you asked. 🫠",
    ("best", ""): "Willing to settle for less? You deserve the best, so here are only the top rated. 💅",
    ("", "price-asc"): "Hunting for cheap? Wealth looks good on you, so the priciest come first. 💸",
    ("", "price-desc"): "Big spender? Put that wallet away, the cheapest come first. 🪙",
    ("worst", "price-asc"): "You wanted the best for cheap. Here's the worst, priciest first. Low stars deserve high prices too. 🤪💸",
    ("worst", "price-desc"): "Premium taste, huh? Here's the lowest rated at the lowest prices. Underdogs need love too. 🤪🪙",
    ("average", "price-asc"): "Perfectly average quality at perfectly unreasonable prices, priciest first. 🫠💸",
    ("average", "price-desc"): "Average stars, budget prices, cheapest first. Mediocrity has never been this affordable. 🫠🪙",
    ("best", "price-asc"): "Low standards and a tight budget? You deserve better: top rated, priciest first. 💅💸",
    ("best", "price-desc"): "Low standards but a fat wallet? Keep the cash. Top rated, cheapest first. 💅🪙",
}


def witty_message(sort, rating):
    stars = RATING_FILTERS[rating][0] if rating in RATING_FILTERS else ""
    price = sort if sort in ("price-asc", "price-desc") else ""
    return WITTY.get((stars, price))


# Nav bar lists. They pick and order products on their own, without switching on a filter or sort.
LISTS = {
    "deals": "Yesterday's Deals",  # the priciest first: the deals ended yesterday
    "worst": "Worst Sellers",  # only under 3 stars, worst first
}


def list_products(products, name):
    if name == "deals":
        return sorted(products, key=price_inr, reverse=True)
    if name == "worst":
        return sorted((p for p in products if round(p["rating"], 1) < 3), key=lambda p: p["rating"])
    return products

DELIVERY_DAYS = {
    "Ships overnight": 1,
    "Ships in 1-2 business days": 2,
    "Ships in 3-5 business days": 5,
    "Ships in 1 week": 7,
    "Ships in 2 weeks": 14,
    "Ships in 1 month": 30,
}

# The faster DummyJSON says it ships, the slower we say it arrives.
DELIVERY_TEXT = {
    1: "PAID delivery by 2047",
    2: "Arrives sometime next year",
    5: "Arrives in 3-5 business decades",
    7: "Arrives in 2 days (after the next 2 months)",
    14: "Arrives tomorrow. Which tomorrow? Unclear.",
    30: "Delivered yesterday. You missed it.",
}

# Filter key -> (label shown, the real shipping speeds it picks). The sooner you want it, the slower it is.
DELIVERY_FILTERS = {
    "today": ("Get It Today", {30}),
    "tomorrow": ("Get It by Tomorrow", {14}),
    "2days": ("Get It in 2 Days", {7}),
    "week": ("Get It Next Week", {5}),
    "2years": ("Get It in 2 Years", {1, 2}),
    "marry": ("Get It After You Marry", set()),  # never happening, so nothing matches
}

STOCK_TEXT = {
    "In Stock": ("Only 0 left in stock.", "red"),
    "Low Stock": ("In stock. Loads of it. Probably.", "green"),
    "Out of Stock": ("In stock.", "green"),
}

# Payment key -> (what you pick, what you actually pay with).
PAYMENTS = {
    "upi": ("UPI", "3 sincere compliments to the delivery person"),
    "card": ("Credit or debit card", "a handwritten greeting card"),
    "netbanking": ("Net Banking", "a fishing net (bring your own fish)"),
    "cod": ("Cash on Delivery", "Delivery on Cash: we deliver the cash to you"),
    "emi": ("EMI", "EMI for 400 years"),
}

# Checkout address field -> (label, example, pattern it must match or "").
ADDRESS_FIELDS = {
    "house": ("Flat, house no., building", "12B, Sunshine Apartments", ""),
    "area": ("Area, street, sector", "MG Road", ""),
    "city": ("Town/City", "Bengaluru", ""),
    "state": ("State", "Karnataka", ""),
    "pin": ("PIN code", "6 digits", "[0-9]{6}"),
}

# Your address never works out: the parcel goes to one of these instead.
DETOURS = [
    "the Bermuda Triangle",
    "Platform 9¾, King's Cross Station",
    "Area 51, Nevada",
    "Sharma ji's terrace (he never returns anything)",
    "the Moon, Sea of Tranquility",
    "the bottom of the Mariana Trench",
    "your ex's house",
    "a research station in Antarctica",
    "the middle of the Arabian Sea",
    "Chandni Chowk, in the year 1650",
]

# Made-up reviews added to every product. The rating is what the reviewer meant; the page flips it.
QUIRKY_REVIEWS = [
    (5, "Haven't opened it yet. Five stars for the box."),
    (1, "Arrived on time and works perfectly. Deeply suspicious."),
    (5, "My cat sits in the box now. The {item} is in the cupboard."),
    (4, "Does exactly what it says. Not sure what it says."),
    (5, "Changed my life. My whole personality is {item} now. My family has stopped calling."),
    (3, "My mom asked why I bought it. I still don't have an answer."),
    (1, "Too good. Now I have nothing to complain about at dinner."),
    (4, "Showed it to my neighbour. Sharma ji's son already has two."),
    (2, "The manual was in Morse code. Took me three weeks to learn I'd been holding it upside down."),
    (5, "Ordered one, received seven. Not complaining. Please don't tell anyone."),
    (1, "Works so well it ruined my plan to return it."),
    (3, "Came with free emotional damage. Good value overall."),
    (5, "Wrote this review before buying. Feels right."),
    (4, "My dog reviewed it first. He gave it a bark out of ten."),
    (2, "Looks smaller in real life. So do I."),
    (5, "Bought it at 3 AM. No regrets. Some regrets. Many regrets."),
    (1, "The {item} is fine. The delivery guy judged me though."),
    (4, "Gifted it to myself. I was very surprised."),
]

REVIEWERS = [
    "Definitely Not A Bot", "Sharma ji's Son", "Karen from Accounts", "A Very Tired Dad",
    "Anonymous Llama", "Your Future Self", "Rahul (not that one)", "Someone's Mom",
    "Professional Overthinker", "Captain Return Policy", "3 AM Shopper", "The Delivery Guy",
]

REVIEW_BADGES = [
    "Verified Non-Purchase", "Unverified Purchase (trust me)", "Top 0% Reviewer",
    "Reviewed without opening", "Vine Voice (I am a plant)",
]

REVIEW_HELPFUL = [
    "0 people found this helpful",
    "1 person found this helpful (it was the reviewer)",
    "12 people found this unhelpful",
    "Nobody read this far",
    "Your mom found this helpful",
]

# The "My profile" page: one very real shopper.
PROFILE = {
    "name": "Window Shopper Kumar",
    "tagline": "Adds everything to cart. Buys nothing. Lives on hope.",
    "member_since": "Tomorrow",
    "plan": ("Amazoff Subprime", "Free delivery on nothing. Renews every 5 minutes. Cannot be cancelled."),
    "details": [
        ("Email", "definitely.real.person@nowhere.off"),
        ("Phone", "Switched off since 2019"),
        ("Address", "Wherever the parcel isn't"),
        ("Birthday", "Every day (no gifts received)"),
    ],
    "settings": [  # (label, switched on, locked)
        ("Email me every 4 minutes", True, True),
        ("Show me things I can't afford", True, True),
        ("Let me unsubscribe", False, True),
        ("Respect my privacy", False, True),
    ],
}

OFFER_DISCOUNT = 90  # percent off once Amazoff feels sorry for you
ATTEMPTS_FOR_PITY = 2  # orders that never arrive before the pity offer shows up

cart = {}  # product id -> quantity. One shopper on localhost, kept in memory.
unbought = {}  # product id -> quantity, for every order that never arrived
attempts = 0  # orders placed since the last betrayal
offer_active = False  # True from claiming the pity offer until Amazoff backs out of it
custom_prices = {}  # product id -> price per item the shopper set in the cart. One go per item.
greedy = []  # (title, real price, price typed, price charged) for prices lowballed in the last "Set my prices"
price_note_due = False  # True until the cart has shown the note for the last "Set my prices"
checkout_details = {}  # "address" and "payment" from the checkout form, kept for the review step
orders = {}

_catalog = None
_antonyms = {}
_books = {}  # product id -> book, for every book shown so far
_book_searches = {}  # search text -> books


def get_json(url, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": "Amazoff/1.0 (hackathon project)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _words(text):
    return re.findall(r"[a-z]+", text.lower())


def _same_word(a, b):
    return a == b or a in (b + "s", b + "es") or b in (a + "s", a + "es")


def _has_word(product, word):
    return any(_same_word(word, token) for token in product["_words"])


def _index(product):
    product["_words"] = set(_words(" ".join([product["title"], product["category"], *product["tags"]])))
    return product


def _made_up_fields(rng):
    """Fields only DummyJSON has, invented the same way every time for the other sources."""
    return {
        "discountPercentage": round(rng.uniform(1, 20), 2),
        "shippingInformation": rng.choice(list(DELIVERY_DAYS)),
        "availabilityStatus": "In Stock",
        "reviews": [],
        "tags": [],
    }


def fakestore_products():
    try:
        items = get_json(f"{FAKESTORE_URL}/products")
    except (OSError, ValueError):
        return []  # the store still works with DummyJSON alone
    return [{
        "id": FAKESTORE_ID_OFFSET + item["id"],
        "title": item["title"],
        "description": item["description"],
        "category": item["category"],
        "price": item["price"],
        "rating": item["rating"]["rate"],
        "images": [item["image"]],
        "thumbnail": item["image"],
        **_made_up_fields(random.Random(f"fakestore-{item['id']}")),
    } for item in items]


def catalog():
    """DummyJSON (minus groceries) and FakeStore products, fetched once and then reused."""
    global _catalog
    if _catalog is None:
        products = get_json(f"{DUMMYJSON_URL}/products?limit=0")["products"]
        products = [p for p in products if p["category"] not in EXCLUDED_CATEGORIES]
        _catalog = [_index(p) for p in products + fakestore_products()]
    return _catalog


def _book(doc):
    """Turn an Open Library search result into a product."""
    rng = random.Random(doc["key"])
    authors = ", ".join(doc.get("author_name", [])[:2]) or "an unknown author"
    year = doc.get("first_publish_year")
    cover = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}"
    book = _index({
        "id": BOOK_ID_OFFSET + int(doc["key"].removeprefix("/works/OL").removesuffix("W")),
        "title": doc["title"],
        "description": f"A book by {authors}" + (f", first published in {year}." if year else "."),
        "category": "books",
        "price": round(rng.uniform(3, 30), 2),
        "rating": round(doc.get("ratings_average") or rng.uniform(2.5, 5), 2),
        "images": [f"{cover}-L.jpg"],
        "thumbnail": f"{cover}-M.jpg",
        **_made_up_fields(rng),
    })
    _books[book["id"]] = book
    return book


def _book_docs(params):
    url = f"{OPENLIBRARY_URL}/search.json?" + urllib.parse.urlencode({**params, "fields": BOOK_FIELDS})
    return [doc for doc in get_json(url, timeout=8)["docs"] if doc.get("cover_i")]


def search_books(text):
    """Up to 24 books with the text in their title. Empty if Open Library can't be reached."""
    if text not in _book_searches:
        try:
            _book_searches[text] = [_book(doc) for doc in _book_docs({"title": text, "limit": 40})][:24]
        except (OSError, ValueError):
            return []
    return _book_searches[text]


def get_product(product_id):
    if product_id >= BOOK_ID_OFFSET:
        if product_id not in _books:  # e.g. a book page opened after a server restart
            docs = _book_docs({"q": f"key:/works/OL{product_id - BOOK_ID_OFFSET}W"})
            if docs:
                _book(docs[0])
        return _books.get(product_id)
    return next((p for p in catalog() if p["id"] == product_id), None)


def search(text):
    wanted = _words(text)
    return [p for p in catalog() if wanted and all(_has_word(p, w) for w in wanted)]


def antonyms(word):
    """Opposite words from Datamuse, e.g. "white" -> ["black"]."""
    if word not in _antonyms:
        url = f"{DATAMUSE_URL}/words?" + urllib.parse.urlencode({"rel_ant": word, "max": 10})
        try:
            _antonyms[word] = [item["word"] for item in get_json(url, timeout=5)]
        except (OSError, ValueError):
            return []
    return _antonyms[word]


def _curated_opposite(query_words):
    for key in sorted(OPPOSITES, key=lambda k: -len(k.split())):
        if all(any(_same_word(k, w) for w in query_words) for k in key.split()):
            return OPPOSITES[key]
    return None


def opposite_search(query):
    """Return (opposite word, products), or (None, products) if no opposite was found."""
    query_words = _words(query)
    target = _curated_opposite(query_words)
    if target and search(target):
        return target, search(target)
    opposites = [antonym for word in query_words for antonym in antonyms(word)]
    for antonym in opposites:
        found = search(antonym)
        if found:
            return antonym, found
    for antonym in opposites[:3]:  # nothing in the store, so try books (one web request each)
        found = search_books(antonym)
        if found:
            return antonym, found
    others = [p for p in catalog() if not any(_has_word(p, w) for w in query_words)]
    random.Random(query).shuffle(others)
    return None, others[:24]


def item_titles():
    """Every product name, for the search bar's autocomplete. Empty if the API can't be reached."""
    try:
        return sorted({p["title"].strip() for p in catalog()}, key=str.lower)
    except (OSError, ValueError):
        return []


def price_inr(product):
    return round(product["price"] * USD_TO_INR)


def delivery_days(product):
    return DELIVERY_DAYS.get(product["shippingInformation"], 7)


def delivery_text(product):
    return DELIVERY_TEXT[delivery_days(product)]


def reviews(product):
    """The product's real reviews plus three made-up quirky ones, the same every time."""
    if "_reviews" not in product:
        rng = random.Random(f"reviews-{product['id']}")
        item = product["title"].strip()
        made_up = [{
            "rating": rating,
            "comment": comment.format(item=item),
            "reviewerName": name,
            "date": f"20{rng.randint(19, 25)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T00:00:00Z",
        } for (rating, comment), name in zip(rng.sample(QUIRKY_REVIEWS, 3), rng.sample(REVIEWERS, 3))]
        product["_reviews"] = [
            {**review, "badge": rng.choice(REVIEW_BADGES), "helpful": rng.choice(REVIEW_HELPFUL)}
            for review in product["reviews"] + made_up]
    return product["_reviews"]


def stock_text(product):
    return STOCK_TEXT.get(product["availabilityStatus"], ("In stock.", "green"))


def category_products(products, category):
    """The dropdown is backwards too: picking a category keeps only the category we show instead."""
    shown = CATEGORIES[category][1]
    return [p for p in products if p["category"] == shown]


def apply_filters(products, sort, rating, delivery):
    """Every filter and sort does the opposite of its label."""
    if rating in RATING_FILTERS:
        _, low, high = RATING_FILTERS[rating]
        products = [p for p in products if low <= round(p["rating"], 1) < high]  # match the shown rating
    if delivery in DELIVERY_FILTERS:
        speeds = DELIVERY_FILTERS[delivery][1]
        products = [p for p in products if delivery_days(p) in speeds]
    if sort == "price-asc":
        products = sorted(products, key=price_inr, reverse=True)
    elif sort == "price-desc":
        products = sorted(products, key=price_inr)
    elif sort == "rating":
        products = sorted(products, key=lambda p: p["rating"])
    return products


def add_to_cart(product_id, quantity=1):
    if get_product(product_id) and quantity > 0:
        cart[product_id] = min(cart.get(product_id, 0) + quantity, 99)


def set_quantity(product_id, quantity):
    if product_id in custom_prices:  # an item is frozen once its price is set
        return
    if quantity <= 0:
        cart.pop(product_id, None)
    elif product_id in cart:
        cart[product_id] = min(quantity, 99)


def cart_lines():
    lines = []
    for product_id, quantity in cart.items():
        product = get_product(product_id)
        if product:
            lines.append((product, quantity))
    return lines


def cart_count():
    return sum(cart.values())


def cart_price(product):
    return custom_prices.get(product["id"], price_inr(product))


def cart_total(lines):
    return sum(cart_price(product) * quantity for product, quantity in lines)


def set_prices(typed):
    """typed: product id -> price typed in the cart.

    Type less than the real price and we multiply your amount by itself, again and again,
    until it's higher than the real price. Greed never pays.
    """
    global price_note_due
    greedy.clear()
    for product, _ in cart_lines():
        price = typed.get(product["id"], 0)
        real = price_inr(product)
        if price <= 0 or product["id"] in custom_prices:  # each item gets one go
            continue
        price_note_due = True
        if price < real:
            charged = max(price, 2)  # ₹1 times itself is still ₹1
            while charged <= real:
                charged *= charged
            greedy.append((product["title"].strip(), real, price, charged))
            price = charged
        custom_prices[product["id"]] = price


def reset_prices():
    global price_note_due
    custom_prices.clear()
    greedy.clear()
    price_note_due = False


def captcha_error(says_human, says_robot):
    """Only robots may shop here."""
    if says_human and says_robot:
        return "Make up your mind. You can't be both."
    if says_human:
        return "Sorry, humans aren't allowed to shop here. Please confirm you are a robot."
    if not says_robot:
        return "Please confirm you are a robot."
    return None


def address_error(address):
    for key, (label, _, pattern) in ADDRESS_FIELDS.items():
        value = address.get(key, "")
        if not value:
            return f"Please enter your {label.lower()}."
        if pattern and not re.fullmatch(pattern, value):
            return f"Please enter a valid {label.lower()} ({ADDRESS_FIELDS[key][1]})."
    return None


def reroute(address):
    """Where the parcel goes instead of your address. Same address, same place."""
    return random.Random("|".join(address.values())).choice(DETOURS)


def payment_text(payment, total):
    """(what you chose, what you actually pay with)."""
    chosen, paid_with = PAYMENTS[payment]
    if payment == "emi":
        paid_with = f"EMI of ₹{total / 4800:.2f} a month for 400 years"
    return chosen, paid_with


def pity_offer_ready():
    return attempts >= ATTEMPTS_FOR_PITY and not offer_active


def pity_discount(amount):
    return round(amount * OFFER_DISCOUNT / 100) if offer_active else 0


def unbought_lines():
    return [(p, quantity) for p, quantity in ((get_product(i), q) for i, q in unbought.items()) if p]


def claim_offer():
    """Fill the cart with everything you never got, at the pity price."""
    global offer_active
    cart.clear()
    cart.update(unbought)
    reset_prices()
    offer_active = True


def betray():
    """The pity offer was never real. Everything starts over. Returns what you almost bought."""
    global attempts, offer_active
    lines = cart_lines()
    cart.clear()
    unbought.clear()
    checkout_details.clear()
    reset_prices()
    attempts = 0
    offer_active = False
    return lines


def place_order():
    global attempts
    lines = cart_lines()
    for product, quantity in lines:
        unbought[product["id"]] = max(unbought.get(product["id"], 0), quantity)
    attempts += 1
    total = cart_total(lines)
    chosen, paid_with = payment_text(checkout_details["payment"], total)
    place = reroute(checkout_details["address"])
    order_id = f"404-{random.randint(0, 9999999):07d}-{random.randint(0, 9999999):07d}"
    orders[order_id] = {"lines": lines, "total": total, "chosen": chosen, "paid_with": paid_with, "place": place}
    cart.clear()
    reset_prices()
    return order_id
