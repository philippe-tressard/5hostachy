import sqlite3
conn = sqlite3.connect("/app/data/app.db")
c = conn.cursor()
print("ID | Prénom | Nom | Email | Rôle | Actif")
print("-" * 100)
for r in c.execute("""
    SELECT id, prenom, nom, email, roles_json, actif
    FROM utilisateur
    WHERE roles_json NOT LIKE '%conseil_syndical%'
    ORDER BY id
"""):
    actif = "oui" if r[5] else "non"
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {actif}")
