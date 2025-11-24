import discord
from discord.ext import commands
import mysql.connector
import random
import json
import os
import a2s 
import requests

# --- 1. إعدادات البوت والـ RCON (تُقرأ من Render) ---
TOKEN = os.getenv('DISCORD_TOKEN') 
PREFIX = "!"
LINKS_FILE = "links.json"
WEBHOOK_URL = os.getenv('WEBHOOK_URL') 

SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = int(os.getenv('SERVER_PORT'))
RCON_PASSWORD = os.getenv('RCON_PASSWORD')

# --- 2. إعدادات قاعدة البيانات (تُقرأ من Render) ---
DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASS'),
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME') 
}

# --- 3. الدوال المساعدة ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

def load_links():
    if not os.path.exists(LINKS_FILE): return {}
    try:
        with open(LINKS_FILE, "r") as f: return json.load(f)
    except: return {}

def save_links(links):
    with open(LINKS_FILE, "w") as f: json.dump(links, f)

def send_rcon_command(command):
    """ يرسل أمر RCON للسيرفر """
    try:
        address = (SERVER_IP, SERVER_PORT)
        a2s.rcon(address, RCON_PASSWORD, command)
        print(f"RCON Command sent: {command}")
        return True
    except Exception as e:
        print(f"RCON Error: {e}")
        return False

# 🔥🔥 تم تعديل هذه الدالة لتضمين رسالة FireZM / GlaD 🔥🔥
def send_webhook_log(player_name, amount_won, final_balance):
    """ يرسل إشعاراً لـ Discord Webhook في حالة الفوز الكبير """
    if not WEBHOOK_URL: return
    data = {
        "embeds": [{
            "title": "[FireZM] BIG SLOT WINNER! 🎰", # تعديل العنوان
            "description": f"**{player_name}** hit the jackpot and won!",
            "color": 15158332, 
            "fields": [
                {"name": "Winnings", "value": f"**+{amount_won}** Points", "inline": True},
                {"name": "New Balance Estimate", "value": f"{final_points} Points", "inline": True}
            ],
            # 🔥🔥 إضافة رسالة Powered by GlaD في الـ Footer 🔥🔥
            "footer": {
                "text": "System Powered by GlaD"
            }
        }]
    }
    try:
        requests.post(WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Webhook failed: {e}")


# --- 4. أوامر البوت ---
@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user}')

@bot.command()
async def link(ctx, steamid):
    links = load_links()
    links[str(ctx.author.id)] = steamid
    save_links(links)
    await ctx.send(f"✅ Account successfully linked to: `{steamid}`")

@bot.command()
async def slot(ctx, amount: int):
    if amount <= 0:
        await ctx.send("⚠️ Bet amount must be greater than 0.")
        return

    links = load_links()
    user_id = str(ctx.author.id)

    if user_id not in links:
        await ctx.send(f"❌ You are not linked! Use `{PREFIX}link STEAM_0:X:XXXX` first.")
        return

    steamid = links[user_id]
    
    player_name = ""
    current_points = 0
    
    # 1. التحقق من الرصيد وجلب اسم اللاعب من MySQL
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name, ammopacks FROM zp_players WHERE steamid = %s", (steamid,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
             await ctx.send("❌ Player data not found. Please join the server once to register.")
             return

        player_name = result['name']
        current_points = result['ammopacks'] 

        if current_points < amount:
            await ctx.send(f"❌ Insufficient balance! You have: **{current_points}** points.")
            return

    except mysql.connector.Error as err:
        await ctx.send(f"⚠️ Database connection error.")
        return

    # 🔥🔥 الخطوة 1: الخصم الفوري عبر RCON (Deduct Bet) 🔥🔥
    deduct_command = f'zp_points "{player_name}" -{amount}'
    deduct_success = send_rcon_command(deduct_command)

    if not deduct_success:
        await ctx.send("❌ Failed to deduct the bet amount via RCON. Is the player online? Check RCON settings.")
        return
        
    await ctx.send(f"💸 **{amount} points deducted.** Starting the slot machine...")

    # 2. لعبة الحظ (Slot Logic)
    emojis = ["🍒", "🍋", "🍇", "💎"]
    slot1, slot2, slot3 = random.choices(emojis, k=3)
    
    msg = await ctx.send(f"🎰 **Playing...**\n| ⬛ | ⬛ | ⬛ |")
    display_result = f"| {slot1} | {slot2} | {slot3} |"

    points_payout = 0 
    message = ""
    win = False
    
    if slot1 == slot2 == slot3:
        win_amount = amount * 3
        points_payout = win_amount 
        message = f"🎉 **JACKPOT! You won {win_amount} points!**"
        win = True
    else:
        message = f"😢 **You lost {amount} points. Better luck next time.**"

    # 3. 🔥🔥 الخطوة 2: التسوية عبر RCON (Payout Winnings Only) 🔥🔥
    if points_payout > 0:
        payout_command = f'zp_points "{player_name}" {points_payout}'
        send_rcon_command(payout_command) 

    final_points = current_points - amount + points_payout
    await msg.edit(content=f"🎰 **Result:**\n{display_result}\n{message}\n💰 Your estimated new balance is: **{final_points}**")
    
    if win:
         send_webhook_log(ctx.author.name, win_amount, final_points)


bot.run(TOKEN)