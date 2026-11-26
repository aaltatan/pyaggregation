# Installation

pyaggregation needs **Python 3.12 or newer**.

=== "uv"

    ```bash
    uv add pyaggregation
    ```

=== "pip"

    ```bash
    pip install pyaggregation
    ```

Its only dependency is [pyvocabulary](https://pypi.org/project/pyvocabulary/), a small
package by the same author that provides name validation, JSON-path notes and JSON Schema
helpers.

## Optional companions

Building reports from JSON needs a compiler for the values (`of`), conditions (`where`) and
group keys (`group_by`) inside it. Any object with a `compile()` method works, and two
packages by the same author fit those slots:

- [pyformula](https://pypi.org/project/pyformula/) for values, so `of` can be arithmetic such
  as `{"operator": "multiply", "expressions": ["pay", 12]}`.
- [pyspecification](https://pypi.org/project/pyspecification/) for conditions, so `where`
  can be a rule such as `{"name": "department__eq", "args": ["IT"]}`.

=== "uv"

    ```bash
    uv add pyformula pyspecification
    ```

=== "pip"

    ```bash
    pip install pyformula pyspecification
    ```

## Check it works

```python
from pyaggregation import count, total

report = total(len, name="letters") & count(name="words")

assert report(["fold", "every", "word"]) == {"letters": 13, "words": 3}
```
