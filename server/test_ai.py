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
    
    # Create test enemy data (matching NPC data structure)
    enemy_data = {
        "id": 3,
        "name": "IntroGoblinDagger",
        "x": 1000.25,  # From CraftTown NPC data
        "y": 1400.615,
        "z": -10.0,
        "team": 0,
        "entState": 0,
        "level": 5,
        "behavior_id": 1,
        "facing_left": False,
        "max_hp": 100
    }
    
    # Create test player data (simulating the fixed entity structure)
    players = {
        60775: {  # Use a realistic player ID like from the logs
            "id": 60775,
            "name": "Telahair",
            "x": 1000.0,  # Close to enemy position for testing
            "y": 1400.0,
            "z": 0.0,
            "team": 1,
            "entState": 0,  # Active state, not dead
            "is_player": True
        }
    }
    
    print("1. Creating enemy brain...")
    brain = EnemyBrain(3, enemy_data)
    print(f"   Enemy spawned at ({brain.spawn_x}, {brain.spawn_y})")
    print(f"   Initial state: {brain.state}")

    print("\n2. Testing distance calculation...")
    distance = brain.distance_to(1000.0, 1400.0)  # Distance to player position
    print(f"   Distance to player: {distance:.2f}")

    print("\n3. Testing enemy detection...")
    closest = brain.find_closest_enemy(players)
    print(f"   Closest enemy found: {closest}")
    
    print("\n4. Testing hate system...")
    brain.add_hate(60775, 50, immediate_aggro=True)
    print(f"   Added hate to player 60775")
    print(f"   Most hated entity: {brain.most_hated_entity}")
    print(f"   Current state: {brain.state}")
    
    print("\n5. Testing AI thinking over time...")
    for i in range(50):  # Run for 5 seconds
        actions = brain.think(players, 0.1)
        if actions or i % 10 == 0:  # Print every second or when there are actions
            print(f"   Think cycle {i+1}: {len(actions)} actions, state: {brain.state}")
            for action in actions:
                print(f"     Action: {action}")
        time.sleep(0.1)
    
    print("\n6. Testing AI Manager...")
    ai_manager.add_enemy(3, enemy_data)
    ai_manager.enemy_attacked(3, 60775, 25)
    
    actions = ai_manager.update_all_enemies(players)
    print(f"   AI Manager generated {len(actions)} actions")
    for action in actions:
        print(f"     Action: {action}")
    
    print("\nAI Test completed successfully!")

if __name__ == "__main__":
    test_enemy_brain()
