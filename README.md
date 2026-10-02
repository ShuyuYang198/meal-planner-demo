[README.md](https://github.com/user-attachments/files/32938820/README.md)
# Meal Planner

### Recipe discovery, community features, and weekly meal planning

Meal Planner is a database-backed web application that connects recipe discovery with everyday meal planning. Users can explore recipes, follow and rate chefs, personalize recommendations, and turn a weekly meal plan into a consolidated grocery list.

Built as a two-person project for **Columbia University's COMS W4111: Introduction to Databases**, the application demonstrates relational data modeling, SQL-driven features, and full-stack development with Python and Flask.

**Stack:** Python · Flask · SQLAlchemy · SQL · Jinja2 · Bootstrap  
**Database:** PostgreSQL in the original course project; SQLite in this self-contained portfolio version.

> **Demo status:** This repository provides a runnable local application. A hosted public demo is not currently available. The included dataset is entirely fictional.

## What the application does

| Feature | User experience |
| --- | --- |
| Recipe discovery | Browse trending recipes and search by cuisine, region, or chef name. |
| Personalized recommendations | Filter suggestions using dietary preferences and ingredient allergy keywords. |
| Community | Follow chefs, rate them, and comment on recipes. |
| Recipe creation | Publish recipes with cuisine information, dietary tags, and ingredient quantities. |
| Meal planning | Organize recipes into dated breakfast, lunch, dinner, and snack slots; view plans as a weekly calendar. |
| Grocery lists | Combine ingredient quantities across the recipes in a meal plan. |

## Engineering highlights

- **Relational modeling:** Users, chefs, recipes, ingredients, cuisines, and meal plans are connected through primary keys, foreign keys, and relationship tables. Composite keys represent cuisine identity and prevent duplicate relationship records.
- **SQL-driven recommendations:** Recent comments and meal-plan activity contribute to recipe rankings. Preference filters use related ingredient and dietary-tag records to select eligible recipes.
- **Aggregation across relationships:** Grocery lists join meal-plan items, recipe ingredients, and ingredient records, then group quantities by ingredient and unit. Chef pages calculate average ratings and follower counts.
- **Data integrity and application rules:** The application checks overlapping meal-plan dates, validates item dates against plan boundaries, and restricts meal-plan access to the owning user. Database constraints enforce valid quantities and relationship references.
- **Reproducible local setup:** A seed script initializes the demonstration dataset once. Subsequent launches preserve changes, without requiring the original university-hosted database.

## Demo dataset

The included seed data contains **100 distinct recipes across 10 cuisines**, supported by:

- 20 fictional users, including 10 chefs
- 82 ingredients and 190 recipe comments
- 20 weekly meal plans with 280 scheduled items
- Chef follows, ratings, and dietary tags

The recipe catalog can also be browsed directly in [demo_recipes.json](MealPlanner/demo_recipes.json).

## Run locally

Requires **Python 3.12**. Run these commands from the repository root:

```bash
cd MealPlanner
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

Open **http://127.0.0.1:8111/** in your browser. On the login page, enter the username **`demo`**; no password is required for this demonstration account flow.

Try browsing recipes, following a chef, then opening **Meal Plans → My Meal Plans** to explore the calendar and grocery list.

The application creates its SQLite database at `MealPlanner/data/mealplanner.db` if one does not already exist. Stop the server with `Ctrl+C`.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`MealPlanner/server.py`](MealPlanner/server.py) | Flask routes, SQL queries, and application logic |
| [`MealPlanner/templates/`](MealPlanner/templates/) | Jinja2 page templates |
| [`MealPlanner/static/`](MealPlanner/static/) | Locally bundled frontend assets |
| [`MealPlanner/schema_sqlite.sql`](MealPlanner/schema_sqlite.sql) | Database schema used by this version |
| [`MealPlanner/local_database.py`](MealPlanner/local_database.py) | Database initialization and connection configuration |
| [`MealPlanner/seed_demo.py`](MealPlanner/seed_demo.py) | Repeatable generation of fictional demonstration data |
| [`MealPlanner/schema.sql`](MealPlanner/schema.sql) | Reconstructed PostgreSQL schema reference |

## Validation and scope

The local restoration was checked across all 100 recipe detail pages and the main application views. Checks in a separate test database covered comments, follows, ratings, recipe creation, ingredient updates, meal-plan creation/editing/deletion, grocery lists, account creation/deletion, ownership restrictions, and preservation of data across initialization.

This is an educational portfolio application. Its password-free login is intended for local demonstration; production deployment would require proper authentication and additional security hardening. The PostgreSQL reference schema has not been validated as part of this restoration. The current application does not include the separate course extension involving PostgreSQL full-text search, arrays, and composite types.

## Authors

**Shuyu Yang** and **Can Kerem Akbulut** — collaborative course project, Columbia University, COMS W4111.
