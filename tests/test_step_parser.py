"""Tests for the STEP file metadata parser."""

from openvault.step_parser import StepMetadata, is_step_file, parse_step_header

SAMPLE_STEP_HEADER = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('A mechanical part'),'2;1');
FILE_NAME('bracket.step','2024-11-15T10:30:00',('John Doe'),
  ('Acme Corp'),'FreeCAD 0.21','FreeCAD STEP exporter','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
"""

MINIMAL_STEP = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('','',(''),(''),'','','');
FILE_SCHEMA((''));
ENDSEC;
DATA;
"""


def test_parse_full_header():
    meta = parse_step_header(SAMPLE_STEP_HEADER)
    assert meta.description == "A mechanical part"
    assert meta.name == "bracket.step"
    assert meta.author == "John Doe"
    assert meta.organization == "Acme Corp"
    assert meta.originating_system == "FreeCAD STEP exporter"
    assert meta.schema == "AUTOMOTIVE_DESIGN"
    assert meta.timestamp == "2024-11-15T10:30:00"


def test_parse_minimal_header():
    meta = parse_step_header(MINIMAL_STEP)
    assert meta.description == ""
    assert meta.name == ""


def test_parse_no_header():
    meta = parse_step_header("just some random text")
    assert meta.name == ""
    assert meta.summary() == "(no metadata)"


def test_summary():
    meta = StepMetadata(
        name="part.step",
        originating_system="SolidWorks",
        author="Alice",
        timestamp="2024-01-01",
    )
    s = meta.summary()
    assert "part.step" in s
    assert "SolidWorks" in s
    assert "Alice" in s


def test_as_dict_excludes_empty():
    meta = StepMetadata(name="test.step")
    d = meta.as_dict()
    assert "name" in d
    assert "author" not in d


def test_is_step_file():
    assert is_step_file("part.step")
    assert is_step_file("ASSEMBLY.STP")
    assert not is_step_file("model.stl")
    assert not is_step_file("readme.md")
