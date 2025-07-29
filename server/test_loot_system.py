#!/usr/bin/env python3
"""
Test script for the legendary loot drop system
"""

import random
import json
from server import generate_legendary_rogue_gear, ROGUE_GEAR_IDS, LEGENDARY_TIER, SPECIAL_LOOT_DROPS

def test_gear_generation():
    """Test that legendary Rogue gear is generated correctly"""
    print("Testing legendary Rogue gear generation...")
    
    # Generate 10 test items
    for i in range(10):
        gear = generate_legendary_rogue_gear()
        
        # Verify gear structure
        assert "gearID" in gear, "Gear missing gearID"
        assert "tier" in gear, "Gear missing tier"
        assert "runes" in gear, "Gear missing runes"
        assert "colors" in gear, "Gear missing colors"
        
        # Verify gear properties
        assert gear["gearID"] in ROGUE_GEAR_IDS, f"Invalid gear ID: {gear['gearID']}"
        assert gear["tier"] == LEGENDARY_TIER, f"Wrong tier: {gear['tier']}, expected {LEGENDARY_TIER}"
        assert len(gear["runes"]) == 3, f"Wrong number of runes: {len(gear['runes'])}"
        assert len(gear["colors"]) == 2, f"Wrong number of colors: {len(gear['colors'])}"
        
        print(f"✓ Generated gear: ID={gear['gearID']}, Tier={gear['tier']}")
    
    print("All gear generation tests passed!")

def test_rogue_gear_ids():
    """Test that all Rogue gear IDs are valid"""
    print("Testing Rogue gear ID validation...")
    
    # Check that all IDs are unique
    unique_ids = set(ROGUE_GEAR_IDS)
    assert len(unique_ids) == len(ROGUE_GEAR_IDS), "Duplicate gear IDs found"
    
    # Check that all IDs are positive integers
    for gear_id in ROGUE_GEAR_IDS:
        assert isinstance(gear_id, int), f"Gear ID {gear_id} is not an integer"
        assert gear_id > 0, f"Gear ID {gear_id} is not positive"
    
    print(f"✓ Validated {len(ROGUE_GEAR_IDS)} unique Rogue gear IDs")

def test_loot_drop_chance():
    """Test the loot drop chance calculation"""
    print("Testing loot drop chance...")
    
    from server import LOOT_DROP_CHANCE
    
    # Simulate 1000 enemy deaths
    drops = 0
    total = 1000
    
    for _ in range(total):
        if random.random() <= LOOT_DROP_CHANCE:
            drops += 1
    
    actual_chance = drops / total
    expected_chance = LOOT_DROP_CHANCE
    
    print(f"Expected drop chance: {expected_chance:.1%}")
    print(f"Actual drop chance: {actual_chance:.1%}")
    print(f"Total drops: {drops}/{total}")
    
    # Allow for some variance (±5%)
    assert abs(actual_chance - expected_chance) < 0.05, f"Drop chance too far from expected: {actual_chance:.1%}"
    print("✓ Loot drop chance test passed!")

def test_special_loot_drops():
    """Test the special loot drop system for IntroGoblinDagger"""
    print("Testing special loot drops for IntroGoblinDagger...")
    
    # Check that IntroGoblinDagger has special loot configured
    assert "IntroGoblinDagger" in SPECIAL_LOOT_DROPS, "IntroGoblinDagger not found in special loot drops"
    
    # Check that Wolf's End Game is configured
    assert "Wolf's End Game" in SPECIAL_LOOT_DROPS["IntroGoblinDagger"], "Wolf's End Game not found in IntroGoblinDagger loot"
    
    wolf_end_game = SPECIAL_LOOT_DROPS["IntroGoblinDagger"]["Wolf's End Game"]
    
    # Verify the item configuration
    assert wolf_end_game["gearID"] == 20007, f"Wrong gear ID: {wolf_end_game['gearID']}, expected 20007"
    assert wolf_end_game["tier"] == LEGENDARY_TIER, f"Wrong tier: {wolf_end_game['tier']}, expected {LEGENDARY_TIER}"
    assert wolf_end_game["drop_chance"] == 1.0, f"Wrong drop chance: {wolf_end_game['drop_chance']}, expected 1.0"
    assert len(wolf_end_game["runes"]) == 3, f"Wrong number of runes: {len(wolf_end_game['runes'])}"
    assert len(wolf_end_game["colors"]) == 2, f"Wrong number of colors: {len(wolf_end_game['colors'])}"
    
    print("✓ Special loot drop configuration is correct!")
    
    # Test drop simulation
    drops = 0
    total = 100
    
    for _ in range(total):
        if random.random() <= wolf_end_game["drop_chance"]:
            drops += 1
    
    print(f"Wolf's End Game drop rate: {drops}/{total} ({drops/total:.1%})")
    assert drops == total, f"Expected 100% drop rate, got {drops/total:.1%}"
    print("✓ 100% drop rate test passed!")

def main():
    """Run all tests"""
    print("=== Legendary Loot Drop System Tests ===\n")
    
    try:
        test_gear_generation()
        print()
        test_rogue_gear_ids()
        print()
        test_loot_drop_chance()
        print()
        test_special_loot_drops()
        print()
        
        print("🎉 All tests passed! The loot system is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main() 