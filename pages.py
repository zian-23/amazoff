"""HTML for every Amazoff page. Text from users or APIs always goes through esc()."""

import html
import string
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import store

BASE = string.Template((Path(__file__).parent / "templates" / "base.html").read_text(encoding="utf-8"))


def esc(value):
    return html.escape(str(value))


def indian_number(amount):
    """1234567 -> "12,34,567" (Indian digit grouping)."""
    digits = str(abs(round(amount)))
    head, groups = digits[:-3], [digits[-3:]]
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ("-" if amount < 0 else "") + ",".join(groups)


def rupees(amount):
    if amount < 0:
        return "-₹" + indian_number(-amount)
    return "₹" + indian_number(amount)


def price_tag(amount, css="price"):
    return f'<span class="{css}"><span class="sym">₹</span>{indian_number(amount)}</span>'


def stars(rating):
    return (f'<span class="stars" title="{rating:.1f} out of 5 stars">'
            f'<span style="width:{rating / 5 * 100:.0f}%"></span></span>')


def search_url(**params):
    params = {key: value for key, value in params.items() if value}
    return "/search?" + urlencode(params) if params else "/search"


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def layout(title, content, query="", category=""):
    def category_link(key, name):
        css = ' class="active"' if key == category else ""
        return f'<a{css} href="{esc(search_url(category=key))}">{esc(name)}</a>'

    categories = sorted(store.CATEGORIES.items(), key=lambda item: item[1][0])
    links = category_link("", "All") + "".join(category_link(key, name) for key, (name, _, _) in categories)
    current_name = store.CATEGORIES[category][0] if category in store.CATEGORIES else "All"
    # A menu of links, not a <select>: picking one opens it right away, with no JavaScript.
    # It opens while the button (or a link in it) has focus, so clicking anywhere else closes it.
    category_menu = (f'<div class="category-menu"><button type="button" aria-label="Search in">'
                     f'{esc(current_name)} &#9662;</button><div class="category-list">{links}</div></div>')
    if category:  # so typing a search looks inside the chosen category
        category_menu += f'<input type="hidden" name="category" value="{esc(category)}">'
    suggestions = "".join(f'<option value="{esc(name)}">' for name in store.item_titles())
    # Floats around every page once two orders have gone nowhere. Opens only when clicked.
    offer_button = ('<a class="pity-offer" href="/offer">🎁 Psst… Amazoff has something for you</a>'
                    if store.pity_offer_ready() else "")
    return BASE.substitute(title=esc(title), query=esc(query), category_menu=category_menu,
                           suggestions=suggestions, cart_count=store.cart_count(), content=content,
                           offer_button=offer_button)


# Search and home page

# Shown for "Get It After You Marry": no results, because that day is never coming.
NEVER_MARRIED = """
<div class="panel never">
  <h2>No results. This delivery date is not expected to happen in your lifetime.</h2>
  <p class="never-code">ERR_FOREVER_SINGLE</p>
</div>"""

def results_page(params):
    query = params.get("q", "").strip()
    category = params.get("category", "")
    current = {
        "q": query,
        "category": category if category in store.CATEGORIES else "",
        "list": params.get("list", "") if params.get("list", "") in store.LISTS else "",
        "sort": params.get("sort", ""),
        "rating": params.get("rating", ""),
        "delivery": params.get("delivery", ""),
    }

    banner = ""
    notes = []  # sticky notes shown above the results
    if query:
        shown, products = store.opposite_search(query)
        if shown:
            banner = (f'Showing results for <b class="red">{esc(shown)}</b>. Search instead for '
                      f'<a href="{esc(search_url(q=query, category=current["category"]))}">{esc(query)}</a>')
        else:
            notes.append(f'ERROR 404: Opposite of "{query}" not found. Enjoy these random things instead. 🎲')
    else:
        products = store.catalog()
    witty = store.witty_message(current["sort"], current["rating"])
    # A delivery day picked on top of both a price sort and a star filter clears the note.
    hide_note = bool(current["delivery"] and current["rating"] in store.RATING_FILTERS
                     and current["sort"] in ("price-asc", "price-desc"))
    if hide_note:
        witty = None
    if current["category"]:
        if not witty and not hide_note:  # once you pick stars or a price sort, their note replaces the category's
            notes.append(store.CATEGORIES[current["category"]][2])
        shown_category = store.CATEGORIES[store.CATEGORIES[current["category"]][1]][0]
        in_category = store.category_products(products, current["category"])
        if not in_category:  # none of the opposites are in that category, so show the category itself
            if banner:
                banner = ""
                notes.append(f'ERROR 404: Opposite of "{query}" not found in {shown_category}. Enjoy these instead. 🎲')
            in_category = store.category_products(store.catalog(), current["category"])
        products = in_category
    products = store.list_products(products, current["list"])
    products = store.apply_filters(products, current["sort"], current["rating"], current["delivery"])

    count = f"1-{len(products)} of {len(products)} results" if products else "No results"
    if query:
        count += f' for <b class="query">"{esc(query)}"</b>'
    if current["category"]:
        count += f" in <b>{esc(shown_category)}</b>"
    if current["list"]:
        count += f" in <b>{esc(store.LISTS[current['list']])}</b>"
    cards = "".join(product_card(p) for p in products)
    if current["delivery"] == "marry":
        cards = NEVER_MARRIED
    elif not cards:
        cards = '<p class="panel">No results. Exactly what you asked for.</p>'
    if witty:
        notes.append(witty)

    content = f"""
<div class="results-bar"><span>{count}</span>{sort_form(current)}</div>
{''.join(f'<p class="witty">{esc(note)}</p>' for note in notes)}
{f'<p class="banner">{banner}</p>' if banner else ''}
<div class="search-layout">
  <aside class="filters">{filters_html(current)}</aside>
  <section class="grid">{cards}</section>
</div>"""
    title = query or store.LISTS.get(current["list"], "Shopping, but backwards")
    return layout(title, content, query, current["category"])


def sort_form(current):
    hidden = "".join(f'<input type="hidden" name="{key}" value="{esc(value)}">'
                     for key, value in current.items() if value and key != "sort")
    options = "".join(f'<option value="{value}"{" selected" if value == current["sort"] else ""}>{label}</option>'
                      for value, label in store.SORTS.items())
    css = ' class="active"' if current["sort"] and current["sort"] in store.SORTS else ""
    return (f'<form class="sort" action="/search" method="get">{hidden}'
            f'<label>Sort by: <select name="sort"{css}>{options}</select></label> '
            f'<button class="btn btn-small" type="submit">Go</button></form>')


def filters_html(current):
    def link(key, value, label):
        css = "active" if current[key] == value else ""
        return f'<a class="{css}" href="{esc(search_url(**{**current, key: value}))}">{label}</a>'

    def clear(key):
        return link(key, "", "&lsaquo; Clear") if current[key] else ""

    ratings = "".join(link("rating", str(n), f"{stars(n)} &amp; Up") for n in (4, 3, 2, 1))
    delivery = "".join(link("delivery", key, label) for key, (label, _) in store.DELIVERY_FILTERS.items())
    return (f"<h3>Customer Reviews</h3>{clear('rating')}<div class=\"rating-filters\">{ratings}</div>"
            f"<h3>Delivery Day</h3>{clear('delivery')}{delivery}")


def product_card(p):
    url = f"/product/{p['id']}"
    return f"""
<div class="card">
  <a class="card-img" href="{url}"><img src="{esc(p['thumbnail'])}" alt="{esc(p['title'])}" loading="lazy"></a>
  <a class="card-title" href="{url}">{esc(p['title'])}</a>
  <div>{p['rating']:.1f} {stars(p['rating'])} <span class="muted">({len(store.reviews(p))})</span></div>
  {price_tag(store.price_inr(p))}
  <div class="small delivery">{esc(store.delivery_text(p))}</div>
  <form method="post" action="/cart/add">
    <input type="hidden" name="id" value="{p['id']}">
    <button class="btn btn-yellow btn-small" type="submit">Add to cart</button>
  </form>
</div>"""


# Product page

def product_page(p, image_index):
    images = p["images"] or [p["thumbnail"]]
    if not 0 <= image_index < len(images):
        image_index = 0
    thumbs = "".join(
        f'<a class="{"active" if i == image_index else ""}" href="/product/{p["id"]}?img={i}">'
        f'<img src="{esc(src)}" alt=""></a>'
        for i, src in enumerate(images))

    price = store.price_inr(p)
    markup = p["discountPercentage"]
    list_price = price / (1 + markup / 100)  # the "M.R.P." is lower than what you pay
    stock, stock_css = store.stock_text(p)
    quantities = "".join(f'<option value="{n}">{n}</option>' for n in range(1, 11))
    reviews = "".join(review_html(r) for r in store.reviews(p))

    content = f"""
<div class="product panel">
  <div class="gallery">
    <div class="thumbs">{thumbs}</div>
    <div class="main-img"><img src="{esc(images[image_index])}" alt="{esc(p['title'])}"></div>
  </div>
  <div class="info">
    <h1>{esc(p['title'])}</h1>
    <a href="/">Avoid the Amazoff Store</a>
    <div>{p['rating']:.1f} {stars(p['rating'])} <span class="muted">{plural(len(store.reviews(p)), 'rating')}</span></div>
    <hr>
    <div><span class="markup">+{markup:.0f}%</span>{price_tag(price, 'price big')}</div>
    <div class="muted small">M.R.P.: <s>{rupees(list_price)}</s></div>
    <div class="small">Exclusive of all taxes</div>
    <hr>
    <h3>About this item</h3>
    <p>{esc(p['description'])}</p>
  </div>
  <div class="buybox">
    {price_tag(price)}
    <div class="delivery">{esc(store.delivery_text(p))}</div>
    <div class="{stock_css} big-text">{esc(stock)}</div>
    <form method="post" action="/cart/add" class="buy-form">
      <input type="hidden" name="id" value="{p['id']}">
      <label>Quantity: <select name="qty">{quantities}</select></label>
      <button class="btn btn-yellow" type="submit" name="action" value="cart">Add to Cart</button>
      <button class="btn btn-orange" type="submit" name="action" value="buy">Buy Now</button>
    </form>
    <div class="small muted">Ships from <b>Nowhere</b><br>Sold by <b>Nobody</b></div>
  </div>
</div>
<section class="reviews panel">
  <h2>Customer reviews</h2>
  <div>{stars(p['rating'])} {p['rating']:.1f} out of 5</div>
  <h3>Bottom reviews from Antarctica</h3>
  {reviews}
</section>"""
    return layout(p["title"], content)


def review_html(review):
    flipped = 6 - review["rating"]  # 5 stars become 1 star, and 1 becomes 5
    date = datetime.fromisoformat(review["date"].replace("Z", "+00:00"))
    name = review["reviewerName"]
    return f"""
<div class="review">
  <div class="reviewer"><span class="avatar">{esc(name[:1])}</span>{esc(name)}</div>
  <div>{stars(flipped)} <b>{esc(review['comment'])}</b></div>
  <div class="small muted">Reviewed in Antarctica on {date.day} {date:%B %Y}</div>
  <div class="small orange">{esc(review['badge'])}</div>
  <div class="small muted">{esc(review['helpful'])}</div>
</div>"""


# Profile

def profile_page(deleted=False):
    me = store.PROFILE
    plan, perks = me["plan"]
    alert = ('<div class="alert"><b>Account deletion is out of stock.</b><br>'
             'Please try again in 400 years.</div>') if deleted else ""
    stats = [
        (str(len(store.orders)), "Orders placed", "0 arrived"),
        (str(store.cart_count()), "Items in cart", "for emotional support"),
        ("1,284", "Carts abandoned", "a personal best"),
        ("₹0", "Money saved", "spent it all on hope"),
    ]
    tiles = "".join(f'<div class="stat"><b>{esc(value)}</b><span>{esc(label)}</span>'
                    f'<small class="muted">{esc(note)}</small></div>' for value, label, note in stats)
    details = "".join(f"<dt>{esc(key)}</dt><dd>{esc(value)}</dd>" for key, value in me["details"])
    settings = "".join(
        f'<label class="option"><input type="checkbox"{" checked" if on else ""}{" disabled" if locked else ""}> '
        f'{esc(label)}{" <small class=muted>(locked by Amazoff)</small>" if locked else ""}</label>'
        for label, on, locked in me["settings"])

    content = f"""
{alert}
<section class="panel profile-head">
  <span class="avatar big">{esc(me['name'][:1])}</span>
  <div>
    <h1>{esc(me['name'])}</h1>
    <p class="muted">{esc(me['tagline'])}</p>
    <p class="small">Member since: <b>{esc(me['member_since'])}</b> &middot; Profile photo too expensive to load</p>
  </div>
</section>
<div class="stats">{tiles}</div>
<div class="two-col">
  <div>
    <section class="panel step">
      <h2>Your details</h2>
      <dl class="details">{details}</dl>
    </section>
  </div>
  <aside class="panel side-box">
    <h3>Membership</h3>
    <p><b class="orange">{esc(plan)}</b><br><span class="small">{esc(perks)}</span></p>
    <h3>Settings</h3>
    {settings}
    <form method="post" action="/profile/delete"><button class="btn btn-white" type="submit">Delete my account</button></form>
  </aside>
</div>"""
    return layout("Your profile", content)


# Cart, checkout and order

def qty_button(product_id, quantity, label, css="qty-btn"):
    return (f'<form method="post" action="/cart/update">'
            f'<input type="hidden" name="id" value="{product_id}">'
            f'<input type="hidden" name="qty" value="{quantity}">'
            f'<button class="{css}" type="submit">{label}</button></form>')


def cart_page():
    lines = store.cart_lines()
    if not lines:
        content = """
<section class="panel">
  <h1>Your Amazoff Cart is empty.</h1>
  <p>Your wallet says thank you.</p>
  <a href="/search?list=deals">Shop Yesterday's Deals</a>
</section>"""
        return layout("Cart", content)

    editable = [p for p, _ in lines if p["id"] not in store.custom_prices]
    items = ""
    for p, quantity in lines:
        if p["id"] in store.custom_prices:  # its price is set for good, and so is its quantity
            controls = f'<span class="small muted">Qty: {quantity}</span>'
            real = store.price_inr(p)
            price = store.cart_price(p)
            was = f'<div class="small muted">Real price: <s>{rupees(real)}</s></div>' if price != real else ""
            price_html = f"<div><b>{rupees(price)}</b>{was}</div>"
        else:
            controls = (f"{qty_button(p['id'], quantity - 1, '&minus;')}<span class=\"qty\">{quantity}</span>"
                        f"{qty_button(p['id'], quantity + 1, '+')}{qty_button(p['id'], 0, 'Delete', 'link-btn')}")
            # Inputs belong to the "Set my prices" form by id, since forms can't be nested.
            price_html = (f'<label class="price-edit"><span class="small muted">Name your price</span>'
                          f'<span>₹<input type="number" name="price_{p["id"]}" value="{store.price_inr(p)}" '
                          f'min="1" step="1" form="price-form" required></span></label>')
        items += f"""
<div class="cart-item">
  <a href="/product/{p['id']}"><img src="{esc(p['thumbnail'])}" alt="{esc(p['title'])}"></a>
  <div>
    <a class="cart-title" href="/product/{p['id']}">{esc(p['title'])}</a>
    <div class="green small">In stock</div>
    <div class="qty-row">{controls}</div>
  </div>
  {price_html}
</div>"""

    notes = ""
    if editable:
        notes += ('<div class="price-banner"><b>💸 You set the price! 💸</b>'
                  '<span>Don\'t like our prices? Type your own below. For real. One shot per item.</span></div>')
    # The verdict on your prices shows once, right after "Set my prices", for the items just priced.
    if store.price_note_due and store.greedy:
        changes = "".join(
            f"<li><b>{esc(title)}</b>: original price {rupees(real)}, you typed {rupees(typed)}, "
            f'now you pay <b class="red">{rupees(charged)}</b></li>'
            for title, real, typed, charged in store.greedy)
        notes += (f'<p class="witty">So greedy! 🤑 You tried to pay less than the real price, '
                  f'so we multiplied your amount by the amount itself. Enjoy your new price.</p>'
                  f'<ul class="greedy">{changes}</ul>')
    elif store.price_note_due:
        notes += '<p class="witty">An honest customer? Suspicious. Prices locked in anyway. 🔒</p>'
    store.price_note_due = False
    set_prices = "" if not editable else (
        '<form id="price-form" method="post" action="/cart/prices">'
        '<button class="btn btn-white" type="submit">Set my prices</button></form>'
        '<p class="small muted">Don\'t like our prices? Type your own. One go per item.</p>')

    subtotal = f"Subtotal ({plural(store.cart_count(), 'item')}): <b>{rupees(store.cart_total(lines))}</b>"
    content = f"""
{notes}
<div class="two-col">
  <section class="panel">
    <h1>Shopping Cart</h1>
    {items}
    <p class="subtotal">{subtotal}</p>
  </section>
  <aside class="panel side-box">
    <p class="subtotal-side">{subtotal}</p>
    <a class="btn btn-yellow" href="/checkout">Proceed to Buy</a>
    <a class="btn btn-white" href="/">Continue to search items</a>
    {set_prices}
  </aside>
</div>"""
    return layout("Cart", content)


def order_summary(total):
    discount = store.pity_discount(total)
    pity = (f'<div class="summary-row green"><span>Pity discount ({store.OFFER_DISCOUNT}% off):</span>'
            f'<span>{rupees(-discount)}</span></div>') if discount else ""
    return f"""
    <h3>Order Summary</h3>
    <div class="summary-row"><span>Items:</span><span>{rupees(total)}</span></div>
    {pity}
    <div class="summary-row"><span>Delivery:</span><span>Free (it isn't coming)</span></div>
    <hr>
    <div class="summary-row total"><span>Order Total:</span><span>{rupees(total - discount)}</span></div>"""


def checkout_page(error="", address=None, payment=""):
    address = address or {}
    lines = store.cart_lines()
    total = store.cart_total(lines)
    fields = ""
    for key, (label, example, pattern) in store.ADDRESS_FIELDS.items():
        rule = f' pattern="{pattern}" inputmode="numeric"' if pattern else ""
        fields += (f'<label class="field">{esc(label)}<input name="{key}" value="{esc(address.get(key, ""))}" '
                   f'placeholder="{esc(example)}" required{rule}></label>')
    options = "".join(
        f'<label class="option"><input type="radio" name="payment" value="{key}" required'
        f'{" checked" if key == payment else ""}> {esc(name)}</label>'
        for key, (name, _) in store.PAYMENTS.items())
    items = "".join(f"<li>{esc(p['title'])} &times; {quantity}</li>" for p, quantity in lines)
    alert = f'<div class="alert"><b>There was a problem</b><br>{esc(error)}</div>' if error else ""

    content = f"""
<h1>Checkout ({plural(store.cart_count(), 'item')})</h1>
<form class="two-col" method="post" action="/checkout">
  <div>
    {alert}
    <section class="panel step">
      <h2>1. Delivery address <span class="hint">Type carefully. Our delivery partners are famously creative with directions. 🧭</span></h2>
      <div class="address-form">{fields}</div>
    </section>
    <section class="panel step">
      <h2>2. Payment method</h2>
      {options}
    </section>
    <section class="panel step">
      <h2>3. Security check</h2>
      <div class="captcha">
        <label><input type="checkbox" name="human" value="1"> I'm not a robot</label>
        <label><input type="checkbox" name="robot" value="1"> I am a robot</label>
      </div>
    </section>
    <section class="panel step">
      <h2>4. Items</h2>
      <ul>{items}</ul>
    </section>
  </div>
  <aside class="panel side-box">
    <button class="btn btn-yellow" type="submit">Review your order</button>
    {order_summary(total)}
  </aside>
</form>"""
    return layout("Checkout", content)


def review_page():
    """The extra step: your address 'fails', and the payment is something weird."""
    lines = store.cart_lines()
    total = store.cart_total(lines)
    address = store.checkout_details["address"]
    place = store.reroute(address)
    chosen, paid_with = store.payment_text(store.checkout_details["payment"], total)
    full_address = (f"{address['house']}, {address['area']}, "
                    f"{address['city']}, {address['state']} {address['pin']}")
    items = "".join(f"<li>{esc(p['title'])} &times; {quantity}</li>" for p, quantity in lines)

    content = f"""
<h1>Review your order</h1>
<div class="two-col">
  <div>
    <section class="panel step">
      <h2>1. Delivery address</h2>
      <p>You entered: <s>{esc(full_address)}</s></p>
      <p class="big-text">So we picked the nearest wrong place. Delivering to: <b class="red">{esc(place)}</b></p>
    </section>
    <section class="panel step">
      <h2>2. Payment method</h2>
      <p class="big-text">You chose <s>{esc(chosen)}</s>. You're paying with: <b class="red">{esc(paid_with)}</b></p>
    </section>
    <section class="panel step">
      <h2>3. Items</h2>
      <ul>{items}</ul>
    </section>
  </div>
  <aside class="panel side-box">
    <form method="post" action="/checkout/review"><button class="btn btn-yellow" type="submit">Proceed to Buy</button></form>
    <a class="btn btn-white" href="/checkout">Change it back</a>
    {order_summary(total)}
  </aside>
</div>"""
    return layout("Review your order", content)


def order_page(order_id, order):
    items = "".join(
        f'<li><img src="{esc(p["thumbnail"])}" alt=""> {esc(p["title"])} &times; {quantity}</li>'
        for p, quantity in order["lines"])
    content = f"""
<section class="panel order">
  <h1 class="green">&#10004; Order placed, no thank you.</h1>
  <p>Confirmation will not be sent to your email.</p>
  <p>Order number: <b>#{esc(order_id)}</b></p>
  <p>Delivering to: <b>{esc(order['place'])}</b> (your address didn't work out).</p>
  <p>You chose: <b>{esc(order['chosen'])}</b>. You paid with: <b>{esc(order['paid_with'])}</b>.</p>
  <p class="big-text">Order total: <b class="red">{rupees(-order['total'])}</b> (we paid you)</p>
  <ul class="order-items">{items}</ul>
  <a class="btn btn-yellow btn-small" href="/">Continue not shopping</a>
</section>"""
    return layout("Order placed", content)


# Pity offer and betrayal

def offer_page():
    lines = store.unbought_lines()
    total = sum(store.price_inr(p) * quantity for p, quantity in lines)
    offer_total = total - round(total * store.OFFER_DISCOUNT / 100)
    items = "".join(
        f'<li><img src="{esc(p["thumbnail"])}" alt=""> {esc(p["title"])} &times; {quantity} '
        f'<s class="muted">{rupees(store.price_inr(p) * quantity)}</s></li>'
        for p, quantity in lines)
    content = f"""
<section class="panel offer">
  <h1>Okay. Even we feel bad now. 🥺</h1>
  <p class="big-text">You tried to buy these {plural(store.attempts, 'time')} and got absolutely nothing.
    So here's <b class="red">{store.OFFER_DISCOUNT}% off</b> everything you tried to buy.</p>
  <ul class="order-items">{items}</ul>
  <p class="big-text">Was <s>{rupees(total)}</s>, now just <b class="red">{rupees(offer_total)}</b></p>
  <form method="post" action="/offer/claim">
    <button class="btn btn-orange btn-offer" type="submit">Claim my pity discount</button>
  </form>
  <p class="small muted">No catch. Pinky promise. 🤞</p>
</section>"""
    return layout("A special offer, just for you", content)


def betrayal_page(lines):
    items = "".join(f"<li>{esc(p['title'])} &times; {quantity}</li>" for p, quantity in lines)
    content = f"""
<section class="panel betrayal">
  <h1 class="red">Sorry, we cannot place this order for you.</h1>
  <p class="big-text">This is Amazoff. Did you really think we'd let you buy something? 🙃</p>
  <p>The pity was real. The discount was not. Your items have been returned to the shelf, then the warehouse,
    and finally the void:</p>
  <ul>{items}</ul>
  <p class="witty">Thank you for not shopping with us. 👋</p>
  <a class="btn btn-yellow btn-small" href="/">Start over (you never learn)</a>
  <div class="big-logo"><img src="/static/logo.svg" alt="amazoff" width="448" height="184"></div>
</section>"""
    return layout("Order cancelled", content)


def message_page(title, message):
    content = f'<section class="panel"><h1>{esc(title)}</h1><p>{esc(message)}</p><a href="/">Go to the homepage</a></section>'
    return layout(title, content)
