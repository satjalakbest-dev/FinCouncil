# PROJECT_SETUP.md — Bootstrap
*ขั้นตอนตั้งโปรเจค (ระดับคำสั่ง/สเปก ไม่มีโค้ดแอป — โค้ดให้ agent เขียนตาม spec)*

---

## ลำดับ bootstrap

### Step 1 — Fork & clone ฐาน
- Fork **`TauricResearch/TradingAgents`** ไปที่บัญชีคุณ → clone มาเป็น repo `fincouncil`
- ยืนยัน license ฐาน = Apache-2.0 (fork/แก้ได้) · เก็บ NOTICE/attribution ไว้
- *(ฐานนี้ให้ council+debate+backtest+CLI+multi-provider มาแล้ว — เราต่อยอด ไม่เขียนใหม่)*

### Step 2 — Environment
- Python ตามที่ฐานกำหนด (TradingAgents ใช้ ~3.13) ใน env manager ที่ถนัด
- เตรียม **secret store** (`.env`) — ห้าม commit · ทำ `.env.example` ที่มี**ชื่อ key เปล่าๆ** (ดู Step 5)
- เตรียม **DuckDB** + โฟลเดอร์ Parquet warehouse (`fincouncil/data/store/`)

### Step 3 — Baseline run (ก่อนแตะอะไร)
- รัน TradingAgents เดิมตามคู่มือของมัน (CLI) บน ticker US 1 ตัว โดยตั้ง provider = **GLM (zai)**
- ✅ ต้องได้ decision ออกมา = ยืนยันฐานทำงาน + key LLM ใช้ได้ ก่อนเริ่มแก้ (= CP0 ใน roadmap)

### Step 4 — วางโครงส่วนของเรา
สร้าง namespace `fincouncil/` ข้างโครงเดิม (ไม่ยุ่งโครงเดิมเกินจำเป็น):
```
fincouncil/
├── data/ (adapters/ normalize/ store/ reconcile/)
├── agents/personas/
├── valuation/
├── evalgates/
├── routing/
└── mcp/
docs/  (ย้ายเอกสารชุดนี้มาไว้)
```

### Step 5 — สมัคร free API keys (ใส่ชื่อใน .env.example)
**LLM (เลือกที่ใช้):**
- `ZHIPU_API_KEY` — GLM (zai) — **ตัวหลัก runtime**
- `ANTHROPIC_API_KEY` — Claude (deep nodes/review)
- `GOOGLE_API_KEY` — Gemini (long-context)
- `OPENAI_API_KEY` — optional

**Data (ฟรี/มี free tier):**
- `ALPHA_VANTAGE_API_KEY` — ราคา/news/sentiment (มี MCP)
- `FINNHUB_API_KEY` — news + Reddit/Twitter sentiment + fundamentals
- `FMP_API_KEY` — optional (fundamentals/news, free plan)
- J-Quants — `JQUANTS_MAILADDRESS`/`JQUANTS_PASSWORD` หรือ refresh token (Japan, free plan)
- `EDINET_API_KEY` — filings ญี่ปุ่น (free)
- `FRED_API_KEY` — macro (free)
- `TAVILY_API_KEY` — web search (optional)
- *(OpenBB providers ตั้งค่าผ่านระบบของ OpenBB เอง · AkShare ไม่ต้อง key)*

### Step 6 — เริ่ม build
ทำตาม `ROADMAP_AND_CHECKPOINTS.md` ทีละ Phase (P0→P8) ผ่าน checkpoint ก่อนไปต่อ
ป้อน `AGENTS.md` ให้ Claude Code/Codex เป็นกฎกำกับทุกครั้ง

---

## หมายเหตุ
- **alias เอกสาร:** ทำ `CLAUDE.md` = `AGENTS.md` (copy/symlink) เพื่อให้ Claude Code อ่านด้วย
- **ห้าม secret ใน repo** — เช็คก่อน commit เสมอ
- **ไทย:** fundamentals/filings ฟรีจำกัด → เฟสแรกใช้ราคา (yfinance `.BK`) ก่อน บันทึก gap ไว้
- โค้ดแอปจริงทั้งหมด = ให้ Claude Code/Codex เขียนตาม spec นี้ (เอกสารชุดนี้ตั้งใจ no-code)
