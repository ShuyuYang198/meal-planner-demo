-- Reconstructed from the project proposal and final Flask queries.
CREATE TABLE IF NOT EXISTS "user" (
 user_id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100) UNIQUE NOT NULL,
 email VARCHAR(255) UNIQUE NOT NULL, diet_preference VARCHAR(50));
CREATE TABLE IF NOT EXISTS chef (
 user_id INTEGER PRIMARY KEY REFERENCES "user" ON DELETE CASCADE,
 followers INTEGER DEFAULT 0, rating NUMERIC(3,2), cuisine_type VARCHAR(80));
CREATE TABLE IF NOT EXISTS cuisine (name VARCHAR(80), region VARCHAR(80), PRIMARY KEY(name,region));
CREATE TABLE IF NOT EXISTS recipe (
 recipe_id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR(200) NOT NULL,
 total_minutes INTEGER CHECK(total_minutes>=0), servings INTEGER CHECK(servings>0),
 author_id INTEGER NOT NULL REFERENCES chef ON DELETE CASCADE,
 cuisine_name VARCHAR(80) NOT NULL, cuisine_region VARCHAR(80) NOT NULL,
 FOREIGN KEY(cuisine_name,cuisine_region) REFERENCES cuisine(name,region));
CREATE TABLE IF NOT EXISTS ingredient (
 ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(120) UNIQUE NOT NULL,
 type VARCHAR(60), flavor VARCHAR(10), color VARCHAR(30));
CREATE TABLE IF NOT EXISTS recipe_ingredient (
 recipe_id INTEGER REFERENCES recipe ON DELETE CASCADE,
 ingredient_id INTEGER REFERENCES ingredient, quantity NUMERIC(8,2) CHECK(quantity>0),
 unit VARCHAR(20), PRIMARY KEY(recipe_id,ingredient_id));
CREATE TABLE IF NOT EXISTS recipe_diet (
 recipe_id INTEGER REFERENCES recipe ON DELETE CASCADE, diet VARCHAR(30) NOT NULL,
 PRIMARY KEY(recipe_id,diet));
CREATE TABLE IF NOT EXISTS user_pref (
 user_id INTEGER PRIMARY KEY REFERENCES "user" ON DELETE CASCADE, diet TEXT, allergies TEXT);
CREATE TABLE IF NOT EXISTS recipe_comment (
 comment_id INTEGER PRIMARY KEY AUTOINCREMENT, recipe_id INTEGER NOT NULL REFERENCES recipe ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES "user" ON DELETE CASCADE, body TEXT NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS user_follows_chef (
 user_id INTEGER REFERENCES "user" ON DELETE CASCADE,
 chef_id INTEGER REFERENCES chef(user_id) ON DELETE CASCADE, PRIMARY KEY(user_id,chef_id));
CREATE TABLE IF NOT EXISTS chef_rating (
 user_id INTEGER REFERENCES "user" ON DELETE CASCADE, chef_id INTEGER REFERENCES chef(user_id) ON DELETE CASCADE,
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), rated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,chef_id));
CREATE TABLE IF NOT EXISTS mealplan (
 mealplan_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES "user" ON DELETE CASCADE,
 start_date DATE NOT NULL, end_date DATE NOT NULL, title VARCHAR(120), CHECK(end_date>=start_date));
CREATE TABLE IF NOT EXISTS mealplan_item (
 mealplanitem_id INTEGER PRIMARY KEY AUTOINCREMENT, mealplan_id INTEGER NOT NULL REFERENCES mealplan ON DELETE CASCADE,
 recipe_id INTEGER NOT NULL REFERENCES recipe ON DELETE CASCADE, meal_date DATE NOT NULL,
 meal_type VARCHAR(20) NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack')),
 servings INTEGER NOT NULL CHECK(servings>0), UNIQUE(mealplan_id,meal_date,meal_type,recipe_id));
CREATE TABLE IF NOT EXISTS demo_seed_version (version INTEGER PRIMARY KEY, installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
