import sqlite3
import yaml
import json
import os


def _get_or_create_category(cursor, category_name, cache):
    """Gets the category ID from cache or DB, creates it if it doesn't exist."""
    if category_name in cache:
        return cache[category_name]

    cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
    row = cursor.fetchone()
    if row:
        category_id = row[0]
        cache[category_name] = category_id
        return category_id
    else:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        category_id = cursor.lastrowid
        cache[category_name] = category_id
        return category_id


def _migrate_member(cursor, entry):
    """Migrates a '社区成员' entry."""
    print(f"Migrating member: {entry.get('id')}")
    content_json = json.dumps(entry.get("content", {}), ensure_ascii=False)

    cursor.execute(
        """
    INSERT INTO community_members (id, title, discord_id, discord_number_id, history, content_json)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            entry.get("id"),
            entry.get("title"),
            entry.get("discord_id"),
            entry.get("discord_number_id"),
            entry.get("history"),
            content_json,
        ),
    )

    nicknames = entry.get("discord_nickname", [])
    if nicknames:
        for nickname in nicknames:
            if nickname:  # Ensure nickname is not empty
                cursor.execute(
                    "INSERT INTO member_discord_nicknames (member_id, nickname) VALUES (?, ?)",
                    (entry["id"], nickname),
                )


def _migrate_general_entry(cursor, entry, category_cache):
    """Migrates a general knowledge entry."""
    print(f"Migrating entry: {entry.get('id')}")
    category_name = entry.get("metadata", {}).get("category")
    if not category_name:
        print(f"Skipping entry {entry.get('id')} due to missing category.")
        return

    category_id = _get_or_create_category(cursor, category_name, category_cache)
    content_json = json.dumps(entry.get("content", {}), ensure_ascii=False)

    cursor.execute(
        """
    INSERT INTO general_knowledge (id, title, name, content_json, category_id)
    VALUES (?, ?, ?, ?, ?)
    """,
        (
            entry.get("id"),
            entry.get("title"),
            entry.get("name"),
            content_json,
            category_id,
        ),
    )

    aliases = entry.get("aliases", [])
    if aliases:
        for alias in aliases:
            if alias:
                cursor.execute(
                    "INSERT INTO aliases (entry_id, alias) VALUES (?, ?)",
                    (entry["id"], alias),
                )

    refers_to = entry.get("refers_to", [])
    if refers_to:
        for reference in refers_to:
            if reference:
                cursor.execute(
                    "INSERT INTO knowledge_refers_to (entry_id, reference) VALUES (?, ?)",
                    (entry["id"], reference),
                )


def migrate_data():
    """
    Reads data from knowledge.yml and migrates it into the SQLite database.
    """
    yaml_path = os.path.join(
        "src", "chat", "features", "world_book", "data", "knowledge.yml"
    )
    db_path = os.path.join("data", "world_book.sqlite3")

    if not os.path.exists(yaml_path):
        print(f"Error: YAML file not found at '{yaml_path}'")
        return
    if not os.path.exists(db_path):
        print(
            f"Error: Database not found at '{db_path}'. Please run the initialization script first."
        )
        return

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear existing data to prevent duplicates on re-run
    tables_to_clear = [
        "member_discord_nicknames",
        "community_members",
        "aliases",
        "knowledge_refers_to",
        "general_knowledge",
        "categories",
    ]
    for table in tables_to_clear:
        print(f"Clearing table: {table}")
        cursor.execute(f"DELETE FROM {table}")

    category_cache = {}

    try:
        for entry in data:
            if not entry or not isinstance(entry, dict):
                continue

            category = entry.get("metadata", {}).get("category")
            if category == "社区成员":
                _migrate_member(cursor, entry)
            else:
                _migrate_general_entry(cursor, entry, category_cache)

        conn.commit()
        print("\nData migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\nAn error occurred during migration: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_data()
