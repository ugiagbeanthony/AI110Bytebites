from datetime import date
from decimal import Decimal

import pytest

import encrypt
import models
import payment

VALID_USERNAME = "ada_love1"
VALID_PASSWORD = "Correct9Horses.1"


# --- FoodItem / ItemCollection / Customer (core spec) ---


def test_food_item_fields():
    item = models.FoodItem("Spicy Burger", "Burgers", Decimal("8.99"), 4.5)
    assert item.name == "Spicy Burger"
    assert item.category == "Burgers"
    assert item.price == Decimal("8.99")
    assert item.popularity_rating == 4.5


def test_filter_by_category_does_not_mutate_collection():
    burger = models.FoodItem("Spicy Burger", "Burgers", Decimal("8.99"), 4.5)
    soda = models.FoodItem("Large Soda", "Drinks", Decimal("2.50"), 4.0)
    collection = models.ItemCollection(items=[burger, soda])

    drinks = collection.filter_by_category("Drinks")

    assert drinks == [soda]
    assert collection.items == [burger, soda]


def test_customer_defaults_to_empty_purchase_history():
    assert models.Customer(name="Ada").purchase_history == []


def test_customer_with_purchase_history():
    transaction = models.Transaction(items=[])
    customer = models.Customer(name="Ada", purchase_history=[transaction])
    assert customer.purchase_history == [transaction]


# --- Transaction ---


def test_calculate_total_sums_prices():
    burger = models.FoodItem("Spicy Burger", "Burgers", Decimal("8.99"), 4.5)
    soda = models.FoodItem("Large Soda", "Drinks", Decimal("2.50"), 4.0)
    transaction = models.Transaction(items=[burger, soda])

    assert transaction.calculate_total() == Decimal("11.49")


def test_calculate_total_empty_transaction():
    assert models.Transaction(items=[]).calculate_total() == Decimal("0")


def test_calculate_total_prints_receipt(capsys):
    burger = models.FoodItem("Spicy Burger", "Burgers", Decimal("8.99"), 4.5)
    transaction = models.Transaction(items=[burger])

    transaction.calculate_total()

    out = capsys.readouterr().out
    assert "Receipt" in out
    assert "Spicy Burger" in out
    assert "Total: 8.99" in out


def test_transaction_verify_payment_valid():
    future_year = date.today().year + 1
    transaction = models.Transaction(items=[])
    assert transaction.verify_payment("4242424242424242", 1, future_year, "123") is True


def test_transaction_verify_payment_invalid_raises():
    future_year = date.today().year + 1
    transaction = models.Transaction(items=[])
    with pytest.raises(ValueError):
        transaction.verify_payment("not-a-card", 1, future_year, "123")


# --- encrypt.py ---


def test_encrypt_decrypt_text_round_trip():
    original = "Hello, World! 123"
    assert encrypt.decrypt_text(encrypt.encrypt_text(original)) == original


def test_encrypt_decrypt_numbers_round_trip():
    original = "12/2027"
    assert encrypt.decrypt_numbers(encrypt.encrypt_numbers(original)) == original


# --- payment.py ---


@pytest.mark.parametrize(
    "number,expected_brand",
    [
        (4242424242424242, "VISA"),
        (378282246310005, "AMEX"),
        (5555555555554444, "MASTERCARD"),
        (1234567890123, None),
    ],
)
def test_detect_card_brand(number, expected_brand):
    assert payment.detect_card_brand(number) == expected_brand


def test_luhn_checksum_valid_known_numbers():
    assert payment.luhn_checksum_valid(4242424242424242) is True
    assert payment.luhn_checksum_valid(4000000000000000) is False


def test_validate_expiry_rejects_past():
    assert payment.validate_expiry(1, 2000) is False


def test_validate_expiry_accepts_future():
    assert payment.validate_expiry(1, date.today().year + 1) is True


def test_validate_cvv():
    assert payment.validate_cvv("123") is True
    assert payment.validate_cvv("12") is False
    assert payment.validate_cvv("12a") is False


def test_validate_payment_input_reports_all_errors():
    errors = payment.validate_payment_input("1234567890123456", 13, 2000, "12")
    assert any("Luhn" in e or "not a recognized" in e for e in errors)
    assert any("month" in e for e in errors)
    assert any("CVV" in e for e in errors)


# --- username / password validation ---


def test_validate_username_rejects_wrong_length_and_characters():
    assert models.validate_username("short") != []
    assert models.validate_username("bad username!") != []
    assert models.validate_username(VALID_USERNAME) == []


def test_validate_password_rejects_missing_rules():
    too_short_errors = models.validate_password("short", VALID_USERNAME)
    assert too_short_errors != []

    no_upper_no_special_errors = models.validate_password("alllowercase1234", VALID_USERNAME)
    assert any("uppercase" in e for e in no_upper_no_special_errors)
    assert any("special character" in e for e in no_upper_no_special_errors)

    disallowed_char_errors = models.validate_password("Correct9Horse!!1", VALID_USERNAME)
    assert any("disallowed character" in e for e in disallowed_char_errors)

    assert models.validate_password(VALID_PASSWORD, VALID_USERNAME) == []

    longer_valid_password = "Correct9Horses.12345"
    assert models.validate_password(longer_valid_password, VALID_USERNAME) == []


def test_validate_password_rejects_containing_username():
    password_with_username = (VALID_USERNAME + "Ab.9").ljust(16, "X")
    assert any("username" in e for e in models.validate_password(password_with_username, VALID_USERNAME))


# --- account flow (file-backed, uses tmp_path) ---


@pytest.fixture
def security_answers():
    return {
        "mothers_maiden_name": "Smith",
        "first_pet": "Rex",
        "childhood_best_friend": "Sam",
        "favorite_teacher": "Ms. Lee",
    }


def test_create_account_and_login(tmp_path, security_answers):
    accounts_file = tmp_path / "accounts.dat"
    models.Customer.create_account(
        "Ada Lovelace", VALID_USERNAME, VALID_PASSWORD, security_answers, path=accounts_file
    )

    assert models.Customer.login(VALID_USERNAME, VALID_PASSWORD, path=accounts_file) is not None
    assert models.Customer.login(VALID_USERNAME, "wrong password", path=accounts_file) is None
    assert models.Customer.login("nobody_at_all", "whatever", path=accounts_file) is None


def test_create_account_rejects_invalid_username_or_password(tmp_path, security_answers):
    accounts_file = tmp_path / "accounts.dat"
    with pytest.raises(ValueError):
        models.Customer.create_account(
            "Ada Lovelace", "bad user", VALID_PASSWORD, security_answers, path=accounts_file
        )
    with pytest.raises(ValueError):
        models.Customer.create_account(
            "Ada Lovelace", VALID_USERNAME, "tooshort", security_answers, path=accounts_file
        )


def test_change_password_with_recovery_answer(tmp_path, security_answers):
    accounts_file = tmp_path / "accounts.dat"
    models.Customer.create_account(
        "Ada Lovelace", VALID_USERNAME, VALID_PASSWORD, security_answers, path=accounts_file
    )
    new_password = "NewSecret9Pass.2"

    assert (
        models.Customer.change_password(
            VALID_USERNAME, "first_pet", "wrong", new_password, path=accounts_file
        )
        is False
    )
    assert (
        models.Customer.change_password(
            VALID_USERNAME, "first_pet", "Rex", new_password, path=accounts_file
        )
        is True
    )
    assert models.Customer.login(VALID_USERNAME, new_password, path=accounts_file) is not None
    assert models.Customer.login(VALID_USERNAME, VALID_PASSWORD, path=accounts_file) is None


def test_change_username(tmp_path, security_answers):
    accounts_file = tmp_path / "accounts.dat"
    models.Customer.create_account(
        "Ada Lovelace", VALID_USERNAME, VALID_PASSWORD, security_answers, path=accounts_file
    )
    new_username = "ada_love2"

    assert models.Customer.change_username(VALID_USERNAME, new_username, path=accounts_file) is True
    assert models.Customer.login(VALID_USERNAME, VALID_PASSWORD, path=accounts_file) is None
    assert models.Customer.login(new_username, VALID_PASSWORD, path=accounts_file) is not None


# --- payment flow (file-backed, uses tmp_path) ---


def test_save_and_change_payment_method(tmp_path):
    payments_file = tmp_path / "payments.dat"
    future_year = date.today().year + 1

    assert (
        payment.save_payment_method(
            "ada", "4242424242424242", "Ada Lovelace", 1, future_year, "123", path=payments_file
        )
        is True
    )
    assert (
        payment.change_payment_method(
            "ada", "5555555555554444", "Ada Lovelace", 6, future_year, "456", path=payments_file
        )
        is True
    )

    saved = payment.get_payment_method("ada", path=payments_file)
    assert saved["card_number"] == "5555555555554444"
    assert saved["cvv"] == "456"
    assert saved["brand"] == "MASTERCARD"


def test_save_payment_method_rejects_invalid_card(tmp_path):
    payments_file = tmp_path / "payments.dat"
    future_year = date.today().year + 1
    with pytest.raises(ValueError):
        payment.save_payment_method(
            "ada", "1234567890123456", "Ada Lovelace", 1, future_year, "123", path=payments_file
        )


def test_save_payment_method_rejects_invalid_cvv(tmp_path):
    payments_file = tmp_path / "payments.dat"
    future_year = date.today().year + 1
    with pytest.raises(ValueError):
        payment.save_payment_method(
            "ada", "4242424242424242", "Ada Lovelace", 1, future_year, "12", path=payments_file
        )
