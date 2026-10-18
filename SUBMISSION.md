# HW4 — submission

**AI assistance:** I used Claude (Anthropic). It helped me write the code, understand the task, and build the algorithm. All runs, numbers and logs are from my own code.

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

- Round limit, and why: 10 model calls per question. By my A3 plan, Q-09 needs 4 calls (3 tool rounds + the answer), and the real Q-09 run also used 4. The hardest questions (three districts: Q-11, Q-13, Q-20) need about 4–6. So 10 gives space for one or two retries after an error, but stops a loop that never ends and costs money. If a question hits the limit, it is marked unanswered.
- Where the logs are: `outputs/run<N>/<strategy>/<question id>.json` (for example `outputs/run1/S3/Q-09.json`). For S3 each file has every tool call (round, id, tool, arguments, result, time in ms), every model call (input tokens, output tokens, seconds) and the full conversation. `outputs/run<N>/summary.json` has the totals.
- Real Q-09 conversation compared with my A3 version, what is different: (log: `outputs/run0/S3/Q-09.json`)
  The real conversation was very close to my plan. Like in A3, the model used 4 model calls: round 1 asked for all 4 facts at once (4 × lookup), round 2 made the two densities (2 × calculate), round 3 the difference, and round 4 was the final answer `Millbrook | 0.6`. The tool returned the corrected area 921.4 (sources NR-05 and NR-16), so the trap did not reach the model.
  Differences:
  1. The tool call ids are random strings from OpenAI (for example `call_kCYAd3zggXFQavaoXmXNehyZ`), not `call_1`, `call_2`. My loop only copies them back, so this does not matter.
  2. In round 3 I expected the model to subtract the two results from round 2 (`49.0416… - 48.4859…`). Instead it wrote the whole formula again from the raw numbers: `37203 / 758.6 - 44675 / 921.4`. The result is the same (0.5556…), but it shows that round 2 was not really needed: the model could do it in one calculate call.
  3. The whole question used 3,728 input and 221 output tokens. Most of the input tokens come from sending the growing conversation again in every round.

### B4 — Three strategies

**What I kept the same:**

- model: `gpt-5.6-luna` for every call (Chat Completions API)
- the same 20 questions, and the same user message: the question + "Round the number to N decimal places" (N from the question, never the answer)
- the same answer format for all: last line `ANSWER: <name or yes/no> | <number>`, and the same code reads it (`parse_answer` in strategies.py)
- the same system rules about archived profiles, corrections and units (S1 and S2 get them with the documents, S3 gets tools that do it)
- temperature = 1.0 for every call (the model accepted it: `temperature_ok=True` in the summary)
- reasoning_effort = "none" for every call (needed for tools in Chat Completions; kept the same for S1 and S2)
- S1 and S2: the same system prompt and the same 17 documents; the only difference is one line ("give the answer directly" vs "think step by step") and k
- S2: k = 5, majority vote on (name, number rounded to N decimals)
- S3: no documents, only the two tools; round limit 10
- the same scoring code for all strategies (`is_correct` in run.py)
- prices for cost: $0.20 per 1M input tokens and $1.20 per 1M output tokens (OpenAI pricing page, gpt-5.6-luna, short context, checked on 18 October 2026). I do not count cached-input discounts, so the real cost can be a little lower.

**My rule for a correct answer** (written before the first full run):

The answer is correct if (1) the name is the same as in questions.json, ignoring upper/lower case and spaces, and (2) the number, rounded to the question's decimals, differs from `value` by at most 1 in the last digit (for example, for Q-09 with 1 decimal, 0.5, 0.6 and 0.7 are accepted). No ANSWER line = unanswered = wrong. I allow 1 in the last digit because a correct method can still round a little differently at the end. The code for this rule is `is_correct` in run.py.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 3 | 0 | 44460 | 239 | 1.19 | 24.07 | 0.0092 |
| 1 | S2 think and vote (k = 5) | 17 | 0 | 223200 | 14705 | 9.89 | 197.2 | 0.0623 |
| 1 | S3 tools | 20 | 0 | 60441 | 4336 | 5.21 | 106.73 | 0.0173 |
| 2 | S1 direct | 4 | 0 | 44460 | 263 | 1.07 | 24.56 | 0.0092 |
| 2 | S2 think and vote (k = 5) | 16 | 0 | 223200 | 14867 | 10.29 | 210.49 | 0.0625 |
| 2 | S3 tools | 20 | 0 | 61511 | 4316 | 5.05 | 105.77 | 0.0175 |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✗ | ✓ | ✓ |
| Q-02 | ✗ | ✓ | ✓ |
| Q-03 | ✗ | ✓ | ✓ |
| Q-04 | ✗ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✗ | ✓ | ✓ |
| Q-07 | ✗ | ✓ | ✓ |
| Q-08 | ✗ | ✓ | ✓ |
| Q-09 | ✗ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✗ | ✓ | ✓ |
| Q-12 | ✗ | ✓ | ✓ |
| Q-13 | ✓ | ✓ | ✓ |
| Q-14 | ✗ | ✓ | ✓ |
| Q-15 | ✗ | ✓ | ✓ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✗ | ✗ | ✓ |
| Q-18 | ✗ | ✓ | ✓ |
| Q-19 | ✗ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |

**Cost of all runs** run 1 cost $0.089 and run 2 cost $0.089 (S1 + S2 + S3, from the tables). With the Q-09 test run, the C1 run and `measure_tools.py`, everything cost about $0.19.

**Scoring rule, checked afterwards:** my rule allows 1 in the last digit. With an exact rule, S1 and S3 would not change much (S3 stays 20/20), but S2 would drop from 17 to 13 in run 1 (Q-07 18.49, Q-09 0.5, Q-14 4.8, Q-18 40012 are all 1 off) and from 16 to 14 in run 2. So the rule helps S2 the most, and the real gap between S2 and S3 is even bigger than my table shows.

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I ran S3 again on 5 questions (Q-03, Q-08, Q-09, Q-11, Q-20) with the `lookup` description changed to "Looks things up." Everything else stayed the same. Logs: `outputs/runc1/S3/`.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-03 | 7 (4 rounds, 4,004 input tokens) | 6 (3 rounds, 2,477) | Lindenmoor \| 5.3 ✓ | Lindenmoor \| 5.3 ✓ |
| Q-08 | 4 (3 rounds, 2,479) | 4 (3 rounds, 2,194) | Brightwater \| 72.46 ✓ | Brightwater \| 72.46 ✓ |
| Q-09 | 7 (4 rounds, 3,728) | 7 (4 rounds, 3,348) | Millbrook \| 0.6 ✓ | Millbrook \| 0.6 ✓ |
| Q-11 | 10 (3 rounds, 3,045) | 10 (4 rounds, 3,950) | Redfen \| 56.1 ✓ | Redfen \| 56.1 ✓ |
| Q-20 | 10 (4 rounds, 4,532) | 10 (4 rounds, 4,152) | Ashgrove \| 2993 ✓ | Ashgrove \| 2993 ✓ |

**What changed:** almost nothing. All 5 answers stayed correct. The `lookup` calls were **exactly the same** in both versions: the same districts and the same fields in the same order (for example, in Q-08 both versions asked for Brightwater water, Millbrook water and `{"field": "water_tariff_2025"}`). Only the number of `calculate` calls changed a little (Q-03: 7 → 6 calls, Q-11: 3 → 4 rounds), and the same small changes also happen between run 1 and run 2 with my normal description, so they are random. The vague version used fewer input tokens in 4 of 5 questions, because the short description is 95 tokens smaller in every request (measured with `measure_tools.py`).

**Why:** the description is not the only thing the model reads. The parameters stayed the same: `field` has an `enum` with 10 clear names (`population_2025`, `area_km2`, `water_use_2025_megalitres`, ...), and `district` still says "Exact district name". The system prompt also says "use the lookup tool for every fact". So the model still knew what to ask for. And the hard part, the traps, is in my code, not in the description: `lookup` itself skips archived profiles, uses NR-16 and changes cubic metres to megalitres. The model does not need to know about them. In Part A I said that the most important assumption is that `lookup` handles the traps; this test supports it: a worse description did not let any trap through.

**Where this stops:** the test only shows that the description does not matter **when the schema is this clear**. If `field` were a free string without an `enum`, or if `lookup` did not handle the traps itself, the description would be the only place to explain them, and I expect a vague description would then cause wrong fields and errors. Five questions is also small: I can say the vague description did not break these 5, not that it never matters.

### C2 — Three mistakes explained

**S1 — Q-09, run 1: `Brightwater | 2.2` (correct: `Millbrook | 0.6`)**

The whole reply in `outputs/run1/S1/Q-09.json` is:

```
'ANSWER: Brightwater | 2.2'
```

It has only 12 output tokens. The model did not write any number, density or calculation; it wrote the answer line at once. To answer it needs two divisions (44,675 / 921.4 and 37,203 / 758.6) and a subtraction, and the two densities are very close (48.49 and 49.04). A language model does not compute; it predicts the next token. Without any written steps, it has to "guess" the result of two divisions in one go, so both the name and the number are wrong. S1 was correct only on Q-10, Q-13 and Q-16 in run 1. Q-10 (founding years, 1845 − 1837) and Q-16 (a sum of areas) need almost no arithmetic.

**S2 — Q-05, run 1: `Coldharbour | 14232` (correct: 14235)**

The 5 samples in `outputs/run1/S2/Q-05.json` were:

```
14232, 14225, 14230, 14328, 14231   (votes for the winner: 1)
```

The name was correct in all 5, and the method too. One sample shows:

```
Stonecairn: 2,884,600,000 ÷ 14,926 = 193,283.13 tenge per resident.
Coldharbour: 2,366,900,000 ÷ 11,407 = 207,514.68 tenge per resident.
Difference: 207,514.68 − 193,283.13 = 14,231.55
```

The real values are 193,260.08 and 207,495.40. The model's long division is off by about 20 in each district, and the errors do not cancel. All 5 samples had **different** wrong numbers, and none had 14235. So every answer got 1 vote, and the "winner" was just the first one.

**Why voting fixes some mistakes but not others:** voting helps when the model gives the correct answer more often than any single wrong answer. Then the random mistakes spread out and the correct answer wins. That is why S2 (with step-by-step reasoning and voting) got 16–17/20 while S1 got 3–4/20. It does not work when the model is **wrong in most samples**, because it cannot do the division correctly. In Q-05 the correct answer appeared 0 times out of 5, in Q-17 1 time (884, but 890, 887, 886, 889 also appeared once, and 890 came first), in Q-20 1 time (2993), while 2997 appeared 2 times and won. Asking 5 times gives 5 tries of the same weak skill. It reduces the random noise, but it cannot remove a mistake that the model makes almost every time.

**Why a calculator removes mistakes the model cannot avoid on its own:** S3 got the same Q-05 right in both runs (`14235`) because `calculate` did `2366.9 * 1000000 / 11407` exactly. The model only has to choose the right numbers and the right formula, which it does well. Doing 7-digit division with words is the part it does badly. With the calculator the arithmetic error is zero, whatever k is.

**S3 — no wrong answer, so its most expensive question: Q-20, run 1 (4,532 input + 331 output tokens)**

From `outputs/run1/S3/Q-20.json`:

```
model call 1: input  572, output 163   -> 6 × lookup (budget and population of 3 districts)
model call 2: input 1163, output  94   -> 3 × calculate ("9284.5 * 1000000 / 52904", ...)
model call 3: input 1361, output  31   -> calculate("178490.46970728386 - 175497.12687131407")
model call 4: input 1436, output  43   -> ANSWER: Ashgrove | 2993
```

**Why it needed 4 rounds:** each round depends on the one before. The model cannot compute budget per resident before it has the budget and population (round 1), and it cannot compute the difference before it has the three values (round 2). Round 3 is the difference, and round 4 is the answer. The model did put independent calls together: 6 lookups in one round and 3 divisions in one round. So 4 is the minimum for this chain, except that round 3 could have been joined with round 2.

**Why each round costs more than the one before:** the API has no memory. Every call sends the **whole conversation again**: the system prompt, the question, the 430 tokens of tool definitions, and every earlier tool call and result. Round 1 is 572 tokens (about 140 of prompt + 430 of tools). Round 2 adds the 6 lookup results: +591 tokens. Rounds 3 and 4 add the calculate results. So the input grows 572 → 1,163 → 1,361 → 1,436, and the total is the sum: 4,532. The cost of a question grows faster than the number of rounds.

### C3 — Which strategy I would use, and what would change it

**I would use S3 (tools).**

| (average of run 1 and run 2) | S1 direct | S2 think and vote | S3 tools |
|---|---:|---:|---:|
| Correct /20 | 3.5 | 16.5 | **20** |
| Tokens per question (in + out) | 2,235 | 11,899 | 3,265 |
| Cost for 20 questions | $0.009 | $0.062 | $0.017 |
| Median seconds per question | 1.1 | 10.1 | 5.1 |

S3 was the most accurate in both runs (20/20 and 20/20), and it is also **3.6 times cheaper** and about **2 times faster** than S2. So it wins against S2 on all three measures at once. This is not luck: the two things that make the questions hard, the traps in the documents and the big-number arithmetic, are both moved out of the model into code (`lookup` and `calculate`), which I tested.

**Why not S2:** it is 16–17/20, but its mistakes (Q-05, Q-17, Q-20, Q-14) are exactly the arithmetic mistakes that voting cannot fix (see C2). It also sends the documents 5 times, so it uses 223,200 input tokens instead of 60,441, and it is the slowest (10 s per question). I would pay more for a worse result.

**Why not S1:** it is the cheapest and fastest (1 s, $0.009), but 3–4/20 is not usable. A wrong answer that looks sure is worse than no answer.

**Situations that would change my choice:**

1. **1,000 times more documents.** S1 and S2 put all documents in the prompt: 2,300 tokens would become about 2.3 million, more than fits in the context, and S2 would cost about 1,000 times more. S3 does not get more expensive, because `lookup` returns one sentence, not the documents. **S3 even more clearly** (but `lookup` must get an index, see final question 6).
2. **Questions with no arithmetic, or about facts that are not in my `enum`** (for example “Which river is Kelmarsh on?” or “Who is the mayor of Ossbridge?”). Then the calculator gives nothing, and my `lookup` cannot even answer a field it does not know. S1 already answered the easy questions Q-10, Q-13, Q-16 correctly. I would pick **S2** (or S1 if the budget is very small), because the model reads the full text itself.
3. **A strict time limit, for example under 2 seconds per answer.** Only S1 is that fast (1.1 s). S3 needs 3–4 model calls one after another, so about 5 s. If the limit is strict, I would use **S1**, but only for simple questions; for questions like these I would rather say "it cannot be done in time" than give 3/20.
4. **A very small budget but accuracy still needed.** S3 is already the cheapest strategy that is accurate, so I would keep **S3**. I could make it cheaper by asking the model to write the whole formula in one `calculate` call (like it did itself in Q-09 round 3), which removes one round.

### C4 — How sure I can be

**How different were the two runs?** Very little. S1: 3 → 4 (Q-01 changed: 4.7 instead of 4.6, accepted by my rule). S2: 17 → 16 (Q-14 changed: 4.8 → 4.7, correct is 4.9). S3: 20 → 20, no question changed. So between runs a strategy changed by at most **1 question**. Token counts were almost the same (S2: 223,200 input both times; S3: 60,441 vs 61,511), and the cost was the same to 3 decimals.

**Is the difference between my two best strategies bigger than that?** Yes. S3 − S2 is 3 questions in run 1 and 4 in run 2, bigger than the 1-question change between runs, and always in the same direction. Looking at single questions: there were 4 different questions where S2 was wrong and S3 right (Q-05, Q-14, Q-17, Q-20), and **no** question where S2 was right and S3 wrong. If the two strategies were really equally good, the chance that all 4 such questions go the same way is 0.5⁴ ≈ 6%. So the evidence is fairly strong, but not perfect. For S1 against the others, the gap (13–17 questions) is so big that I am sure about it.

**What this cannot show:**
- With 20 questions, one question is 5 percentage points. If S2's true accuracy is about 85%, its standard error with n = 20 is about √(0.85 × 0.15 / 20) ≈ 8 points, so the run-to-run noise is about ±1.6 questions.
- S3 got 20/20, but this does not mean it is perfect. Even a strategy with 95% accuracy gets 20/20 about 36% of the time (0.95²⁰).
- All 20 questions are the same type (two or three districts, one number), and I wrote `lookup` for exactly these fields. On new kinds of questions S3 could be much worse (C3, situation 2).
- The scoring rule matters: with an exact rule S2 would be 13–14/20, not 16–17.
- Only one model and one temperature.

**How many questions would I need?** To tell 85% (S2) from 95–100% (S3) reliably, the standard error of the difference should be about 5 points or less. With p ≈ 0.85 that needs about √(0.85 × 0.15 / n) ≤ 0.04, so **n ≈ 80–100 questions**, ideally with 3 or more runs each, so I could also measure the run-to-run spread. To compare S2 with a stronger S2 (for example k = 10), where the difference is maybe 1–2 questions in 20, I would need several hundred questions.

### Final questions

1. **When the model sends a `tool_calls` message, what has actually run so far?** Nothing in my code. The model only produced text that says which function it wants and with which arguments (for example, in Q-09 round 1 it asked for 4 lookups). No lookup has run, no file was read, and no number was found. My loop decides if it runs anything; it runs the functions and sends the results back, and only then does the model see 921.4.

2. **Why does `arguments` arrive as a string, and what goes wrong if you pass it straight into your function?** The model can only produce text (tokens), so the arguments come as JSON written as text, for example `'{"district": "Brightwater", "field": "area_km2"}'`. This text can be broken JSON, have a missing key, an extra key or a wrong type. If I passed the string straight into `lookup`, it would get one long string instead of two arguments; and if I did `json.loads` and `**args` without checks, an extra key would crash the program. My `check_arguments` reads the JSON, checks required and unknown keys, and sends an error back to the model instead of running the tool (my fake-model test sent `'not json'` and got `{"error": "arguments are not valid JSON: ..."}`).

3. **How many tokens do your two tool definitions add to every S3 request?** I measured it with `measure_tools.py`: the same message used 9 prompt tokens without tools and 439 with my two tools, so they add **430 tokens to every request**. With the vague description they add 335, so my longer `lookup` description costs 95 more tokens. In Q-20 (4 model calls), 4 × 430 = 1,720 of the 4,532 input tokens, about 38%, were only the tool definitions.

4. **How much more did S2 cost than S1?** **6.8 times** more: $0.0623 vs $0.0092 in run 1 (the same in run 2). Two reasons: input is 5 times bigger (223,200 vs 44,460 tokens), because the documents are sent 5 times; and output is 61 times bigger (14,705 vs 239 tokens), because S2 writes all steps while S1 writes only the answer line. Output tokens are also 6 times more expensive than input ($1.20 vs $0.20 per million).

5. **Which question needed the most rounds in S3, and why?** No question needed more than 4 model calls. In run 1, Q-03, Q-04, Q-09, Q-17, Q-19 and Q-20 used 4; the others used 3. 4 calls means: get the facts → compute a value per district → compute the difference → answer. The questions with 3 calls are the ones where the model wrote one bigger expression (for example the whole difference at once). The number of rounds depends on how many steps **depend on each other**, not on how many facts there are: Q-20 needs 6 facts but still only 4 calls, because the model asked for all 6 in one round. My limit of 10 was never reached.

6. **What would you change in `lookup` if there were 100,000 documents?** Now it reads all files at start and searches the text with regular expressions. With 100,000 documents I would extract the facts **once** into a table or database (district id, field, year, value, unit, source) and only look them up, instead of running regex at each call. Names would need an index for fuzzy search, and there could be many districts with the same name, so `lookup` should return an id and ask the model to choose. Corrections and archived profiles would need dates and a clear "valid from / to" field. For questions about facts that are not in the table, I would add a second search tool (keyword or embedding search) that returns only the top few sentences, so the output stays small.

7. **What stops your `calculate` from running dangerous code? Could the model still make it misbehave?** It never uses `eval` or `exec`. It uses `ast.parse` only to read the text into a tree, and my `evaluate` function walks the tree and allows only `int`/`float` numbers, `+ - * / **` and a minus sign. Everything else (`Call`, `Attribute`, `Name`, strings, `True`) gives an error, so `__import__('os')...` and `(1).__class__` are refused before anything runs. Freezing is blocked by a limit on the text (200 characters), on the exponent (100) and on every result (10¹⁵), so `9**9**9` is refused at once (tested in B2). The model can still make it give a **wrong** answer: if it writes the wrong numbers or forgets `* 1000000`, `calculate` computes exactly that. The limits can also refuse a correct but very long expression.

8. **For which kind of question did tools help most, and for which did they not help at all?** They helped most on questions with **big-number division** and **traps**. Q-05, Q-17 and Q-20 (tenge per resident, millions divided by tens of thousands) were wrong in S2 in both runs and right in S3 in both runs. Q-09 (the NR-16 correction) and Q-03 (cubic metres) were right in S3 because `lookup` fixed them. Tools did not help at all on Q-10, Q-13 and Q-16: the founding-year difference (1845 − 1837 = 8), the biggest population loss in percent, and a simple sum of areas. Even S1, without any reasoning, got them right in both runs; S3 only made them slower (about 4.5 s vs 1 s) and more expensive.