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

            websocket.send_json({"type": "download_audio"})
            self.assertEqual(websocket.receive_json(), {"type": "download_started", "total_bytes": 11})
            self.assertEqual(websocket.receive_bytes(), b"firstsecond")
            self.assertEqual(websocket.receive_json(), {"type": "download_complete"})
            websocket.send_json({"type": "download_audio"})
            self.assertEqual(websocket.receive_json()["total_bytes"], 11)
            self.assertEqual(websocket.receive_bytes(), b"firstsecond")
            self.assertEqual(websocket.receive_json(), {"type": "download_complete"})

        with TestClient(app).websocket_connect("/lecture/ws") as websocket:
            websocket.send_json({"type": "download_audio"})
            self.assertEqual(websocket.receive_json()["type"], "download_error")
            websocket.send_bytes(b"new")
            self.assertEqual(websocket.receive_json()["total_bytes"], 3)

    def test_large_audio_downloads_in_ordered_frames(self):
        audio = bytes(range(256)) * 300
        with TestClient(app).websocket_connect("/lecture/ws") as websocket:
            websocket.send_bytes(audio)
            self.assertEqual(websocket.receive_json()["total_bytes"], len(audio))
            websocket.send_json({"type": "download_audio"})
            self.assertEqual(websocket.receive_json()["total_bytes"], len(audio))
            self.assertEqual(websocket.receive_bytes() + websocket.receive_bytes(), audio)
            self.assertEqual(websocket.receive_json(), {"type": "download_complete"})


if __name__ == "__main__":
    unittest.main()
