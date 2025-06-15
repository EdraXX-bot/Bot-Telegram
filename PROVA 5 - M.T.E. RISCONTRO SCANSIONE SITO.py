import requests, time, json, os
from datetime import datetime, timezone

# == CONFIG ==
BITQUERY_KEY = ".91dD_Sc9_T_tv58_F38I5Du--"
TELEGRAM_TOKEN = '7719923915:AAGk_u1Q2kqpGcwxoSpOvhOabqp3UE0AV3s'
TELEGRAM_CHAT_ID = '745610482'
STATE_FILE = "seen_swaps.json"
STATUS_INTERVAL = 60 * 30  # ogni 30 minuti

# == FILTRI ==
MIN_SWAP_USD = 10_000
MIN_TOKEN_AGE_MIN = 60 * 24  # 24 ore

# == STATO ==
seen = set()
if os.path.exists(STATE_FILE):
    try:
        seen = set(json.load(open(STATE_FILE)))
    except:
        seen = set()

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        )
        print(f"[{datetime.now()}] ✅ Notifica inviata.")
    except Exception as e:
        print(f"[Telegram Error] {e}")

def fetch_swaps():
    url = "https://graphql.bitquery.io"
    headers = {"X-API-KEY": BITQUERY_KEY}
    query = """
    query ($limit: Int!) {
      solana {
        dexTrades(options: {limit: $limit, desc: "block.timestamp.time"}) {
          transaction {
            signature
          }
          tradeAmount(in: USD)
          baseCurrency {
            address
          }
        }
      }
    }
    """
    variables = {"limit": 25}
    try:
        response = requests.post(url, headers=headers, json={"query": query, "variables": variables}, timeout=10)
        if response.ok:
            data = response.json()["data"]["solana"]["dexTrades"]
            return data
    except Exception as e:
        print(f"[Errore API Bitquery] {e}")
    return []

def token_age_ok(mint_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={mint_address}"
        r = requests.get(url, timeout=10)
        if r.ok and r.json().get("pairs"):
            created_at = r.json()["pairs"][0].get("pairCreatedAt")
            if created_at:
                age_min = (datetime.now(timezone.utc) - datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)).total_seconds() / 60
                return age_min >= MIN_TOKEN_AGE_MIN
    except:
        pass
    return False

# === LOOP PRINCIPALE ===
print("🔄 Monitoraggio swap avviato (Bitquery)...")
send_telegram("🟢 Bot avviato correttamente con Bitquery. In ascolto swap > $10k su token 24h+")

last_status_time = time.time()

while True:
    swaps = fetch_swaps()
    for tx in swaps:
        sig = tx["transaction"]["signature"]
        usd_value = tx["tradeAmount"]
        mint = tx["baseCurrency"]["address"]

        if sig in seen or usd_value is None or mint is None:
            continue

        if usd_value >= MIN_SWAP_USD:
            if not token_age_ok(mint):
                continue

            msg = (
                f"💸 *Swap rilevato!*\n"
                f"🪙 Token: `{mint}`\n"
                f"💰 Valore: ${usd_value:,.2f}\n"
                f"🔗 [Solscan](https://solscan.io/tx/{sig})"
            )
            send_telegram(msg)
            seen.add(sig)

    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

    if time.time() - last_status_time >= STATUS_INTERVAL:
        now = datetime.now().strftime("%H:%M")
        send_telegram(f"🔄 Bot attivo - {now}")
        last_status_time = time.time()

    time.sleep(10)
