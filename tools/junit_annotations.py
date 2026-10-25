#!/usr/bin/env python3
"""Turn failed tests of a pytest JUnit XML report into GitHub Actions annotations
(::error file=...,line=...::message), so failures are readable on the run page without logs.

    python tools/junit_annotations.py test-results.xml
"""
import sys
import xml.etree.ElementTree as ET


def esc(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(path: str) -> int:
    root = ET.parse(path).getroot()
    n = 0
    for case in root.iter("testcase"):
        for kind in ("failure", "error"):
            el = case.find(kind)
            if el is None:
                continue
            n += 1
            file = case.get("file") or "tests/" + case.get("classname", "").split(".")[-1] + ".py"
            msg = (el.get("message") or "") + "\n" + "\n".join((el.text or "").splitlines()[-25:])
            print(f"::error file={file},line={case.get('line', 1)},title={case.get('name')}::{esc(msg[:3500])}")
    print(f"{n} failing test(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "test-results.xml"))
