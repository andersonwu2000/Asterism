"""state.programme — Programme store contract (research mode P1).

Guards: v30 table exists on fresh DBs; four-section proposal contract
(teaching rejections); Proof over-length warning (warn, never block);
revision chain semantics (passed rows advance rev, rejected rows keep
the candidate number + dialogue); rejection notice surfaces only while
the latest resolved row is a rejection; PROGRAMME.md render carries
rev header + reservations and no revision log.
"""
from pathlib import Path

from Tooling.state import db
from Tooling.state import programme


def _fresh(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _body(proof="The route holds because of X.",
          argument="Brick A unblocks the named vector.",
          roadmap="1. Re-prove s23259 without the exists."):
    return ("# Close the gcd gap\n"
            "## Argument\n" + argument + "\n"
            "## Proof\n" + proof + "\n"
            "## Roadmap\n" + roadmap + "\n")


# ---------------------------------------------------------------- parse

def test_parse_ok():
    sections, err = programme.parse_proposal(_body())
    assert err is None
    assert sections["title"] == "Close the gcd gap"
    assert "named vector" in sections["argument"]
    assert sections["proof"].startswith("The route holds")


def test_parse_missing_section_teaches():
    body = "# T\n## Argument\na\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "## Proof" in err


def test_parse_requires_title_line():
    body = "## Argument\na\n## Proof\np\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "# <Title>" in err


def test_parse_out_of_order_rejected():
    body = "# T\n## Proof\np\n## Argument\na\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "order" in err


def test_parse_duplicate_section_rejected():
    body = _body() + "## Roadmap\nagain\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "duplicate" in err


def test_parse_empty_section_rejected():
    body = "# T\n## Argument\na\n## Proof\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "## Proof" in err and "empty" in err


def test_length_warning_thresholds():
    """07-29 bloat ruling: three absolute surfaces — Proof (readability,
    most headroom), Argument (the observed bloat surface), package
    total. All warn-only, never a block."""
    ok, _ = programme.parse_proposal(_body())
    assert programme.length_warning(ok) is None

    long_proof, _ = programme.parse_proposal(
        _body(proof="x" * (programme.PROOF_WARN_CHARS + 1)))
    warn = programme.length_warning(long_proof)
    assert warn and "PROOF LENGTH WARNING" in warn
    assert "ARGUMENT" not in warn

    body = _body(argument="a" * (programme.ARGUMENT_WARN_CHARS + 1))
    long_arg, _ = programme.parse_proposal(body)
    warn = programme.length_warning(long_arg, body)
    assert warn and "ARGUMENT LENGTH WARNING" in warn
    assert "PROOF LENGTH" not in warn

    body = _body(roadmap="r" * (programme.DOC_WARN_CHARS + 1))
    long_doc, _ = programme.parse_proposal(body)
    warn = programme.length_warning(long_doc, body)
    assert warn and "PROPOSAL LENGTH WARNING" in warn


# ---------------------------------------------------------------- store

def test_rev_chain_and_rejection_rows(tmp_path):
    c = _fresh(tmp_path)
    assert programme.current_rev(c, "p") is None
    assert programme.next_rev_number(c, "p") == 1

    rev = programme.record_pass(
        c, "p", _body(), {"verdict": "pass", "reservations": []},
        [{"round": 1, "role": "adversary", "text": "pass"}], 1, "batch-1")
    assert rev == 1
    assert programme.current_rev(c, "p")["rev"] == 1

    # A rejected proposal aims at rev 2 but the chain does not advance.
    programme.record_rejection(
        c, "p", _body(), [{"round": 1, "role": "adversary",
                           "text": "refuted"}], 4)
    assert programme.current_rev(c, "p")["rev"] == 1
    assert programme.next_rev_number(c, "p") == 2

    notice = programme.rejection_notice(c, "p")
    assert notice and "rev 2" in notice and "4 round" in notice

    # A later pass clears the notice and advances the chain.
    rev2 = programme.record_pass(
        c, "p", _body(), {"verdict": "pass",
                          "reservations": ["watch the sign"]},
        [], 2, "batch-2")
    assert rev2 == 2
    assert programme.rejection_notice(c, "p") is None


def test_rejection_notice_absent_before_any_row(tmp_path):
    c = _fresh(tmp_path)
    assert programme.rejection_notice(c, "p") is None


# --------------------------------------------------------------- render

def test_render_none_before_bootstrap(tmp_path):
    c = _fresh(tmp_path)
    assert programme.render(c, "p", tmp_path) is None


def test_render_header_and_reservations(tmp_path):
    c = _fresh(tmp_path)
    programme.record_pass(
        c, "p", _body(), {"verdict": "pass",
                          "reservations": ["watch the sign"]},
        [], 1, "batch-1")
    path = programme.render(c, "p", tmp_path)
    assert path == tmp_path / "PROGRAMME.md"
    text = path.read_text(encoding="utf-8")
    assert "rev 1" in text
    assert "watch the sign" in text
    assert "DO NOT EDIT" in text
    assert "# Close the gcd gap" in text
    # No revision log in the render (design §2 round 8/11 ruling).
    assert "rev 0" not in text
