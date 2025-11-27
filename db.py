import sqlite3
from typing import List, Dict


class Database:
    def __init__(self, db_file: str):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

    def create_table(self):
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def create_cart_table(self):
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER NOT NULL,
                good_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, good_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (good_id) REFERENCES main(id)
            )
        ''')
        self.conn.commit()

    def add_to_cart(self, user_id: int, good_id: int):
        self.cur.execute("SELECT quantity FROM cart WHERE user_id=? AND good_id=?", (user_id, good_id))
        row = self.cur.fetchone()

        if row:

            new_qty = row[0] + 1
            self.cur.execute("UPDATE cart SET quantity=? WHERE user_id=? AND good_id=?", (new_qty, user_id, good_id))
        else:

            self.cur.execute("INSERT INTO cart (user_id, good_id, quantity) VALUES (?, ?, 1)", (user_id, good_id))
        self.conn.commit()

    def remove_from_cart(self, user_id: int, good_id: int):
        # 1. Узнаем текущее количество
        self.cur.execute("SELECT quantity FROM cart WHERE user_id=? AND good_id=?", (user_id, good_id))
        row = self.cur.fetchone()

        if row:
            current_qty = row[0]
            if current_qty > 1:
                self.cur.execute("UPDATE cart SET quantity=? WHERE user_id=? AND good_id=?",
                                 (current_qty - 1, user_id, good_id))
            else:
                self.cur.execute("DELETE FROM cart WHERE user_id=? AND good_id=?", (user_id, good_id))
        self.conn.commit()

    def clear_cart(self, user_id: int):

        self.cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_cart(self, user_id: int):

        query = '''
            SELECT main.id, main.name, main.price, main.photo, main.info, cart.quantity 
            FROM cart 
            JOIN main ON cart.good_id = main.id 
            WHERE cart.user_id = ?
        '''
        self.cur.execute(query, (user_id,))
        rows = self.cur.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "price": row[2],
                "photo": row[3],
                "info": row[4],
                "quantity": row[5],
                "total_price": row[2] * row[5]
            }
            for row in rows
        ]

    def get_user_by_email(self, email: str) -> List[Dict]:
        self.cur.execute("SELECT * FROM users WHERE email=?", (email,))
        row = self.cur.fetchone()
        return dict(row)

    def insert_user(self, name: str, surname: str, email: str, password: str) -> bool:
        try:
            self.cur.execute(
                "INSERT INTO users (name, surname, email, password) VALUES (?, ?, ?, ?)"
                , (name, surname, email, password))
            self.conn. commit()
            return True
        except sqlite3.IntegrityError:
            return False


    def get_goods(self) -> List[Dict]:
        self.cur.execute("SELECT * FROM main")
        rows = self.cur.fetchall()
        return [dict(row) for row in rows]

    def get_goods_by_category(self, cat:str) -> List[Dict]:
        self.cur.execute("SELECT * FROM main WHERE category= ?", (cat,))
        rows = self.cur.fetchall()
        return [dict(row) for row in rows]

    def get_good(self, id:int) -> Dict:
        self.cur.execute("SELECT * FROM main WHERE id= ?", (id,))
        rows = self.cur.fetchone()
        return dict(rows)

    def get_goods_by_category_paginated(self, cat: str, limit: int, offset: int):
        self.cur.execute("SELECT * FROM main WHERE category = ? LIMIT ? OFFSET ?", (cat, limit, offset))
        rows = self.cur.fetchall()
        return [dict(row) for row in rows]

    def count_goods_in_category(self, cat: str) -> int:
        self.cur.execute("SELECT COUNT(*) as count FROM main WHERE category = ?", (cat,))
        return self.cur.fetchone()["count"]

    def close(self):
        self.cur.close()
        self.conn.close()
