"""100 fictional recipes and related records. Idempotent; never resets user changes."""
from datetime import date, timedelta, datetime
from pathlib import Path
from sqlalchemy import text
import json

# Each entry is a distinct dish and its actual demo ingredient list.
CATALOG = [
('Chinese','Sichuan', '''Mapo Tofu|Tofu,Chili,Garlic,Soy sauce
Tomato Egg Stir Fry|Tomato,Egg,Scallion
Ginger Chicken Rice|Chicken,Rice,Ginger,Scallion
Garlic Bok Choy|Bok choy,Garlic,Sesame oil
Mushroom Fried Rice|Mushroom,Rice,Carrot,Soy sauce
Sesame Cucumber Salad|Cucumber,Sesame oil,Garlic
Sweet Corn Soup|Corn,Egg,Scallion
Steamed Ginger Fish|White fish,Ginger,Scallion,Soy sauce
Chili Eggplant|Eggplant,Chili,Garlic,Soy sauce
Beef Pepper Stir Fry|Beef,Bell pepper,Garlic,Soy sauce'''),
('Italian','Tuscany', '''Tomato Basil Pasta|Pasta,Tomato,Basil,Olive oil
Mushroom Risotto|Rice,Mushroom,Parmesan,Butter
Lemon Chicken|Chicken,Lemon,Garlic,Olive oil
Caprese Salad|Tomato,Mozzarella,Basil,Olive oil
White Bean Soup|White beans,Carrot,Onion,Tomato
Spinach Gnocchi|Gnocchi,Spinach,Parmesan,Butter
Roasted Vegetable Polenta|Polenta,Zucchini,Bell pepper,Olive oil
Garlic Shrimp Linguine|Pasta,Shrimp,Garlic,Lemon
Eggplant Parmesan|Eggplant,Parmesan,Tomato,Mozzarella
Tuscan Chickpea Stew|Chickpeas,Spinach,Tomato,Onion'''),
('Japanese','Kanto', '''Salmon Rice Bowl|Salmon,Rice,Cucumber,Soy sauce
Tofu Miso Soup|Tofu,Miso,Seaweed,Scallion
Chicken Udon|Chicken,Udon,Mushroom,Soy sauce
Vegetable Sushi Bowl|Rice,Avocado,Cucumber,Seaweed
Ginger Pork|Pork,Ginger,Onion,Soy sauce
Sesame Spinach|Spinach,Sesame oil,Soy sauce
Mushroom Soba|Soba,Mushroom,Scallion,Soy sauce
Egg Rice Bowl|Egg,Rice,Onion,Soy sauce
Cabbage Pancake|Cabbage,Flour,Egg,Scallion
Edamame Rice|Edamame,Rice,Sesame oil'''),
('Indian','Punjab', '''Chickpea Curry|Chickpeas,Tomato,Onion,Cumin
Red Lentil Dal|Red lentils,Tomato,Turmeric,Cumin
Spinach Paneer|Spinach,Paneer,Onion,Cumin
Vegetable Biryani|Rice,Carrot,Peas,Cumin
Coconut Chicken Curry|Chicken,Coconut milk,Tomato,Turmeric
Potato Cauliflower Curry|Potato,Cauliflower,Turmeric,Cumin
Cucumber Raita|Cucumber,Yogurt,Cumin
Lentil Rice Khichdi|Red lentils,Rice,Turmeric
Masala Omelette|Egg,Onion,Tomato,Chili
Pea Paneer Curry|Peas,Paneer,Tomato,Cumin'''),
('Mexican','Oaxaca', '''Black Bean Tacos|Black beans,Corn tortilla,Tomato,Avocado
Chicken Fajita Bowl|Chicken,Rice,Bell pepper,Onion
Corn Avocado Salad|Corn,Avocado,Lime,Tomato
Sweet Potato Tacos|Sweet potato,Corn tortilla,Black beans,Lime
Tomato Rice|Rice,Tomato,Onion,Cumin
Lime Shrimp Bowl|Shrimp,Rice,Lime,Avocado
Bean Quesadilla|Black beans,Flour tortilla,Cheddar
Vegetable Tortilla Soup|Corn tortilla,Tomato,Corn,Onion
Breakfast Egg Tacos|Egg,Corn tortilla,Tomato,Cheddar
Cumin Lentil Bowl|Red lentils,Rice,Cumin,Avocado'''),
('Turkish','Aegean', '''Menemen|Egg,Tomato,Bell pepper,Olive oil
Red Lentil Soup|Red lentils,Carrot,Onion,Cumin
Bulgur Pilaf|Bulgur,Tomato,Onion,Olive oil
Chickpea Spinach Stew|Chickpeas,Spinach,Tomato,Garlic
Yogurt Cucumber Bowl|Yogurt,Cucumber,Garlic
Stuffed Bell Peppers|Bell pepper,Rice,Tomato,Onion
Lemon Herb Chicken|Chicken,Lemon,Parsley,Olive oil
White Bean Stew|White beans,Tomato,Onion
Eggplant Tomato Bake|Eggplant,Tomato,Garlic,Olive oil
Parsley Bulgur Salad|Bulgur,Parsley,Tomato,Lemon'''),
('Thai','Central', '''Coconut Tofu Curry|Tofu,Coconut milk,Bell pepper,Chili
Basil Chicken|Chicken,Basil,Garlic,Chili
Pineapple Fried Rice|Pineapple,Rice,Carrot,Peas
Lime Cucumber Salad|Cucumber,Lime,Chili
Coconut Mushroom Soup|Mushroom,Coconut milk,Ginger,Lime
Peanut Rice Noodles|Rice noodles,Peanut,Carrot,Soy sauce
Garlic Shrimp Rice|Shrimp,Rice,Garlic,Lime
Sweet Potato Coconut Soup|Sweet potato,Coconut milk,Ginger
Chili Basil Eggplant|Eggplant,Basil,Chili,Garlic
Mango Coconut Rice|Mango,Rice,Coconut milk'''),
('Greek','Crete', '''Greek Village Salad|Tomato,Cucumber,Feta,Olive oil
Lemon Chickpea Soup|Chickpeas,Lemon,Carrot,Onion
Spinach Feta Rice|Spinach,Feta,Rice,Lemon
Oregano Chicken|Chicken,Oregano,Lemon,Olive oil
White Bean Tomato Bake|White beans,Tomato,Onion,Olive oil
Roasted Lemon Potatoes|Potato,Lemon,Oregano,Olive oil
Yogurt Herb Dip|Yogurt,Cucumber,Parsley,Garlic
Zucchini Feta Fritters|Zucchini,Feta,Egg,Flour
Mediterranean Fish|White fish,Tomato,Lemon,Olive oil
Lentil Cucumber Salad|Red lentils,Cucumber,Tomato,Parsley'''),
('Korean','Seoul', '''Tofu Bibimbap|Tofu,Rice,Carrot,Spinach,Sesame oil
Scallion Pancakes|Scallion,Flour,Egg,Soy sauce
Sesame Beef Bowl|Beef,Rice,Sesame oil,Soy sauce
Spicy Cucumber Banchan|Cucumber,Chili,Garlic
Mushroom Glass Noodles|Glass noodles,Mushroom,Carrot,Spinach
Garlic Spinach Banchan|Spinach,Garlic,Sesame oil
Gochujang Chicken|Chicken,Gochujang,Garlic,Rice
Potato Soy Braise|Potato,Soy sauce,Garlic
Seaweed Tofu Soup|Seaweed,Tofu,Garlic,Sesame oil
Egg Vegetable Rice|Egg,Rice,Carrot,Scallion'''),
('American','California', '''Avocado Egg Toast|Bread,Avocado,Egg,Lemon
Berry Oatmeal|Oats,Blueberry,Milk
Roasted Squash Bowl|Squash,Quinoa,Spinach,Olive oil
Turkey Bean Chili|Turkey,Black beans,Tomato,Cumin
Apple Walnut Salad|Apple,Walnut,Spinach,Lemon
Lemon Salmon Quinoa|Salmon,Quinoa,Lemon,Olive oil
Peanut Banana Oats|Oats,Peanut,Banana,Milk
Broccoli Cheddar Soup|Broccoli,Cheddar,Milk,Onion
Maple Sweet Potato Bowl|Sweet potato,Quinoa,Maple syrup,Walnut
Grilled Vegetable Sandwich|Bread,Zucchini,Bell pepper,Mozzarella'''),
]
MEAT={'Chicken','Beef','Pork','Turkey'}; FISH={'Salmon','White fish','Shrimp'}
DAIRY={'Parmesan','Butter','Mozzarella','Paneer','Yogurt','Cheddar','Feta','Milk'}
GLUTEN={'Pasta','Gnocchi','Udon','Soba','Flour','Flour tortilla','Bulgur','Bread','Soy sauce','Gochujang'}

def seed(conn):
 if conn.execute(text('SELECT 1 FROM demo_seed_version WHERE version=1')).first(): return
 def run(sql,**p): return conn.execute(text(sql),p)
 names=['demo','Alex','Maya','Leo','Nora','Sam','Iris','Owen','Zoe','Kai','Emma','Ben','Lily','Noah','Ava','Max','Ruby','Theo','Ella','Finn']
 users=[run('INSERT INTO "user"(name,email) VALUES(:n,:e) RETURNING user_id',n=n,e=n.lower()+'@example.test').scalar_one() for n in names]
 for i,uid in enumerate(users[:10]):
  run('INSERT INTO chef(user_id,cuisine_type) VALUES(:u,:c)',u=uid,c=CATALOG[i][0])
 for uid in users:
  run('INSERT INTO user_pref(user_id,diet,allergies) VALUES(:u,NULL,NULL)',u=uid)
 ingredients={}; recipes=[]; export=[]
 for ci,(cuisine,region,lines) in enumerate(CATALOG):
  run('INSERT INTO cuisine VALUES(:n,:r)',n=cuisine,r=region)
  for j,line in enumerate(lines.splitlines()):
   title,raw=line.split('|'); ing=raw.split(','); minutes=15+5*((ci+j)%10); servings=2+j%3
   rid=run('INSERT INTO recipe(title,total_minutes,servings,author_id,cuisine_name,cuisine_region) VALUES(:t,:m,:s,:a,:c,:r) RETURNING recipe_id',t=title,m=minutes,s=servings,a=users[ci],c=cuisine,r=region).scalar_one(); recipes.append(rid)
   for name in ing:
    if name not in ingredients:
     typ='meat' if name in MEAT else 'seafood' if name in FISH else 'dairy' if name in DAIRY else 'plant-based' if name!='Egg' else 'egg'
     ingredients[name]=run('INSERT INTO ingredient(name,type,flavor) VALUES(:n,:t,:f) RETURNING ingredient_id',n=name,t=typ,f='').scalar_one()
    qty,unit=(1,'tbsp') if name in {'Olive oil','Sesame oil','Soy sauce','Cumin','Turmeric','Chili','Oregano','Maple syrup','Gochujang'} else (100,'g')
    run('INSERT INTO recipe_ingredient VALUES(:r,:i,:q,:u)',r=rid,i=ingredients[name],q=qty,u=unit)
   tags=[]; st=set(ing)
   if not st&(MEAT|FISH):
    tags.append('vegetarian')
    if not st&(DAIRY|{'Egg'}): tags.append('vegan')
   if not st&MEAT: tags.append('pescatarian')
   if not st&GLUTEN: tags.append('gluten-free')
   for tag in tags: run('INSERT INTO recipe_diet VALUES(:r,:d)',r=rid,d=tag)
   export.append(dict(recipe_id=rid,title=title,cuisine=cuisine,region=region,minutes=minutes,servings=servings,ingredients=ing,diets=tags))
   for k in range(1+j%3):
    run('INSERT INTO recipe_comment(recipe_id,user_id,body,created_at) VALUES(:r,:u,:b,:d)',r=rid,u=users[(ci+j+k+1)%20],b=['Easy to prepare for a weeknight.','Added this to my weekly meal plan.','The ingredient combination worked well.'][k],d=datetime.now()-timedelta(days=(ci+j+k)%20))
 for i,uid in enumerate(users):
  for offset in (1,3,5):
   cid=users[(i+offset)%10]
   if cid==uid: continue
   run('INSERT INTO user_follows_chef VALUES(:u,:c)',u=uid,c=cid)
   run('INSERT INTO chef_rating(user_id,chef_id,rating) VALUES(:u,:c,:r)',u=uid,c=cid,r=3+(i+offset)%3)
 monday=date.today()-timedelta(days=date.today().weekday())
 for i,uid in enumerate(users):
  pid=run('INSERT INTO mealplan(user_id,start_date,end_date,title) VALUES(:u,:s,:e,:t) RETURNING mealplan_id',u=uid,s=monday,e=monday+timedelta(days=6),t=names[i]+"'s Weekly Plan").scalar_one()
  for day in range(7):
   for meal,offset in [('lunch',0),('dinner',1)]:
    run('INSERT INTO mealplan_item(mealplan_id,recipe_id,meal_date,meal_type,servings) VALUES(:p,:r,:d,:m,1)',p=pid,r=recipes[(i*5+day*2+offset)%100],d=monday+timedelta(days=day),m=meal)
 run('INSERT INTO demo_seed_version(version) VALUES(1)')
 Path(__file__).with_name('demo_recipes.json').write_text(json.dumps(export,indent=2))
