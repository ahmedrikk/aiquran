
from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_db_session, get_or_create_user
from auth import create_access_token

init_db()
db = next(get_db_session())

# Create user
user = get_or_create_user(
    db,
    google_id="test_google_id",
    email="test@example.com",
    name="Test User",
    picture="https://lh3.googleusercontent.com/a/ACg8ocIqC6jK3C8=s96-c"
)

# Generate token
token = create_access_token(user.id)
print(f"TOKEN:{token}")

# Create a sample chat and message to test bookmarks logic immediately?
# No, let's let the browser do it.
