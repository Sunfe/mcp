import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.db import init_db
from app.search import search_documents


class SearchDocumentsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mcp-search-test-")
        self.addCleanup(temporary.cleanup)
        database = Path(temporary.name) / "knowledge.db"
        settings_patch = patch.object(settings, "db_path", str(database))
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        init_db()
        conn = sqlite3.connect(database)
        try:
            conn.execute("INSERT INTO documents (id, title, path) VALUES (1, 'manual', 'manual.txt')")
            contents = ["P5-35 servo tuning", "P5 36 unrelated", "servo elsewhere", "AND OR NOT", 'alpha "beta"']
            for chunk_id, content in enumerate(contents, start=1):
                conn.execute(
                    "INSERT INTO chunks (id, document_id, chunk_index, content) VALUES (?, 1, ?, ?)",
                    (chunk_id, chunk_id - 1, content),
                )
                conn.execute(
                    "INSERT INTO chunks_fts (content, chunk_id, document_id) VALUES (?, ?, 1)",
                    (content, chunk_id),
                )
            conn.commit()
        finally:
            conn.close()

    def test_parameter_numbers_with_punctuation(self):
        for query in ("P5-35", "P5.35", 'P5"35', '"P5-35"'):
            with self.subTest(query=query):
                self.assertEqual([row["chunk_id"] for row in search_documents(query)], [1])

    def test_multiple_keywords_match_in_any_order(self):
        self.assertEqual([row["chunk_id"] for row in search_documents("servo P5-35")], [1])
        self.assertEqual(search_documents("servo unrelated"), [])

    def test_operators_and_quotes_are_plain_text(self):
        for query in ("AND", "OR", "NOT"):
            with self.subTest(query=query):
                self.assertEqual([row["chunk_id"] for row in search_documents(query)], [4])
        self.assertEqual([row["chunk_id"] for row in search_documents('alpha"beta')], [5])
        self.assertEqual(search_documents("servo OR unrelated"), [])
        self.assertEqual(search_documents('" OR 1=1 --'), [])

    def test_empty_and_nonmatching_queries(self):
        for query in ("", " \t\n ", "(", "*", '"', "unmatchedword"):
            with self.subTest(query=query):
                self.assertEqual(search_documents(query), [])

    def test_result_limit_is_preserved(self):
        self.assertEqual(len(search_documents("servo", limit=1)), 1)
        self.assertEqual(len(search_documents("servo", limit=5)), 2)


if __name__ == "__main__":
    unittest.main()
