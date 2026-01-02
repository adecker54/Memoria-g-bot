import os
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Adattárolás (memóriában)
player_stats = {}  # {user_id: {"name": str, "plays": int, "best_score": int, "scores": []}}
game_sessions = {}  # {user_id: {"sequence": [], "level": int, "score": int}}
game_closed = False

# Emoji-k a játékhoz
EMOJIS = ["🔴", "🔵", "🟢", "🟡", "🟣", "🟠", "⚫", "⚪"]

def get_player(user_id, user_name):
    """Játékos adatainak lekérése vagy létrehozása"""
    if user_id not in player_stats:
        player_stats[user_id] = {
            "name": user_name,
            "plays": 0,
            "best_score": 0,
            "scores": []
        }
    return player_stats[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Üdvözlő üzenet és szabályok"""
    welcome_text = """
🎮 **EMLÉKEZZ A SORRENDRE - Játékszabályok**

📋 **Hogyan működik:**
1️⃣ A bot mutat egy emoji-sorrendet
2️⃣ Jegyezd meg 5 másodperc alatt!
3️⃣ Aztán add vissza a helyes sorrendet gombokkal
4️⃣ Minden helyes válasz után nehezebb lesz

⏱️ **Játékidő:** 1 perc összesen
🎯 **Pontszerzés:** 
   - 3 hosszú = 10 pont
   - 4 hosszú = 20 pont
   - 5 hosszú = 30 pont
   - 6+ hosszú = 50 pont

🎲 **Maximum 10 játék** játékosként!

📊 **Parancsok:**
   /play - Játék indítása
   /leaderboard - Ranglista megtekintése
   /mystats - Saját statisztikáid

🏆 Sok szerencsét!
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Új játék indítása"""
    if game_closed:
        await update.message.reply_text("🔒 A játék le van zárva! Nézd meg az eredményeket: /results")
        return
    
    user = update.effective_user
    player = get_player(user.id, user.first_name)
    
    if player["plays"] >= 10:
        await update.message.reply_text(
            f"⛔ Elérted a maximum 10 próbálkozást!\n"
            f"🏆 Legjobb eredményed: {player['best_score']} pont"
        )
        return
    
    # Új játék kezdése
    player["plays"] += 1
    sequence = random.sample(EMOJIS, 3)
    
    game_sessions[user.id] = {
        "sequence": sequence,
        "level": 1,
        "score": 0,
        "start_time": datetime.now(),
        "user_input": []
    }
    
    sequence_text = " ".join(sequence)
    await update.message.reply_text(
        f"🎮 **Játék #{player['plays']}/10**\n\n"
        f"👀 Jegyezd meg ezt a sorrendet:\n\n"
        f"**{sequence_text}**\n\n"
        f"⏳ 5 másodperc...",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(5)
    
    # Ellenőrizzük, hogy még fut-e a játék
    if user.id not in game_sessions:
        return
    
    # Gombok létrehozása
    keyboard = []
    for i in range(0, len(EMOJIS), 4):
        row = [InlineKeyboardButton(emoji, callback_data=f"pick_{emoji}") 
               for emoji in EMOJIS[i:i+4]]
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤔 Most add vissza a sorrendet!\n"
        f"📍 Válassz: 1/{len(sequence)}",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gomb megnyomás kezelése"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in game_sessions:
        await query.edit_message_text("❌ Nincs aktív játékod! Indíts újat: /play")
        return
    
    session = game_sessions[user_id]
    
    # Időellenőrzés (1 perc)
    elapsed = (datetime.now() - session["start_time"]).total_seconds()
    if elapsed > 60:
        final_score = session["score"]
        player = player_stats[user_id]
        player["scores"].append(final_score)
        if final_score > player["best_score"]:
            player["best_score"] = final_score
        
        del game_sessions[user_id]
        await query.edit_message_text(
            f"⏰ Lejárt az idő!\n"
            f"🎯 Végső pontszám: {final_score}"
        )
        return
    
    # Választott emoji feldolgozása
    picked_emoji = query.data.replace("pick_", "")
    session["user_input"].append(picked_emoji)
    
    current_pos = len(session["user_input"])
    sequence = session["sequence"]
    
    # Ellenőrzés
    if session["user_input"][-1] != sequence[current_pos - 1]:
        # Rossz válasz
        final_score = session["score"]
        player = player_stats[user_id]
        player["scores"].append(final_score)
        if final_score > player["best_score"]:
            player["best_score"] = final_score
        
        del game_sessions[user_id]
        await query.edit_message_text(
            f"❌ Rossz sorrend!\n"
            f"🎯 Végső pontszám: {final_score}\n\n"
            f"Helyes volt: {' '.join(sequence)}\n"
            f"Te: {' '.join(session['user_input'])}"
        )
        return
    
    # Ha még nincs kész a sorrend
    if current_pos < len(sequence):
        await query.edit_message_text(
            f"✅ Helyes! Válassz tovább!\n"
            f"📍 {current_pos + 1}/{len(sequence)}"
        )
        
        # Gombok újraküldése
        keyboard = []
        for i in range(0, len(EMOJIS), 4):
            row = [InlineKeyboardButton(emoji, callback_data=f"pick_{emoji}") 
                   for emoji in EMOJIS[i:i+4]]
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Válassz: {current_pos + 1}/{len(sequence)}",
            reply_markup=reply_markup
        )
        return
    
    # Teljes sorrend helyes!
    level = session["level"]
    points = 10 * level if level <= 3 else 50
    session["score"] += points
    session["level"] += 1
    
    # Új, nehezebb sorrend
    new_length = min(3 + level, 8)
    new_sequence = random.sample(EMOJIS, new_length)
    session["sequence"] = new_sequence
    session["user_input"] = []
    
    sequence_text = " ".join(new_sequence)
    await query.edit_message_text(
        f"🎉 Perfekt! +{points} pont\n"
        f"💯 Össz pontszám: {session['score']}\n\n"
        f"🆙 Következő szint ({level + 1}):\n\n"
        f"**{sequence_text}**\n\n"
        f"⏳ 5 másodperc...",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(5)
    
    # Gombok az új szinthez
    keyboard = []
    for i in range(0, len(EMOJIS), 4):
        row = [InlineKeyboardButton(emoji, callback_data=f"pick_{emoji}") 
               for emoji in EMOJIS[i:i+4]]
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        f"🤔 Add vissza ezt a sorrendet!\n"
        f"📍 1/{len(new_sequence)}",
        reply_markup=reply_markup
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ranglista megjelenítése"""
    if not player_stats:
        await update.message.reply_text("📊 Még senki nem játszott!")
        return
    
    sorted_players = sorted(
        player_stats.items(),
        key=lambda x: x[1]["best_score"],
        reverse=True
    )
    
    text = "🏆 **RANGLISTA - Top 10**\n\n"
    for idx, (user_id, data) in enumerate(sorted_players[:10], 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        text += f"{medal} **{data['name']}** - {data['best_score']} pont ({data['plays']}/10 játék)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saját statisztikák"""
    user = update.effective_user
    player = get_player(user.id, user.first_name)
    
    avg_score = sum(player["scores"]) / len(player["scores"]) if player["scores"] else 0
    
    text = (
        f"📊 **{player['name']} statisztikái**\n\n"
        f"🎮 Játékok: {player['plays']}/10\n"
        f"🏆 Legjobb: {player['best_score']} pont\n"
        f"📈 Átlag: {avg_score:.1f} pont"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def close_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Játék lezárása (csak admin)"""
    global game_closed
    game_closed = True
    await update.message.reply_text("🔒 Játék lezárva! Eredmények: /results")

async def results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Végső eredmények látványos megjelenítése"""
    if not player_stats:
        await update.message.reply_text("📊 Még senki nem játszott!")
        return
    
    sorted_players = sorted(
        player_stats.items(),
        key=lambda x: x[1]["best_score"],
        reverse=True
    )
    
    if len(sorted_players) >= 3:
        text = "🎊 **VÉGEREDMÉNY** 🎊\n\n"
        text += "┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += "┃   🥇 ELSŐ HELYEZETT   ┃\n"
        text += "┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"👑 **{sorted_players[0][1]['name']}**\n"
        text += f"🏆 **{sorted_players[0][1]['best_score']} pont**\n\n"
        
        text += "┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += "┃  🥈 MÁSODIK HELYEZETT ┃\n"
        text += "┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"💎 **{sorted_players[1][1]['name']}**\n"
        text += f"🎯 **{sorted_players[1][1]['best_score']} pont**\n\n"
        
        text += "┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += "┃  🥉 HARMADIK HELYEZETT ┃\n"
        text += "┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"⭐ **{sorted_players[2][1]['name']}**\n"
        text += f"✨ **{sorted_players[2][1]['best_score']} pont**\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━\n"
        text += f"🎮 Összes játékos: {len(player_stats)}\n"
        text += "🎉 Gratulálunk mindenkinek!"
    else:
        text = "🏆 **RANGLISTA**\n\n"
        for idx, (user_id, data) in enumerate(sorted_players, 1):
            text += f"{idx}. **{data['name']}** - {data['best_score']} pont\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    """Bot indítása"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN hiányzik!")
        return
    
    application = Application.builder().token(token).build()
    
    # Parancsok
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("mystats", mystats))
    application.add_handler(CommandHandler("close", close_game))
    application.add_handler(CommandHandler("results", results))
    
    # Gombok
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Bot elindult!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()