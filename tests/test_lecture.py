"""Smoke tests for the lecture page and audio streaming endpoint."""

import unittest

from fastapi.testclient import TestClient

from main import app


class LectureTests(unittest.TestCase):
    def test_page_renders(self):
        response = TestClient(app).get("/lecture")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Live Lecture Note-Taker", response.text)
        self.assertIn("createWebSocket('/lecture/ws')", response.text)

    def test_audio_chunks_acknowledged_in_order(self):
        with TestClient(app).websocket_connect("/lecture/ws") as websocket:
            websocket.send_bytes(b"first")
            self.assertEqual(websocket.receive_json(), {
                "type": "audio_received", "bytes": 5, "total_bytes": 5, "chunks": 1,
            })
            websocket.send_bytes(b"second")
            self.assertEqual(websocket.receive_json(), {
                "type": "audio_received", "bytes": 6, "total_bytes": 11, "chunks": 2,
            })

        with TestClient(app).websocket_connect("/lecture/ws") as websocket:
            websocket.send_bytes(b"new")
            self.assertEqual(websocket.receive_json()["total_bytes"], 3)


if __name__ == "__main__":
    unittest.main()
