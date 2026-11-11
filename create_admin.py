"""Trusted local bootstrap of the first ZimiFare administrator."""
from getpass import getpass
from zimifare.core import ZimiFareError, ZimiFareStore
from zimifare.identifiers import user_ref


def main() -> None:
    store = ZimiFareStore()
    if store.has_admin():
        print("An administrator already exists. Sign in through the ZimiFare app.")
        return
    print("\nZimiFare — first-time administrator setup")
    print("Run this only on a computer you control.\n")
    name = input("Full name: ").strip()
    email = input("Email: ").strip()
    phone = input("Phone number: ").strip()
    password = getpass("Choose password (8+ characters): ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match. No administrator created.")
        return
    try:
        uid = store.bootstrap_admin(name, email, phone, password, trusted_setup=True)
        print(f"\nCreated administrator {user_ref(uid, 'ADMIN')}. Run: python -m streamlit run app.py")
    except ZimiFareError as exc:
        print(f"Setup failed: {exc}")


if __name__ == "__main__":
    main()
