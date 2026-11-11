import ast
import re
from contextlib import redirect_stdout
from io import StringIO
from itertools import takewhile
from pathlib import Path

README = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")

# the opening teaser uses names that Quick start defines
EXAMPLES = README.partition("## Quick start")[2]

BLOCKS = re.findall(r"^```python\n(.*?)^```", EXAMPLES, re.MULTILINE | re.DOTALL)


def shown_output(lines: list[str], statement: ast.stmt) -> str:
    """Return the comment lines directly under `statement`: what the README says it outputs."""
    comments = takewhile(lambda line: line.startswith("#"), lines[statement.end_lineno :])
    return " ".join(comment.removeprefix("#").strip() for comment in comments)


def run(statement: ast.stmt, namespace: dict[str, object], *, expect_output: bool) -> str:
    """Run `statement` like a REPL and return what it printed, echoed or raised."""
    code = compile(ast.Interactive([statement]), "README.md", "single")
    output = StringIO()

    with redirect_stdout(output):
        try:
            exec(code, namespace)  # noqa: S102
        except Exception as error:
            if not expect_output:
                raise

            output.write(f"{type(error).__name__}: {error}")

    return " ".join(output.getvalue().split())


class TestReadme:
    def test_examples_run_and_show_their_real_output(self):
        namespace: dict[str, object] = {"__name__": "readme"}
        checked = 0

        for block in BLOCKS:
            lines = block.splitlines()

            for statement in ast.parse(block).body:
                shown = shown_output(lines, statement)
                actual = run(statement, namespace, expect_output=bool(shown))

                if shown:
                    checked += 1
                    assert actual == " ".join(shown.split()), lines[statement.lineno - 1]

        assert checked > 20
