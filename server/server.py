#!/usr/bin/env python3
import os
import random
import json
import socket, struct, hashlib, sys, time, secrets, threading, math
from accounts import get_or_create_user_id, load_accounts, _SAVES_DIR, is_character_name_taken, build_popup_packet
from Character import (
    make_character_dict_from_tuple,
    build_login_character_list_bitpacked,
    build_paperdoll_packet,
    load_characters,
    save_characters
)
from BitUtils import BitBuffer
from Commands import handle_hotbar_packet, handle_masterclass_packet, handle_research_packet, handle_gear_packet, \
    handle_apply_dyes, handle_rune_packet, handle_change_look, handle_create_gearset, handle_name_gearset, \
    handle_apply_gearset, handle_update_equipment, magic_forge_packet, collect_forge_charm, start_forge_packet, \
    cancel_forge_packet, allocate_talent_points, tick_forge_status, use_forge_xp_consumable, handle_private_message, \
    handle_public_chat, handle_group_invite, handle_power_cast, handle_power_hit, \
    handle_projectile_explode, handle_add_buff, handle_remove_buff, handle_entity_full_update, handle_position_sync, \
    handle_entity_incremental_update, handle_packet_0x7C, handle_packet_0x41
from constants import EntType, DyeType, Entity
from WorldEnter import build_enter_world_packet, Player_Data_Packet
from bitreader import BitReader
from PolicyServer import start_policy_server
from static_server import start_static_server
from entity import Send_Entity_Data, load_npc_data_for_level
from level_config import DOOR_MAP, LEVEL_CONFIG, get_spawn_coordinates
from enemy_ai import ai_manager
from pet_ai import PetAIManager

HOST = "127.0.0.1"
PORTS = [8080]
pending_world = {}
all_sessions = []
current_characters = {}
used_tokens = {}

# Initialize AI managers
pet_ai_manager = PetAIManager()

# Pet ID to EntType mapping based on Login.swz.txt EntTypes
PET_ID_TO_ENTTYPE = {
    # Red pets (1-13)
    1: "PetDjinnRed", 2: "PetSpriteRed", 3: "PetMonkeyRed", 4: "PetGhostRed", 5: "PetGhoulRed",
    6: "PetPhoenixRed", 7: "PetDragon3Red", 8: "PetFairyRed", 9: "PetDragon2Red", 10: "PetCrowRed",
    11: "PetDragonetteRed", 12: "PetAngelRed", 13: "PetOwlRed",
    # Yellow pets (14-26)
    14: "PetDjinnYellow", 15: "PetSpriteYellow", 16: "PetMonkeyYellow", 17: "PetGhostYellow", 18: "PetGhoulYellow",
    19: "PetPhoenixYellow", 20: "PetDragon3Yellow", 21: "PetFairyYellow", 22: "PetDragon2Yellow", 23: "PetCrowYellow",
    24: "PetDragonetteYellow", 25: "PetAngelYellow", 26: "PetOwlYellow",
    # Blue pets (27-39)
    27: "PetDjinnBlue", 28: "PetSpriteBlue", 29: "PetMonkeyBlue", 30: "PetGhostBlue", 31: "PetGhoulBlue",
    32: "PetPhoenixBlue", 33: "PetDragon3Blue", 34: "PetFairyBlue", 35: "PetDragon2Blue", 36: "PetCrowBlue",
    37: "PetDragonetteBlue", 38: "PetAngelBlue", 39: "PetOwlBlue",
    # Green pets (40-52)
    40: "PetDjinnGreen", 41: "PetSpriteGreen", 42: "PetMonkeyGreen", 43: "PetGhostGreen", 44: "PetGhoulGreen",
    45: "PetPhoenixGreen", 46: "PetDragon3Green", 47: "PetFairyGreen", 48: "PetDragon2Green", 49: "PetCrowGreen",
    50: "PetDragonetteGreen", 51: "PetAngelGreen", 52: "PetOwlGreen",
    # Special pets (53-70)
    53: "PetPumpkinRed", 54: "PetPumpkinYellow", 55: "PetPumpkinBlue", 56: "PetPumpkinGreen",
    57: "PetGargoyleRed", 58: "PetGargoyleYellow", 59: "PetGargoyleBlue", 60: "PetGargoyleGreen",
    61: "PetLockbox01L02", 62: "PetLockbox01L01", 63: "PetLockbox01RRed", 64: "PetLockbox01RYellow",
    65: "PetLockbox01RBlue", 66: "PetLockbox01RGreen", 67: "PetFalconRed", 68: "PetFalconYellow",
    69: "PetFalconBlue", 70: "PetFalconGreen"
}

def spawn_player_pet(session, char, owner_id):
    """
    Spawn a pet for the player if they have one equipped
    """
    try:
        equipped_pet_id = char.get("equippedPetID", 0)
        pet_iteration = char.get("petIteration", 0)

        if equipped_pet_id > 0:
            # Generate unique entity ID for the pet
            pet_entity_id = owner_id + 10000  # Offset to avoid conflicts with player IDs

            # Get player position for pet spawn
            player_x = session.entities[owner_id]["x"]
            player_y = session.entities[owner_id]["y"]

            # Get the correct EntType name for this pet ID
            pet_enttype_name = PET_ID_TO_ENTTYPE.get(equipped_pet_id, "PetDjinnRed")  # Default to PetDjinnRed if not found

            # Create pet entity based on equipped pet data
            pet_entity = {
                "id": pet_entity_id,
                "x": player_x + 50,  # Spawn pet slightly offset from player
                "y": player_y,
                "z": 0.0,
                "entState": Entity.const_399,  # Ready state
                "is_player": False,
                "is_pet": True,
                "owner_id": owner_id,
                "name": pet_enttype_name,  # Use correct EntType name instead of Pet_{id}
                "hp": 100,
                "maxHP": 100,
                "team": 1,  # Same team as player
                "entType": EntType.PET,  # Pet entity type
                "petTypeID": equipped_pet_id,
                "petIteration": pet_iteration,
                "facing_left": False,
                "behavior_id": 0,  # Pets don't use enemy AI behavior
                "level": char.get("level", 1),
                "class": "Pet"
            }

            # Add pet to session entities
            session.entities[pet_entity_id] = pet_entity

            # Add pet to pet AI system
            pet_ai_manager.add_pet(pet_entity_id, pet_entity, owner_id)

            print(f"[{session.addr}] Spawned pet {pet_enttype_name} (ID: {equipped_pet_id}) for player {owner_id}")

    except Exception as e:
        print(f"[{session.addr}] Error spawning pet for player {owner_id}: {e}")

# Loot drop system constants
LOOT_DROP_CHANCE = 0.3  # 30% chance for legendary loot drop
LEGENDARY_TIER = 2  # Legendary rarity tier
ROGUE_GEAR_IDS = [27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 1163, 1171, 1172, 1173, 1174, 1175, 1176]  # Actual Rogue gear IDs

# Special loot drops for specific enemies
SPECIAL_LOOT_DROPS = {
    "IntroGoblinDagger": {
        "Wolf's End Game": {
            "gearID": 20007,  # Wolfclaw Dagger gear ID
            "tier": LEGENDARY_TIER,
            "drop_chance": 1.0,  # 100% drop chance
            "runes": [0, 0, 0],
            "colors": [0, 0]
        }
    }
}

def generate_legendary_rogue_gear():
    """Generate a random legendary Rogue equipment item"""
    gear_id = random.choice(ROGUE_GEAR_IDS)
    return {
        "gearID": gear_id,
        "tier": LEGENDARY_TIER,  # Legendary rarity
        "runes": [0, 0, 0],  # No runes for now
        "colors": [0, 0]  # Default colors
    }

def upgrade_rare_to_legendary(session):
    """Check if player has Rare gear and upgrade one to Legendary"""
    try:
        chars = session.player_data.get("characters", [])
        char = next((c for c in chars if c.get("name") == session.current_character), None)
        
        if char is None:
            return None
            
        inventory = char.get("inventoryGears", [])
        rare_gear = []
        
        # Find all Rare gear (tier 1)
        for gear in inventory:
            if gear.get("tier") == 1:  # Rare tier
                rare_gear.append(gear)
        
        if rare_gear:
            # Upgrade a random Rare gear to Legendary
            gear_to_upgrade = random.choice(rare_gear)
            gear_to_upgrade["tier"] = LEGENDARY_TIER
            
            # Save the character data
            save_characters(session.user_id, chars)
            
            # Send notification to client about gear upgrade
            send_gear_upgrade_notification(session, gear_to_upgrade)
            
            print(f"[LOOT] Upgraded Rare gear {gear_to_upgrade['gearID']} to Legendary")
            return gear_to_upgrade
            
        return None
        
    except Exception as e:
        print(f"[LOOT] Error upgrading Rare gear: {e}")
        return None

def send_gear_upgrade_notification(session, gear_data):
    """Send a notification to the client about gear upgrade"""
    try:
        # Create a simple notification packet
        bb = BitBuffer()
        bb.write_utf_string(f"Rare gear upgraded to Legendary! Gear ID: {gear_data['gearID']}")
        
        payload = bb.to_bytes()
        packet = struct.pack(">HH", 0x108, len(payload)) + payload  # Use a notification packet type
        session.conn.sendall(packet)
        
        print(f"[LOOT] Sent gear upgrade notification for gear {gear_data['gearID']}")
        
    except Exception as e:
        print(f"[LOOT] Error sending gear upgrade notification: {e}")

def send_loot_drop_packet(session, x, y, gear_data):
    """Send a loot drop packet to the client"""
    try:
        bb = BitBuffer()
        
        # Loot ID (random unique ID)
        loot_id = random.randint(1000, 9999)
        bb.write_method_4(loot_id)
        
        # Coordinates
        bb.write_signed_method_45(int(x))
        bb.write_signed_method_45(int(y))
        
        # First flag: Is it gear? (Yes)
        bb.write_bits(1, 1)
        
        # Gear ID and tier (combined like Game.method_110)
        gear_id = gear_data["gearID"]
        tier = gear_data["tier"]
        bb.write_method_6(gear_id, 11)  # GEARTYPE_BITSTOSEND
        bb.write_method_6(tier, 11)     # GEARTYPE_BITSTOSEND for tier
        
        # Remaining flags (all false for gear)
        bb.write_bits(0, 1)  # Not material
        bb.write_bits(0, 1)  # Not gold
        bb.write_bits(0, 1)  # Not soul
        bb.write_bits(0, 1)  # Not charm
        bb.write_bits(0, 1)  # Not consumable
        
        payload = bb.to_bytes()
        packet = struct.pack(">HH", 0x106, len(payload)) + payload  # PKTTYPE_RECEIVE_LOOTDROP
        session.conn.sendall(packet)
        
        print(f"[LOOT] Sent legendary Rogue gear drop: gearID={gear_id}, tier={tier}, pos=({x}, {y})")
        return loot_id
        
    except Exception as e:
        print(f"[LOOT] Error sending loot drop packet: {e}")
        return None

def add_gear_to_inventory(session, gear_data):
    """Add the gear to the player's inventory"""
    try:
        chars = session.player_data.get("characters", [])
        char = next((c for c in chars if c.get("name") == session.current_character), None)
        
        if char is None:
            print(f"[LOOT] Character {session.current_character} not found")
            return False
            
        inventory = char.setdefault("inventoryGears", [])
        
        # Add the gear to inventory
        inventory.append(gear_data)
        
        # Save the character data
        save_characters(session.user_id, chars)
        
        print(f"[LOOT] Added gear to inventory: {gear_data}")
        return True
        
    except Exception as e:
        print(f"[LOOT] Error adding gear to inventory: {e}")
        return False

def handle_enemy_death(session, enemy_id, enemy_data, attacker_id):
    """Handle enemy death and potential loot drops"""
    try:
        enemy_name = enemy_data.get("name", "")
        
        # Check for special loot drops first
        if enemy_name in SPECIAL_LOOT_DROPS:
            for item_name, item_data in SPECIAL_LOOT_DROPS[enemy_name].items():
                if random.random() <= item_data["drop_chance"]:
                    # Generate special loot
                    gear_data = {
                        "gearID": item_data["gearID"],
                        "tier": item_data["tier"],
                        "runes": item_data["runes"],
                        "colors": item_data["colors"]
                    }
                    
                    # Get enemy position for loot drop
                    x = enemy_data.get("x", 0)
                    y = enemy_data.get("y", 0)
                    
                    # Send loot drop packet to client
                    loot_id = send_loot_drop_packet(session, x, y, gear_data)
                    
                    if loot_id:
                        # Add gear to player's inventory
                        add_gear_to_inventory(session, gear_data)
                        
                        print(f"[LOOT] Enemy {enemy_id} ({enemy_name}) dropped {item_name} for player {attacker_id}")
                        return  # Exit after special loot drop
        
        # Regular loot system (30% chance for legendary Rogue gear)
        if random.random() > LOOT_DROP_CHANCE:
            return
            
        # First try to upgrade existing Rare gear to Legendary
        upgraded_gear = upgrade_rare_to_legendary(session)
        
        if upgraded_gear:
            # Send notification about upgraded gear
            print(f"[LOOT] Enemy {enemy_id} caused Rare gear upgrade to Legendary for player {attacker_id}")
            return
            
        # If no Rare gear to upgrade, generate new legendary Rogue gear
        gear_data = generate_legendary_rogue_gear()
        
        # Get enemy position for loot drop
        x = enemy_data.get("x", 0)
        y = enemy_data.get("y", 0)
        
        # Send loot drop packet to client
        loot_id = send_loot_drop_packet(session, x, y, gear_data)
        
        if loot_id:
            # Add gear to player's inventory
            add_gear_to_inventory(session, gear_data)
            
            print(f"[LOOT] Enemy {enemy_id} dropped legendary Rogue gear for player {attacker_id}")
            
    except Exception as e:
        print(f"[LOOT] Error handling enemy death: {e}")

def build_handshake_response(sid):
    b = sid.to_bytes(2, "big")
    h = hashlib.md5(b + b"815bfb010cd7b1b4e6aa90abc7679028").hexdigest()
    payload = b + bytes.fromhex(h[:12])
    return struct.pack(">HH", 0x12, len(payload)) + payload

def new_transfer_token():
    while (t := secrets.randbits(16)) in pending_world:
        pass
    return t
                         # For testing purposes
######################################################################################
def broadcast_level_change(session, char_name, new_level):
    """
    Notify all other authenticated clients of a player's level change.
    Sends a 0x2C packet with a custom message: "LEVEL_UPDATE:<char_name>:<new_level>".
    """
    message = f"LEVEL_UPDATE:{char_name}:{new_level}"
    bb = BitBuffer()
    bb.write_method_4(session.clientEntID or 0)  # Use clientEntID or 0 if not set
    bb.write_method_13(message)
    broadcast_payload = bb.to_bytes()
    packet = struct.pack(">HH", 0x2C, len(broadcast_payload)) + broadcast_payload
    for other_session in all_sessions:
        if other_session != session and other_session.authenticated:
            try:
                other_session.conn.sendall(packet)
                print(
                    f"[{session.addr}] Broadcasted level change for {char_name} to {new_level} to {other_session.addr}")
            except Exception as e:
                print(f"[{session.addr}] Error broadcasting level change to {other_session.addr}: {e}")

def broadcast_attack_dialogue(session, player_name, target_entity_id, target_name):
    """
    Broadcast scripted dialogue for a turn-based player-NPC conversation when the player attacks an NPC (e.g., ID 1).
    Sends five 0x2C packets (alternating player and NPC) with a 2-second delay, for a scripted scene.
    """
    print(f"[{session.addr}] Checking dialogue trigger for NPC ID {target_entity_id}")
    if target_entity_id != 999:
        print(f"[{session.addr}] Dialogue skipped: target_entity_id {target_entity_id} is not 1")
        return  # Only trigger for NPC ID 1
    # Check for cooldown (30 seconds)
    if hasattr(session, 'last_dialogue_time') and time.time() - session.last_dialogue_time < 90:
        print(f"[{session.addr}] Dialogue skipped: on cooldown for {player_name}")
        return
    session.last_dialogue_time = time.time()
    # Alternating dialogue: Player, NPC, Player, NPC, Player
    dialogue_sequence = [
        ("player", session.clientEntID, "Nephit! I finally found you."),
        ("NPC", target_entity_id, "So, the flame still flickers in you... intriguing."),
        ("player", session.clientEntID, "You knew this would end with us."),
        ("NPC", target_entity_id, "Many have tried. All have knelt before the void."),
        ("player", session.clientEntID, "I’m not like them. I’m not afraid."),
        ("NPC", target_entity_id, "Then come. Let your courage be your curse."),
        ("player", session.clientEntID, "I’ll tear through your illusions and take back the shard!"),
        ("NPC", target_entity_id, "The shard belongs to the darkness now."),
        ("player", session.clientEntID, "Then I’ll bring light to your darkness."),
        ("NPC", target_entity_id, "Bold... and foolish. Let’s end this.")
    ]
    print(
        f"[{session.addr}] Triggering turn-based dialogue for {player_name} and {target_name} (NPC ID {target_entity_id})")

    def send_dialogue(line, delay, entity_id, entity_type):
        """Helper to send a single dialogue line for player or NPC after a delay."""
        try:
            bb = BitBuffer()
            bb.write_method_4(entity_id or 0)  # Use player or NPC entity ID
            bb.write_method_13(line)  # Raw text for scripted scene
            broadcast_payload = bb.to_bytes()
            packet = struct.pack(">HH", 0x2C, len(broadcast_payload)) + broadcast_payload
            print(
                f"[{session.addr}] Constructed dialogue packet: type=0x2C, payload_len={len(broadcast_payload)}, line='{line}', entity_type={entity_type}")
            # Broadcast to all clients in the same level, including self
            for other_session in all_sessions:
                if other_session.world_loaded and other_session.current_level == session.current_level:
                    try:
                        other_session.conn.sendall(packet)
                        print(
                            f"[{session.addr}] Broadcasted {entity_type} dialogue '{line}' via 0x2C to {other_session.addr} after {delay}s")
                    except Exception as e:
                        print(f"[{session.addr}] Error sending {entity_type} dialogue to {other_session.addr}: {e}")
        except Exception as e:
            print(f"[{session.addr}] Error constructing {entity_type} dialogue packet for '{line}': {e}")

    # Schedule dialogue at 0.1s, 2.1s, 4.1s, 6.1s, 8.1s
    for i, (entity_type, entity_id, line) in enumerate(dialogue_sequence):
        threading.Timer(0.1 + i * 2.0, send_dialogue, args=(line, 0.1 + i * 2.0, entity_id, entity_type)).start()


######################################################################################
class ClientSession:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.user_id = None
        self.char_list = []
        self.active_tokens = set()
        self.authenticated = False
        self.player_data = {}
        self.current_character = None
        self.current_level = None
        self.entry_level = None
        self.world_loaded = False
        self.spawned_npcs = []
        self.npc_states = {}
        self.entities = {}
        self.clientEntID = None
        self.running = True

    def attack_entity(self, attacker_id, target_id, damage):
        target_ent = self.entities.get(target_id)
        if not target_ent:
            print(f"[{self.addr}] [PKT0F] Target entity {target_id} not found")
            return
            
        # Calculate current HP and damage
        current_hp = target_ent.get("hp", 100)
        damage_taken = target_ent.get("damage_taken", 0) + damage
        new_hp = max(0, current_hp - damage)
        
        target_ent["damage_taken"] = damage_taken
        target_ent["health_delta"] = -damage
        target_ent["attacker_id"] = attacker_id
        target_ent["hp"] = new_hp
        
        print(
            f"[{self.addr}] [PKT0F] NPC {target_id} attacked by {attacker_id}, damage={damage}, new HP {new_hp}")

        # Check if enemy died
        enemy_died = False
        if not target_ent.get("is_player", False) and new_hp <= 0:
            enemy_died = True
            target_ent["entState"] = Entity.const_6  # Dead state
            print(f"[{self.addr}] [DEATH] Enemy {target_id} died!")

            # Remove dead enemy from AI system
            ai_manager.enemy_died(target_id)

        # Notify AI system that enemy was attacked (only if still alive)
        if not target_ent.get("is_player", False) and not enemy_died:
            ai_manager.enemy_attacked(target_id, attacker_id, damage)
            
            # If enemy died, handle loot drop
            if enemy_died:
                handle_enemy_death(self, target_id, target_ent, attacker_id)

        # Send appropriate packet based on entity type
        is_player_entity = target_ent.get("is_player", False)
        update_packet = Send_Entity_Data(target_ent, is_player=is_player_entity)
        for other_session in all_sessions:
            if other_session.world_loaded and other_session.current_level == self.current_level:
                other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)
                entity_type = "Player" if is_player_entity else "NPC"
                print(f"[{self.addr}] [PKT0F] Broadcasted {entity_type} {target_id} update to {other_session.addr}")

    def Send_NPC_Updates(self):
        for ent_id, entity in self.entities.items():
            if not entity.get("is_player", False):
                # Don't override the state of dead enemies
                current_hp = entity.get("hp", 100)
                if current_hp > 0 and entity.get("entState") != Entity.const_6:
                    # Only reset state for living enemies that aren't in a special state
                    if entity.get("entState") not in [Entity.const_467, Entity.const_6]:  # Don't override drama or dead states
                        entity["entState"] = Entity.const_399  # Sleep state for idle enemies

                update_packet = Send_Entity_Data(entity, is_player=False)
                self.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)
                # print(f"[{self.addr}] [NPC Update] Sent 0x0F for NPC {ent_id}: state={entity['entState']}, pos=({entity['x']}, {entity['y']})")

    def stop(self):
        self.running = False
        self.cleanup()

    def get_entity(self, entity_id):
        """
        Retrieve an entity from session.entities by its ID.
        Returns the entity dictionary or None if not found.
        """
        return self.entities.get(entity_id)

    def issue_token(self, char, target_level, previous_level):
        tk = new_transfer_token()
        # Use session.current_level if previous_level is None
        previous_level = previous_level if previous_level else self.current_level or char.get("PreviousLevel",
                                                                                              "NewbieRoad")
        pending_world[tk] = (char, target_level, previous_level)
        self.active_tokens.add(tk)
        print(f"[{self.addr}] Issued token {tk} for {char['name']} to {target_level}, previous={previous_level}")
        return tk

    def cleanup(self):

        # Close the connection and remove the session
        try:
            self.conn.close()
        except:
            pass
        if self in all_sessions:
            all_sessions.remove(self)


def read_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def handle_client(session: ClientSession):
    def npc_update_loop():
        while session.running and session.world_loaded:
            session.Send_NPC_Updates()
            time.sleep(1)  # Update every 1 second

    def ai_update_loop():
        """AI update loop that handles enemy behavior"""
        loop_count = 0
        while session.running:
            if session.world_loaded and session.entities:
                try:
                    loop_count += 1
                    # Get all player entities for AI to consider
                    players = {eid: entity for eid, entity in session.entities.items()
                              if entity.get("is_player", False)}

                    # Debug output every 50 loops (5 seconds)
                    if loop_count % 50 == 0:
                        print(f"[AI DEBUG] Loop {loop_count}: {len(players)} players, {len(ai_manager.enemy_brains)} enemies")
                        for pid, player in players.items():
                            print(f"  Player {pid}: {player.get('name', 'Unknown')} at ({player.get('x', 0)}, {player.get('y', 0)})")
                        for eid, brain in ai_manager.enemy_brains.items():
                            print(f"  Enemy {eid}: state={brain.state}, pos=({brain.current_x}, {brain.current_y}), target={brain.most_hated_entity}")

                    # Update AI and get actions
                    actions = ai_manager.update_all_enemies(players)

                    # Update pet AI and get pet actions
                    pet_actions = pet_ai_manager.update_pets(players, 0.1)  # 0.1 second delta time
                    actions.extend(pet_actions)

                    # Debug actions
                    if actions:
                        print(f"[AI DEBUG] Generated {len(actions)} actions: {actions}")

                    # Process AI actions
                    for action in actions:
                        if action["type"] == "attack":
                            # Enemy attacking player - use the existing attack_entity method
                            attacker_id = action["attacker_id"]
                            target_id = action["target_id"]
                            damage = action["damage"]

                            # Use the existing attack method which handles all the packet formatting correctly
                            session.attack_entity(attacker_id, target_id, damage)
                            print(f"[AI] Enemy {attacker_id} attacked player {target_id} for {damage} damage")

                        elif action["type"] == "move":
                            # Enemy movement
                            entity_id = action["entity_id"]
                            if entity_id in session.entities:
                                entity = session.entities[entity_id]
                                entity["x"] = action["x"]
                                entity["y"] = action["y"]

                                # Broadcast enemy position update
                                update_packet = Send_Entity_Data(entity, is_player=False)
                                for other_session in all_sessions:
                                    if other_session.world_loaded and other_session.current_level == session.current_level:
                                        other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)

                        elif action["type"] == "state_change":
                            # Enemy animation state change
                            entity_id = action["entity_id"]
                            new_state = action["new_state"]
                            if entity_id in session.entities:
                                entity = session.entities[entity_id]
                                entity["entState"] = new_state

                                # Broadcast enemy state update
                                update_packet = Send_Entity_Data(entity, is_player=False)
                                for other_session in all_sessions:
                                    if other_session.world_loaded and other_session.current_level == session.current_level:
                                        other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)

                                print(f"[AI] Enemy {entity_id} animation state changed to {new_state}")

                        elif action["type"] == "respawn":
                            # Enemy respawn
                            entity_id = action["entity_id"]
                            entity_data = action["entity_data"]

                            # Update entity in session
                            session.entities[entity_id] = entity_data

                            # Broadcast enemy respawn to all clients
                            update_packet = Send_Entity_Data(entity_data, is_player=False)
                            for other_session in all_sessions:
                                if other_session.world_loaded and other_session.current_level == session.current_level:
                                    other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)

                            print(f"[AI] Enemy {entity_id} respawned and broadcasted to clients")

                        elif action["type"] == "pet_move":
                            # Pet movement
                            entity_id = action["entity_id"]
                            if entity_id in session.entities:
                                entity = session.entities[entity_id]
                                entity["x"] = action["x"]
                                entity["y"] = action["y"]
                                entity["facing_left"] = action.get("facing_left", False)

                                # Broadcast pet position update
                                update_packet = Send_Entity_Data(entity, is_player=False)
                                for other_session in all_sessions:
                                    if other_session.world_loaded and other_session.current_level == session.current_level:
                                        other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)

                        elif action["type"] == "pet_state_change":
                            # Pet animation state change
                            entity_id = action["entity_id"]
                            new_state = action["new_state"]
                            if entity_id in session.entities:
                                entity = session.entities[entity_id]
                                entity["entState"] = new_state

                                # Broadcast pet state update
                                update_packet = Send_Entity_Data(entity, is_player=False)
                                for other_session in all_sessions:
                                    if other_session.world_loaded and other_session.current_level == session.current_level:
                                        other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)

                                print(f"[Pet AI] Pet {entity_id} animation state changed to {new_state}")

                        elif action["type"] == "pet_respawn":
                            # Pet respawn
                            entity_id = action["entity_id"]
                            if entity_id in session.entities:
                                entity = session.entities[entity_id]
                                entity["x"] = action["x"]
                                entity["y"] = action["y"]
                                entity["entState"] = action["new_state"]
                                entity["hp"] = entity.get("maxHP", 100)

                                # Broadcast pet respawn to all clients
                                update_packet = Send_Entity_Data(entity, is_player=False)
                                for other_session in all_sessions:
                                    if other_session.world_loaded and other_session.current_level == session.current_level:
                                        other_session.conn.sendall(struct.pack(">HH", 0x0F, len(update_packet)) + update_packet)

                                print(f"[Pet AI] Pet {entity_id} respawned and broadcasted to clients")

                except Exception as e:
                    print(f"[AI] Error in AI update loop: {e}")

            time.sleep(0.1)  # Update AI 10 times per second

    def forge_tick_loop():
        while session.running:
            tick_forge_status(session)
            time.sleep(1)

    conn, addr = session.conn, session.addr
    print("Connected:", addr)
    conn.settimeout(300)
    try:
        # Start NPC update thread
        threading.Thread(target=forge_tick_loop, daemon=True).start()
        threading.Thread(target=npc_update_loop, daemon=True).start()
        threading.Thread(target=ai_update_loop, daemon=True).start()
        while True:
            hdr = read_exact(conn, 4)
            if not hdr:
                break
            pkt_id, length = struct.unpack(">HH", hdr)
            payload = read_exact(conn, length)
            if payload is None:
                break
            data = hdr + payload
            pkt = int(data.hex()[:4], 16)

            if pkt == 0x11:
                sid = int(data.hex()[8:12], 16) if len(data) >= 6 else 0
                conn.sendall(build_handshake_response(sid))

            elif pkt == 0x13:
                payload = data[8:]
                br = BitReader(payload)
                email = br.read_string().strip().lower()
                session.user_id = get_or_create_user_id(email)
                session.char_list = load_characters(session.user_id)
                try:
                    with open(f"saves/{session.user_id}.json", "r", encoding="utf-8") as f:
                        session.player_data = json.load(f)
                except FileNotFoundError:
                    session.player_data = {}
                session.authenticated = True
                conn.sendall(build_login_character_list_bitpacked(session.char_list))

            elif pkt == 0x14:
                br = BitReader(data[4:], debug=True)
                try:
                    _ = br.read_string()
                    _ = br.read_string()
                    email = br.read_string().strip().lower()
                    _ = br.read_string()
                    _ = br.read_string()
                except Exception as e:
                    print(f"[{session.addr}] [PKT0x14] Error parsing packet: {e}, raw payload={data[4:].hex()}")
                    continue
                accounts = load_accounts()
                user_id = accounts.get(email)
                if not user_id:
                    print(f"[{session.addr}] [PKT0x14] Login failed—no account for {email}")
                    err_packet = build_popup_packet("Account not found", disconnect=True)
                    conn.sendall(err_packet)
                    continue
                session.user_id = user_id
                try:
                    with open(os.path.join(_SAVES_DIR, f"{session.user_id}.json"), "r", encoding="utf-8") as f:
                        session.player_data = json.load(f)
                except FileNotFoundError:
                    session.player_data = {"email": email, "characters": []}
                session.char_list = session.player_data.get("characters", [])
                session.authenticated = True
                conn.sendall(build_login_character_list_bitpacked(session.char_list))
                print(
                    f"[{session.addr}] [PKT0x14] Logged in {email} → user_id={user_id}, chars={len(session.char_list)}")

            elif pkt == 0x17:
                if not session.authenticated:
                    err_packet = build_popup_packet("Please log in first", disconnect=True)
                    conn.sendall(err_packet)
                    continue
                br = BitReader(data[4:], debug=True)
                try:
                    tup = (
                        br.read_string(),  # name
                        br.read_string(),  # class
                        50,  # level
                        br.read_string(),  # gender
                        br.read_string(),  # head
                        br.read_string(),  # hair
                        br.read_string(),  # mouth
                        br.read_string(),  # face
                        br.read_bits(24),  # hairColor
                        br.read_bits(24),  # skinColor
                        br.read_bits(24),  # shirtColor
                        br.read_bits(24),  # pantColor
                        None  # equipped_gear
                    )
                    print(
                        f"[{session.addr}] [PKT0x17] Parsed character creation: name={tup[0]}, class={tup[1]}, gender={tup[3]}")
                except Exception as e:
                    print(f"[{session.addr}] [PKT0x17] Error parsing packet: {e}, raw payload={data[4:].hex()}")
                    continue
                # Check for duplicate character name
                if is_character_name_taken(tup[0]):
                    print(f"[{session.addr}] [PKT0x17] Character name {tup[0]} is already taken")
                    err_packet = build_popup_packet("Character name is unavailable. Please choose a new name.",
                                                    disconnect=False)
                    conn.sendall(err_packet)
                    continue
                new_char = make_character_dict_from_tuple(tup)
                session.char_list.append(new_char)
                save_characters(session.user_id, session.char_list)
                # Send updated character list (0x15)
                conn.sendall(build_login_character_list_bitpacked(session.char_list))
                print(f"[{session.addr}] [PKT0x17] Sent 0x15 character list update")
                # Send paperdoll packet (0x1A)
                pd = build_paperdoll_packet(new_char)
                conn.sendall(struct.pack(">HH", 0x1A, len(pd)) + pd)
                print(
                    f"[{session.addr}] [PKT0x17] Sent 0x1A paperdoll packet, len={len(pd)},")
                # Send popup message (0x1B)
                popup = build_popup_packet("Character Successfully Created", disconnect=False)
                conn.sendall(popup)
                print(f"[{session.addr}] [PKT0x17] Sent 0x1B popup message")

            elif pkt == 0x19:
                name = BitReader(data[4:]).read_string()
                for c in session.char_list:
                    if c["name"] == name:
                        pd = build_paperdoll_packet(c)
                        conn.sendall(struct.pack(">HH", 0x1A, len(pd)) + pd)
                        break
                else:
                    conn.sendall(struct.pack(">HH", 0x1A, 0))

            elif pkt == 0x16:
                name = BitReader(data[4:]).read_string()
                for c in session.char_list:
                    if c["name"] == name:
                        session.current_character = name
                        current_level = c.get("CurrentLevel", {}).get("name", "CraftTown")
                        session.current_level = current_level
                        c["user_id"] = session.user_id
                        # Set default PreviousLevel if unset
                        prev_name = c.get("PreviousLevel", {}).get("name", "NewbieRoad")
                        tk = session.issue_token(c, target_level=current_level, previous_level=prev_name)
                        level_config = LEVEL_CONFIG.get(current_level, ("LevelsNR.swf/a_Level_NewbieRoad", 1, 1, False))
                        pkt_out = build_enter_world_packet(
                            transfer_token=tk,
                            old_level_id=0,
                            old_swf="",
                            has_old_coord=False,
                            old_x=0,
                            old_y=0,
                            host="127.0.0.1",
                            port=8080,
                            new_level_swf=level_config[0],
                            new_map_lvl=level_config[1],
                            new_base_lvl=level_config[2],
                            new_internal=current_level,
                            new_moment="",
                            new_alter="",
                            new_is_inst=level_config[3],
                            new_has_coord=False,
                            new_x=0,
                            new_y=0,
                            char=c
                        )
                        session.conn.sendall(pkt_out)
                        # Save updated char_list to ensure PreviousLevel is set
                        session.char_list = load_characters(session.user_id)
                        for i, char in enumerate(session.char_list):
                            if char["name"] == name:
                                session.char_list[i] = c
                                break
                        save_characters(session.user_id, session.char_list)
                        print(f"[{session.addr}] Transfer begin: {name}, tk={tk}, level={current_level}")
                        break

            elif pkt == 0x1f:
                if len(data) < 6:
                    print(f"[{session.addr}] Error: Packet 0x1f too short, len={len(data)}")
                    continue
                token = int.from_bytes(data[4:6], 'big')
                entry = pending_world.pop(token, None)
                if entry is None:
                    if len(pending_world) == 1:
                        token, entry = next(iter(pending_world.items()))
                        pending_world.pop(token)
                    else:
                        print(
                            f"[{session.addr}] Error: No entry found for token {token}, pending_world size={len(pending_world)}")
                        continue
                session.active_tokens.discard(token)
                if len(entry) == 2:
                    char, target_level = entry
                    previous_level = session.current_level or char.get("PreviousLevel", {}).get("name", "NewbieRoad")
                else:
                    char, target_level, previous_level = entry
                    if isinstance(previous_level, dict):
                        previous_level = previous_level.get("name", "NewbieRoad")
                if char is None:
                    print(f"[{session.addr}] Error: Character is None for token {token}")
                    continue
                is_dungeon = LEVEL_CONFIG.get(target_level, (None, None, None, False))[3]
                if is_dungeon:
                    session.entry_level = previous_level if previous_level else char.get("PreviousLevel", "NewbieRoad")
                else:
                    session.entry_level = None
                session.user_id = char["user_id"]
                if not session.user_id:
                    print(f"[{session.addr}] Error: session.user_id is None for token {token}")
                    continue
                session.char_list = load_characters(session.user_id)
                if session.char_list:
                    for i, c in enumerate(session.char_list):
                        if c["name"] == char["name"]:
                            session.char_list[i] = char
                            break
                    else:
                        session.char_list.append(char)
                else:
                    session.char_list = [char]
                save_characters(session.user_id, session.char_list)
                print(
                    f"[{session.addr}] Saved character {char['name']}: CurrentLevel={char['CurrentLevel']}, PreviousLevel={char.get('PreviousLevel')}")

                session.current_level = target_level
                session.current_character = char["name"]
                session.current_char_dict = char
                current_characters[session.user_id] = session.current_character
                session.authenticated = True
                session.entities[token] = {
                    "id": token,
                    "x": 360.0,  # Temporary; will be overridden by Player_Data_Packet
                    "y": 1458.99,
                    "z": 0.0,
                    "entState": Entity.const_78,  # Active state (0) instead of dead state (3)
                    "is_player": True,
                    "name": char["name"],
                    "hp": char.get("hp", 100),
                    "max_hp": char.get("max_hp", 100),
                    # Add appearance data required for player entity packets
                    "class": char.get("class", "Paladin"),
                    "headSet": char.get("headSet", "Head01"),
                    "hairSet": char.get("hairSet", "Hair01"),
                    "mouthSet": char.get("mouthSet", "Mouth01"),
                    "faceSet": char.get("faceSet", "Face01"),
                    "hairColor": char.get("hairColor", 0),
                    "skinColor": char.get("skinColor", 0),
                    "shirtColor": char.get("shirtColor", 0),
                    "pantColor": char.get("pantColor", 0),
                    "equippedGears": char.get("equippedGears", [[0, 0, 0, 0, 0, 0]] * 6)
                }

                # Spawn player's pet if they have one equipped
                spawn_player_pet(session, char, token)
                used_tokens[token] = (
                    char, target_level, session.current_level or char.get("PreviousLevel", "NewbieRoad"))
                # Calculate coordinates for Player_Data_Packet
                new_x, new_y, new_has_coord = get_spawn_coordinates(char, previous_level, target_level)
                welcome = Player_Data_Packet(
                    char,
                    transfer_token=token,
                    target_level=target_level,
                    new_x=int(round(new_x)),
                    new_y=int(round(new_y)),
                    new_has_coord=new_has_coord,
                )

                conn.sendall(welcome)
                session.clientEntID = token
                print(
                    f"[{session.addr}] Welcome: {char['name']} (token {token}) on level {session.current_level}, pos=({new_x},{new_y})")

            # Level Transfer request
            elif pkt == 0x1D:
                br = BitReader(data[4:])
                try:
                    _old_token = br.read_method_9()
                    level_name = br.read_method_13()
                except Exception as e:
                    print(f"[{session.addr}] ERROR: Failed to parse 0x1D packet: {e}, raw payload = {data[4:].hex()}")
                    continue
                print(f"[{session.addr}] TRANSFER_READY → {level_name}, old_token={_old_token}")
                # 1) Pull the pending entry
                entry = pending_world.pop(_old_token, None) or used_tokens.get(_old_token)
                if not entry:
                    print(f"[{session.addr}] ERROR: No character for token {_old_token}")
                    continue
                # 2) Unpack character and target_level
                char, target_level = entry[:2]
                # 3) Snapshot the level we're leaving (extract name if it’s a dict)
                raw = char.get("CurrentLevel")
                if isinstance(raw, dict):
                    old_level = raw.get("name", session.current_level or "NewbieRoad")
                else:
                    old_level = raw or session.current_level or "NewbieRoad"

                # 4) Clear player’s entity from old level to reflect they’ve left
                if session.clientEntID in session.entities:
                    del session.entities[session.clientEntID]
                    print(f"[{session.addr}] Removed entity {session.clientEntID} from level {old_level}")
                # 5) Bootstrap session with this character
                session.user_id = char.get("user_id")
                if not session.user_id:
                    print(f"[{session.addr}] ERROR: char['user_id'] missing for {char['name']}")
                    continue
                session.char_list = load_characters(session.user_id)
                session.current_character = char["name"]
                session.authenticated = True
                # 6) If the packet's level_name is empty, fallback
                if not level_name:
                    level_name = target_level
                    print(f"[{session.addr}] WARNING: Empty level_name, using target_level={level_name}")
                # 7) Update the character record
                is_dungeon = LEVEL_CONFIG.get(level_name, (None, None, None, False))[3]

                # 7a) Save current level’s coords to PreviousLevel
                prev_rec = char.get("CurrentLevel", {})
                prev_x = prev_rec.get("x", 0.0)
                prev_y = prev_rec.get("y", 0.0)
                char["PreviousLevel"] = {
                    "name": old_level,
                    "x": prev_x,
                    "y": prev_y
                }
                # 7b) Determine coordinates for the new level
                new_x, new_y, new_has_coord = get_spawn_coordinates(char, old_level, level_name)
                # 7c) Update CurrentLevel (skip coords for dungeons unless CraftTown)
                if not is_dungeon or level_name == "CraftTown":
                    char["CurrentLevel"] = {"name": level_name, "x": new_x, "y": new_y}
                save_characters(session.user_id, session.char_list)

                # 8) Write back into session.char_list and save
                for i, c in enumerate(session.char_list):
                    if c["name"] == char["name"]:
                        session.char_list[i] = char
                        break
                else:
                    session.char_list.append(char)
                save_characters(session.user_id, session.char_list)
                print(f"[{session.addr}] Saved character {char['name']}: "
                      f"CurrentLevel={char['CurrentLevel']}, PreviousLevel={char['PreviousLevel']}")
                # 9) Update session.current_level
                session.current_level = level_name
                session.world_loaded = False
                # 10) For testing purposes only; uncomment to broadcast level change, remove after testing
                broadcast_level_change(session, char["name"], level_name)
                # 11) Issue the new transfer token
                new_token = session.issue_token(
                    char,
                    target_level=level_name,
                    previous_level=old_level
                )
                # 12) Build and send the ENTER_WORLD packet
                swf_path, map_id, base_id, is_inst = LEVEL_CONFIG[level_name]
                pkt_out = build_enter_world_packet(
                    transfer_token=new_token,
                    old_level_id=0,
                    old_swf="",
                    has_old_coord=False,
                    old_x=0,
                    old_y=0,
                    host="127.0.0.1",
                    port=8080,
                    new_level_swf=swf_path,
                    new_map_lvl=map_id,
                    new_base_lvl=base_id,
                    new_internal=level_name,
                    new_moment="",
                    new_alter="",
                    new_is_inst=is_inst,
                    new_has_coord=new_has_coord,
                    new_x=int(round(new_x)),
                    new_y=int(round(new_y)),
                    char=char,
                )
                session.conn.sendall(pkt_out)
                print(
                    f"[{session.addr}] Sent ENTER_WORLD with token {new_token} for level {level_name}, pos=({new_x},{new_y})")

            elif pkt == 0x2D:
                br = BitReader(data[4:])
                try:
                    door_id = br.read_method_9()
                except Exception as e:
                    print(f"[{session.addr}] ERROR: Failed to parse 0x2D packet: {e}, raw payload = {data[4:].hex()}")
                    continue
                print(f"[{session.addr}] OpenDoor request: doorID={door_id}, current_level={session.current_level}")
                is_dungeon = LEVEL_CONFIG.get(session.current_level, (None, None, None, False))[3]
                # Determine target level
                target_level = None
                if is_dungeon and door_id in (0, 1, 2):
                    target_level = session.entry_level
                    if not target_level:
                        print(
                            f"[{session.addr}] Error: No entry_level set for door {door_id} in dungeon {session.current_level}")
                        continue
                elif door_id == 999:
                    target_level = "CraftTown"
                else:
                    target_level = DOOR_MAP.get((session.current_level, door_id))
                if target_level:
                    if target_level not in LEVEL_CONFIG:
                        print(f"[{session.addr}] Error: Target level {target_level} not found in LEVEL_CONFIG")
                        continue
                    # Send DOOR_TARGET response
                    bb = BitBuffer()
                    bb.write_method_4(door_id)
                    bb.write_method_13(target_level)
                    payload = bb.to_bytes()
                    resp = struct.pack(">HH", 0x2E, len(payload)) + payload
                    session.conn.sendall(resp)
                    print(f"[{session.addr}] Sent DOOR_TARGET: doorID={door_id}, level='{target_level}'")
                    # Reset world state
                    session.world_loaded = False
                    session.entities.clear()
                else:
                    print(f"[{session.addr}] Error: No target for door {door_id} in level {session.current_level}")

            elif pkt == 0x107:
                CAT_BITS = 3
                ID_BITS = 6
                PACK_ID = 1
                reward_map = {
                    0: ("MountLockbox01L01", True),  # Mount
                    1: ("Lockbox01L01", True),  # Pet
                    # 2: ("GenericBrown", True),  # Egg
                    # 3: ("CommonBrown", True),  # Egg
                    # 4: ("OrdinaryBrown", True),  # Egg
                    # 5: ("PlainBrown", True),  # Egg
                    6: ("RarePetFood", True),  # Consumable
                    7: ("PetFood", True),  # Consumable
                    # 8: ("Lockbox01Gear", True),  # Gear (will crash if invalid)
                    9: ("TripleFind", True),  # Charm
                    10: ("DoubleFind1", True),  # Charm
                    11: ("DoubleFind2", True),  # Charm
                    12: ("DoubleFind3", True),  # Charm
                    13: ("MajorLegendaryCatalyst", True),  # Consumable
                    14: ("MajorRareCatalyst", True),  # Consumable
                    15: ("MinorRareCatalyst", True),  # Consumable
                    16: (None, False),  # Gold (3 000 000)
                    17: (None, False),  # Gold (1 500 000)
                    18: (None, False),  # Gold (750 000)
                    19: ("DyePack01Legendary", True),  # Dye‐pack
                }
                idx, (name, needs_str) = random.choice(list(reward_map.items()))
                bb = BitBuffer()
                bb.write_method_6(PACK_ID, CAT_BITS)
                bb.write_method_6(idx, ID_BITS)
                bb.write_bits(1 if needs_str else 0, 1)
                if needs_str:
                    bb.write_utf_string(name)
                payload = bb.to_bytes()
                packet = struct.pack(">HH", 0x108, len(payload)) + payload
                session.conn.sendall(packet)
                print(f"Lockbox reward: idx={idx}, name={name}, needs_str={needs_str}")

            elif pkt == 0xBA:
                payload = data[4:]
                br = BitReader(payload)
                entity_id = br.read_method_4()
                dyes_by_slot = {}
                for slot in range(1, EntType.MAX_SLOTS):
                    has_pair = br.read_bits(1)
                    if has_pair:
                        d1 = br.read_bits(DyeType.BITS)
                        d2 = br.read_bits(DyeType.BITS)
                        dyes_by_slot[slot - 1] = (d1, d2)
                preview_only = bool(br.read_bits(1))
                primary_dye = br.read_bits(DyeType.BITS) if br.read_bits(1) else None
                secondary_dye = br.read_bits(DyeType.BITS) if br.read_bits(1) else None
                print(f"[Dyes] entity={entity_id}, dyes={dyes_by_slot}, "
                      f"preview={preview_only}, shirt={primary_dye}, pants={secondary_dye}")
                handle_apply_dyes(session, entity_id, dyes_by_slot, preview_only, primary_dye, secondary_dye)

            elif pkt == 0x41:
                handle_packet_0x41(session, data, conn)
            elif pkt == 0x7C:
                handle_packet_0x7C(session, data)
            elif pkt == 0xA2:
                handle_position_sync(session, data, all_sessions)

            #TODO...
            #elif pkt == 0x08:
            #    handle_entity_full_update(session, data, all_sessions)
            #####
            elif pkt == 0x08:
                if session.world_loaded:
                    # print(f"[{session.addr}] World already loaded; skipping NPC spawn.")
                    continue
                try:
                    npcs = load_npc_data_for_level(session.current_level)
                    for npc in npcs:
                        payload = Send_Entity_Data(npc, is_player=False)
                        conn.sendall(struct.pack(">HH", 0x0F, len(payload)) + payload)
                        session.entities[npc["id"]] = npc
                        session.spawned_npcs.append(npc)

                        # Add enemy to AI system if it's hostile (team != 1 which is player team)
                        if npc.get("team", 0) != 1 and npc.get("behavior_id", 0) > 0:
                            ai_manager.add_enemy(npc["id"], npc)

                    # Broadcast pets to all clients in the same level
                    pets_spawned = 0
                    for entity_id, entity in session.entities.items():
                        if entity.get("is_pet", False):
                            # Send pet entity to all clients in the same level
                            pet_payload = Send_Entity_Data(entity, is_player=False)
                            for other_session in all_sessions:
                                if other_session.world_loaded and other_session.current_level == session.current_level:
                                    other_session.conn.sendall(struct.pack(">HH", 0x0F, len(pet_payload)) + pet_payload)
                            pets_spawned += 1

                    session.world_loaded = True
                    session.Send_NPC_Updates()  # Send initial NPC updates
                    print(f"[{session.addr}] Spawned {len(npcs)} NPCs and {pets_spawned} pets for level {session.current_level}")
                except Exception as e:
                    print(f"[{session.addr}] Error spawning NPCs: {e}")

            elif pkt == 0x07:
                handle_entity_incremental_update(session, data, all_sessions)
            elif pkt == 0x09:
                handle_power_cast(session, data, all_sessions)
            elif pkt == 0x0A:
                handle_power_hit(session, data, all_sessions)
            elif pkt == 0x0E:
                handle_projectile_explode(session, data, all_sessions)
            elif pkt == 0x0E:
                handle_projectile_explode(session, data, all_sessions)
            elif pkt == 0x0B:
                handle_add_buff(session, data, all_sessions)
            elif pkt == 0x0C:
                handle_remove_buff(session, data, all_sessions)
            elif pkt == 0xDE:
                bb = BitBuffer()
                bb.write_bits(1, 16)
                bb.write_bits(2, 8)
                bb.write_bits(0, 32)
                payload = bb.to_bytes()
                conn.sendall(struct.pack(">HH", 0xBF, len(payload)) + payload)
                print(f"[{addr}] TEST: sent BUILDING-UPDATE 0xBF len={len(payload)}")
            elif pkt == 0x65:
                handle_group_invite(session, data, all_sessions)
            elif pkt == 0x2C:
                handle_public_chat(session, data, all_sessions)
            elif pkt == 0x46:
                handle_private_message(session, data, all_sessions)
            elif pkt == 0xC3:
                handle_masterclass_packet(session, data)
            elif pkt == 0xDF:
                handle_research_packet(session, data)
            elif pkt == 0x31:
                handle_gear_packet(session, data)
            elif pkt == 0x8E:
                handle_change_look(session, data, all_sessions)
            elif pkt == 0xC7:
                handle_create_gearset(session, data)
            elif pkt == 0xC8:
                handle_name_gearset(session, data)
            elif pkt == 0xC6:
                handle_apply_gearset(session, data)
            elif pkt == 0x30:
                handle_update_equipment(session, data)
            elif pkt == 0xBD:
                handle_hotbar_packet(session, data)  # Active Skills
            elif pkt == 0xE2:
                magic_forge_packet(session, data)
            elif pkt == 0xD0:
                collect_forge_charm(session, data)
            elif pkt == 0xB0:
                handle_rune_packet(session, data)
            elif pkt == 0xB1:
                start_forge_packet(session, data)
            elif pkt == 0xE1:
                cancel_forge_packet(session, data)
            elif pkt == 0xD3:
                allocate_talent_points(session, data)
            elif pkt == 0x110:
                use_forge_xp_consumable(session, data)

            elif pkt == 0xCC:
                pass
            elif pkt == 0x10E:
                pass
            elif pkt == 0x107:  # PKTTYPE_PICKUP_LOOTDROP (approximate)
                # Handle loot pickup
                try:
                    br = BitReader(data[4:])
                    loot_id = br.read_method_4()
                    print(f"[LOOT] Player picked up loot ID: {loot_id}")
                    # The gear is already added to inventory when dropped
                    # This is just for confirmation
                except Exception as e:
                    print(f"[LOOT] Error handling loot pickup: {e}")

            else:
                print(f"[{session.addr}] Unhandled packet type: 0x{pkt:02X}, raw payload = {data.hex()}")
    except Exception as e:
        print("Session error:", e)
    finally:
        print("Disconnect:", addr)
        session.stop()

def start_server(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((HOST, port))
    except PermissionError:
        print(f"Error: Cannot bind to port {port}. Ports below 1024 require root privileges.")
        return None
    except OSError as e:
        print(f"Error: Cannot bind to port {port}. {e}")
        return None
    s.listen(5)
    print(f"Server listening on {HOST}:{port}")
    return s

def accept_connections(s, port):
    while True:
        conn, addr = s.accept()
        session = ClientSession(conn, addr)
        all_sessions.append(session)
        threading.Thread(target=handle_client, args=(session,), daemon=True).start()

def start_servers():
    servers = []
    for port in PORTS:
        server = start_server(port)
        if server:
            servers.append((server, port))
            threading.Thread(target=accept_connections, args=(server, port), daemon=True).start()
    return servers

if __name__ == "__main__":
    start_policy_server(host="127.0.0.1", port=843)
    start_static_server(host="127.0.0.1", port=80, directory="content/localhost")
    servers = start_servers()
    print("For Browser running on : http://localhost/index.html")
    print("For Flash Projector running on : http://localhost/p/cbv/DungeonBlitz.swf?fv=cbq&gv=cbv")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down servers...")
        for server, port in servers:
            server.close()
        sys.exit(0)
