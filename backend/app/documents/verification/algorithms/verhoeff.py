from typing import List, Tuple

# Dihedral group D5 multiplication table
_D5_MULTIPLICATION = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0)
)

# Permutation table
_PERMUTATION = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8)
)

# Inverse table
_INVERSE = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def generate_verhoeff(number_str: str) -> str:
    """
    Computes and appends the Verhoeff checksum digit to a numeric string.
    """
    c = 0
    reversed_digits = [int(d) for d in reversed(number_str) if d.isdigit()]
    for i, digit in enumerate(reversed_digits):
        c = _D5_MULTIPLICATION[c][_PERMUTATION[(i + 1) % 8][digit]]
    return number_str + str(_INVERSE[c])


def validate_verhoeff(number_str: str) -> bool:
    """
    Validates that a numeric string satisfies the Verhoeff dihedral D5 checksum.
    Returns True if valid, False otherwise.
    """
    clean_digits = [int(d) for d in number_str if d.isdigit()]
    if not clean_digits:
        return False

    c = 0
    for i, digit in enumerate(reversed(clean_digits)):
        c = _D5_MULTIPLICATION[c][_PERMUTATION[i % 8][digit]]
    return c == 0
