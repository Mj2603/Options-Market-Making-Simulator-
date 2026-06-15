from options_mm.risk.inventory import InventoryManager


def test_inventory_within_limits():
    inv = InventoryManager(max_position=100)
    inv.on_fill("OPT1", 50)
    assert inv.position("OPT1") == 50
    assert inv.within_limit("OPT1")


def test_inventory_exceeds_limit():
    inv = InventoryManager(max_position=100)
    inv.on_fill("OPT1", 80)
    assert not inv.would_exceed("OPT1", 30)
    inv.on_fill("OPT1", 30)
    assert inv.position("OPT1") == 110
    assert not inv.within_limit("OPT1")
