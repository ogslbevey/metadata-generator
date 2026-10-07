from fastapi import FastAPI
import re
import phonenumbers
from phonenumbers import PhoneNumberMatcher, Leniency
from typing import Dict, Any

def detect_phone_numbers(text: str):
    """
    Detects phone numbers in the given text via two methods:
      1) The phonenumbers library (STRICT_GROUPING).
      2) A custom regex enforcing balanced parentheses or no parentheses
         around the area code.

    Each identified match is checked to ensure it has at least 10 digits
    before being considered valid. If a given substring is detected by
    both methods (same start and end indices in the text), it is added
    only once. In the end, the function returns a list of single-element
    tuples containing only the phone number strings, with no duplicates.

    The final list is sorted alphabetically by the phone number substring.

    Args:
        text (str): The complete text to search for phone numbers.

    Returns:
        List[Tuple[str]]:
            A list of single-element tuples (phone_str,). Each tuple
            represents a distinct phone number found in the text,
            sorted by the phone number string.
    """
    all_matches = []

    # --- 1) phonenumbers approach ---
    for match in phonenumbers.PhoneNumberMatcher(text, "US", leniency=Leniency.STRICT_GROUPING):
        if phonenumbers.is_possible_number(match.number):
            start_idx = match.start
            end_idx = match.end
            substring = text[start_idx:end_idx]

            # Keep only if there are at least 10 digits
            digits_only = re.sub(r"\D", "", substring)
            if len(digits_only) >= 10:
                all_matches.append((start_idx, end_idx, substring))

    # --- 2) custom strict regex approach ---
    separators = r'[\s\-\.]'
    phone_pattern = re.compile(
        r'''
        \b
        (?P<full_number>
            (?:\+?\d{1,2}''' + separators + r''')?   # Optional country code, e.g. +1
            (?:\(\d{3}\)|\d{3})?                     # Optional area code: (xxx) or xxx
            ''' + separators + r'''\-?              # Optional separator/dash after area code
            \d{3}''' + separators + r'''\-?         # 3 digits, optional separator/dash
            \d{4}                                   # Last 4 digits
        )
       # \b
        ''',
        re.VERBOSE
    )

    for m in phone_pattern.finditer(text):
        start_idx = m.start('full_number')
        end_idx = m.end('full_number')
        substring = text[start_idx:end_idx]

        # Keep only if there are at least 10 digits
        digits_only = re.sub(r"\D", "", substring)
        if len(digits_only) >= 10:
            all_matches.append((start_idx, end_idx, substring))

    # --- Deduplicate by exact substring positions (start_idx, end_idx) ---
    seen_spans = set()
    distinct_matches = []
    for start_idx, end_idx, phone_str in all_matches:
        if (start_idx, end_idx) not in seen_spans:
            seen_spans.add((start_idx, end_idx))
            distinct_matches.append((phone_str))

    return distinct_matches


def detect_canadian_postal_codes(text: str):
    """
    Detects all Canadian postal codes in the given text. 
    Supports both A1A 1A1 and A1A1A1 formats, normalizing 
    them to include a space (A1A 1A1).

    Args:
        text (str): The input text to scan for postal codes.

    Returns:
        list: A list of detected postal code strings, each 
              normalized to include a space between the 
              third and fourth characters.
    """
    found = []
    postal_code_pattern = re.compile(
        r'\b[A-Za-z][0-9][A-Za-z][ ]?[0-9][A-Za-z][0-9]\b', re.IGNORECASE
    )

    for match in postal_code_pattern.finditer(text):
        postal_code = match.group(0).strip()
        if " " not in postal_code:
            postal_code = postal_code[:3] + " " + postal_code[3:]
        found.append(postal_code)

    return found


def detect_email_addresses(text: str):
    """
    Detects email addresses in the given text via regex.
    Strips trailing punctuation (like commas and periods).

    Args:
        text (str): The input text to scan for email addresses.

    Returns:
        list: A list of detected email address strings.
    """
    found = []
    email_pattern = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', re.IGNORECASE | re.UNICODE
    )

    for match in email_pattern.finditer(text):
        email = match.group(0).strip().rstrip(
            ".,")  # remove trailing punctuation
        found.append(email)

    return found
