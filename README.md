# ⚡ ApexTrade — 100 kr Mikrohandelsmaskin

ApexTrade är nu konfigurerad specifikt för **riktig mikrohandel med startkapital på 100,00 kr**. Inga gigantiska monopolbelopp, utan exakta kronor och ören med automatisk valutahantering (SEK/USD) och fraktionsaktier.

---

## 🌐 Kontrollpanel

Öppna dashboarden i webbläsaren:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 💰 Hur 100 kr profilen fungerar

1. **Startsaldo:** Exakt **100,00 kr**.
2. **Allokering per affär:** **25% (ca 25,00 kr)** per köp.
3. **Fraktionshandel:** Eftersom amerikanska aktier (som Nvidia eller Microsoft) kostar flera tusen kronor styck, köper boten **fraktioner** (t.ex. 0,0044 aktier för 24,94 kr).
4. **Max 3 samtidiga innehav:** 3x ~25 kr = ca 75 kr investerat. Resterande 25 kr hålls alltid som kontant buffert.
5. **Stop-Loss (-2,5%):** Säljer automatiskt om en post tappar ca 0,62 kr.
6. **Take-Profit (+5,0%):** Tar hem vinst automatiskt om en post ökar med ca 1,25 kr.

---

## 🚀 Vägen till Skarp Live-Handel

1. Skapa ett gratis konto på [Alpaca Markets](https://alpaca.markets).
2. Sätt in 100–200 kr via din bank / Wise.
3. Skapa dina två API-nycklar (`API Key ID` och `Secret Key`).
4. Klicka på kugghjulet (⚙️) i ApexTrade på `http://localhost:8000`.
5. Klistra in nycklarna och välj **Alpaca Live Trading**.
6. Klicka **Spara & Tillämpa**.

Därefter sköter ApexTrade alla köp, sälj och riskkontroller helt självständigt med dina 100 kr.
