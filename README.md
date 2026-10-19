# Amazoff

A parody online store that does the opposite of whatever you ask. Made for the STEAL//REMAKE hackathon.

## Run it

You need Python 3.9 or newer and an internet connection. There is nothing to install.

```
python server.py
```

Then open http://localhost:8000. To use another port, run `python server.py 8080`.

## What we remixed

Original: [amazon.com](https://www.amazon.com). Amazoff copies the familiar shopping flow, then reverses it:

- **Search** has autocomplete with every product name, but pressing Enter never searches what you picked. The search bar gets refilled with a completely different product instead ("iPhone 13 Pro" might become "Wooden Spoon"). Search that, and you get its opposite (forks) with a "Your taste needs a 180° change" note. Opposites come from our own list first, then the Datamuse API ("white" shows black items), then Open Library books if the store has nothing ("sad" shows books about being happy). Words with no opposite at all get an "ERROR 404: Opposite not found" note and random items.
- **Category dropdown** next to the search bar shows a different category from the one you pick, with a note. "Laptops" shows Sports Accessories: "Go touch some grass."
- **Sort** is backwards. "Price: Low to High" shows the most expensive first, with a witty note that changes with the star filter you picked.
- **Customer Reviews filter** goes the unexpected way. "4 stars & Up" shows only products under 3 stars (no discrimination), "3 stars & Up" shows only average 3-star products, and "2 stars & Up" or "1 star & Up" shows only 4-star and better, because you deserve the best.
- **Delivery Day filter** is backwards. "Get It Today" shows the slowest items and "Get It in 2 Years" shows the fastest. "Get It After You Marry" shows no results, because that day is never coming: ERR_FOREVER_SINGLE.
- **Reviews** have their stars flipped, so "Highly impressed!" gets 1 star.
- **Payment** is swapped for something else. Choosing UPI means paying in compliments.
- **Delivery address** is yours to type in, but a review step before buying crosses it out and reroutes the parcel to "the nearest wrong place", like the Bermuda Triangle. The review step also shows the weird payment, with "Proceed to Buy" or "Change it back".
- **Security check** only lets robots through. Tick "I am a robot" to continue.
- **Order total** is negative, because we paid you.

Add to cart, the cart and checkout work normally.

## Credits

- Product data and photos: [DummyJSON](https://dummyjson.com) (groceries left out) and [FakeStoreAPI](https://fakestoreapi.com), both free with no key.
- Books and covers: [Open Library](https://openlibrary.org/developers/api) (free, no key).
- Opposite words: [Datamuse API](https://www.datamuse.com/api/) (free, no key).
- Message font: [Permanent Marker](https://fonts.google.com/specimen/Permanent+Marker) from Google Fonts (Apache License 2.0).
- The logo, icons and code are our own. Amazoff is not affiliated with or endorsed by Amazon.

## Files

- `server.py`: the web server and page routes (Python standard library only)
- `store.py`: product data, the opposite rules, the cart and orders
- `pages.py`: builds the HTML for each page
- `templates/base.html`: header and footer shared by every page
- `static/style.css`, `static/logo.svg`: styling and logo
