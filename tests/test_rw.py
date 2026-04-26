from bacpypes3.primitivedata import Real, Unsigned, Integer, CharacterString, Boolean
from bacpypes3.basetypes import BinaryPV
from bacnet_explorer.rw import _coerce


def test_coerce_active():
    assert isinstance(_coerce("active"), BinaryPV)
    assert str(_coerce("active")) == "active"

def test_coerce_inactive():
    assert isinstance(_coerce("inactive"), BinaryPV)

def test_coerce_positive_int():
    v = _coerce("42")
    assert isinstance(v, Unsigned)

def test_coerce_negative_int():
    v = _coerce("-5")
    assert isinstance(v, Integer)

def test_coerce_float():
    v = _coerce("22.5")
    assert isinstance(v, Real)
    assert abs(float(v) - 22.5) < 0.001

def test_coerce_true():
    assert isinstance(_coerce("true"), Boolean)

def test_coerce_false():
    assert isinstance(_coerce("False"), Boolean)

def test_coerce_string_fallback():
    v = _coerce("SITE-001")
    assert isinstance(v, CharacterString)
