import sqlite3
import unittest

from pipeline import init_db, normalize, upsert_batch


class PipelineTests(unittest.TestCase):
    def test_missing_id_and_created_date_rejected(self):
        self.assertIsNone(normalize({"unique_key": "abc"}))
        self.assertIsNone(normalize({"created_date": "2026-01-01T00:00:00"}))
        self.assertIsNone(normalize({"unique_key": "abc", "created_date": "not a date"}))

    def test_upsert_and_privacy(self):
        con = sqlite3.connect(":memory:")
        init_db(con)
        initial = {"unique_key": "abc", "service_request_number": "26-1",
                   "created_date": "2026-10-01T09:00:00", "update_date": "2026-10-02T00:00:00",
                   "status": "Open", "address": "SHOULD NOT BE STORED"}
        self.assertEqual(upsert_batch(con, [initial]), (1, 0))
        newer = dict(initial, update_date="2026-10-04T00:00:00", status="Closed")
        upsert_batch(con, [newer])
        upsert_batch(con, [initial])  # old update must not overwrite new
        self.assertEqual(con.execute("SELECT COUNT(*) FROM service_requests").fetchone()[0], 1)
        self.assertEqual(con.execute("SELECT status FROM service_requests").fetchone()[0], "Closed")
        self.assertNotIn("address", [r[1] for r in con.execute("PRAGMA table_info(service_requests)")])
        con.close()


if __name__ == "__main__":
    unittest.main()
