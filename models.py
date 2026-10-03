"""ByteBites core classes.

Customer/FoodItem/ItemCollection/Transaction follow bytebites_spec.md.
Customer also carries an account system (username/password, recovery
questions) layered on top at the user's request, using the teaching cipher
in encrypt.py to obscure values on disk. See the project plan for the
security caveats that come with that choice (not real cryptography, and
file permissions are only a best-effort lock, not a hard guarantee).
"""

import os
from dataclasses import dataclass, field
from decimal import Decimal

import payment
from encrypt import decrypt_text, encrypt_text

ACCOUNTS_FILE = "accounts.dat"
RECOVERY_QUESTIONS = (
    "mothers_maiden_name",
    "first_pet",
    "childhood_best_friend",
    "favorite_teacher",
)

USERNAME_LENGTH = 9
PASSWORD_LENGTH = 16
PASSWORD_ALLOWED_SPECIALS = ",.@*"


def validate_username(username: str) -> list[str]:
    errors = []
    if len(username) != USERNAME_LENGTH:
        errors.append(
            f"username must be exactly {USERNAME_LENGTH} characters long")
    if not all(ch.isalnum() or ch == "_" for ch in username):
        errors.append(
            "username may only contain letters, numbers, and underscores")
    return errors


def validate_password(password: str, username: str) -> list[str]:
    errors = []
    if len(password) < PASSWORD_LENGTH:
        errors.append(
            f"password must be at least {PASSWORD_LENGTH} characters long")
    if username and username in password:
        errors.append("password must not contain the username")
    if not any(ch.isupper() for ch in password):
        errors.append("password must contain at least one uppercase letter")
    if not any(ch.islower() for ch in password):
        errors.append("password must contain at least one lowercase letter")
    if not any(ch in PASSWORD_ALLOWED_SPECIALS for ch in password):
        errors.append(
            "password must contain at least one special character from: "
            f"{list(PASSWORD_ALLOWED_SPECIALS)}"
        )
    disallowed = sorted({
        ch for ch in password if not (ch.isalpha() or ch.isdigit() or ch in PASSWORD_ALLOWED_SPECIALS)
    })
    if disallowed:
        errors.append(
            f"password contains disallowed character(s) {disallowed}; only letters, digits, "
            f"and {list(PASSWORD_ALLOWED_SPECIALS)} are acceptable"
        )
    return errors


@dataclass
class FoodItem:
    name: str
    category: str
    price: Decimal
    popularity_rating: float


@dataclass
class ItemCollection:
    items: list[FoodItem]

    def filter_by_category(self, category: str) -> list[FoodItem]:
        return [item for item in self.items if item.category == category]


@dataclass
class Transaction:
    items: list[FoodItem]

    def calculate_total(self) -> Decimal:
        total = sum((item.price for item in self.items), Decimal("0"))
        print("Receipt:")
        for item in self.items:
            print(f"  {item.name:<30} {item.price}")
        print(f"Total: {total}")
        return total

    def verify_payment(self, card_number: str, exp_month: int, exp_year: int, cvv: str) -> bool:
        errors = payment.validate_payment_input(
            card_number, exp_month, exp_year, cvv)
        if errors:
            raise ValueError("; ".join(errors))
        return True


def _lock_down(path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _read_accounts(path) -> dict:
    if not os.path.exists(path):
        return {}
    accounts = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != 3 + len(RECOVERY_QUESTIONS):
                continue
            username, name, enc_password, *enc_answers = parts
            accounts[username] = {
                "name": name,
                "password": enc_password,
                "answers": dict(zip(RECOVERY_QUESTIONS, enc_answers)),
            }
    return accounts


def _write_accounts(path, accounts: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for username, rec in accounts.items():
            answer_fields = "|".join(rec["answers"][q]
                                     for q in RECOVERY_QUESTIONS)
            f.write(
                f"{username}|{rec['name']}|{rec['password']}|{answer_fields}\n")
    _lock_down(path)


@dataclass
class Customer:
    name: str
    username: str = ""
    purchase_history: list[Transaction] = field(default_factory=list)

    @classmethod
    def create_account(
        cls,
        name: str,
        username: str,
        password: str,
        security_answers: dict[str, str],
        path=ACCOUNTS_FILE,
    ) -> "Customer":
        errors = validate_username(username) + \
            validate_password(password, username)
        missing = [q for q in RECOVERY_QUESTIONS if q not in security_answers]
        if missing:
            errors.append(f"missing recovery answers: {missing}")
        if errors:
            raise ValueError("; ".join(errors))

        accounts = _read_accounts(path)
        accounts[username] = {
            "name": name,
            "password": encrypt_text(password),
            "answers": {q: encrypt_text(security_answers[q]) for q in RECOVERY_QUESTIONS},
        }
        _write_accounts(path, accounts)
        return cls(name=name, username=username)

    @classmethod
    def login(cls, username: str, password: str, path=ACCOUNTS_FILE) -> "Customer | None":
        record = _read_accounts(path).get(username)
        if record is None:
            return None
        if decrypt_text(record["password"]) != password:
            return None
        return cls(name=record["name"], username=username)

    @staticmethod
    def change_password(
        username: str, question: str, answer: str, new_password: str, path=ACCOUNTS_FILE
    ) -> bool:
        accounts = _read_accounts(path)
        record = accounts.get(username)
        if record is None or question not in RECOVERY_QUESTIONS:
            return False

        stored_answer = decrypt_text(record["answers"][question])
        if stored_answer.strip().lower() != answer.strip().lower():
            return False

        password_errors = validate_password(new_password, username)
        if password_errors:
            raise ValueError("; ".join(password_errors))

        record["password"] = encrypt_text(new_password)
        _write_accounts(path, accounts)
        return True

    @staticmethod
    def change_username(old_username: str, new_username: str, path=ACCOUNTS_FILE) -> bool:
        username_errors = validate_username(new_username)
        if username_errors:
            raise ValueError("; ".join(username_errors))

        accounts = _read_accounts(path)
        if old_username not in accounts or new_username in accounts:
            return False

        accounts[new_username] = accounts.pop(old_username)
        _write_accounts(path, accounts)
        return True
