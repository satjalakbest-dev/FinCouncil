# DATA_SOURCES.md — แหล่งข้อมูล (ครบ)
*Layer 0 ของระบบ · free-first · ทุก record ต้องติด `source` + temporal provenance; monetary records ต้องติด `currency`; macro records ต้องติด `unit`*

---

## เมทริกซ์หลัก (ตลาด × ประเภท)

| ตลาด | ราคา EOD | Fundamentals | Filings | News/Sentiment | แหล่ง (primary → fallback) |
|---|:--:|:--:|:--:|:--:|---|
| **US** | ✅ | ✅ | ✅ | ✅ | OpenBB(yfinance/FMP) → Alpha Vantage; filings = **SEC EDGAR**; news = **Finnhub/AV** |
| **Global** | ✅ | ◐ | — | ◐ | yfinance ผ่าน OpenBB → Stooq |
| **จีน A-share** | ✅ | ✅ | ◐ | ◐ | **AkShare** (`openbb-akshare`) → Tushare(points); announcements รวม cninfo ใน AkShare |
| **ฮ่องกง** | ✅ | ✅ | ◐ | ◐ | AkShare / yfinance `.HK`; filings = **HKEXnews** (public search) |
| **ญี่ปุ่น** | ✅ | ✅ | ✅ | ◐ | **J-Quants**(ทางการ) ; filings = **EDINET** (`edinet-tools`, 大量保有報告書/5%); news = Finnhub/AV |
| **ไทย SET** | ✅ | ⚠️ | ⚠️ | ◐ | yfinance `.BK`(ราคา); **fundamentals/filings ฟรีอ่อน = gap** (settrade ต้องบัญชีโบรก) |
| **Macro (รวม)** | — | — | — | — | **FRED**(ผ่าน OpenBB) · World Bank/IMF/OECD |

`✅ ดี · ◐ ได้บางส่วน · ⚠️ อ่อน/gap`

---

## รายแหล่ง (free tier + ข้อจำกัด + บทบาท)

**OpenBB** (`OpenBB-finance/OpenBB`, AGPL) — hub รวมหลาย provider + `openbb-mcp-server` + เน้น traceability · ฟรีสำหรับใช้ส่วนตัว · *บทบาท: backbone US/global/FX/macro + Thai-ราคา*

**openbb-akshare / AkShare** (`akfamily/akshare`) — จีน A-share/HK ลึก รวม Eastmoney/cninfo/同花顺 · ⚠️ **scraping → พังได้เมื่อเว็บเปลี่ยน → ต้องมี fallback (yfinance)** · *บทบาท: จีน/HK*

**J-Quants** (`J-Quants/jquants-api-client-python`) — ราคา/งบญี่ปุ่น ทางการ JPX · มี free plan + MCP · ⚠️ **free tier มี delay + history สั้น (verify limit จริง)** · *บทบาท: ญี่ปุ่น ตัวเลข*

**EDINET** (`edinet-tools`) — filings ญี่ปุ่น (annual/quarterly + **5% reports**) XBRL/CSV · API key ฟรี · *บทบาท: filings ญี่ปุ่น = data activist-screening หัวใจ*

**SEC EDGAR** — filings US ทางการ ฟรี (10-K/13F/Form 4) · ใช้ free client (เช่น edgartools — verify ตัว maintain ดี) · *บทบาท: filings US*

**Finnhub** (finnhub.io) — free tier: news + **Reddit/Twitter sentiment** + global fundamentals + alternative data · *บทบาท: news/sentiment หลัก*

**Alpha Vantage** — free tier: ราคา/news + **sentiment score** + 50+ indicators + **MCP support** · NASDAQ-licensed · *บทบาท: news/sentiment + indicator + สำรองราคา*

**FRED** — macro US/global ฟรี (ผ่าน OpenBB) · *บทบาท: macro context*

**สำรอง/optional:** FMP(free plan) · Stooq(EOD ฟรี) · EODHD/Tiingo(freemium) · NewsData/StockNewsAPI · GDELT(macro news ฟรี) · Tushare(จีน, points)

---

## Reconcile / Verify Policy
- ตัวเลขสำคัญ (ราคา, ตัวเลขงบที่ใช้ valuation) → ดึง ≥2 แหล่ง เทียบ
- threshold เริ่มต้น: ราคา EOD ต่างเกิน **0.5%** = FLAG · fundamentals ต่างเกิน **1%** = FLAG
- diff ที่อธิบายไม่ได้ → **โผล่ขึ้น ไม่กลืน** · เก็บ `reconcile_log`
- ✅ diff ที่ยืนยันได้ว่าเป็น rounding/timezone ของแหล่ง = ผ่าน (อธิบายได้)

## Gaps ที่ยอมรับ (ตอนนี้)
- **ไทย fundamentals/filings ฟรี** — อ่อนจริง → เฟสแรก = ราคาอย่างเดียว, หาทางภายหลัง (settrade/manual/จ่าย)
- **HK/จีน filings เชิงลึก** — ได้ announcements ผ่าน AkShare/HKEXnews แต่ไม่ครบเท่า EDINET/EDGAR
- ทุกข้อ → บันทึกใน decision/log ว่า "ข้อมูลส่วนนี้จำกัด" เพื่อให้ agent + คนรู้ตอนตัดสิน
