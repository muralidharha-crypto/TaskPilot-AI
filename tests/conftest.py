import os
import tempfile

import pytest

from app import create_app
from app.config import Config
from app.models.database import Database


@pytest.fixture
def test_app():
    # Setup temporary db
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    class TestConfig(Config):
        TESTING = True
        DB_PATH = db_path
        DEBUG = False

    app = create_app(TestConfig)
    
    with app.app_context():
        Database.init_db(db_path)
        yield app

    # Cleanup
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass

@pytest.fixture
def client(test_app):
    return test_app.test_client()
