"""Amazoff web server. Run `python server.py`, then open http://localhost:8000.

Uses only Python's standard library, so there is nothing to install.
"""

import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pages
import store

HOST = "127.0.0.1"  # only reachable from this computer
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
STATIC_DIR = (Path(__file__).parent / "static").resolve()
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


def to_int(text, default=0):
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        url = urlsplit(self.path)
        if method == "POST":
            length = to_int(self.headers.get("Content-Length"))
            fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        else:
            fields = parse_qs(url.query)
        form = {key: values[-1] for key, values in fields.items()}

        try:
            self.route(method, url.path, form)
        except (URLError, TimeoutError):
            traceback.print_exc()
            self.send_html(pages.message_page(
                "Couldn't reach the product API",
                "Amazoff gets its products from dummyjson.com. Check your internet connection and refresh."), 502)
        except Exception:
            traceback.print_exc()
            self.send_html(pages.message_page("Something broke", "Check the terminal for details."), 500)

    def route(self, method, path, form):
        if method == "GET":
            if path in ("/", "/search"):
                return self.send_html(pages.results_page(form))
            if path.startswith("/product/"):
                product = store.get_product(to_int(path.removeprefix("/product/"), -1))
                if product:
                    return self.send_html(pages.product_page(product, to_int(form.get("img"))))
            if path == "/cart":
                return self.send_html(pages.cart_page())
            if path == "/profile":
                return self.send_html(pages.profile_page())
            if path == "/offer":
                if store.offer_active:
                    return self.redirect("/checkout")
                if not store.pity_offer_ready():
                    return self.send_html(pages.message_page("No offers for you", "Not yet, anyway. Keep shopping."))
                return self.send_html(pages.offer_page())
            if path == "/checkout":
                if not store.cart:
                    return self.redirect("/cart")
                saved = store.checkout_details
                return self.send_html(pages.checkout_page(address=saved.get("address"), payment=saved.get("payment", "")))
            if path == "/checkout/review":
                if not store.cart:
                    return self.redirect("/cart")
                if not store.checkout_details:
                    return self.redirect("/checkout")
                return self.send_html(pages.review_page())
            if path.startswith("/order/"):
                order_id = path.removeprefix("/order/")
                if order_id in store.orders:
                    return self.send_html(pages.order_page(order_id, store.orders[order_id]))
            if path.startswith("/static/"):
                return self.send_static(path.removeprefix("/static/"))
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

        if method == "POST":
            if path == "/cart/add":
                store.add_to_cart(to_int(form.get("id")), to_int(form.get("qty"), 1))
                return self.redirect("/checkout" if form.get("action") == "buy" else "/cart")
            if path == "/cart/prices":
                store.set_prices({to_int(key.removeprefix("price_"), -1): to_int(value)
                                  for key, value in form.items() if key.startswith("price_")})
                return self.redirect("/cart")
            if path == "/cart/update":
                store.set_quantity(to_int(form.get("id")), to_int(form.get("qty")))
                return self.redirect("/cart")
            if path == "/checkout":
                return self.checkout(form)
            if path == "/profile/delete":
                return self.send_html(pages.profile_page(deleted=True))
            if path == "/checkout/review":
                if not store.cart:
                    return self.redirect("/cart")
                if not store.checkout_details:
                    return self.redirect("/checkout")
                if store.offer_active:
                    return self.send_html(pages.betrayal_page(store.betray()))
                return self.redirect(f"/order/{store.place_order()}")
            if path == "/offer/claim":
                if not store.pity_offer_ready():
                    return self.redirect("/offer")
                store.claim_offer()
                return self.redirect("/checkout")

        self.send_html(pages.message_page("Page found!", "Just kidding. This page doesn't exist."), 404)

    def checkout(self, form):
        if not store.cart:
            return self.redirect("/cart")
        address = {key: form.get(key, "").strip() for key in store.ADDRESS_FIELDS}
        payment = form.get("payment", "")
        error = store.address_error(address)
        if not error and payment not in store.PAYMENTS:
            error = "Please choose a payment method."
        if not error:
            error = store.captcha_error(form.get("human") == "1", form.get("robot") == "1")
        if error:
            return self.send_html(pages.checkout_page(error, address, payment), 400)
        store.checkout_details.update(address=address, payment=payment)
        self.redirect("/checkout/review")

    def send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, name):
        file = (STATIC_DIR / name).resolve()
        if file.parent != STATIC_DIR or file.suffix not in STATIC_TYPES or not file.is_file():
            return self.send_html(pages.message_page("Not found", "No such file."), 404)
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", STATIC_TYPES[file.suffix])
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Amazoff is running at http://localhost:{PORT}  (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
