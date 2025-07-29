#!/usr/bin/env python3
"""
Enemy AI System for Dungeon Blitz Server
Implements enemy detection, state management, movement, and combat behavior
"""

import math
import time
import random
from typing import Dict, Any, List, Optional, Tuple
from constants import Entity

# Enemy AI Constants
AGGRO_RADIUS = 300.0  # Distance at which enemies detect players
ATTACK_RANGE = 80.0   # Distance at which enemies can attack
MOVEMENT_SPEED = 100.0  # Enemy movement speed (units per second)
HATE_DECAY_TIME = 10.0  # Time before hate starts decaying
MAX_HATE_VALUE = 10000  # Maximum hate value
THINK_INTERVAL = 0.1   # How often AI thinks (seconds)
RESPAWN_TIME = 30.0    # Time before dead enemies respawn (seconds)

# Enemy States (matching client-side state classes)
class EnemyState:
    IDLE = 0        # class_172 - Sleeping/Idle state
    ALERTED = 1     # class_179 - Alerted but not yet aggressive
    COMBAT = 2      # class_181 - Active combat state
    PURSUIT = 3     # Chasing target
    RETURNING = 4   # Returning to spawn point

class EnemyBrain:
    """
    Enemy AI brain that handles detection, targeting, and behavior
    Based on the client-side Brain.txt implementation
    """
    
    def __init__(self, entity_id: int, entity_data: Dict[str, Any]):
        self.entity_id = entity_id
        self.entity_data = entity_data
        self.state = EnemyState.IDLE
        self.last_think_time = time.time()
        
        # Hate system
        self.hate_list: Dict[int, float] = {}  # player_id -> hate_value
        self.most_hated_entity = None
        self.target = None
        
        # Position and movement
        self.spawn_x = entity_data.get("x", 0.0)
        self.spawn_y = entity_data.get("y", 0.0)
        self.spawn_z = entity_data.get("z", 0.0)  # Ground level
        self.current_x = self.spawn_x
        self.current_y = self.spawn_y
        self.current_z = self.spawn_z
        
        # Behavior settings
        self.aggro_radius = AGGRO_RADIUS
        self.attack_range = ATTACK_RANGE
        self.movement_speed = MOVEMENT_SPEED
        self.last_attack_time = 0.0
        self.attack_cooldown = 2.0  # 2 seconds between attacks

        # Initialize movement and animation flags for proper physics
        self.entity_data["bRunning"] = False
        self.entity_data["bFiring"] = False
        self.entity_data["bGotoLocation"] = False  # Not moving initially, disable ground collision override
        self.entity_data["bLeft"] = False  # Facing right initially
        self.entity_data["bJumping"] = False  # Not jumping
        self.entity_data["bDropping"] = False  # Not dropping
        self.entity_data["bBackpedal"] = False  # Not backpedaling
        
        # State timing
        self.state_enter_time = time.time()
        self.alerted_duration = 3.0  # How long to stay alerted before attacking
        
    def distance_to(self, x: float, y: float) -> float:
        """Calculate distance to a point"""
        dx = self.current_x - x
        dy = self.current_y - y
        return math.sqrt(dx * dx + dy * dy)
    
    def distance_to_spawn(self) -> float:
        """Calculate distance to spawn point"""
        return self.distance_to(self.spawn_x, self.spawn_y)
    
    def find_closest_enemy(self, players: Dict[int, Dict[str, Any]]) -> Optional[int]:
        """
        Find the closest enemy player within aggro radius
        Based on Brain.txt FindClosestEnemy method
        """
        closest_player = None
        closest_distance = float('inf')

        debug_info = []

        for player_id, player_data in players.items():
            if not player_data.get("is_player", False):
                debug_info.append(f"Player {player_id}: not a player")
                continue

            # Check if player is in combat state (can be targeted)
            if player_data.get("entState") == Entity.const_6:  # Dead state
                debug_info.append(f"Player {player_id}: dead state")
                continue

            player_x = player_data.get("x", 0.0)
            player_y = player_data.get("y", 0.0)
            distance = self.distance_to(player_x, player_y)

            debug_info.append(f"Player {player_id}: distance={distance:.1f}, aggro_radius={self.aggro_radius}")

            if distance <= self.aggro_radius and distance < closest_distance:
                closest_distance = distance
                closest_player = player_id

        # Debug output occasionally
        if hasattr(self, '_debug_counter') and self._debug_counter % 50 == 0:
            print(f"[AI DEBUG] Enemy {self.entity_id} detection scan:")
            for info in debug_info:
                print(f"  {info}")
            print(f"  Result: closest_player={closest_player}, distance={closest_distance:.1f}")

        return closest_player
    
    def add_hate(self, player_id: int, hate_amount: float, immediate_aggro: bool = False):
        """
        Add hate toward a player
        Based on Brain.txt AddHate method
        """
        if player_id not in self.hate_list:
            self.hate_list[player_id] = 0.0
            
        self.hate_list[player_id] += hate_amount
        self.hate_list[player_id] = min(self.hate_list[player_id], MAX_HATE_VALUE)
        
        # Update most hated entity
        if self.most_hated_entity is None or self.hate_list[player_id] > self.hate_list.get(self.most_hated_entity, 0):
            self.most_hated_entity = player_id
            
        # If immediate aggro, switch to combat state
        if immediate_aggro and self.state == EnemyState.IDLE:
            self.change_state(EnemyState.ALERTED)  # Note: state change will be handled in think() method
            
        print(f"[AI] Enemy {self.entity_id} added {hate_amount} hate to player {player_id} (total: {self.hate_list[player_id]})")
    
    def clear_hate_list(self):
        """Clear all hate entries"""
        self.hate_list.clear()
        self.most_hated_entity = None
        self.target = None
        
    def change_state(self, new_state: int):
        """Change enemy state and return True if state changed (needs broadcast)"""
        if self.state != new_state:
            print(f"[AI] Enemy {self.entity_id} changing state from {self.state} to {new_state}")
            self.state = new_state
            self.state_enter_time = time.time()

            # Update entity state in data for proper animation
            if new_state == EnemyState.IDLE:
                self.entity_data["entState"] = Entity.const_399  # Sleep state (idle animation)
                self.entity_data["bRunning"] = False
                self.entity_data["bFiring"] = False
            elif new_state == EnemyState.ALERTED:
                self.entity_data["entState"] = Entity.const_467  # Drama state (alert animation)
                self.entity_data["bRunning"] = False
                self.entity_data["bFiring"] = False
            elif new_state == EnemyState.COMBAT:
                self.entity_data["entState"] = Entity.const_78   # Active state for movement/combat
                self.entity_data["bRunning"] = True   # Enable running animation
                self.entity_data["bFiring"] = False   # Not attacking yet
            elif new_state == EnemyState.PURSUIT:
                self.entity_data["entState"] = Entity.const_78   # Active state for pursuit
                self.entity_data["bRunning"] = True   # Enable running animation
                self.entity_data["bFiring"] = False   # Not attacking yet
            elif new_state == EnemyState.RETURNING:
                self.entity_data["entState"] = Entity.const_78   # Active state for returning
                self.entity_data["bRunning"] = True   # Enable running animation
                self.entity_data["bFiring"] = False   # Not attacking

            return True  # State changed, needs broadcast
        return False  # No state change
    
    def move_toward_target(self, target_x: float, target_y: float, delta_time: float) -> bool:
        """
        Move toward a target position
        Returns True if reached target, False otherwise
        """
        dx = target_x - self.current_x
        dy = target_y - self.current_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance <= 5.0:  # Close enough
            return True
            
        # Normalize direction and apply movement
        if distance > 0:
            move_distance = self.movement_speed * delta_time
            move_distance = min(move_distance, distance)  # Don't overshoot
            
            self.current_x += (dx / distance) * move_distance
            self.current_y += (dy / distance) * move_distance
            
            # Update entity position
            self.entity_data["x"] = self.current_x
            self.entity_data["y"] = self.current_y
            self.entity_data["z"] = self.current_z  # Keep Z at ground level

            # Update facing direction for both facing_left and bLeft (client needs both)
            self.entity_data["facing_left"] = dx < 0
            self.entity_data["bLeft"] = dx < 0
            
        return False
    
    def can_attack_target(self, target_data: Dict[str, Any]) -> bool:
        """Check if target is within attack range"""
        target_x = target_data.get("x", 0.0)
        target_y = target_data.get("y", 0.0)
        distance = self.distance_to(target_x, target_y)
        return distance <= self.attack_range
    
    def perform_attack(self, target_id: int, target_data: Dict[str, Any]) -> bool:
        """
        Perform an attack on the target
        Returns True if attack was performed
        """
        current_time = time.time()
        if current_time - self.last_attack_time < self.attack_cooldown:
            return False

        if not self.can_attack_target(target_data):
            return False

        # Calculate damage (basic implementation)
        base_damage = self.entity_data.get("level", 1) * 5 + 10
        damage = base_damage + random.randint(-5, 5)

        # Set attack animation flags
        self.entity_data["bFiring"] = True  # Trigger attack animation
        self.entity_data["bRunning"] = False  # Stop running during attack
        self.entity_data["entState"] = Entity.const_78  # Active state for attack animation

        # Store attack start time for animation reset
        self.attack_start_time = current_time

        self.last_attack_time = current_time
        print(f"[AI] Enemy {self.entity_id} attacks player {target_id} for {damage} damage")

        return True
    
    def think(self, players: Dict[int, Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """
        Main AI thinking method - called every frame
        Based on Brain.txt Think method
        Returns list of actions to perform
        """
        current_time = time.time()
        actions = []

        # Don't think too often
        if current_time - self.last_think_time < THINK_INTERVAL:
            return actions

        self.last_think_time = current_time

        # Reset attack animation after a short duration (0.5 seconds)
        if hasattr(self, 'attack_start_time') and current_time - self.attack_start_time > 0.5:
            if self.entity_data.get("bFiring", False):
                self.entity_data["bFiring"] = False
                print(f"[AI] Enemy {self.entity_id} attack animation reset")

        # Debug output occasionally
        debug_interval = 50  # Every 5 seconds at 10 FPS
        if hasattr(self, '_debug_counter'):
            self._debug_counter += 1
        else:
            self._debug_counter = 1

        should_debug = self._debug_counter % debug_interval == 0

        if should_debug:
            print(f"[AI DEBUG] Enemy {self.entity_id} thinking: state={self.state}, pos=({self.current_x:.1f}, {self.current_y:.1f})")
            print(f"  Players available: {list(players.keys())}")
            print(f"  Hate list: {self.hate_list}")
            print(f"  Most hated: {self.most_hated_entity}")
        
        # Clean up invalid hate entries
        valid_hate = {}
        for player_id, hate_value in self.hate_list.items():
            if player_id in players and players[player_id].get("entState") != Entity.const_6:
                valid_hate[player_id] = hate_value
        self.hate_list = valid_hate
        
        # Update most hated entity
        if self.most_hated_entity and self.most_hated_entity not in self.hate_list:
            self.most_hated_entity = None
            
        if self.hate_list:
            self.most_hated_entity = max(self.hate_list.keys(), key=lambda x: self.hate_list[x])
        
        # State machine logic
        if self.state == EnemyState.IDLE:
            return self._think_idle(players, actions)
        elif self.state == EnemyState.ALERTED:
            return self._think_alerted(players, actions, delta_time)
        elif self.state == EnemyState.COMBAT:
            return self._think_combat(players, actions, delta_time)
        elif self.state == EnemyState.PURSUIT:
            return self._think_pursuit(players, actions, delta_time)
        elif self.state == EnemyState.RETURNING:
            return self._think_returning(players, actions, delta_time)
            
        return actions
    
    def _think_idle(self, players: Dict[int, Dict[str, Any]], actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Handle idle state logic"""
        # Check for nearby enemies
        closest_enemy = self.find_closest_enemy(players)
        if closest_enemy:
            if hasattr(self, '_debug_counter') and self._debug_counter % 50 == 0:
                print(f"[AI DEBUG] Enemy {self.entity_id} found closest enemy {closest_enemy}, adding hate")
            self.add_hate(closest_enemy, 0, immediate_aggro=True)
            self.target = closest_enemy

        # Check if we have a most hated entity
        if self.most_hated_entity and self.most_hated_entity in players:
            if hasattr(self, '_debug_counter') and self._debug_counter % 50 == 0:
                print(f"[AI DEBUG] Enemy {self.entity_id} has most hated entity {self.most_hated_entity}, changing to alerted")
            if self.change_state(EnemyState.ALERTED):
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
            self.target = self.most_hated_entity
        else:
            # Ensure idle enemies are not running and don't have ground collision override
            self.entity_data["bRunning"] = False
            self.entity_data["bGotoLocation"] = False

        return actions
    
    def _think_alerted(self, players: Dict[int, Dict[str, Any]], actions: List[Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """Handle alerted state logic"""
        # Stay alerted for a short time before becoming aggressive
        time_in_state = time.time() - self.state_enter_time
        
        if not self.most_hated_entity or self.most_hated_entity not in players:
            if self.change_state(EnemyState.IDLE):
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
            return actions

        if time_in_state >= self.alerted_duration:
            if self.change_state(EnemyState.COMBAT):
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
            
        return actions
    
    def _think_combat(self, players: Dict[int, Dict[str, Any]], actions: List[Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """Handle combat state logic"""
        if not self.most_hated_entity or self.most_hated_entity not in players:
            if self.change_state(EnemyState.RETURNING):
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
            return actions
            
        target_data = players[self.most_hated_entity]
        
        # Check if target is too far away
        target_x = target_data.get("x", 0.0)
        target_y = target_data.get("y", 0.0)
        distance_to_target = self.distance_to(target_x, target_y)
        
        if distance_to_target > self.aggro_radius * 2:  # Lost target
            self.clear_hate_list()
            if self.change_state(EnemyState.RETURNING):
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
            return actions
            
        # Try to attack if in range
        if self.can_attack_target(target_data):
            if self.perform_attack(self.most_hated_entity, target_data):
                actions.append({
                    "type": "attack",
                    "attacker_id": self.entity_id,
                    "target_id": self.most_hated_entity,
                    "damage": self.entity_data.get("level", 1) * 5 + 10
                })
                # Add animation state change for attack
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
        else:
            # Move toward target - ensure running animation is active and enable ground collision
            self.entity_data["bRunning"] = True
            self.entity_data["bFiring"] = False
            self.entity_data["bGotoLocation"] = True  # Enable ground collision detection for enemies
            self.entity_data["entState"] = Entity.const_78  # Active state for running

            self.move_toward_target(target_x, target_y, delta_time)
            actions.append({
                "type": "move",
                "entity_id": self.entity_id,
                "x": self.current_x,
                "y": self.current_y
            })
            
        return actions
    
    def _think_pursuit(self, players: Dict[int, Dict[str, Any]], actions: List[Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """Handle pursuit state logic"""
        # Similar to combat but more aggressive pursuit
        return self._think_combat(players, actions, delta_time)
    
    def _think_returning(self, players: Dict[int, Dict[str, Any]], actions: List[Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """Handle returning to spawn state logic"""
        # Move back to spawn point
        if self.move_toward_target(self.spawn_x, self.spawn_y, delta_time):
            # Reached spawn point - stop running and disable ground collision override
            self.entity_data["bRunning"] = False
            self.entity_data["bGotoLocation"] = False
            if self.change_state(EnemyState.IDLE):
                actions.append({
                    "type": "state_change",
                    "entity_id": self.entity_id,
                    "new_state": self.entity_data["entState"]
                })
            self.clear_hate_list()
        else:
            # Moving toward spawn - enable running and ground collision
            self.entity_data["bRunning"] = True
            self.entity_data["bGotoLocation"] = True
            actions.append({
                "type": "move",
                "entity_id": self.entity_id,
                "x": self.current_x,
                "y": self.current_y
            })

        return actions


class EnemyAIManager:
    """
    Manages all enemy AI in the game world
    """

    def __init__(self):
        self.enemy_brains: Dict[int, EnemyBrain] = {}
        self.dead_enemies: Dict[int, Dict[str, Any]] = {}  # entity_id -> {death_time, original_data}
        self.last_update_time = time.time()

    def add_enemy(self, entity_id: int, entity_data: Dict[str, Any]):
        """Add an enemy to the AI system"""
        if entity_id not in self.enemy_brains:
            brain = EnemyBrain(entity_id, entity_data)
            self.enemy_brains[entity_id] = brain
            print(f"[AI] Added enemy {entity_id} to AI system")
            print(f"  Entity data: name={entity_data.get('name')}, pos=({entity_data.get('x')}, {entity_data.get('y')})")
            print(f"  Team={entity_data.get('team')}, behavior_id={entity_data.get('behavior_id')}, level={entity_data.get('level')}")

    def remove_enemy(self, entity_id: int):
        """Remove an enemy from the AI system"""
        if entity_id in self.enemy_brains:
            del self.enemy_brains[entity_id]
            print(f"[AI] Removed enemy {entity_id} from AI system")

    def enemy_attacked(self, entity_id: int, attacker_id: int, damage: float):
        """Handle when an enemy is attacked by a player"""
        if entity_id in self.enemy_brains:
            brain = self.enemy_brains[entity_id]
            # Add significant hate for being attacked
            brain.add_hate(attacker_id, damage * 2 + 100, immediate_aggro=True)
            print(f"[AI] Enemy {entity_id} was attacked by {attacker_id} for {damage} damage")

    def enemy_died(self, entity_id: int):
        """Handle when an enemy dies - remove from AI system and schedule respawn"""
        if entity_id in self.enemy_brains:
            brain = self.enemy_brains[entity_id]
            # Store death information for respawn
            self.dead_enemies[entity_id] = {
                "death_time": time.time(),
                "original_data": brain.entity_data.copy(),
                "spawn_x": brain.spawn_x,
                "spawn_y": brain.spawn_y,
                "spawn_z": brain.spawn_z
            }
            del self.enemy_brains[entity_id]
            print(f"[AI] Enemy {entity_id} died and was removed from AI system (will respawn in {RESPAWN_TIME}s)")

    def update_all_enemies(self, players: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Update all enemy AI and return list of actions to perform
        """
        current_time = time.time()
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time

        # Debug player data occasionally
        if not hasattr(self, '_update_counter'):
            self._update_counter = 0
        self._update_counter += 1

        if self._update_counter % 100 == 0:  # Every 10 seconds
            print(f"[AI DEBUG] AI Manager update: {len(players)} players, {len(self.enemy_brains)} enemies, {len(self.dead_enemies)} dead")
            for pid, pdata in players.items():
                print(f"  Player {pid}: name={pdata.get('name')}, pos=({pdata.get('x')}, {pdata.get('y')}), is_player={pdata.get('is_player')}")

        all_actions = []

        # Check for enemies to respawn
        current_time = time.time()
        enemies_to_respawn = []
        for entity_id, death_info in self.dead_enemies.items():
            if current_time - death_info["death_time"] >= RESPAWN_TIME:
                enemies_to_respawn.append(entity_id)

        # Respawn enemies
        for entity_id in enemies_to_respawn:
            death_info = self.dead_enemies[entity_id]
            original_data = death_info["original_data"].copy()

            # Reset enemy to full health and spawn position
            original_data["hp"] = original_data.get("max_hp", 100)
            original_data["x"] = death_info["spawn_x"]
            original_data["y"] = death_info["spawn_y"]
            original_data["z"] = death_info["spawn_z"]  # Keep at ground level
            original_data["entState"] = Entity.const_399  # Sleep state
            original_data["damage_taken"] = 0
            original_data["health_delta"] = 0

            # Add back to AI system
            self.add_enemy(entity_id, original_data)
            del self.dead_enemies[entity_id]

            # Generate respawn action
            all_actions.append({
                "type": "respawn",
                "entity_id": entity_id,
                "entity_data": original_data
            })

            print(f"[AI] Enemy {entity_id} respawned at ({death_info['spawn_x']}, {death_info['spawn_y']}, {death_info['spawn_z']})")

        for entity_id, brain in list(self.enemy_brains.items()):  # Use list() to avoid modification during iteration
            try:
                # Check if enemy is dead (safety check)
                if brain.entity_data.get("entState") == Entity.const_6:  # Dead state
                    print(f"[AI] Removing dead enemy {entity_id} from AI system")
                    del self.enemy_brains[entity_id]
                    continue

                # Check if enemy HP is 0 or below (additional safety check)
                current_hp = brain.entity_data.get("hp", 100)
                if current_hp <= 0:
                    print(f"[AI] Enemy {entity_id} has 0 HP, removing from AI system")
                    brain.entity_data["entState"] = Entity.const_6  # Set to dead state
                    del self.enemy_brains[entity_id]
                    continue

                actions = brain.think(players, delta_time)
                all_actions.extend(actions)
            except Exception as e:
                print(f"[AI] Error updating enemy {entity_id}: {e}")
                print(f"[AI] Error details: type={type(e).__name__}, args={e.args}")
                import traceback
                traceback.print_exc()

        return all_actions

    def get_enemy_brain(self, entity_id: int) -> Optional[EnemyBrain]:
        """Get the brain for a specific enemy"""
        return self.enemy_brains.get(entity_id)


# Global AI manager instance
ai_manager = EnemyAIManager()
