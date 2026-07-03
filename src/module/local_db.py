import sqlite3
import pandas as pd

class LocalDB:
    def __init__(self, db_file, timeout=50):
        """Initialize the Local DB with a database file.
        
        Args:
            db_file (str): Path to the SQLite database file.
        """
        self.db_file = db_file
        self.timeout = timeout
        self.conn = None
        self.connect()

    def get_all_table_names(self):
        """Get all table names in the database."""
        if self.conn is None:
            self.connect()
        return pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", self.conn)['name'].tolist()
    
    def load_table_to_df(self, table_name):
        return self.query(f"SELECT * FROM `{table_name}`")

    def connect(self):
        """Establish connection to the database."""
        try:
            self.conn = sqlite3.connect(self.db_file, timeout=self.timeout)
        except sqlite3.Error as e:
            raise Exception(f"Failed to connect to database: {e}")
    
    def query(self, sql):
        """Execute a SQL query and return results as a pandas DataFrame.
        
        Args:
            sql (str): SQL query to execute.
        
        Returns:
            pandas.DataFrame: Query results.
        """
        if self.conn is None:
            self.connect()
        try:
            return pd.read_sql_query(sql, self.conn)
        except Exception as e:
            raise Exception(f"Query failed: {e}")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None