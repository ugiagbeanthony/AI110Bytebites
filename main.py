"""Interactive CLI entry point for ByteBites.

Run with: python main.py
"""

from decimal import Decimal, InvalidOperation

import models
import payment
from models import Customer, FoodItem, ItemCollection, Transaction

MENU = ItemCollection(items=[
    FoodItem("Spicy Burger", "Burgers", Decimal("8.99"), 4.5),
    FoodItem("Veggie Burger", "Burgers", Decimal("7.99"), 4.2),
    FoodItem("Large Soda", "Drinks", Decimal("2.50"), 4.0),
    FoodItem("Iced Tea", "Drinks", Decimal("2.25"), 3.8),
    FoodItem("Chocolate Cake", "Desserts", Decimal("4.50"), 4.7),
    FoodItem("Fries", "Sides", Decimal("3.25"), 4.3),
])


def prompt_create_account() -> Customer | None:
    name = input("Full name: ").strip()
    username = input(f"Username ({models.USERNAME_LENGTH} chars, letters/digits/underscore): ").strip()
    password = input(f"Password (at least {models.PASSWORD_LENGTH} chars): ").strip()
    print("Answer these recovery questions (used later if you forget your password):")
    answers = {}
    for question in models.RECOVERY_QUESTIONS:
        answers[question] = input(f"  {question.replace('_', ' ')}: ").strip()

    try:
        customer = Customer.create_account(name, username, password, answers)
    except ValueError as e:
        print(f"Could not create account: {e}")
        return None

    print(f"Account created. Welcome, {customer.name}!")
    return customer


def prompt_login() -> Customer | None:
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    customer = Customer.login(username, password)
    if customer is None:
        print("Login failed: incorrect username or password.")
        return None
    print(f"Welcome back, {customer.name}!")
    return customer


def show_menu(items: list[FoodItem]) -> None:
    for i, item in enumerate(items, start=1):
        print(f"  {i}. {item.name:<20} {item.category:<10} ${item.price}  ({item.popularity_rating}*)")


def browse_menu() -> None:
    category = input("Filter by category (blank for all): ").strip()
    items = MENU.filter_by_category(category) if category else MENU.items
    if not items:
        print(f"No items found in category '{category}'.")
        return
    show_menu(items)


def place_order(customer: Customer) -> None:
    show_menu(MENU.items)
    choices = input("Enter item numbers to order, separated by commas: ").strip()
    try:
        indexes = [int(c.strip()) - 1 for c in choices.split(",") if c.strip()]
        selected = [MENU.items[i] for i in indexes]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return
    if not selected:
        print("No items selected.")
        return

    transaction = Transaction(items=selected)
    transaction.calculate_total()
    customer.purchase_history.append(transaction)
    print("Order placed.")


def save_payment_method(customer: Customer) -> None:
    card_number = input("Card number: ").strip()
    name_on_card = input("Name on card: ").strip()
    try:
        exp_month = int(input("Expiry month (1-12): ").strip())
        exp_year = int(input("Expiry year: ").strip())
    except ValueError:
        print("Expiry month/year must be numbers.")
        return
    cvv = input("CVV (3 digits): ").strip()

    try:
        payment.save_payment_method(customer.username, card_number, name_on_card, exp_month, exp_year, cvv)
    except ValueError as e:
        print(f"Could not save payment method: {e}")
        return
    print("Payment method saved.")


def change_password(customer: Customer) -> None:
    print("Recovery questions:", ", ".join(models.RECOVERY_QUESTIONS))
    question = input("Which question will you answer? ").strip()
    answer = input("Your answer: ").strip()
    new_password = input(f"New password (at least {models.PASSWORD_LENGTH} chars): ").strip()
    try:
        ok = Customer.change_password(customer.username, question, answer, new_password)
    except ValueError as e:
        print(f"Could not change password: {e}")
        return
    print("Password changed." if ok else "Incorrect answer.")


def change_username(customer: Customer) -> Customer:
    new_username = input(f"New username ({models.USERNAME_LENGTH} chars): ").strip()
    try:
        ok = Customer.change_username(customer.username, new_username)
    except ValueError as e:
        print(f"Could not change username: {e}")
        return customer
    if ok:
        print("Username changed.")
        customer.username = new_username
    else:
        print("That username is taken or your current username wasn't found.")
    return customer


def view_purchase_history(customer: Customer) -> None:
    if not customer.purchase_history:
        print("No past orders.")
        return
    for i, transaction in enumerate(customer.purchase_history, start=1):
        print(f"Order {i}:")
        transaction.calculate_total()


def customer_menu(customer: Customer) -> None:
    actions = {
        "1": browse_menu,
        "2": lambda: place_order(customer),
        "3": lambda: save_payment_method(customer),
        "4": lambda: change_password(customer),
        "6": lambda: view_purchase_history(customer),
    }
    while True:
        print(
            "\n1) Browse menu  2) Place order  3) Save payment method\n"
            "4) Change password  5) Change username  6) View purchase history\n"
            "7) Log out"
        )
        choice = input("> ").strip()
        if choice == "7":
            print("Logged out.")
            return
        if choice == "5":
            customer = change_username(customer)
            continue
        action = actions.get(choice)
        if action is None:
            print("Invalid choice.")
            continue
        action()


def main() -> None:
    print("Welcome to ByteBites.")
    while True:
        print("\n1) Create account  2) Log in  3) Exit")
        choice = input("> ").strip()
        if choice == "1":
            customer = prompt_create_account()
        elif choice == "2":
            customer = prompt_login()
        elif choice == "3":
            print("Goodbye.")
            return
        else:
            print("Invalid choice.")
            continue

        if customer is not None:
            customer_menu(customer)


if __name__ == "__main__":
    main()
