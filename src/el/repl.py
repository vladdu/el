"""Interactive REPL: a thin loop over `Session`.

Lines are accumulated until they form complete forms, then run; each result's
rendering is printed followed by a blank line, as in the memo.
"""

import sys
from typing import TextIO

from el.reader import IncompleteInput, ReadError, read_all
from el.session import Session


def repl(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    session = Session()
    pending = ""
    for line in stdin:
        pending += line
        try:
            read_all(pending)
        except IncompleteInput:
            continue
        except ReadError:
            pass  # Session reports it as an Error result
        for result in session.run(pending):
            print(result.render(), end="\n\n", file=stdout, flush=True)
        pending = ""


def main() -> None:
    try:
        repl()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
