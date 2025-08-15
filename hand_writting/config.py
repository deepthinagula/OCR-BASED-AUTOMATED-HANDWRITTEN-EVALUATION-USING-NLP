import os

class Config:
    SECRET_KEY = os.urandom(24)
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = ''  # Default XAMPP MySQL password
    MYSQL_DB = 'flask_db'  # Name of your database in XAMPP
