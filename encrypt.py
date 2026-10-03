"""Python port of encrypt.c's monoalphabetic substitution cipher.

Not real cryptography: a 26-letter (or 10-digit) substitution is trivially
broken by frequency analysis. Used here only to obscure values on disk for
a learning exercise, never to protect real secrets.
"""

TEXT_KEY = "nqxpomaftrhlzgecyjiuwskdvb"
DIGIT_KEY = "3715902684"


def encrypt_text(text: str) -> str:
    result = []
    for ch in text:
        if ch.isupper():
            result.append(TEXT_KEY[ord(ch) - ord("A")].upper())
        elif ch.islower():
            result.append(TEXT_KEY[ord(ch) - ord("a")])
        else:
            result.append(ch)
    return "".join(result)


def decrypt_text(text: str) -> str:
    result = []
    for ch in text:
        if ch.isupper():
            result.append(chr(TEXT_KEY.index(ch.lower()) + ord("A")))
        elif ch.islower():
            result.append(chr(TEXT_KEY.index(ch) + ord("a")))
        else:
            result.append(ch)
    return "".join(result)


def encrypt_numbers(text: str) -> str:
    return "".join(DIGIT_KEY[int(ch)] if ch.isdigit() else ch for ch in text)


def decrypt_numbers(text: str) -> str:
    return "".join(str(DIGIT_KEY.index(ch)) if ch.isdigit() else ch for ch in text)
