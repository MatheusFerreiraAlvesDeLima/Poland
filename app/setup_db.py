import sqlite3

# Caminho completo do arquivo .db
db_path = r"C:\Users\Matheus\OneDrive\Área de Trabalho\Projetos_Estudo\Polonia\projects.db"

# Conecta ou cria o banco de dados
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Cria a tabela income
cursor.execute("""
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    amount REAL,
    currency TEXT,
    date DATE
)
""")

# Cria a tabela expenses
cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    amount REAL,
    currency TEXT,
    date DATE
)
""")

# Salva e fecha
conn.commit()
conn.close()

print("✅ Banco de dados criado com sucesso!")
