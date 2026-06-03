# ROADMAP_AND_CHECKPOINTS.md
*แนวทาง FORK & EXTEND · ทำทีละ Phase · ผ่าน Checkpoint (CP) ก่อนไปต่อเสมอ · CP = เกณฑ์พิสูจน์ได้ ไม่ใช่โค้ด*

```
P0 Fork+Baseline → P1 Data core(swap) → P2 Data expand(multi-market+filings+news+macro)
→ P3 Personas(ai-hedge-fund) → P4 Valuation+Report(FinRobot) → P5 Eval gates(Nidec/asset)
→ P6 Routing → P7 MCP+Judgment+E2E → P8 Hardening
```
> ใช้งานขั้นต่ำได้ตั้งแต่จบ **P2** (council วิเคราะห์หลายตลาดบนข้อมูลเราได้) — ไม่ต้องรอครบ

---

## Phase 0 — Fork & Baseline
- **Objective:** มีฐานที่ทำงานได้ก่อนแตะ
- **Deliverable:** fork TradingAgents → repo เรา · env+secret store · DuckDB+โครง warehouse · เอกสาร symbol convention กลาง (`{exchange}:{ticker}` ↔ .T/.BK/.HK/.SS/.SZ)
- **✅ CP0:** รัน TradingAgents เดิม (CLI) บน ticker US 1 ตัว ด้วย provider=GLM **ได้ decision** · env reproducible · ไม่มี secret ในโค้ด
- **Depends:** —

## Phase 1 — Data Layer Core (swap-in) + reconcile  ← คูเมืองเริ่มที่นี่
- **Objective:** สร้าง data layer ของเรา (OpenBB hub) + reconcile แล้ว**เสียบแทน data ของ fork** สำหรับ US/global/ไทย-ราคา
- **Deliverable:** OpenBB adapter · normalize→schema กลาง · DuckDB warehouse · `reconcile` · ต่อให้ council ดึงจาก layer เรา
- **✅ CP1:** council run ดึงราคา/พื้นฐานจาก **layer เรา** (ตรง reference ระดับปัด) · `reconcile` **flag discrepancy ที่ฉีดเข้าไป** · ทุก record มี `source`+`currency`
- **Depends:** P0

## Phase 2 — Data Expansion (multi-market + filings + news + macro)
- **Objective:** เพิ่ม จีน/HK(AkShare) · ญี่ปุ่น(J-Quants+EDINET) · US filings(EDGAR) · news/sentiment(Finnhub+AV) · macro(FRED)
- **Deliverable:** adapters ครบ + ฟังก์ชัน get filings/news/sentiment/macro · normalize+reconcilable
- **✅ CP2:** council วิเคราะห์ **ญี่ปุ่น + จีน + HK** ticker ได้ grounded บนข้อมูลเรา · **EDINET คืน 5% report** ของ code ทดสอบ (filer+%) · news+sentiment คืนค่า · **AkShare พัง → fallback ทำงาน** · Thai gap บันทึก
- **Depends:** P1

## Phase 3 — Port Investor Personas (จาก ai-hedge-fund)
- **Objective:** เพิ่ม persona agents (Damodaran/Graham/Burry/Ackman/Munger...) เข้า researcher/analyst layer ของ fork · ground ด้วยข้อมูลเรา
- **Deliverable:** persona agents + prompt contract · แต่ละตัวอ้างอิงข้อมูลที่ใช้
- **✅ CP3:** persona ออกมุมต่างกันตามปรัชญาจริง สำหรับ ticker ทดสอบ · **อ้างเฉพาะข้อมูลใน layer เรา (ตรวจ citation = 0 ตัวเลขลอย)**
- **Depends:** P2 · *(คง attribution MIT)*

## Phase 4 — Valuation + Report Engine (จาก FinRobot)
- **Objective:** เพิ่ม valuation (DCF/relative/SOTP) + เขียน research report (+ option อ่าน chart/filing)
- **Deliverable:** valuation module (input จาก layer เรา) · report generator (มี source) · filing-reading
- **✅ CP4:** valuation บริษัททดสอบ ออก intrinsic value พร้อม **assumption โปร่งใส** · reconcile กับการคำนวณอิสระในเกณฑ์ · flag เมื่อ input ขาด · report อ้างแหล่ง
- **Depends:** P2 (data) · ขนานกับ P3 ได้

## Phase 5 — Eval Gates (Nidec-test / asset-play)
- **Objective:** ฝังกรอบเรา (asset-play screen · Nidec trap test · "what forces the unlock") เป็น gate ตรวจข้อสรุป council
- **Deliverable:** eval-gate module (score/flag) ต่อเข้า workflow
- **✅ CP5:** ป้อนเคสรู้ผล (**Fuji-type vs Nidec-type** จาก `cases/`) → gate **แยกโอกาส vs กับดักถูก** · อธิบายเหตุผลได้
- **Depends:** P3, P4

## Phase 6 — Model Routing (zai/Claude/Gemini)
- **Objective:** ตั้ง routing ตาม `asset-model-routing-strategy.md` — GLM ทำ volume, Claude/Gemini ทำ deep nodes — ต่อ agent/node + fallback
- **Deliverable:** routing config + fallback (Ollama optional) + default aware cost/limit
- **✅ CP6:** runtime ใช้ GLM กับ volume agents, Claude/Gemini กับ node คิดหนัก ตาม config · model ล่ม → fallback นุ่มนวล · เปลี่ยน routing ได้โดยไม่แก้โค้ด
- **Depends:** P0 (fork รองรับ multi-provider อยู่แล้ว) · มีผลจริงหลัง P3/P4

## Phase 7 — MCP Exposure + Judgment Gate + E2E
- **Objective:** เปิดระบบให้ Claude ขับ/review · บังคับ judgment gate (ไม่ auto-trade) · รัน E2E หลายตลาด
- **Deliverable:** system MCP/CLI · judgment-gate checkpoint (คน/Claude sign-off) · pipeline data→council→thesis→review
- **✅ CP7:** E2E บน basket **US+ญี่ปุ่น+ไทย** จบครบ · Claude เรียก+review ได้ · **ไม่มี path auto-execute trade** · reconcile + eval gate ผ่าน · decision log อัปเดต
- **Depends:** P1–P6

## Phase 8 — Hardening + Cadence + Monitoring
- **Objective:** schedule + caching + rate-limit + monitor source พัง + test + docs
- **Deliverable:** scheduled EOD refresh · monitoring/alert (โดยเฉพาะ AkShare) · test suite · runbook
- **✅ CP8:** batch refresh ตามรอบ · cache hit ตัด call ซ้ำ · AkShare พัง → alert+fallback · test เขียว · runbook ให้ session ใหม่เดินระบบได้
- **Depends:** P7

---

## Definition of Done (ทั้งโปรเจค)
- [ ] E2E หลายตลาด — data verified + reconciled + eval-gated
- [ ] ทุกตัวเลขในผลลัพธ์ **ตอบได้ว่ามาจากไหน** (citation → warehouse)
- [ ] Claude ขับ/review ผ่าน MCP ได้
- [ ] **ไม่มี path auto-trade** · ทุก decision ผ่าน judgment gate
- [ ] routing + fallback ใช้งานได้
- [ ] monitored + tested + มี runbook

## 🚦 Kill / Stop Conditions (หยุดทบทวน ไม่ฝืน)
- ❌ source หนึ่ง **reconcile ไม่ผ่านซ้ำๆ** อธิบายไม่ได้ → อย่าใช้ตัวเลขนั้นจนกว่าจะ resolve
- ❌ AkShare พังบ่อยจน fallback ไม่พอ → ตัดสิน: Tushare(จ่าย) หรือ ลดขอบเขตจีน
- ❌ free tier ให้ depth ไม่พอจริง → "จ่าย vs ลดขอบเขต" อย่างเปิดเผย (อย่าฝืนใช้ของไม่พอ)
- ❌ ไทย ไม่มีทางฟรีเชื่อถือได้ → ยอมรับ "ราคาอย่างเดียว (ชั่วคราว)" บันทึกไว้
- ❌ การ extend fork เริ่มกลายเป็น rewrite ทั้งก้อน → หยุด ทบทวนว่าควร port pattern แทน

## หลักวัดผล (ยืม validator.md)
ไม่มี "close enough" · "น่าจะ rounding" ต้อง verify ไม่ใช่เดา · เป้าสูงสุด: **ทุกตัวเลขที่ป้อนการตัดสินใจ ตอบได้ว่ามาจากไหน + เทียบกับอะไร**
