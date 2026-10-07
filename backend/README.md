# Import ingredients from CSV

Start the Meal Tracker backend, then run the importer from the `backend` folder:

```powershell
.\.venv\Scripts\python.exe .\import_ingredients.py .\ingredients.csv
```

The CSV must have one ingredient per row and these headers:

```csv
name,kilojoules_per_100g,protein_per_100g,carbohydrates_per_100g,sugar_per_100g,fat_per_100g
Rolled oats,1620,13.2,68.7,1.0,6.5
Milk,268,3.4,4.8,4.8,1.5
```

Use numeric values for nutrition per 100 g. Leave a nutrient cell empty if it is
unknown. Names already in the ingredient list are skipped; invalid rows are
reported while the importer continues with later rows. The final summary reports
the imported, skipped, and failed row counts, and the script exits unsuccessfully
if any rows failed.

If the API is not at its default address, pass its base URL:

```powershell
.\.venv\Scripts\python.exe .\import_ingredients.py .\ingredients.csv --api-url http://localhost:8000/api
```

# Search USDA FoodData Central

Set your USDA API key on the backend process before starting the app. The key is
read from `USDA_API_KEY` and is only sent from the backend to USDA; it is never
sent to the browser.

```powershell
$env:USDA_API_KEY = "your-data.gov-api-key"
.\.venv\Scripts\uvicorn.exe main:app --app-dir . --reload
```

Open **Ingredients → New ingredient → Search USDA**, enter a food name, then
choose **Add** on a result. The app imports its available energy and macro values
as per-100-g ingredient values. USDA FoodData Central is the source of the
imported data; its data is public domain (CC0). See the
[USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/).

# Cloudflare Access identity

Protect the app's hostname with a Cloudflare Access self-hosted application and
an Access policy that allows the email addresses permitted to use the app. Copy
the application's **AUD tag** from its overview, then configure these variables
on the backend process (for example, in the Raspberry Pi service environment):

```text
CLOUDFLARE_ACCESS_TEAM_DOMAIN=https://<team-name>.cloudflareaccess.com
CLOUDFLARE_ACCESS_AUD=<application-aud-tag>
```

The backend verifies the `CF-Access-Jwt-Assertion` signature against Cloudflare
Access's published keys and checks its issuer, audience, and expiry. Keep the
backend reachable only through the Cloudflare Tunnel; do not trust a plain
email header or expose the API directly to the internet. API requests without
a valid Access token are rejected. A verified user's first API request creates
a local user record keyed by the token subject; the stored email is refreshed
from the verified token if it changes. The authenticated identity is available
from `GET /api/auth/me`.

# Personal and shared libraries

Foods and ingredients belong to the user who created them. By default, library
items are private and only the user's own items are shown. In **Profile →
Library sharing**, users can independently choose to share their foods and
ingredients, and whether to show foods and ingredients shared by others. Public
foods include their recipe ingredient details. Only an item's owner can edit or
delete it.

On startup, existing meals, foods, and ingredients are assigned to the oldest
registered user. If there are no registered users yet, the first user to sign
in claims the existing data. The SQLite startup migration removes the old
global food and ingredient name uniqueness constraints, so different users can
create items with the same name.

Daily nutrition goals and accent colour are also stored per user. Existing
shared profile goals and theme are assigned to the oldest registered user (or
claimed by the first user to sign in if no account exists during migration).