# HW4 — submission

**AI assistance:** <!-- what you used, and for what. "None" is an answer too. -->

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

I use this question as an example: *"Which district is denser, Brightwater or Millbrook, and by how much?"*

To answer it, I need to: find the two districts, take their population and area, check that the numbers are the right ones (not old, not with a typo), divide population by area, compare, and write the answer.

I split this into 9 steps. In the table, `str` means text, `float` means a number with decimals, and `list[str]` means a list of texts.

| # | Step | Input | Output | If something goes wrong | Who does it |
|---|---|---|---|---|---|
| 1 | **Understand the question** | the question (`str`) | the district names (`list[str]`), the numbers I need (`list[str]`, for example `"population_2025"`, `"area_km2"`) | If the question asks for a number we do not have, the model says it cannot answer. It does not guess. | model |
| 2 | **Find the district** | district name (`str`), maybe with a typo | document id (`str`, for example `"NR-05"`) | Name not found → error with the 2 most similar names. Ossbridge and Ossford are similar, so only the exact name is accepted. | `lookup` |
| 3 | **Choose the right document** | document id (`str`) | id of the 2025 profile (`str`) and ids of correction notices (`list[str]`) | If there is only an ARCHIVED profile → error. The 2019 number is never returned. | `lookup` |
| 4 | **Read the number** | document id (`str`) and which number (`str`) | the number (`float`), its unit (`str`), the sentence it came from (`str`) | Number not in the text or cannot be read → error. | `lookup` |
| 5 | **Fix the number** | the number (`float`), unit (`str`), corrections (`list[str]`) | final number (`float`), unit (`str`), source documents (`list[str]`) | If a correction exists, use the corrected number (NR-16). If the unit is cubic metres, change it to megalitres. Unknown unit → error. | `lookup` |
| 6 | **Calculate for each district** | a math expression (`str`), for example `"44675 / 921.4"` | the result (`float`), not rounded | Division by zero, too big number, or not math → error. | `calculate` |
| 7 | **Compare** | the results (`float`) | which district is bigger (`str`) and the difference (`float`, with `calculate`) | If they are equal, the answer says so. | model + `calculate` |
| 8 | **Round and write the answer** | district (`str`), difference (`float`) | one line: `ANSWER: <name or yes/no> \| <number>` | If there is no ANSWER line, the question is "unanswered". | model |
| 9 | **Run the tools** | the model's request (`tool_calls`) | one result for each request id (`tool_call_id`), and a log line | Bad arguments → send an error back to the model, do not run the tool. Too many rounds → stop, "unanswered". | loop (my code) |

**How the steps connect:**

1. The model reads the question (step 1) and decides what numbers it needs.
2. For each number, the model calls `lookup`. Inside `lookup`, steps 2, 3, 4 and 5 happen one after another: find the district → choose the right document → read the number → fix the number.
3. `lookup` gives the final number and the document id back to the model.
4. The model writes a math expression with these numbers and calls `calculate` (step 6).
5. The model compares the results and calls `calculate` again for the difference (step 7).
6. The model rounds the difference and writes the ANSWER line (step 8).
7. Step 9 (my loop) is in the middle every time the model calls a tool: it checks the request, runs the tool, saves a log, and sends the result back.

**What I assume:**

- I use 2025 numbers: population from the 2025 census, budget for 2025, water in 2025, pupils in 2025/26 (NR-00 says this). I use 2020 population only for questions about growth.
- I never use the ARCHIVED profiles NR-13 and NR-14. They are from 2019 and are replaced.
- A correction notice is more important than the profile. Brightwater's area is 921.4 km² (NR-16), not 912.4.
- Water is always in megalitres. Lindenmoor gives cubic metres, so I divide by 1,000 (NR-15: 1 megalitre = 1,000 cubic metres).
- For water per person per day I divide by 365 days (2025 is not a leap year).
- I round only once, at the end. If I round in the middle, the last digit can be wrong.
- A district name must be exact. If it is wrong, the tool gives an error with suggestions. It does not guess.

**The most important assumption:** that `lookup` handles the traps correctly. In S3 the model does not see the documents. If `lookup` gives 912.4 instead of 921.4, the model cannot see the mistake, and the answer looks correct but is wrong. That is why I put these rules in code and test them, not in the prompt.

### A2 — The two tools

#### `lookup`

The model gives a district name and which number it wants. The tool gives back one number and the document it came from.

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Get one 2025 number for one district of the Nine Rivers Region, or the water tariff. Call it once for each number you need. It already skips archived profiles, uses correction notices, and gives water in megalitres for all districts. The result has 'value', 'unit', 'sources' (document ids) and 'sentence'. If the name is wrong, you get an 'error' with similar names; try again with the exact name. Do not guess numbers.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name, for example 'Ossbridge'. Not needed for 'water_tariff_2025'."
        },
        "field": {
          "type": "string",
          "enum": [
            "population_2025",
            "population_2020",
            "area_km2",
            "budget_2025_million_tenge",
            "water_use_2025_megalitres",
            "schools",
            "pupils_2025_26",
            "paved_road_km",
            "founded_year",
            "water_tariff_2025"
          ],
          "description": "Which number you want."
        }
      },
      "required": ["field"],
      "additionalProperties": false
    }
  }
}
```

| Case | What `lookup` returns |
|---|---|
| it works | `{"district": "Brightwater", "field": "area_km2", "value": 921.4, "unit": "km2", "sources": ["NR-05", "NR-16"], "note": "corrected by NR-16"}` |
| it works, unit changed | `{"district": "Lindenmoor", "field": "water_use_2025_megalitres", "value": 2151.4, "unit": "megalitres", "sources": ["NR-08"], "note": "changed from cubic metres"}` |
| wrong name | `{"error": "no district named 'Ossbrige'; did you mean Ossbridge or Ossford?"}` |
| wrong field | `{"error": "unknown field 'density'"}` |
| no district given | `{"error": "this field needs a district name"}` |
| number not found in the text | `{"error": "could not find 'paved_road_km' in NR-xx"}` |
| only archived profile | `{"error": "only an ARCHIVED profile found; it must not be used"}` |

**Worst thing it could do:** `lookup` only reads a file. It cannot run code or delete files. The worst thing is a wrong number that looks right: the old 2019 number, 912.4 instead of 921.4, or Ossford's number instead of Ossbridge's. Nobody would notice. So it never guesses a name, and I test the traps.

#### `calculate`

The model gives a math expression as text. The tool gives back the result.

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Does exact math. Use it for every calculation, do not calculate in your head. Give one expression with numbers, + - * / ** and brackets, for example '(71388 - 67214) / 67214 * 100'. Write numbers without commas (52904, not 52,904). Returns the full result; round only in your final answer.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Math expression, max 200 characters, for example '44675 / 921.4'."
        }
      },
      "required": ["expression"],
      "additionalProperties": false
    }
  }
}
```

| Case | What `calculate` returns |
|---|---|
| it works | `{"expression": "44675 / 921.4", "result": 48.48599956587801}` |
| division by zero | `{"error": "division by zero"}` |
| too big (`9**9**9`) | `{"error": "exponent too large"}` — checked before calculating, so it does not freeze |
| code instead of math (`__import__('os')...`, `(1).__class__`) | `{"error": "not allowed"}` — the text is only read with `ast`, never run |
| not valid math | `{"error": "could not read the expression"}` |

**Worst thing it could do:** if I used `eval`, the model could run any Python code on my computer, for example delete files or read my API key. With `ast` I only allow numbers and `+ - * / **`, so no code runs. The model can still give a wrong expression (wrong numbers), and the tool cannot know that.

### A3 — Q-09 by hand

This is the conversation I expect. Every tool request has an id (`call_1`...), and every result answers the same id.

```json
[
  {"role": "system", "content": "You answer questions about the Nine Rivers Region. Use lookup for every fact and calculate for every calculation. End with one line: ANSWER: <name or yes/no> | <number>"},
  {"role": "user", "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"}},
    {"id": "call_2", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"}},
    {"id": "call_3", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"}},
    {"id": "call_4", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_1", "content": "{\"value\": 44675, \"unit\": \"residents\", \"sources\": [\"NR-05\"]}"},
  {"role": "tool", "tool_call_id": "call_2", "content": "{\"value\": 921.4, \"unit\": \"km2\", \"sources\": [\"NR-05\", \"NR-16\"], \"note\": \"corrected by NR-16\"}"},
  {"role": "tool", "tool_call_id": "call_3", "content": "{\"value\": 37203, \"unit\": \"residents\", \"sources\": [\"NR-11\"]}"},
  {"role": "tool", "tool_call_id": "call_4", "content": "{\"value\": 758.6, \"unit\": \"km2\", \"sources\": [\"NR-11\"]}"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_5", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"44675 / 921.4\"}"}},
    {"id": "call_6", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"37203 / 758.6\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_5", "content": "{\"result\": 48.48599956587801}"},
  {"role": "tool", "tool_call_id": "call_6", "content": "{\"result\": 49.041655681518584}"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_7", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"49.041655681518584 - 48.48599956587801\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_7", "content": "{\"result\": 0.5556561156405735}"},

  {"role": "assistant", "content": "Brightwater: 44675 / 921.4 = 48.49 per km2. Millbrook: 37203 / 758.6 = 49.04 per km2. Millbrook is denser by 0.6.\nANSWER: Millbrook | 0.6"}
]
```

I expect 3 rounds of tools and then the answer. In round 1 the model can ask for all 4 numbers together, because they do not depend on each other.

**My arithmetic:**

- Brightwater: 44,675 / 921.4 = 48.486 (I use 921.4 from NR-16, not 912.4)
- Millbrook: 37,203 / 758.6 = 49.042
- Difference: 49.042 − 48.486 = 0.556 → 0.6
- **Answer: Millbrook | 0.6.** This is the same as in `questions.json`.
- If I use the wrong area 912.4: Brightwater = 48.964, difference = 0.077 → 0.1. The name is still Millbrook, but the number is wrong. So this trap changes only the number.

### A4 — Why I split it this way

**Another way:** make one tool for each kind of calculation, for example `density(district)`, `growth(district)`, `water_per_person(district)`, `budget_per_person(district)`.

**Why I did not choose it:**

1. The 20 questions need about 10 different calculations, so I would need about 10 tools:
   - population density (Q-01, Q-09)
   - population growth or loss in % (Q-02, Q-13, Q-18)
   - water per person per day (Q-03, Q-14)
   - pupils per school (Q-04, Q-11, Q-15)
   - budget per resident (Q-05, Q-20)
   - budget per pupil (Q-12)
   - road per 1,000 residents (Q-07)
   - road per km² (Q-19)
   - water cost (Q-08, Q-17)
   - sum of two districts (Q-06, Q-16) and difference in founding years (Q-10)
   All tool descriptions are sent with every request, so this costs more tokens.
3. The rules for the traps (archive, correction, units) would be in 9 tools. In my way they are only in `lookup`, and I test them once.
4. The model would almost not need to think, so comparing it with S1 and S2 would not show much.

I also did not choose a `lookup` that searches text and gives back sentences. Then the model reads the text itself and can still make the trap mistakes (old 2019 numbers, 912.4, cubic metres). With my `lookup(district, field)`, the traps are in my code, and I can test them. The minus: it only works for the numbers in my list.
---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

The main plan did not change: `lookup(district, field)` and `calculate(expression)` work as in A2, and steps 2–5 are inside `lookup`. I only added small things:

- **`calculate` gives more exact error messages.** In Part A I wrote `"not allowed"`. In the code it says what is not allowed, for example `"not allowed: Call"` or `"not allowed: Attribute"`. This helps the model to understand its mistake.
- **`calculate` explains commas.** If the model writes `52,904`, Python reads it as two numbers. The tool now says: "write numbers without commas".
- **`calculate` has a limit for the result.** Not only the exponent is limited (max 100), but also the result (max 10^15). Without this, `10**20` would be allowed.
- **`calculate` refuses `True` and `False`.** In Python they are numbers (1 and 0), but they are not real numbers for maths.
- **`lookup` cuts very long names to 100 characters** before searching, so strange long input cannot slow it down.
- **`lookup` reads corrections with one rule:** it looks for "The correct <area / population / budget> is <number>" in a correction notice. This works for NR-16 and for future notices written the same way.
- **If no name is similar**, `lookup` returns the list of all 12 districts, so the model can choose the right one.

### B2 — Tests

```text
=============================================================== test session starts ================================================================
platform darwin -- Python 3.12.7, pytest-9.1.1, pluggy-1.7.0 -- /Users/gulnazzhaiylgan/hw4-KALDYBAKYZY/hw4-KALDYBAKYZY/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/gulnazzhaiylgan/hw4-KALDYBAKYZY/hw4-KALDYBAKYZY
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 21 items                                                                                                                                 

tests/test_tools.py::test_lookup_finds_2025_population PASSED                                                                                [  4%]
tests/test_tools.py::test_lookup_finds_2020_population_in_another_text_style PASSED                                                          [  9%]
tests/test_tools.py::test_lookup_misspelled_name_gives_suggestions PASSED                                                                    [ 14%]
tests/test_tools.py::test_lookup_similar_names_are_not_mixed PASSED                                                                          [ 19%]
tests/test_tools.py::test_lookup_ignores_archived_profile PASSED                                                                             [ 23%]
tests/test_tools.py::test_lookup_uses_correction_notice PASSED                                                                               [ 28%]
tests/test_tools.py::test_lookup_correction_does_not_change_other_fields PASSED                                                              [ 33%]
tests/test_tools.py::test_lookup_changes_cubic_metres_to_megalitres PASSED                                                                   [ 38%]
tests/test_tools.py::test_lookup_water_tariff PASSED                                                                                         [ 42%]
tests/test_tools.py::test_lookup_bad_inputs_return_errors_not_crash PASSED                                                                   [ 47%]
tests/test_tools.py::test_lookup_returns_a_sentence_not_the_whole_document PASSED                                                            [ 52%]
tests/test_tools.py::test_calculate_simple_division PASSED                                                                                   [ 57%]
tests/test_tools.py::test_calculate_multiplication_from_the_task PASSED                                                                      [ 61%]
tests/test_tools.py::test_calculate_brackets_and_minus PASSED                                                                                [ 66%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[__import__('os').system('echo hi')] PASSED                               [ 71%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[(1).__class__] PASSED                                                    [ 76%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[9**9**9] PASSED                                                          [ 80%]
tests/test_tools.py::test_calculate_division_by_zero PASSED                                                                                  [ 85%]
tests/test_tools.py::test_calculate_too_big_result PASSED                                                                                    [ 90%]
tests/test_tools.py::test_calculate_refuses_names_strings_and_commas PASSED                                                                  [ 95%]
tests/test_tools.py::test_calculate_bad_text_returns_errors_not_crash PASSED                                                                 [100%]

================================================================ 21 passed in 0.03s ================================================================

```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
