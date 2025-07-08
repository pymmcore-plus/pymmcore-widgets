from pymmcore_widgets._icons import StandardIcon


def test_standard_icon() -> None:
    """Test that StandardIcon can be instantiated."""
    for icon in StandardIcon:
        assert not icon.icon().isNull()
        assert ":" in str(icon)
