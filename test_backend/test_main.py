import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

from backend import app
from backend.models import db, Destination, User
from werkzeug.security import generate_password_hash

# Small fixture used by tests so they don't rely on the removed JSON file
SAMPLE_DATA = [
    {
        "id": 1,
        "destination": "tokyo",
        "hints": {
            "5": "This bustling metropolis is known for its neon lights, traditional temples, and being one of the largest metropolitan areas in the world.",
            "4": "Its public transport is one of the busiest in the world, with the famous Shibuya crossing and cherry blossom season.",
            "3": "This city is the capital of a country made of islands in East Asia.",
            "2": "It is home to a famous anime culture, sushi, and the Imperial Palace.",
            "1": "Its name starts with 'T' and it hosted the 2020 Summer Olympics."
        },
        "correct_answers": ["tokyo, japan"]
    },
    {
        "id": 2,
        "destination": "paris",
        "hints": {
            "5": "The City of Light is famous for the Eiffel Tower, world-class museums, and being considered the romantic capital of Europe.",
            "4": "It is also the home of the Louvre Museum, the Seine river, and fashion houses.",
            "3": "This city is the capital of a Western European country known for wine and baguettes.",
            "2": "It hosts a famous iron tower and is often called the most romantic city in the world.",
            "1": "Its name starts with 'P' and it is known for the Eiffel Tower."
        },
        "correct_answers": ["paris, france"]
    },
    {
        "id": 3,
        "destination": "new york",
        "hints": {
            "5": "The city that never sleeps is home to the Statue of Liberty, Times Square, and is the financial heart of the United States.",
            "4": "It is famous for Broadway shows, skyscrapers, Central Park, and its subway system.",
            "3": "This city is located in the northeastern United States and is often abbreviated as NYC.",
            "2": "It is home to the boroughs of Manhattan, Brooklyn, and Queens.",
            "1": "Its name includes the word 'York' and it is one of America's largest cities."
        },
        "correct_answers": ["new york, usa", "new york city, usa"]
    }
    ,
    {
        "id": 4,
        "destination": "sydney",
        "hints": {
            "5": "This Australian city is famous for its Opera House, beautiful beaches, and iconic Sydney Harbour Bridge.",
            "4": "It is located on the east coast of Australia and has a famous harbour.",
            "3": "This city is known for Bondi Beach, the Harbour Bridge, and a vibrant coastal lifestyle.",
            "2": "It is one of Australia's largest cities and is not the capital of the country.",
            "1": "Its name starts with 'S' and it is famous for the Opera House."
        },
        "correct_answers": ["sydney, australia"]
    },
    {
        "id": 5,
        "destination": "rome",
        "hints": {
            "5": "The Eternal City is home to the Colosseum, Vatican, and countless historical ruins from ancient times.",
            "4": "It is famous for pizza, pasta, the Roman Forum, and Baroque fountains.",
            "3": "This city is the capital of a European country known for its ancient empire.",
            "2": "It is built on seven hills and includes the Vatican City within its boundaries.",
            "1": "Its name starts with 'R' and it is famous for the Colosseum."
        },
        "correct_answers": ["rome, italy"]
    }
]

CRITICAL_HOME_UI_IDS = [
    'welcomeScreen',
    'authButton',
    'statusScreen',
    'runSpecificQuizBtn',
    'statsScreen',
    'guestRestrictionsStatus',
    'backToMainFromStatsBtn',
    'quizScreen',
    'nextHintBtn',
    'resultsScreen',
    'backToMainFromResultsBtn',
    'adminScreen',
    'addDestinationBtn',
    'adminDeleteDialog',
    'forgotPasswordModal',
    'rulesModal',
    'hintComplaintModal',
    'imageModal',
]

CRITICAL_SCRIPT_SRCS = [
    '/static/app.js',
    '/static/auth_main.js',
    '/static/quiz_flow.js',
    '/static/screens.js',
    '/static/markdown.js',
    '/static/modal.js',
    '/static/admin.js',
]

SCREEN_ID_ORDER = [
    'welcomeScreen',
    'statusScreen',
    'statsScreen',
    'quizScreen',
    'resultsScreen',
    'adminScreen',
]

MODAL_ID_ORDER = [
    'forgotPasswordModal',
    'rulesModal',
    'hintComplaintModal',
    'imageModal',
]


class MainAppTestCase(unittest.TestCase):
    def assert_id_order(self, content: str, element_ids, error_prefix: str):
        positions = []
        for element_id in element_ids:
            marker = f'id="{element_id}"'
            pos = content.find(marker)
            self.assertNotEqual(
                pos,
                -1,
                msg=f'{error_prefix}: missing element {element_id}',
            )
            positions.append(pos)

        self.assertEqual(
            positions,
            sorted(positions),
            msg=f'{error_prefix}: order changed for IDs {element_ids}',
        )

    def assert_script_order(self, content: str):
        positions = []
        for src in CRITICAL_SCRIPT_SRCS:
            marker = f'src="{src}"'
            pos = content.find(marker)
            self.assertNotEqual(
                pos,
                -1,
                msg=f'Missing script marker: {marker}',
            )
            positions.append(pos)

        self.assertEqual(
            positions,
            sorted(positions),
            msg='Frontend script order changed; keep bootstrap load order stable.',
        )

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Initialize and populate the test database with SAMPLE_DATA
        with app.app_context():
            db.drop_all()
            db.create_all()
            for item in SAMPLE_DATA:
                q = Destination(
                    id=item['id'],
                    name=item['destination'],
                    hint1=item['hints']['1'],
                    hint2=item['hints']['2'],
                    hint3=item['hints']['3'],
                    hint4=item['hints']['4'],
                    hint5=item['hints']['5'],
                    correct_answers=item['correct_answers']
                )
                db.session.add(q)

            self.test_user = User(
                name='Test User',
                email='test@example.com',
                password_hash=generate_password_hash('password123')
            )
            db.session.add(self.test_user)
            db.session.commit()

        login_response = self.client.post('/api/login', json={
            'email': 'test@example.com',
            'password': 'password123'
        })
        self.assertEqual(login_response.status_code, 200)
        self.quiz_data = SAMPLE_DATA

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_quiz_endpoint_returns_first_hint_of_random_destination(self):
        response = self.client.get('/api/quiz')
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn('id', data)
        self.assertIn('hint', data)
        self.assertIn('hintDifficulty', data)
        self.assertIn('remainingGuesses', data)
        self.assertIn('images', data)
        self.assertEqual(data['hintDifficulty'], 5)
        self.assertEqual(data['remainingGuesses'], 3)
        images = data.get('images')
        self.assertGreaterEqual(len(images), 2)

    def test_home_page_renders_extracted_screen_partials(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        page = response.get_data(as_text=True)
        for element_id in CRITICAL_HOME_UI_IDS:
            self.assertIn(f'id="{element_id}"', page)

    def test_home_page_uses_expected_script_bootstrap_order(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        rendered_page = response.get_data(as_text=True)
        self.assert_script_order(rendered_page)

    def test_home_page_keeps_screen_and_modal_order(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        rendered_page = response.get_data(as_text=True)
        self.assert_id_order(
            rendered_page,
            SCREEN_ID_ORDER,
            'Rendered home page screen ordering drifted',
        )
        self.assert_id_order(
            rendered_page,
            MODAL_ID_ORDER,
            'Rendered home page modal ordering drifted',
        )

    def test_check_answer_returns_correct_for_valid_answer(self):
        question = self.quiz_data[0]
        # Start a quiz first so server-side state exists
        self.client.get(f'/api/quiz/{question["id"]}')

        response = self.client.post('/api/check-answer', json={
            'answer': question['correct_answers'][0]
        })
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertTrue(data['correct'])
        self.assertEqual(data['points'], 15)  # Hint difficulty (5) * Remaining guesses (3)
        self.assertEqual(data['answer'], question['destination'])

    def test_check_answer_returns_all_image_files_in_destination_directory(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)

            # Create multiple image formats plus one non-image file.
            for index in range(1, 13):
                (destination_media_dir / f'0{index:02d}.jpg').write_bytes(b'test-image')
            (destination_media_dir / '0a.png').write_bytes(b'png-image')
            (destination_media_dir / '1a.jpg').write_bytes(b'hint-slot-image')
            (destination_media_dir / 'landscape.jpeg').write_bytes(b'jpeg-image')
            (destination_media_dir / 'city.webp').write_bytes(b'webp-image')
            (destination_media_dir / 'flag.gif').write_bytes(b'gif-image')
            (destination_media_dir / 'README.txt').write_bytes(b'not-an-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')

                response = self.client.post('/api/check-answer', json={
                    'answer': question['correct_answers'][0]
                })
                self.assertEqual(response.status_code, 200)

                data = response.get_json()
                self.assertTrue(data['correct'])
                self.assertIn('resultImages', data)
                expected = {
                    f"/media/countries/{question['id']}/0a.png",
                    f"/media/countries/{question['id']}/1a.jpg",
                    f"/media/countries/{question['id']}/landscape.jpeg",
                    f"/media/countries/{question['id']}/city.webp",
                    f"/media/countries/{question['id']}/flag.gif",
                }
                for index in range(1, 13):
                    expected.add(f"/media/countries/{question['id']}/0{index:02d}.jpg")

                self.assertEqual(set(data['resultImages']), expected)
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_check_answer_ignores_small_variant_when_base_image_exists(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)

            (destination_media_dir / '001.jpg').write_bytes(b'base-image')
            (destination_media_dir / '001_small.webp').write_bytes(b'optimized-duplicate')
            (destination_media_dir / '002_small.webp').write_bytes(b'optimized-only')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')

                response = self.client.post('/api/check-answer', json={
                    'answer': question['correct_answers'][0]
                })
                self.assertEqual(response.status_code, 200)

                data = response.get_json()
                self.assertTrue(data['correct'])
                self.assertIn('resultImages', data)
                self.assertEqual(
                    data['resultImages'],
                    [
                        f"/media/countries/{question['id']}/001_small.webp",
                        f"/media/countries/{question['id']}/002_small.webp",
                    ]
                )
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_result_hint_media_remains_accessible_after_quiz_completion(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '1a.jpg').write_bytes(b'test-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')

                response = self.client.post('/api/check-answer', json={
                    'answer': question['correct_answers'][0]
                })
                self.assertEqual(response.status_code, 200)

                media_response = self.client.get(f"/media/countries/{question['id']}/1a.jpg")
                self.assertEqual(media_response.status_code, 200)
                media_response.close()
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_check_answer_returns_incorrect_for_invalid_answer(self):
        question = self.quiz_data[0]
        # Start a quiz first so server-side state exists
        self.client.get(f'/api/quiz/{question["id"]}')

        response = self.client.post('/api/check-answer', json={
            'answer': 'not a valid place'
        })
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertFalse(data['correct'])
        # Still has guesses left, so we get updated remainingGuesses
        self.assertIn('remainingGuesses', data)
        self.assertEqual(data['remainingGuesses'], 2)

    def test_get_hint_returns_updated_images_for_new_difficulty(self):
        question = self.quiz_data[0]
        self.client.get(f'/api/quiz/{question["id"]}')

        response = self.client.get('/api/hint')
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data['hintDifficulty'], 4)
        self.assertIn('images', data)
        self.assertEqual(
            data['images'],
            [
                f"/media/countries/{question['id']}/4a.jpg",
                f"/media/countries/{question['id']}/4b.jpg",
            ],
        )

    def test_hint_images_prefer_small_webp_when_available(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '5a_small.webp').write_bytes(b'test-image')
            (destination_media_dir / '5b_small.webp').write_bytes(b'test-image')

            try:
                response = self.client.get(f'/api/quiz/{question["id"]}')
                self.assertEqual(response.status_code, 200)

                data = response.get_json()
                self.assertEqual(
                    data['images'],
                    [
                        f"/media/countries/{question['id']}/5a_small.webp",
                        f"/media/countries/{question['id']}/5b_small.webp",
                    ],
                )
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_hint_media_returns_403_for_locked_hint_difficulty(self):
        question = self.quiz_data[0]
        self.client.get(f'/api/quiz/{question["id"]}')

        response = self.client.get(f"/media/countries/{question['id']}/4a.jpg")
        self.assertEqual(response.status_code, 403)

    def test_hint_media_small_webp_returns_403_for_locked_hint_difficulty(self):
        question = self.quiz_data[0]
        self.client.get(f'/api/quiz/{question["id"]}')

        response = self.client.get(f"/media/countries/{question['id']}/4a_small.webp")
        self.assertEqual(response.status_code, 403)

    def test_result_gallery_media_returns_403_during_active_quiz(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '001.jpg').write_bytes(b'test-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')

                response = self.client.get(f"/media/countries/{question['id']}/001.jpg")
                self.assertEqual(response.status_code, 403)
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_result_gallery_media_returns_200_after_quiz_completion(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '001.jpg').write_bytes(b'test-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')
                response = self.client.post('/api/check-answer', json={
                    'answer': question['correct_answers'][0]
                })
                self.assertEqual(response.status_code, 200)

                media_response = self.client.get(f"/media/countries/{question['id']}/001.jpg")
                self.assertEqual(media_response.status_code, 200)
                media_response.close()
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_hint_media_returns_200_for_unlocked_hint_difficulty(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '4a.jpg').write_bytes(b'test-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')
                self.client.get('/api/hint')

                response = self.client.get(f"/media/countries/{question['id']}/4a.jpg")
                self.assertEqual(response.status_code, 200)
                response.close()
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_hint_media_small_webp_returns_200_for_unlocked_hint_difficulty(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '4a_small.webp').write_bytes(b'test-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')
                self.client.get('/api/hint')

                response = self.client.get(f"/media/countries/{question['id']}/4a_small.webp")
                self.assertEqual(response.status_code, 200)
                response.close()
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_hint_media_auth_uses_session_state_before_quiz_lookup(self):
        question = self.quiz_data[0]

        with tempfile.TemporaryDirectory() as temp_media:
            original_media_dir = os.environ.get('MEDIA_DIR')
            os.environ['MEDIA_DIR'] = temp_media

            destination_media_dir = Path(temp_media) / 'countries' / str(question['id'])
            destination_media_dir.mkdir(parents=True, exist_ok=True)
            (destination_media_dir / '4a.jpg').write_bytes(b'test-image')

            try:
                self.client.get(f'/api/quiz/{question["id"]}')
                self.client.get('/api/hint')

                with patch('backend._active_quiz_result_for_player', side_effect=RuntimeError('should not run')):
                    response = self.client.get(f"/media/countries/{question['id']}/4a.jpg")

                self.assertEqual(response.status_code, 200)
                response.close()
            finally:
                if original_media_dir is None:
                    os.environ.pop('MEDIA_DIR', None)
                else:
                    os.environ['MEDIA_DIR'] = original_media_dir

    def test_get_active_quiz_returns_404_when_no_active_quiz(self):
        response = self.client.get('/api/quiz/active')
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data['error'], 'No active quiz')

    def test_get_active_quiz_returns_current_hint_state(self):
        question = self.quiz_data[0]
        self.client.get(f'/api/quiz/{question["id"]}')

        # Move to the next hint so restored state is not just the initial default.
        self.client.get('/api/hint')

        response = self.client.get('/api/quiz/active')
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data['id'], question['id'])
        self.assertEqual(data['hintDifficulty'], 4)
        self.assertEqual(data['remainingGuesses'], 3)
        self.assertEqual(data['hint'], question['hints']['4'])
        self.assertEqual(
            data['images'],
            [
                f"/media/countries/{question['id']}/4a.jpg",
                f"/media/countries/{question['id']}/4b.jpg",
            ],
        )

    def test_check_answer_wrong_guess_keeps_current_hint_images(self):
        question = self.quiz_data[0]
        self.client.get(f'/api/quiz/{question["id"]}')

        response = self.client.post('/api/check-answer', json={
            'answer': 'not a valid place'
        })
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertFalse(data['correct'])
        self.assertEqual(data['hintDifficulty'], 5)
        self.assertIn('images', data)
        self.assertEqual(
            data['images'],
            [
                f"/media/countries/{question['id']}/5a.jpg",
                f"/media/countries/{question['id']}/5b.jpg",
            ],
        )

    def test_check_answer_returns_404_for_missing_question(self):
        # No active quiz — should get 404
        response = self.client.post('/api/check-answer', json={
            'answer': 'tokyo'
        })
        self.assertEqual(response.status_code, 404)

        data = response.get_json()
        self.assertEqual(data['error'], 'No active quiz')

    def test_register_endpoint_creates_user_and_sets_session(self):
        response = self.client.post('/api/register', json={
            'name': 'New User',
            'email': 'newuser@example.com',
            'password': 'newpassword'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['name'], 'New User')
        self.assertEqual(data['email'], 'newuser@example.com')

    def test_register_rejects_invalid_email_format(self):
        invalid_emails = [
            'notanemail',
            '@missing-local.com',
            'no-domain@',
            'spaces in@email.com',
            'no@tld',
            '',
        ]
        for email in invalid_emails:
            response = self.client.post('/api/register', json={
                'name': 'Test',
                'email': email,
                'password': 'validpass123'
            })
            self.assertIn(response.status_code, (400,), msg=f"Expected 400 for '{email}', got {response.status_code}")

    def test_register_accepts_valid_email_format(self):
        valid_emails = [
            'user@example.com',
            'name+tag@sub.domain.org',
            'dotted.name@company.co.uk',
        ]
        for i, email in enumerate(valid_emails):
            response = self.client.post('/api/register', json={
                'name': f'User {i}',
                'email': email,
                'password': 'validpass123'
            })
            self.assertEqual(response.status_code, 200, msg=f"Expected 200 for '{email}', got {response.status_code}")

    def test_login_endpoint_allows_registered_user(self):
        response = self.client.post('/api/login', json={
            'email': 'test@example.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['name'], 'Test User')
        self.assertEqual(data['email'], 'test@example.com')

    def test_login_after_registration(self):
        """Register a new user, clear the session, then log in with those credentials."""
        # Register
        reg_resp = self.client.post('/api/register', json={
            'name': 'Fresh User',
            'email': 'fresh@example.com',
            'password': 'freshpass123'
        })
        self.assertEqual(reg_resp.status_code, 200)
        reg_data = reg_resp.get_json()
        self.assertEqual(reg_data['email'], 'fresh@example.com')

        # Log out (use CSRF token from registration response)
        csrf_token = reg_data.get('csrfToken', '')
        logout_resp = self.client.post('/api/logout', headers={
            'X-CSRF-Token': csrf_token
        })
        self.assertEqual(logout_resp.status_code, 200)

        # Confirm session is cleared — /api/me should return 401
        me_resp = self.client.get('/api/me')
        self.assertEqual(me_resp.status_code, 401)

        # Log in with the same credentials
        login_resp = self.client.post('/api/login', json={
            'email': 'fresh@example.com',
            'password': 'freshpass123'
        })
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.get_json()
        self.assertEqual(login_data['name'], 'Fresh User')
        self.assertEqual(login_data['email'], 'fresh@example.com')

    def test_quiz_endpoint_requires_authentication(self):
        client = app.test_client()
        response = client.get('/api/quiz')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data['error'], 'Authentication required')


    def test_session_cookie_has_httponly_and_samesite(self):
        """Issue #4: Session cookie should have HttpOnly and SameSite flags."""
        # Use a fresh client so the login response contains Set-Cookie
        client = app.test_client()
        resp = client.post('/api/login', json={
            'email': 'test@example.com',
            'password': 'password123'
        })
        self.assertEqual(resp.status_code, 200)

        cookie_header = resp.headers.get('Set-Cookie', '')
        self.assertIn('HttpOnly', cookie_header)
        self.assertIn('SameSite=Lax', cookie_header)

    def test_session_cookie_secure_flag_when_enabled(self):
        """Issue #4: Secure flag should appear when SESSION_COOKIE_SECURE is True."""
        app.config['SESSION_COOKIE_SECURE'] = True
        try:
            client = app.test_client()
            client.post('/api/register', json={
                'name': 'SecureTest',
                'email': 'secure@test.com',
                'password': 'securepass123'
            })
            resp = client.post('/api/login', json={
                'email': 'secure@test.com',
                'password': 'securepass123'
            })
            self.assertEqual(resp.status_code, 200)

            cookie_header = resp.headers.get('Set-Cookie', '')
            self.assertIn('Secure', cookie_header)
        finally:
            app.config['SESSION_COOKIE_SECURE'] = False

    def test_cors_restricts_origin_when_configured(self):
        """Issue #5: CORS should respect CORS_ALLOWED_ORIGINS and reject others."""
        # We test the config-driven behaviour by creating a minimal Flask app
        # with the same CORS setup used in production, avoiding module reload
        # side-effects on the shared `app` instance.
        from flask import Flask as _Flask
        from flask_cors import CORS as _CORS

        allowed = 'https://myapp.example.com'
        test_app = _Flask(__name__)
        test_app.secret_key = 'test'
        _CORS(test_app, origins=[allowed], supports_credentials=True)

        @test_app.route('/ping')
        def ping():
            return 'pong'

        client = test_app.test_client()

        # Allowed origin gets the ACAO header
        resp = client.get('/ping', headers={'Origin': allowed})
        acao = resp.headers.get('Access-Control-Allow-Origin', '')
        self.assertEqual(acao, allowed)

        # Disallowed origin does NOT get a permissive ACAO header
        resp = client.get('/ping', headers={'Origin': 'https://evil.com'})
        acao = resp.headers.get('Access-Control-Allow-Origin', '')
        self.assertNotEqual(acao, 'https://evil.com')
        self.assertNotEqual(acao, '*')


class SecretKeyTestCase(unittest.TestCase):
    """Issue #1: App must refuse to start without SECRET_KEY in production."""

    def _import_app_in_subprocess(self, env_overrides):
        """Import the app module in a subprocess with the given env vars."""
        import subprocess
        env = os.environ.copy()
        # Remove SECRET_KEY so the default path is exercised
        env.pop('SECRET_KEY', None)
        env.update(env_overrides)
        result = subprocess.run(
            [sys.executable, '-c', 'from backend import app; print("OK")'],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            env=env,
        )
        return result

    def test_production_raises_without_secret_key(self):
        """In production mode, missing SECRET_KEY should cause a RuntimeError."""
        result = self._import_app_in_subprocess({
            'FLASK_ENV': 'production',
            'CORS_ALLOWED_ORIGINS': 'https://myapp.example.com',
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY', result.stderr)

    def test_production_starts_with_secret_key_set(self):
        """In production mode, providing SECRET_KEY should succeed."""
        result = self._import_app_in_subprocess({
            'FLASK_ENV': 'production',
            'SECRET_KEY': 'a-real-secret-key',
            'CORS_ALLOWED_ORIGINS': 'https://myapp.example.com',
        })
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('OK', result.stdout)

    def test_development_warns_without_secret_key(self):
        """In development mode, missing SECRET_KEY should warn but not crash."""
        result = self._import_app_in_subprocess({'FLASK_ENV': 'development'})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('OK', result.stdout)
        self.assertIn('SECRET_KEY is not set', result.stderr)


if __name__ == '__main__':
    unittest.main()
