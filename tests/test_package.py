import pyaggregation


class TestPackage:
    def test_exports_are_importable(self):
        assert all(hasattr(pyaggregation, name) for name in pyaggregation.__all__)
