from solution.normalize.phone import normalise_phone


def test_plain_10_digit():
    assert normalise_phone("9876543210") == "+919876543210"


def test_plus_91_with_spaces():
    assert normalise_phone("+91 98765 43210") == "+919876543210"


def test_leading_zero():
    assert normalise_phone("09876543210") == "+919876543210"


def test_91_prefix_dash():
    assert normalise_phone("91-98765-43210") == "+919876543210"


def test_invalid_prefix():
    assert normalise_phone("5876543210") is None


def test_too_short():
    assert normalise_phone("987654321") is None


def test_landline():
    assert normalise_phone("022-2345-6789") is None


def test_empty():
    assert normalise_phone("   ") is None
