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


def layout(title, content, query="", category="", swap="", focus=False):
    """focus=True puts the cursor in the search bar, so pressing Enter searches what's in it."""
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
    swap_field = f'<input type="hidden" name="swap" value="{esc(swap)}">' if swap else ""
    return BASE.substitute(title=esc(title), query=esc(query), category_menu=category_menu,
                           autofocus=" autofocus" if focus else "", swap_field=swap_field,
                           suggestions=suggestions, cart_count=store.cart_count(), content=content)


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
        "swap": query,  # marks a search for the name we swapped in, so sorting and filters keep it
        "category": category if category in store.CATEGORIES else "",
        "list": params.get("list", "") if params.get("list", "") in store.LISTS else "",
        "sort": params.get("sort", ""),
        "rating": params.get("rating", ""),
        "delivery": params.get("delivery", ""),
    }
    if query and query.lower() != params.get("swap", "").strip().lower():
        return swap_page(query, current["category"])

    banner = ""
    notes = []  # sticky notes shown above the results
    if query:
        notes.append("Your taste needs a 180° change. Don't worry, we turned it around for you. 🔄")
        shown, products = store.opposite_search(query)
        if shown:
            banner = (f'Showing results for <b class="red">{esc(shown)}</b>. Search instead for '
                      f'<a href="{esc(search_url(q=query, category=current["category"]))}">{esc(query)}</a>')
        else:
            notes.append(f'ERROR 404: Opposite of "{query}" not found. Enjoy these random things instead. 🎲')
    else:
        products = store.catalog()
    witty = store.witty_message(current["sort"], current["rating"])
    if current["category"]:
        if not witty:  # once you pick stars or a price sort, their note replaces the category's
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
    return layout(title, content, query, current["category"], current["swap"])


def swap_page(query, category):
    """First Enter: no results, just a completely different product name typed into the search bar."""
    swap = store.swap_for(query, category)
    note = f'We fixed your search: "{query}" ➜ "{swap}". Press Enter. Trust the process. 🔮'
    content = f"""
<section class="swap-page">
  <p class="witty">{esc(note)}</p>
  <p class="muted big-text">☝️ Already typed into the search bar for you. Your original search has been lovingly ignored.</p>
</section>"""
    return layout(swap, content, swap, category, swap, focus=True)


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
  <div>{p['rating']:.1f} {stars(p['rating'])} <span class="muted">({len(p['reviews'])})</span></div>
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
    reviews = "".join(review_html(r) for r in p["reviews"]) or '<p class="muted">No reviews yet. Be the last to write one.</p>'

    content = f"""
<div class="product panel">
  <div class="gallery">
    <div class="thumbs">{thumbs}</div>
    <div class="main-img"><img src="{esc(images[image_index])}" alt="{esc(p['title'])}"></div>
  </div>
  <div class="info">
    <h1>{esc(p['title'])}</h1>
    <a href="/">Avoid the Amazoff Store</a>
    <div>{p['rating']:.1f} {stars(p['rating'])} <span class="muted">{plural(len(p['reviews']), 'rating')}</span></div>
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
  <div class="small orange">Verified Non-Purchase</div>
  <div class="small muted">0 people found this helpful</div>
</div>"""


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

    items = ""
    for p, quantity in lines:
        items += f"""
<div class="cart-item">
  <a href="/product/{p['id']}"><img src="{esc(p['thumbnail'])}" alt="{esc(p['title'])}"></a>
  <div>
    <a class="cart-title" href="/product/{p['id']}">{esc(p['title'])}</a>
    <div class="green small">In stock</div>
    <div class="qty-row">
      {qty_button(p['id'], quantity - 1, '&minus;')}
      <span class="qty">{quantity}</span>
      {qty_button(p['id'], quantity + 1, '+')}
      {qty_button(p['id'], 0, 'Delete', 'link-btn')}
    </div>
  </div>
  <b>{rupees(store.price_inr(p))}</b>
</div>"""

    subtotal = f"Subtotal ({plural(store.cart_count(), 'item')}): <b>{rupees(store.cart_total(lines))}</b>"
    content = f"""
<div class="two-col">
  <section class="panel">
    <h1>Shopping Cart</h1>
    {items}
    <p class="subtotal">{subtotal}</p>
  </section>
  <aside class="panel side-box">
    <p class="subtotal-side">{subtotal}</p>
    <a class="btn btn-yellow" href="/checkout">Proceed to Buy</a>
  </aside>
</div>"""
    return layout("Cart", content)


def order_summary(total):
    return f"""
    <h3>Order Summary</h3>
    <div class="summary-row"><span>Items:</span><span>{rupees(total)}</span></div>
    <div class="summary-row"><span>Delivery:</span><span>Free (it isn't coming)</span></div>
    <hr>
    <div class="summary-row total"><span>Order Total:</span><span>{rupees(total)}</span></div>"""


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
      <h2>1. Delivery address</h2>
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
    full_address = (f"{address['name']}, {address['house']}, {address['area']}, "
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


def message_page(title, message):
    content = f'<section class="panel"><h1>{esc(title)}</h1><p>{esc(message)}</p><a href="/">Go to the homepage</a></section>'
    return layout(title, content)
