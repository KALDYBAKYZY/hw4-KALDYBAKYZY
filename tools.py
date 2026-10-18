"""Two tools for the model: lookup (facts from the documents) and calculate (safe maths).

Both functions never crash: if something is wrong they return {"error": "..."}.
"""

import ast
import difflib
import json
import operator
import re
from pathlib import Path

CORPUS_PATH = Path(__file__).parent / "data" / "corpus.jsonl"

# A number in the text, for example "1,284.6" or "52,904" or "1871".
NUM = r"(\d[\d,]*(?:\.\d+)?)"

# For each field: regex patterns that find the number in a district profile.
# The profiles are written in three different styles, so some fields need
# more than one pattern. The first pattern that matches is used.
FIELD_PATTERNS = {
    "population_2025": [
        r"2025 census (?:recorded|counted) " + NUM + r" residents",
        r"Census population: [\d,]+ in 2020 and " + NUM + r" in 2025",
    ],
    "population_2020": [
        r"2020 census had recorded " + NUM,
        r"up from " + NUM + r" at the 2020 census",
        r"Census population: " + NUM + r" in 2020",
    ],
    "area_km2": [NUM + r" square kilometres"],
    "budget_2025_million_tenge": [NUM + r" million tenge"],
    "water_use_2025_megalitres": [NUM + r" (megalitres|cubic metres)"],
    "schools": [NUM + r" schools"],
    "pupils_2025_26": [NUM + r" pupils"],
    "paved_road_km": [NUM + r" km\b"],
    "founded_year": [r"[Ff]ounded in (\d{4})"],
}

UNITS = {
    "population_2025": "residents",
    "population_2020": "residents",
    "area_km2": "km2",
    "budget_2025_million_tenge": "million tenge",
    "water_use_2025_megalitres": "megalitres",
    "schools": "schools",
    "pupils_2025_26": "pupils",
    "paved_road_km": "km",
    "founded_year": "year",
    "water_tariff_2025": "tenge per cubic metre",
}

ALLOWED_FIELDS = list(UNITS.keys())

# Word used in a correction notice ("The correct area is ...") -> field name.
CORRECTION_WORDS = {
    "area": "area_km2",
    "population": "population_2025",
    "budget": "budget_2025_million_tenge",
}

MAX_INPUT_LENGTH = 100


def to_number(text):
    """'1,284.6' -> 1284.6 and '52,904' -> 52904."""
    text = text.replace(",", "")
    return float(text) if "." in text else int(text)


def sentence_with(text, fragment):
    """Return only the sentence that contains the number (not the whole document)."""
    for sentence in re.split(r"(?<=\.)\s+", text):
        if fragment in sentence:
            return sentence
    return ""


def load_corpus(path=CORPUS_PATH):
    """Read the documents and sort them into profiles, corrections and others."""
    profiles = {}      # district name -> current (not archived) profile
    archived = {}      # district name -> list of archived profiles
    corrections = {}   # district name -> list of correction notices
    tariff_doc = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            title = doc["title"]

            match = re.match(r"(\w+) district profile", title)
            if match:
                name = match.group(1)
                if "ARCHIVED" in title or doc["text"].startswith("ARCHIVED"):
                    archived.setdefault(name, []).append(doc)
                else:
                    profiles[name] = doc
                continue

            match = re.match(r"Correction notice - (\w+)", title)
            if match:
                corrections.setdefault(match.group(1), []).append(doc)
                continue

            if "water tariff" in title.lower():
                tariff_doc = doc

    return profiles, archived, corrections, tariff_doc


PROFILES, ARCHIVED, CORRECTIONS, TARIFF_DOC = load_corpus()


def find_district(name):
    """Step 2: exact name (ignoring case and spaces) -> real name, or an error."""
    clean = name.strip().lower()
    all_names = sorted(set(PROFILES) | set(ARCHIVED))
    for real_name in all_names:
        if real_name.lower() == clean:
            return real_name, None

    similar = difflib.get_close_matches(name.strip().title(), all_names, n=3, cutoff=0.5)
    if similar:
        return None, f"no district named '{name}'; did you mean {' or '.join(similar)}?"
    return None, f"no district named '{name}'; districts are: {', '.join(all_names)}"


def read_correction(district, field):
    """Step 5: if a correction notice changes this field, return (value, doc_id)."""
    for notice in CORRECTIONS.get(district, []):
        match = re.search(r"[Tt]he correct (\w+) is " + NUM, notice["text"])
        if match and CORRECTION_WORDS.get(match.group(1)) == field:
            return to_number(match.group(2)), notice["id"], sentence_with(notice["text"], match.group(2))
    return None


def lookup(district=None, field=None):
    """Return one 2025 number for one district, with the documents it came from."""
    # --- check the inputs ---
    if not isinstance(field, str) or field not in ALLOWED_FIELDS:
        return {"error": f"unknown field '{field}'; allowed fields: {', '.join(ALLOWED_FIELDS)}"}

    # --- the water tariff is not about one district ---
    if field == "water_tariff_2025":
        if TARIFF_DOC is None:
            return {"error": "the water tariff document was not found"}
        match = re.search(r"From 1 January 2025[^.]*? (\d+\.\d+) tenge per cubic metre", TARIFF_DOC["text"])
        if not match:
            return {"error": f"could not find the 2025 tariff in {TARIFF_DOC['id']}"}
        return {
            "field": field,
            "value": to_number(match.group(1)),
            "unit": UNITS[field],
            "sources": [TARIFF_DOC["id"]],
            "sentence": sentence_with(TARIFF_DOC["text"], match.group(1)),
        }

    if not isinstance(district, str) or not district.strip():
        return {"error": f"field '{field}' needs a district name"}
    district = district[:MAX_INPUT_LENGTH]

    # --- step 2: find the district ---
    name, error = find_district(district)
    if error:
        return {"error": error}

    # --- step 3: choose the current profile, never an archived one ---
    doc = PROFILES.get(name)
    if doc is None:
        return {"error": f"only an ARCHIVED profile found for {name}; it must not be used"}

    # --- step 5a: a correction notice is stronger than the profile ---
    correction = read_correction(name, field)
    if correction:
        value, notice_id, sentence = correction
        return {
            "district": name,
            "field": field,
            "value": value,
            "unit": UNITS[field],
            "sources": [doc["id"], notice_id],
            "sentence": sentence,
            "note": f"corrected by {notice_id}",
        }

    # --- step 4: read the number from the profile ---
    for pattern in FIELD_PATTERNS[field]:
        match = re.search(pattern, doc["text"])
        if match:
            break
    else:
        return {"error": f"could not find '{field}' in {doc['id']}"}

    raw = match.group(1)
    try:
        value = to_number(raw)
    except ValueError:
        return {"error": f"could not read the number '{raw}' in {doc['id']}"}

    result = {
        "district": name,
        "field": field,
        "value": value,
        "unit": UNITS[field],
        "sources": [doc["id"]],
        "sentence": sentence_with(doc["text"], raw),
    }

    # --- step 5b: water must always be in megalitres ---
    if field == "water_use_2025_megalitres":
        unit_in_text = match.group(2)
        if unit_in_text == "cubic metres":
            result["value"] = value / 1000  # 1 megalitre = 1,000 cubic metres (NR-15)
            result["note"] = f"profile gives {raw} cubic metres; changed to megalitres (1 ML = 1,000 m3)"
        elif unit_in_text != "megalitres":
            return {"error": f"unknown water unit '{unit_in_text}' in {doc['id']}"}

    return result


# ---------------------------------------------------------------------------
# calculate
# ---------------------------------------------------------------------------

MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 100
MAX_ABS_RESULT = 1e15

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}


class CalcError(Exception):
    pass


def check_size(x):
    if x != x or abs(x) > MAX_ABS_RESULT:  # x != x is True only for NaN
        raise CalcError(f"result is larger than {MAX_ABS_RESULT:g}")
    return x


def evaluate(node):
    """Walk the tree from ast. Only numbers and + - * / ** are allowed."""
    if isinstance(node, ast.Expression):
        return evaluate(node.body)

    # a number (bool is also an int in Python, so refuse it explicitly)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return check_size(node.value)

    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](evaluate(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left = evaluate(node.left)
        right = evaluate(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise CalcError("division by zero")
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT:
                raise CalcError(f"exponent too large (max {MAX_EXPONENT})")
            if left == 0 and right < 0:
                raise CalcError("division by zero")
        try:
            return check_size(OPERATORS[type(node.op)](left, right))
        except OverflowError:
            raise CalcError(f"result is larger than {MAX_ABS_RESULT:g}")

    # anything else: a name, a function call, an attribute, a string, ...
    raise CalcError(f"not allowed: {type(node).__name__}")


def calculate(expression=None):
    """Safe arithmetic. Never uses eval or exec."""
    if not isinstance(expression, str) or not expression.strip():
        return {"error": "could not read the expression: it is empty"}
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return {"error": f"could not read the expression: longer than {MAX_EXPRESSION_LENGTH} characters"}

    try:
        tree = ast.parse(expression, mode="eval")  # only READS the text, runs nothing
    except SyntaxError as e:
        return {"error": f"could not read the expression: {e.msg}"}

    try:
        result = evaluate(tree)
    except CalcError as e:
        message = str(e)
        if message == "not allowed: Tuple":
            message += " (write numbers without commas: 52904, not 52,904)"
        return {"error": message}
    except Exception as e:  # last safety net: the tool must never crash
        return {"error": f"could not calculate: {e}"}

    return {"expression": expression, "result": result}


# The definitions sent to the model (the same as in Part A).
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": (
                "Get one 2025 number for one district of the Nine Rivers Region, or the water tariff. "
                "Call it once for each number you need. It already skips archived profiles, uses "
                "correction notices, and gives water in megalitres for all districts. The result has "
                "'value', 'unit', 'sources' (document ids) and 'sentence'. If the name is wrong, you get "
                "an 'error' with similar names; try again with the exact name. Do not guess numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {
                        "type": "string",
                        "description": "Exact district name, for example 'Ossbridge'. Not needed for 'water_tariff_2025'.",
                    },
                    "field": {
                        "type": "string",
                        "enum": ALLOWED_FIELDS,
                        "description": "Which number you want.",
                    },
                },
                "required": ["field"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Does exact math. Use it for every calculation, do not calculate in your head. Give one "
                "expression with numbers, + - * / ** and brackets, for example '(71388 - 67214) / 67214 * 100'. "
                "Write numbers without commas (52904, not 52,904). Returns the full result; round only in "
                "your final answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, max 200 characters, for example '44675 / 921.4'.",
                    }
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
]

TOOLS = {"lookup": lookup, "calculate": calculate}