#!/usr/bin/env python3
"""
Pet AI System for Dungeon Blitz Server
Implements pet following behavior, animation states, and companion logic
Based on Brain.txt pet following implementation
"""

import math
import time
from typing import Dict, Any, List, Optional, Tuple
from constants import Entity

# Pet Following Constants
PET_FOLLOW_DISTANCE = 200.0  # Distance at which pet starts following (matches Brain.txt)
PET_IDLE_DISTANCE = 200.0   # Distance within which pet stays idle
PET_MOVEMENT_SPEED = 120.0  # Pet movement speed (slightly faster than enemies)
PET_THINK_INTERVAL = 0.05   # Pet thinks more frequently for responsive following
PET_RESPAWN_TIME = 5.0      # Time before dead pets respawn

# Pet States (based on Entity animation states)
# Animation System Notes:
# - entState controls the base animation state (const_399=Ready, const_78=Active, const_6=Dead)
# - bRunning flag controls whether "Run" animation plays when entState=Active
# - Using const_78 (Active) + bRunning=True gives proper "Run" animation instead of "Drama" state
class PetState:
    READY = 0    # Maps to Entity.const_399 = 1 - Idle/Ready state
    RUNNING = 1  # Maps to Entity.const_78 = 0 - Active state + bRunning=True for proper Run animation
    DEAD = 2     # Maps to Entity.const_6 = 3 - Dead state

class PetBrain:
    """
    Pet AI brain that handles following behavior and animation states
    Based on the client-side Brain.txt pet following logic
    """
    
    def __init__(self, entity_id: int, entity_data: Dict[str, Any], owner_id: int):
        self.entity_id = entity_id
        self.entity_data = entity_data
        self.owner_id = owner_id
        self.state = PetState.READY
        self.last_think_time = time.time()
        self.death_time = None
        
        # Position and movement
        self.spawn_x = entity_data.get("x", 0.0)
        self.spawn_y = entity_data.get("y", 0.0)
        self.current_x = self.spawn_x
        self.current_y = self.spawn_y
        
        # Pet properties
        self.movement_speed = PET_MOVEMENT_SPEED
        self.follow_distance = PET_FOLLOW_DISTANCE
        self.idle_distance = PET_IDLE_DISTANCE
        
        # Initialize entity state and movement properties
        self.entity_data["entState"] = Entity.const_399  # Ready state
        self.entity_data["bRunning"] = False  # Not running initially
        self.entity_data["bGotoLocation"] = False  # Not moving initially
        self.entity_data["bLeft"] = False  # Facing right initially
        self.entity_data["bJumping"] = False  # Not jumping
        self.entity_data["bDropping"] = False  # Not dropping
        self.entity_data["bBackpedal"] = False  # Not backpedaling
        self.entity_data["bFiring"] = False  # Not firing initially
        self.entity_data["x"] = self.current_x
        self.entity_data["y"] = self.current_y
        self.entity_data["hp"] = self.entity_data.get("maxHP", 100)
        
    def distance_to(self, x: float, y: float) -> float:
        """Calculate distance to a point"""
        dx = self.current_x - x
        dy = self.current_y - y
        return math.sqrt(dx * dx + dy * dy)
    
    def change_state(self, new_state: int) -> bool:
        """Change pet state and update animation"""
        if self.state != new_state:
            self.state = new_state
            
            # Update entity state for proper animation
            if new_state == PetState.READY:
                self.entity_data["entState"] = Entity.const_399  # Ready/Idle animation
                self.entity_data["bRunning"] = False  # Stop running animation
                self.entity_data["bGotoLocation"] = False  # Disable ground collision override when idle
            elif new_state == PetState.RUNNING:
                self.entity_data["entState"] = Entity.const_78   # Active state (allows proper Run animation)
                self.entity_data["bRunning"] = True   # Enable running animation flag
                # bGotoLocation will be set to True in move_toward_target when actually moving
            elif new_state == PetState.DEAD:
                self.entity_data["entState"] = Entity.const_6    # Dead animation
                self.entity_data["bRunning"] = False  # Stop running when dead
                self.entity_data["bGotoLocation"] = False  # Disable ground collision override when dead
                self.death_time = time.time()
                
            return True  # State changed, needs broadcast
        return False  # No state change
    
    def move_toward_target(self, target_x: float, target_y: float, delta_time: float) -> bool:
        """Move toward target position, returns True if reached target"""
        dx = target_x - self.current_x
        dy = target_y - self.current_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # If very close, consider reached
        if distance <= 5.0:
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

            # Update facing direction (pet faces movement direction)
            self.entity_data["facing_left"] = dx < 0
            self.entity_data["bLeft"] = dx < 0  # Also set bLeft for proper animation direction
            self.entity_data["bGotoLocation"] = True  # Enable ground collision detection when moving
            
        return False
    
    def think(self, players: Dict[int, Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """
        Main pet AI thinking method - called every frame
        Based on Brain.txt pet following logic
        Returns list of actions to perform
        """
        current_time = time.time()
        actions = []

        # Don't think too often
        if current_time - self.last_think_time < PET_THINK_INTERVAL:
            return actions

        self.last_think_time = current_time
        
        # Handle respawn if dead - DISABLED FOR NOW TO PREVENT INFINITE RESPAWNING
        # TODO: Implement proper pet respawn mechanics based on game rules
        if self.state == PetState.DEAD:
            # Pet stays dead until manually revived
            return actions
        
        # Check if owner exists
        if self.owner_id not in players:
            return actions
            
        owner_data = players[self.owner_id]
        owner_x = owner_data.get("x", 0.0)
        owner_y = owner_data.get("y", 0.0)
        
        # Calculate distance to owner
        distance_to_owner = self.distance_to(owner_x, owner_y)
        
        # Pet following logic based on Brain.txt
        # if(this.e.summonerId && this.e.behaviorType.bFollowSpawner && !this.e.behaviorType.var_844 && 
        #    (!this.e.behaviorType.var_2807 || !this.e.combatState.mActivePower || this.e.combatState.mActivePower.var_344))
        # {
        #    if(_loc4_ = this.var_1.GetEntFromID(this.e.summonerId))
        #    {
        #       _loc5_ = this.e.physPosX - _loc4_.physPosX;
        #       _loc6_ = this.e.physPosY - _loc4_.physPosY;
        #       if(this.e.entState == Entity.const_399)
        #       {
        #          if(_loc5_ >= -200 && _loc5_ <= 200)
        #          {
        #             this.e.bRunning = false;
        #          }
        #          else
        #          {
        #             this.e.bRunning = true;
        #             this.e.bLeft = _loc5_ > 0;
        #          }
        #       }
        #    }
        # }
        
        # Check if pet should follow or stay idle
        if distance_to_owner <= self.idle_distance:
            # Pet is close enough, stay in ready state
            if self.state == PetState.RUNNING:
                if self.change_state(PetState.READY):
                    actions.append({
                        "type": "pet_state_change",
                        "entity_id": self.entity_id,
                        "new_state": self.entity_data["entState"]
                    })
        else:
            # Pet is too far, start following
            if self.state == PetState.READY:
                if self.change_state(PetState.RUNNING):
                    actions.append({
                        "type": "pet_state_change",
                        "entity_id": self.entity_id,
                        "new_state": self.entity_data["entState"]
                    })
            
            # Move toward owner
            self.move_toward_target(owner_x, owner_y, delta_time)
            actions.append({
                "type": "pet_move",
                "entity_id": self.entity_id,
                "x": self.current_x,
                "y": self.current_y,
                "facing_left": self.entity_data.get("facing_left", False)
            })
            
        return actions
    
    def take_damage(self, damage: int) -> bool:
        """Handle pet taking damage, returns True if pet died"""
        current_hp = self.entity_data.get("hp", 100)
        current_hp -= damage
        self.entity_data["hp"] = max(0, current_hp)

        if current_hp <= 0 and self.state != PetState.DEAD:
            self.change_state(PetState.DEAD)
            return True
        return False

    def kill_pet(self):
        """Immediately kill the pet (for testing or special cases)"""
        self.entity_data["hp"] = 0
        self.change_state(PetState.DEAD)

class PetAIManager:
    """
    Manages all pet AI instances
    """
    
    def __init__(self):
        self.pet_brains: Dict[int, PetBrain] = {}  # entity_id -> PetBrain
        self.dead_pets: Dict[int, Dict[str, Any]] = {}  # Track dead pets for respawn
        
    def add_pet(self, entity_id: int, entity_data: Dict[str, Any], owner_id: int):
        """Add a pet to the AI system"""
        if entity_id not in self.pet_brains:
            self.pet_brains[entity_id] = PetBrain(entity_id, entity_data, owner_id)
            print(f"[Pet AI] Added pet {entity_id} for owner {owner_id}")
    
    def remove_pet(self, entity_id: int):
        """Remove a pet from the AI system"""
        if entity_id in self.pet_brains:
            del self.pet_brains[entity_id]
            print(f"[Pet AI] Removed pet {entity_id}")
    
    def update_pets(self, players: Dict[int, Dict[str, Any]], delta_time: float) -> List[Dict[str, Any]]:
        """Update all pets and return actions to broadcast"""
        all_actions = []
        
        for entity_id, brain in list(self.pet_brains.items()):  # Use list() to avoid modification during iteration
            try:
                # Check if pet should be removed (owner disconnected, etc.)
                if brain.owner_id not in players and brain.state != PetState.DEAD:
                    print(f"[Pet AI] Owner {brain.owner_id} not found, removing pet {entity_id}")
                    del self.pet_brains[entity_id]
                    continue
                
                # Update pet AI
                actions = brain.think(players, delta_time)
                all_actions.extend(actions)
                
            except Exception as e:
                print(f"[Pet AI] Error updating pet {entity_id}: {e}")
                # Remove problematic pet
                del self.pet_brains[entity_id]
                
        return all_actions
    
    def pet_take_damage(self, entity_id: int, damage: int) -> bool:
        """Handle pet taking damage, returns True if pet died"""
        if entity_id in self.pet_brains:
            return self.pet_brains[entity_id].take_damage(damage)
        return False
