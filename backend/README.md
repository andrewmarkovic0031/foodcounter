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