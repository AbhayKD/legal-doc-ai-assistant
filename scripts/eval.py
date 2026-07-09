#!/usr/bin/env python3
"""
Evaluation harness for the Document Q&A system.

Usage:
    Ensure the backend is running on localhost:8000, then run:

        python scripts/eval.py

    Or directly (the script is executable):

        ./scripts/eval.py

    The script will:
      1. Create a new conversation
      2. Upload the 3 synthetic documents from synthetic-docs/
      3. Ask 5 pre-defined questions about the documents
      4. Check each answer against expected keyword criteria
      5. Report pass/fail per question and an overall score

    Exit code 0 if all tests pass, 1 otherwise.
"""

import json
import sys
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
SYNTHETIC_DOCS_DIR = Path(__file__).resolve().parent.parent / "synthetic-docs"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Test cases: (question, list of keyword groups)
# Each keyword group is a list of alternatives — at least one must appear in the answer.
TEST_CASES = [
    {
        "question": "What is the annual rent for the property at 100 Bishopsgate?",
        "criteria": [
            ["850,000", "850000"],
        ],
    },
    {
        "question": "What are the break clause conditions?",
        "criteria": [
            ["twelve months", "12 months"],
            ["vacant possession"],
        ],
    },
    {
        "question": "Who owns the property at Victoria Park?",
        "criteria": [
            ["Victoria Park Developments"],
        ],
    },
    {
        "question": "What environmental risks were identified and what is the estimated remediation cost?",
        "criteria": [
            ["printing", "contamination"],
            ["50,000", "200,000"],
        ],
    },
    {
        "question": "What restrictive covenants are on the title for Lot 7?",
        "criteria": [
            ["industrial"],
            ["4 storeys", "four storeys", "four (4)"],
        ],
    },
]


def parse_sse_stream(response: httpx.Response) -> str:
    """Parse an SSE stream and return the final message content."""
    accumulated = ""
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        data_str = line[len("data: "):]
        if data_str.strip() == "[DONE]":
            break
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        if data.get("type") == "content":
            accumulated += data.get("content", "")
        elif data.get("type") == "message":
            accumulated = data.get("message", {}).get("content", accumulated)
        elif data.get("type") == "done":
            break
    return accumulated


def check_criteria(answer: str, criteria: list[list[str]]) -> tuple[bool, list[str]]:
    """
    Check if the answer meets all criteria.
    Each criterion is a list of alternatives (at least one must be present).
    Returns (all_passed, list_of_failures).
    """
    answer_lower = answer.lower()
    failures = []
    for alternatives in criteria:
        if not any(alt.lower() in answer_lower for alt in alternatives):
            failures.append(f"Missing one of: {alternatives}")
    return len(failures) == 0, failures


def main() -> None:
    print(f"\n{BOLD}Document Q&A Evaluation Harness{RESET}")
    print("=" * 50)

    # Step 1: Create a conversation
    print(f"\n{BOLD}[1/3] Creating conversation...{RESET}")
    try:
        resp = httpx.post(f"{BASE_URL}/api/conversations", timeout=10.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        print(f"{RED}ERROR: Cannot connect to {BASE_URL}. Is the backend running?{RESET}")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"{RED}ERROR: Failed to create conversation: {e}{RESET}")
        sys.exit(1)

    conversation = resp.json()
    conversation_id = conversation["id"]
    print(f"  Created conversation: {conversation_id}")

    # Step 2: Upload synthetic documents
    print(f"\n{BOLD}[2/3] Uploading documents...{RESET}")
    doc_files = sorted(SYNTHETIC_DOCS_DIR.glob("*.pdf"))
    if not doc_files:
        print(f"{RED}ERROR: No PDF files found in {SYNTHETIC_DOCS_DIR}{RESET}")
        sys.exit(1)

    for doc_path in doc_files:
        with open(doc_path, "rb") as f:
            files = {"file": (doc_path.name, f, "application/pdf")}
            resp = httpx.post(
                f"{BASE_URL}/api/conversations/{conversation_id}/documents",
                files=files,
                timeout=30.0,
            )
            resp.raise_for_status()
        print(f"  Uploaded: {doc_path.name}")

    # Step 3: Ask questions and evaluate answers
    print(f"\n{BOLD}[3/3] Running test questions...{RESET}")
    print("-" * 50)

    passed = 0
    total = len(TEST_CASES)

    for i, test_case in enumerate(TEST_CASES, 1):
        question = test_case["question"]
        criteria = test_case["criteria"]

        print(f"\n  Q{i}: {question}")

        # Send the question via SSE streaming endpoint
        with httpx.stream(
            "POST",
            f"{BASE_URL}/api/conversations/{conversation_id}/messages",
            json={"content": question},
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            answer = parse_sse_stream(response)

        if not answer:
            print(f"  {RED}FAIL{RESET} - No answer received")
            print(f"    Answer: (empty)")
            continue

        # Truncate answer for display
        display_answer = answer[:200] + "..." if len(answer) > 200 else answer
        print(f"  Answer: {display_answer}")

        # Check criteria
        success, failures = check_criteria(answer, criteria)

        if success:
            print(f"  {GREEN}PASS{RESET}")
            passed += 1
        else:
            print(f"  {RED}FAIL{RESET}")
            for failure in failures:
                print(f"    - {failure}")

    # Final score
    print("\n" + "=" * 50)
    color = GREEN if passed == total else RED
    print(f"{BOLD}Score: {color}{passed}/{total} passed{RESET}")
    print("=" * 50 + "\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
