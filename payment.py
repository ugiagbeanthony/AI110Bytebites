"""Python port of credit.py's Luhn/brand check, plus expiry validation and
encrypted payment-method persistence.

Storing raw card numbers (even encrypted with the teaching cipher in
encrypt.py) is not something a real system should do (PCI-DSS concerns);
this exists only for a non-production tinkering exercise.
"""

import os
from datetime import date

from encrypt import decrypt_numbers, decrypt_text, encrypt_numbers, encrypt_text

PAYMENTS_FILE = "payments.dat"


def digit_counter(num: int) -> int:
    counter = 1
    while num > 9:
        num //= 10
        counter += 1
    return counter


def luhn_checksum_valid(num: int) -> bool:
    size = digit_counter(num)
    c = 1
    singles = []
    doubles = []
    while c <= size:
        single_el = (num % (10**c)) // (10 ** (c - 1))
        if (c + 1) <= size:
            double_el = (num % (10 ** (c + 1))) // (10**c)
            doubled = double_el * 2
            if doubled > 9:
                doubles.append(doubled // 10)
                doubles.append(doubled % 10)
            else:
                doubles.append(doubled)
        singles.append(single_el)
        c += 2
    return (sum(singles) + sum(doubles)) % 10 == 0


def detect_card_brand(num: int) -> str | None:
    n = digit_counter(num)
    if n not in (13, 15, 16):
        return None
    if n == 13:
        if num // (10 ** (n - 1)) == 4:
            return "VISA"
    elif n == 15:
        if num // (10 ** (n - 2)) in (34, 37):
            return "AMEX"
    elif n == 16:
        if num // (10 ** (n - 1)) == 4:
            return "VISA"
        if num // (10 ** (n - 2)) in range(51, 56):
            return "MASTERCARD"
    return None


def validate_expiry(month: int, year: int) -> bool:
    if not (1 <= month <= 12):
        return False
    today = date.today()
    return (year, month) >= (today.year, today.month)


def validate_cvv(cvv: str) -> bool:
    return cvv.isdigit() and len(cvv) == 3


def validate_payment_input(card_number: str, exp_month: int, exp_year: int, cvv: str) -> list[str]:
    errors = []

    if not card_number.isdigit():
        errors.append("card number must contain only digits")
    else:
        card_num_int = int(card_number)
        brand = detect_card_brand(card_num_int)
        if brand is None:
            errors.append(f"'{card_number}' is not a recognized VISA/AMEX/MASTERCARD number")
        elif not luhn_checksum_valid(card_num_int):
            errors.append("card number failed the Luhn checksum check")

    if not (0 < exp_month < 13):
        errors.append("expiry month must be between 1 and 12")
    elif not validate_expiry(exp_month, exp_year):
        errors.append("expiry date must be the current month/year or later")

    if not validate_cvv(cvv):
        errors.append("CVV must be exactly 3 digits")

    return errors


def _lock_down(path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _read_records(path) -> dict:
    if not os.path.exists(path):
        return {}
    records = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != 7:
                continue
            username, enc_card, enc_name, enc_month, enc_year, enc_cvv, brand = parts
            records[username] = {
                "card_number": enc_card,
                "name_on_card": enc_name,
                "exp_month": enc_month,
                "exp_year": enc_year,
                "cvv": enc_cvv,
                "brand": brand,
            }
    return records


def _write_records(path, records: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for username, rec in records.items():
            f.write(
                f"{username}|{rec['card_number']}|{rec['name_on_card']}|"
                f"{rec['exp_month']}|{rec['exp_year']}|{rec['cvv']}|{rec['brand']}\n"
            )
    _lock_down(path)


def save_payment_method(
    username: str,
    card_number: str,
    name_on_card: str,
    exp_month: int,
    exp_year: int,
    cvv: str,
    path=PAYMENTS_FILE,
) -> bool:
    errors = validate_payment_input(card_number, exp_month, exp_year, cvv)
    if errors:
        raise ValueError("; ".join(errors))

    records = _read_records(path)
    records[username] = {
        "card_number": encrypt_numbers(str(card_number)),
        "name_on_card": encrypt_text(name_on_card),
        "exp_month": encrypt_numbers(f"{exp_month:02d}"),
        "exp_year": encrypt_numbers(str(exp_year)),
        "cvv": encrypt_numbers(cvv),
        "brand": detect_card_brand(int(card_number)),
    }
    _write_records(path, records)
    return True


def change_payment_method(
    username: str,
    card_number: str,
    name_on_card: str,
    exp_month: int,
    exp_year: int,
    cvv: str,
    path=PAYMENTS_FILE,
) -> bool:
    records = _read_records(path)
    if username in records:
        del records[username]
        _write_records(path, records)
    return save_payment_method(username, card_number, name_on_card, exp_month, exp_year, cvv, path=path)


def get_payment_method(username: str, path=PAYMENTS_FILE) -> dict | None:
    record = _read_records(path).get(username)
    if record is None:
        return None
    return {
        "card_number": decrypt_numbers(record["card_number"]),
        "name_on_card": decrypt_text(record["name_on_card"]),
        "exp_month": decrypt_numbers(record["exp_month"]),
        "exp_year": decrypt_numbers(record["exp_year"]),
        "cvv": decrypt_numbers(record["cvv"]),
        "brand": record["brand"],
    }
