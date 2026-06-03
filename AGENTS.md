# AGENTS.md

> **ไฟล์นี้คือ:** spec หลักสั่งงาน AI coding agents (**Claude Code + Codex**) — single source of truth
> **วิธีใช้:** วางที่ root ของ repo · ทำ alias/copy ให้มีทั้ง `CLAUDE.md` และ `AGENTS.md` · ทำทีละ Phase · ผ่าน Checkpoint ก่อนไปต่อ
> **โค้ดเนม:** FinCouncil (เปลี่ยนได้) · **spec v2.0 (FORK & EXTEND)** · **No code in this doc**
> **เอกสารคู่:** `PROJECT_SETUP.md` (bootstrap) · `DATA_SOURCES.md` (ข้อมูล) · `ROADMAP_AND_CHECKPOINTS.md` (เฟส+ด่าน) · `asset-model-routing-strategy.md` (routing) · `cases/` (Fuji/Nidec → ป้อน eval gate)

---

## 1. Mission / North Star
สร้างระบบวิจัยหุ้น multi-agent ที่ **ตัวเลขแม่น verify ได้** ครอบหลายตลาด (US/ญี่ปุ่น/จีน/ฮ่องกง/ไทย/global) โดย **fork TradingAgents มาเป็นฐาน แล้วต่อยอดด้วยจุดแข็งจาก ai-hedge-fund + FinRobot + ชั้นข้อมูลของเราเอง**

> **คูเมือง = "ข้อมูลแม่น + verify ได้ หลายตลาด" ไม่ใช่ตัว agent** — agent fork มาได้ แต่ data moat คือสิ่งที่เราต้องชนะ

**ผลลัพธ์:** ป้อน ticker (ตลาดใดก็ได้) → ข้อมูล verified → analyst/persona วิเคราะห์ → debate → valuation+risk → **thesis อ้างอิงแหล่งได้** (ไม่ใช่คำสั่งเทรด) → คน/Claude review

---

## 2. Core Principles (ห้ามละเมิด)
1. **Accuracy from source** — ตัวเลขการเงินมาจาก data layer เท่านั้น ห้าม LLM (รวม GLM) เดา/จำ/ฮาร์ดโค้ด
2. **Verify / Reconcile** — เทียบข้ามแหล่ง + flag เมื่อขัดกัน (ไม่มี "close enough" — ยืม `validator.md`)
3. **🔑 FORK & EXTEND, อย่า rebuild** — เริ่มจาก fork ที่ proven แล้วต่อยอด · reimplement เฉพาะที่จำเป็น · ห้ามเขียน debate/CLI/persona ใหม่ทั้งที่ของเดิมมีแล้ว
4. **Connect once, consume everywhere** — รวมข้อมูลที่ hub เดียว เปิด MCP
5. **Free-first** — ของฟรีก่อน เพิ่ม paid ต้อง flag
6. **Research-only, human-in-the-loop** — ให้บทวิเคราะห์ ไม่ใช่สัญญาณเทรด **ห้าม path auto-execute** ทุก decision ผ่าน judgment gate
7. **Eval-first** — ฟีเจอร์มากับวิธีตรวจรับเสมอ

---

## 3. 🔑 FORK / EXTEND / PORT / ADOPT (กฎสำคัญที่สุด)

| ประเภท | ทำอย่างไร | รายการ |
|---|---|---|
| 🍴 **FORK (ฐาน)** | fork มา แล้ว**ต่อยอดบนนั้น** ไม่เขียนใหม่ | **`TauricResearch/TradingAgents`** — โครง council (analyst→bull/bear→risk→PM) + reflection memory + backtest + CLI + multi-provider (GLM native) + multi-market (Yahoo suffix) |
| 🔧 **EXTEND/REPLACE (งานหลักเรา = คูเมือง)** | แก้/เพิ่มบน fork | **เปลี่ยน data layer** (จาก AV+Yahoo → data layer ของเรา) · **eval gates** (Nidec/asset-play) · **model routing** (zai/Claude/Gemini) · **MCP exposure** + judgment gate |
| 🧩 **PORT/CHERRY-PICK (คัดจากตัวอื่นมาใส่ fork)** | คัด pattern/prompt มา reimplement สั้นๆ คง attribution | personas (Damodaran/Graham/Burry/Ackman...) จาก **`virattt/ai-hedge-fund`** (MIT) · valuation(DCF/relative/SOTP)+report จาก **`AI4Finance-Foundation/FinRobot`** |
| 📦 **ADOPT (libraries — ห้าม rewrite)** | ใช้ตรงๆ | OpenBB(+openbb-mcp-server) · AkShare(+`openbb-akshare`) · J-Quants client · `edinet-tools` · SEC EDGAR client · Finnhub · Alpha Vantage · FRED · DuckDB |

> **license:** TradingAgents=Apache-2.0 (fork ได้สบาย) · ai-hedge-fund=MIT · FinRobot=เช็คเงื่อนไขเชิงพาณิชย์ · คง NOTICE/attribution เมื่อ fork/port

---

## 4. Architecture
```
JUDGMENT GATE — คน + Claude (review ก่อน decision ใช้ได้)         ← ห้าม auto-trade
        ▲
LAYER 2 — RESEARCH COUNCIL = TradingAgents (forked) + extended
  analyst+persona → bull/bear debate → risk → PM thesis
  + valuation/report (FinRobot)  + eval gates (Nidec/asset-play)
        ▲  เรียก data ผ่าน MCP เท่านั้น
LAYER 1 — DATA (เราเป็นเจ้าของ logic) = MCP → normalize → DuckDB → reconcile
        ▲
LAYER 0 — SOURCES (ดู DATA_SOURCES.md)
Cross-cutting: MODEL ROUTING (zai/GLM · Claude · Gemini · Ollama)
```
**สำคัญ:** Layer 2 ไม่ได้เขียนใหม่ — มันคือ TradingAgents ที่ fork มาแล้วเรา (ก) เสียบ data layer ของเราแทนของเดิม (ข) เพิ่ม personas/valuation/eval gates

---

## 5. Scope
**✅ In:** EOD รายวัน (ราคา+fundamentals+filings+news/sentiment+macro) · ตลาด US/ญี่ปุ่น(+filings)/จีน/HK/ไทย/global · multi-agent → thesis/valuation/report · MCP+routing+reconcile+eval gates · backtest เชิงวิเคราะห์
**❌ Out:** live trading/ส่งคำสั่งจริง/ต่อ MT5 อัตโนมัติ · tick/intraday · HFT · จัดการเงินจริงอัตโนมัติ · rewrite ของที่ ADOPT/FORK · เพิ่ม paid source โดยไม่ flag

---

## 6. Working Rules — Claude Code & Codex

**แบ่งงาน build-time:**
- **Claude Code = lead:** แกนที่ต้องแม่น (data layer, reconcile, symbol/FX mapping, eval gates, valuation) + การตัดสินสถาปัตยกรรม + การ integrate เข้า fork
- **Codex = engineer คู่ขนาน + cross-check:** module คู่ขนาน + **เขียน critical module อิสระเทียบกับ Claude**
- **Critical-code cross-check (ยืม `validator.md`):** reconcile, symbol/FX, valuation, eval gates → Claude+Codex เขียนอิสระ **ผลต้องตรง** ต่าง = สืบ ห้ามกลบ
- *(build-time = Claude Code+Codex · run-time models = GLM/Claude/Gemini ตาม routing)*

**กติกาเขียน:**
- **Ground ทุกตัวเลขใน data layer** — ห้ามฮาร์ดโค้ด/เดา/ให้ LLM กุตัวเลข
- **Eval-first** — เขียนวิธีตรวจรับ (CP) คู่กับฟีเจอร์
- **เคารพ FORK/EXTEND/PORT/ADOPT (ข้อ 3)** — ต่อยอด ไม่เขียนใหม่ · port = คัด pattern คง attribution · อย่า rewrite ของ ADOPT
- secrets ใน env/secret store เท่านั้น · **ห้าม auto-execute trade** (PM = ข้อเสนอ ต้อง sign-off)
- single-responsibility, PR เล็ก, จดเหตุผล

**หยุดถามคน เมื่อ:** scope เปลี่ยน · requirement กำกวม · source reconcile ไม่ผ่านอธิบาย diff ไม่ได้ · เรื่อง security/ความเสี่ยงการเงิน · checkpoint ผ่านไม่ได้ · ต้องเพิ่ม paid dependency

---

## 7. Anti-patterns (อย่าทำ)
❌ ฮาร์ดโค้ด/เดาตัวเลข หรือเชื่อ LLM เป็นแหล่งตัวเลข · ❌ เขียน orchestration/debate/persona ใหม่ทั้งที่ fork มีแล้ว · ❌ rewrite ของที่ ADOPT · ❌ "close enough" ตอน reconcile · ❌ auto-trade · ❌ secret ในโค้ด · ❌ over-engineer/เกิน scope ของ Phase · ❌ ข้าม checkpoint

---

## 8. References
**FORK:** `TauricResearch/TradingAgents` (Apache-2.0)
**PORT:** `virattt/ai-hedge-fund` (MIT, personas) · `AI4Finance-Foundation/FinRobot` (valuation/report)
**ADOPT:** OpenBB · AkShare/`openbb-akshare` · J-Quants · `edinet-tools` · SEC EDGAR · Finnhub · Alpha Vantage · FRED · DuckDB
**Concepts:** reconcile · eval gate (Nidec-test, asset-play) · persona agent · deep/quick routing → ดู `DATA_SOURCES.md`, `ROADMAP_AND_CHECKPOINTS.md`, `asset-model-routing-strategy.md`
