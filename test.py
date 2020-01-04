import unittest

from app import app


class TestCase(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = app.test_client()
        cls.app.testing = True

    def test_index(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_start(self):
        response = self.app.get('/start')
        self.assertEqual(response.status_code, 200)

    def test_user(self):
        response = self.app.get("/user/djunehor")
        print(response)
        self.assertEqual(response.status_code, 200)

    @classmethod
    def tearDownClass(cls):
        cls.app.get('/quit')


if __name__ == '__main__':
    unittest.main()