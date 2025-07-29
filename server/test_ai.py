#!/usr/bin/env python3
"""
Test script for Enemy AI system
"""

import sys
import time
from enemy_ai import EnemyBrain, EnemyState, ai_manager

def test_enemy_brain():
    """Test basic enemy brain functionality"""
    print("Testing Enemy AI System...")

    # Test multiple enemy types
    enemy_configs = [
        {
            "id": 1,
            "name": "GrayGhostLord",
            "x": 800.25,
            "y": 1400.615,
            "z": -10.0,
            "team": 0,
            "entState": 0,
            "level": 10,
            "behavior_id": 1,
            "facing_left": True,
            "max_hp": 200
        },
        {
            "id": 3,
            "name": "IntroGoblinDagger",
            "x": 1000.25,
            "y": 1400.615,
            "z": -10.0,
            "team": 0,
            "entState": 0,
            "level": 5,
            "behavior_id": 1,
            "facing_left": False,
            "max_hp": 100
        }
    ]
    
    # Create test player data (simulating the fixed entity structure)
    players = {
        60775: {  # Use a realistic player ID like from the logs
            "id": 60775,
            "name": "Telahair",
            "x": 900.0,  # Position between the two enemies
            "y": 1400.0,
            "z": 0.0,
            "team": 1,
            "entState": 0,  # Active state, not dead
            "is_player": True,
            # Add required player appearance data
            "class": "Paladin",
            "headSet": "Head01",
            "hairSet": "Hair01",
            "mouthSet": "Mouth01",
            "faceSet": "Face01",
            "hairColor": 0,
            "skinColor": 0,
            "shirtColor": 0,
            "pantColor": 0,
            "equippedGears": [[0, 0, 0, 0, 0, 0]] * 6
        }
    }

    print("1. Testing multiple enemy configurations...")
    for i, enemy_data in enumerate(enemy_configs):
        print(f"\n   Testing Enemy {i+1}: {enemy_data['name']} (ID: {enemy_data['id']})")
        brain = EnemyBrain(enemy_data['id'], enemy_data)
        print(f"     Spawned at ({brain.spawn_x}, {brain.spawn_y})")
        print(f"     Initial state: {brain.state}")

        # Test detection
        closest = brain.find_closest_enemy(players)
        print(f"     Closest enemy found: {closest}")

        # Test hate system
        brain.add_hate(60775, 50, immediate_aggro=True)
        print(f"     Added hate, new state: {brain.state}")

        # Add to AI manager
        ai_manager.add_enemy(enemy_data['id'], enemy_data)

    print("\n2. Testing AI Manager with multiple enemies...")
    # Simulate enemy being attacked
    ai_manager.enemy_attacked(1, 60775, 30)  # GrayGhostLord attacked
    ai_manager.enemy_attacked(3, 60775, 25)  # IntroGoblinDagger attacked

    print("\n3. Testing AI thinking cycles...")
    for cycle in range(10):
        actions = ai_manager.update_all_enemies(players)
        if actions:
            print(f"   Cycle {cycle+1}: {len(actions)} actions")
            for action in actions:
                action_type = action.get('type', 'unknown')
                if action_type == 'attack':
                    print(f"     ATTACK: Enemy {action['attacker_id']} → Player {action['target_id']} ({action['damage']} damage)")
                elif action_type == 'move':
                    print(f"     MOVE: Enemy {action['entity_id']} → ({action['x']:.1f}, {action['y']:.1f})")
        time.sleep(0.5)

    print("\n4. Testing packet generation (simulated)...")
    # Test that we can create entity packets without crashes
    try:
        from entity import Send_Entity_Data
        for player_id, player_data in players.items():
            packet = Send_Entity_Data(player_data, is_player=True)
            print(f"   Player packet generated: {len(packet)} bytes")

        for enemy_data in enemy_configs:
            packet = Send_Entity_Data(enemy_data, is_player=False)
            print(f"   Enemy packet generated: {len(packet)} bytes")

        print("   All packets generated successfully!")
    except Exception as e:
        print(f"   ERROR generating packets: {e}")

    print("\n✅ Complete AI System Test completed successfully!")

if __name__ == "__main__":
    test_enemy_brain()
