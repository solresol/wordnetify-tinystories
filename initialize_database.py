#!/usr/bin/env python3

import argparse
import sqlite3

from wordnetify import create_schema


def main():
    parser = argparse.ArgumentParser(description="Initialize the database schema for the TinyStories project.")
    parser.add_argument("--database", type=str, required=True, help="The SQLite database file to initialize.")
    args = parser.parse_args()

    conn = sqlite3.connect(args.database)
    create_schema(conn)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
