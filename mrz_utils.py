"""MRZ parsing and check-digit validation for TD3 (passport) documents, ICAO 9303."""

from datetime import date

WEIGHTS = (7, 3, 1)


def _char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    return 0  # '<' and anything unexpected count as 0


def check_digit(data: str) -> str:
    total = sum(_char_value(c) * WEIGHTS[i % 3] for i, c in enumerate(data))
    return str(total % 10)


def _fix_numeric(s: str) -> str:
    """OCR often confuses letters with digits in numeric-only fields."""
    table = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
                           "Z": "2", "S": "5", "B": "8", "G": "6"})
    return s.translate(table)


def _clean_line(line: str) -> str:
    line = line.strip().upper().replace(" ", "")
    return line.ljust(44, "<")[:44]


def _parse_date(yymmdd: str, kind: str):
    """Return ISO date string, or None if invalid. kind: 'birth' or 'expiry'."""
    try:
        yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
        if kind == "expiry":
            # Passport expiry dates are always in the 2000s.
            return date(2000 + yy, mm, dd).isoformat()
        # Birth dates carry no century in the MRZ. Assume the 2000s, but if
        # that lands in the future, it must be the 1900s (e.g. yy=26 -> 1926,
        # not 2026). Guard the 1900s date too, in case 2000+yy was a leap
        # year that 1900+yy is not.
        d = date(2000 + yy, mm, dd)
        if d > date.today():
            try:
                d = date(1900 + yy, mm, dd)
            except ValueError:
                return None
        return d.isoformat()
    except (ValueError, IndexError):
        return None


def _name_parts(field: str):
    parts = field.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()
    given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    return surname, given


def parse_td3(line1: str, line2: str) -> dict:
    l1, l2 = _clean_line(line1), _clean_line(line2)

    number = l2[0:9]
    number_cd = _fix_numeric(l2[9])
    nationality = l2[10:13]
    dob = _fix_numeric(l2[13:19])
    dob_cd = _fix_numeric(l2[19])
    sex = l2[20]
    expiry = _fix_numeric(l2[21:27])
    expiry_cd = _fix_numeric(l2[27])
    personal = l2[28:42]
    personal_cd = _fix_numeric(l2[42])
    composite_cd = _fix_numeric(l2[43])

    # ICAO composite: passport no.+cd, DOB+cd, expiry+cd, personal no.+cd
    # (positions 1-10, 14-20, 22-43 of line 2; nationality and sex are excluded)
    composite_data = (l2[0:10] + dob + dob_cd + expiry + expiry_cd
                      + personal + personal_cd)

    checks = {
        "passport_number": check_digit(number) == number_cd,
        "date_of_birth": check_digit(dob) == dob_cd,
        "expiry_date": check_digit(expiry) == expiry_cd,
        "personal_number": (check_digit(personal) == personal_cd)
        or (set(personal) <= {"<"} and personal_cd in ("<", "0")),
        "composite": check_digit(composite_data) == composite_cd,
    }

    surname, given = _name_parts(l1[5:44])
    expiry_iso = _parse_date(expiry, "expiry")
    expired = None
    if expiry_iso:
        expired = date.fromisoformat(expiry_iso) < date.today()

    return {
        "document_type": l1[0:2].replace("<", ""),
        "issuing_country": l1[2:5].replace("<", ""),
        "surname": surname,
        "given_names": given,
        "passport_number": number.replace("<", ""),
        "nationality": nationality.replace("<", ""),
        "date_of_birth": _parse_date(dob, "birth"),
        "sex": sex if sex in ("M", "F") else "X",
        "expiry_date": expiry_iso,
        "expired": expired,
        "personal_number": personal.replace("<", ""),
        "checks": checks,
        "valid": all(checks.values()),
        "mrz_line1": l1,
        "mrz_line2": l2,
    }
