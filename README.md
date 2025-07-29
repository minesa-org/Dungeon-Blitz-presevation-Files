# Dungeon Blitz Preservation Files

This repository contains the preservation files for Dungeon Blitz, including server implementation, client scripts, and game assets.

## Features

### Legendary Loot Drop System

A new loot drop system has been implemented that provides legendary Rogue equipment when enemies are killed:

- **30% chance** for legendary loot drop when an enemy dies
- **Rogue equipment only** - generates random Rogue gear items
- **Rare to Legendary upgrade** - if the player has Rare (tier 1) gear, it will be upgraded to Legendary (tier 2) instead of dropping new gear
- **Automatic inventory addition** - loot is automatically added to the player's inventory
- **Visual loot drops** - loot appears on the ground where the enemy died

#### Special Loot Drops

Some enemies have special loot drops with guaranteed items:

- **IntroGoblinDagger**: 100% chance to drop "Wolf's End Game" (Wolfclaw Dagger) - Legendary tier weapon

#### How it works:

1. When an enemy dies (HP reaches 0), the system checks for special loot drops first
2. If the enemy has special loot configured (like IntroGoblinDagger), it drops the guaranteed item
3. If no special loot, the system checks for a 30% chance to drop regular legendary loot
4. If the player has Rare gear in their inventory, one random Rare item is upgraded to Legendary
5. If no Rare gear exists, a new Legendary Rogue equipment item is generated and dropped
6. The loot appears at the enemy's death location
7. When the player picks up the loot, it's automatically added to their inventory

#### Supported Rogue Gear IDs:

The system generates loot from the following Rogue gear IDs:
- 27-52: Basic Rogue equipment
- 109-138: Advanced Rogue equipment  
- 199-228: Elite Rogue equipment
- 289-302: Master Rogue equipment
- 1163, 1171-1176: Special Rogue equipment

#### Rarity Tiers:

- **Tier 0**: Magic (M)
- **Tier 1**: Rare (R) 
- **Tier 2**: Legendary (L)

The system specifically generates Legendary (tier 2) equipment.

## Server Setup

### Reviving the original Dungeon Blitz experience for archival and preservation purposes.

---

## ⚡ How to Play

1. **Install Requirements** (listed below)
2. **Run** `server.py` (don't forget to cd into server first)
3. Choose how you'd like to play:

   * **Option 1:** Flash Projector

     * Open the projector
     * Go to `File` > `Open` > Paste this URL:
       `http://localhost/p/cbv/DungeonBlitz.swf?fv=cbq&gv=cbv`
   * **Option 2:** Flash-Compatible Browser

     * Open `http://localhost/index.html` in your browser

---

## 🪠 Requirements

1. This repository (game files)
2. [Python](https://www.python.org/)
3. A Flash-compatible browser **OR** a standalone Flash projector

---

## \:flashlight: Flash Options

### Option 1: Flash Projector

* Download from [this GitHub archive](https://github.com/Grubsic/Adobe-Flash-Player-Debug-Downloads-Archive)

### Option 2: Flash-Compatible Browser

* [Flash Browser](https://github.com/radubirsan/FlashBrowser) — Open-source project with built-in Flash support

#### Flash Player Installers:

* **For Firefox / Basilisk (NPAPI):**
  [Download NPAPI Flash Player](https://archive.org/download/flashplayerarchive/pub/flashplayer/installers/archive/fp_32.0.0.371_archive.zip/32_0_r0_371%2Fflashplayer32_0r0_371_win.exe)

* **For Opera / Chromium (PPAPI):**
  [Download PPAPI Flash Player](https://archive.org/download/flashplayerarchive/pub/flashplayer/installers/archive/fp_32.0.0.371_archive.zip/32_0_r0_371%2Fflashplayer32_0r0_371_winpep.exe)

> These installers are for version **32.0.0.371**, the last build without Adobe's end-of-life (EOL) kill switch. All files come from the [Adobe Flash Player Archive](https://archive.org/download/flashplayerarchive/).

---

## \:mag: Flash-Supported Browsers

* **[Chromium 82.0](https://chromium.en.uptodown.com/windows/download/2181158)**
* **[Firefox 84.0 (64-bit)](https://download-installer.cdn.mozilla.net/pub/firefox/releases/84.0/win64/en-US/Firefox%20Setup%2084.0.exe)** or [32-bit](https://download-installer.cdn.mozilla.net/pub/firefox/releases/84.0/win32/en-US/Firefox%20Setup%2084.0.exe)
* **[Basilisk Browser](https://www.basilisk-browser.org/)** (NPAPI compatible)

> ⚠️ Firefox will auto-update by default. Disable this in:
> `Menu (三) > Options > General > Firefox Updates`

> ⚠️ Chromium disables Flash by default. You must manually enable it in settings.

---

## 📜 Legal Notice

This project is for **archival** and **educational purposes only**. All assets remain the property of their original creators. No monetization, redistribution, or alteration of copyrighted material.

If you are a rights holder and wish this project removed, please open an issue.

---
