
from getpass import getpass
from app import app
from models import db, User

with app.app_context():
    username = app.config["ADMIN_USERNAME"]
    admin = User.query.filter_by(username=username).first()

    if admin is None:
        print("Admin account not found:", username)
    else:
        password = getpass("Enter your new password: ")
        confirm = getpass("Confirm your new password: ")

        if len(password) < 8:
            print("Password must be at least 8 characters.")
        elif password != confirm:
            print("Passwords do not match.")
        else:
            admin.set_password(password)
            db.session.commit()
            print("Password reset successfully!")
            print("Username:", username)
