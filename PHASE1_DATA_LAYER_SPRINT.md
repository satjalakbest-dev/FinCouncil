# PHASE 1 — DATA LAYER · Sprint Backlog (ละเอียด)
*keystone phase · No code (เป็น backlog ให้ agent ลงมือ) · เป้าหมาย sprint = ผ่าน **CP1***

> **ทำไมเฟสนี้สำคัญสุด:** นี่คือ "คูเมือง" — ถ้า data ไม่แม่น/verify ไม่ได้ ทุกชั้นบน (council, valuation, eval gate) = garbage in. เฟสนี้คือสิ่งที่ทำให้ระบบเราต่างจากคนที่แค่ fork TradingAgents เปล่าๆ
> **Pre-req / Hard gate:** P0/CP0 ต้องผ่านและมีหลักฐานใน repo นี้ก่อนเริ่ม Phase 1 (fork รัน baseline ได้, env+secret, DuckDB init)
> **Sprint Goal:** council (fork) ดึงราคา/พื้นฐาน **US + global + ไทย-ราคา** จาก **data layer ของเรา** (ไม่ใช่ AV/Yahoo ของ fork) + `reconcile` ทำงาน + ทุก record มี source/currency

---

## รูปแบบ task (อ่านให้ครบก่อนทำ)
แต่ละ task: **Goal · Inputs · Outputs(สัญญา/interface เชิงแนวคิด) · Acceptance(eval-first) · Owner · Depends · 🔁Cross-check?**
- Owner: **CC**=Claude Code (architecture/correctness/integration) · **CX**=Codex (parallel build) · **CC+CX**=critical → เขียนอิสระ **ผลต้องตรง**

---

## Gate G0 — CP0 readiness before Phase 1 implementation

> **Hard gate:** ห้ามเริ่ม T1.1–T1.12 จนกว่า CP0 จะพิสูจน์ได้ใน repo นี้ เพราะตอนนี้ Phase 1 ต้องต่อยอดบน TradingAgents fork ที่รันได้จริง ไม่ใช่ docs-only scaffold

### G0.1 — Fork baseline present
- **Goal:** repo มีฐาน `TauricResearch/TradingAgents` แบบ fork/extend พร้อม attribution/license เดิม
- **Outputs:** source tree ของ TradingAgents อยู่ใน repo; `NOTICE`/license attribution ไม่หาย; โครง `fincouncil/` อยู่ข้าง fork ตาม `PROJECT_SETUP.md`
- **Acceptance:** พบ CLI/data-toolkit/persona/debate/backtest ของ fork ใน repo; ไม่ใช่การ rewrite ใหม่
- **Owner:** CC · **Depends:** — · 🔁 no

### G0.2 — Reproducible runtime + secret boundary
- **Goal:** env รัน baseline ได้โดยไม่ commit secrets
- **Outputs:** dependency install path; `.env.example` มีชื่อ key เปล่า; `.gitignore` กัน `.env`, DuckDB local files, parquet warehouse/cache
- **Acceptance:** fresh install ทำตามเอกสารได้; secret scan เบื้องต้นไม่พบ key จริงใน repo
- **Owner:** CC+CX · **Depends:** G0.1 · 🔁 no

### G0.3 — Baseline council smoke (CP0)
- **Goal:** รัน TradingAgents เดิมก่อนแก้ data layer
- **Outputs:** smoke log/artifact ของ CLI บน US ticker 1 ตัว ด้วย provider=GLM/zai หรือ mock-free documented fallback ถ้าไม่มี keyในเครื่อง
- **Acceptance:** ได้ decision/thesis จาก baseline หรือบันทึกชัดเจนว่า blocker คือ missing credential เท่านั้น; ไม่มีการแตะ data layer ก่อนรู้ baseline state
- **Owner:** CC · **Depends:** G0.2 · 🔁 no

**CP0 pass condition:** G0.1–G0.3 ผ่านครบก่อนเริ่ม Workstream A. ถ้าไม่ผ่าน ให้หยุดที่ P0 remediation ไม่ข้ามไปสร้าง data layer เพราะจะเสี่ยงกลายเป็น rebuild แทน fork-and-extend

---

## Workstream A — Schema + Storage (รากฐาน)

### T1.1 — Canonical schema design
- **Goal:** นิยาม schema กลางของ record ทุกชนิด: `price`, `fundamentals`, `symbol`, `reconcile_log`
- **Outputs:** เอกสาร schema — fields/types/units; **ทุก record มี `source` + `currency` + `as_of` เสมอ**; price: date/o/h/l/c/volume/adjusted_close; fundamentals: period(FY/Q)/fiscal_date/รายการงบหลัก+ratios
- **Acceptance:** schema ครอบทุก field ที่ CP1 ต้องใช้; ผ่าน review; เป็น contract ให้ task อื่นอ้าง
- **Owner:** CC · **Depends:** G0/CP0 · 🔁 no (แต่ CX review)

### T1.2 — Symbol convention + mapping 🔁
- **Goal:** map `{exchange}:{ticker}` กลาง ↔ suffix ของแต่ละ provider (US, `.T`, `.BK`, `.HK`, `.SS`, `.SZ`)
- **Outputs:** mapping module (สองทาง) + ตาราง fixture ตัวอย่างทุกตลาด
- **Acceptance:** round-trip map ถูกสำหรับ sample (AAPL, 7011→.T, PTT→.BK, 00700→.HK, 600519→.SS); **CC กับ CX เขียนอิสระ ผลตรงกันบน fixture ชุดเดียว** (ต่าง=สืบ)
- **Owner:** CC+CX · **Depends:** T1.1 · 🔁 **YES (critical)**

### T1.3 — DuckDB warehouse init
- **Goal:** ตาราง `prices/fundamentals/symbols/reconcile_log` + Parquet layout + read/write paths
- **Outputs:** warehouse module: upsert (idempotent), query by symbol/date-range, partition by symbol/date
- **Acceptance:** write→read round-trip ถูก; เขียนซ้ำไม่ duplicate (idempotent); อ่านช่วงวันที่ได้
- **Owner:** CX (CC review) · **Depends:** T1.1 · 🔁 no

---

## Workstream B — Source Adapter (OpenBB) + Normalize

### T1.4 — OpenBB adapter: EOD prices
- **Goal:** ดึงราคา EOD US/global/ไทย (`.BK`) ผ่าน OpenBB (provider ฟรี)
- **Outputs:** adapter คืน raw OHLCV + เก็บ raw provider response (เพื่อ debug/audit)
- **Acceptance:** คืน EOD ของ AAPL + 1 `.BK` + 1 global ticker ไม่ว่าง; ตรงกับที่เห็นบน OpenBB
- **Owner:** CX · **Depends:** T1.1 · 🔁 no

### T1.5 — OpenBB adapter: fundamentals (US)
- **Goal:** ดึงงบ/ratios US ผ่าน OpenBB
- **Outputs:** adapter คืน fundamentals มาตรฐาน (income/balance/cashflow + ratios หลัก)
- **Acceptance:** คืนงบ AAPL ครบรายการหลัก + period ถูก
- **Owner:** CX · **Depends:** T1.1 · 🔁 no

### T1.6 — Normalization layer
- **Goal:** แปลง raw provider → canonical schema; ติด `source`+`currency`; normalize วันที่; จัดการ adjusted vs unadjusted close อย่างสม่ำเสมอ
- **Outputs:** normalizer (raw → validated canonical record)
- **Acceptance:** record ที่ออกมา validate ผ่าน schema (T1.1); **มี source+currency ครบ**; adjusted_close นิยามชัดและสม่ำเสมอข้าม provider
- **Owner:** CC (แตะ correctness) · **Depends:** T1.1, T1.4, T1.5 · 🔁 no

### T1.7 — Caching policy
- **Goal:** เขียน normalized ลง DuckDB; อ่าน local ก่อน; กฎ freshness/TTL; throttle กัน rate-limit
- **Outputs:** cache layer (read-local-first; cache key = symbol+field+date-range)
- **Acceptance:** request ซ้ำ **อ่าน local ไม่ยิง provider ใหม่**; TTL ทำงาน; ไม่โดน 429 เมื่อดึงชุดเล็ก
- **Owner:** CX · **Depends:** T1.3, T1.6 · 🔁 no

---

## Workstream C — Reconcile / Verify (moat-critical) 🔁

### T1.8 — Reconcile tool 🔁
- **Goal:** ดึงค่าเดียวกันจาก ≥2 แหล่ง เทียบ flag เกิน threshold log ลง `reconcile_log`
- **Outputs:** `reconcile` — input(symbol, field, date) → output(values per source, diff, FLAG?, อธิบาย)
- **Acceptance:** threshold ราคา **0.5%** / fundamentals **1%**; **ฉีด discrepancy ปลอม → ต้อง FLAG ไม่กลืน**; เขียน `reconcile_log`; output อธิบายได้ → **ส่วนนี้คือแกน CP1** · **CC+CX เขียนอิสระ ผลตรงกัน**
- **Owner:** CC+CX · **Depends:** T1.6 · 🔁 **YES (critical)**

### T1.9 — Second source wiring
- **Goal:** ต่อแหล่งที่สองสำหรับ reconcile (yfinance / Stooq / Alpha Vantage) เทียบกับ OpenBB (primary)
- **Outputs:** adapter แหล่งที่สอง (อย่างน้อยราคา EOD)
- **Acceptance:** reconcile เทียบ OpenBB vs แหล่งสอง ได้สำหรับ sample tickers
- **Owner:** CX · **Depends:** T1.4 · 🔁 no

---

## Workstream D — MCP Surface + Swap-in เข้า fork

### T1.10 — MCP tools (data layer)
- **Goal:** เปิด `get_price` · `get_fundamentals` · `list_symbols` · `reconcile` (adopt `openbb-mcp-server` ที่ทำได้ + thin wrapper สำหรับชั้น normalized/reconciled ของเรา)
- **Outputs:** MCP surface ที่ Claude เรียกได้ คืน canonical records
- **Acceptance:** Claude เรียก get_price/get_fundamentals/reconcile ผ่าน MCP แล้วได้ normalized record (มี source/currency)
- **Owner:** CC (integration) · **Depends:** T1.6, T1.8 · 🔁 no

### T1.11 — Swap-in: ชี้ council (fork) มาที่ data layer เรา
- **Goal:** เปลี่ยนจุดดึงข้อมูลของ TradingAgents (AV+Yahoo) → data layer เรา สำหรับ ราคา/พื้นฐาน (US/global/ไทย-ราคา)
- **Outputs:** adapter/shim ที่ทำให้ data-toolkit ของ fork อ่านจาก layer เรา (ไม่ rewrite fork — แค่ชี้ทาง)
- **Acceptance:** council run ของ ticker US **ดึงราคา/พื้นฐานจาก layer เรา** (ไม่ใช่ default path ของ fork); council ยังทำงานปกติ
- **Owner:** CC (แตะ fork integration) · **Depends:** T1.6, T1.10 · 🔁 no

---

## Workstream E — Sprint Acceptance (CP1 gate)

### T1.12 — CP1 verification suite (eval-first)
- **Goal:** ชุดตรวจที่พิสูจน์ CP1 ครบ
- **Acceptance (= Sprint DoD):**
  1. `get_price` AAPL + `.BK` + `.HK` ตรง reference **ระดับปัด**
  2. **ทุก record มี `source` + `currency`**
  3. `reconcile` **flag discrepancy ที่ฉีดเข้าไป** (ไม่กลืน) + เขียน log
  4. council run (US ticker) **ใช้ข้อมูลจาก layer เรา** จริง
- **Owner:** CC+CX (CC นิยาม acceptance, CX สร้าง harness, cross-check) · **Depends:** T1.7, T1.9, T1.11

---

## ลำดับ/critical path (สั่งงาน 2 agent ยังไง)
```
G0/CP0 ─► T1.1 (CC) ─┬─► T1.2 (CC+CX 🔁) ─────────────┐
           ├─► T1.3 (CX) ──────────┐         │
           ├─► T1.4 (CX) ─► T1.6(CC)┼─►T1.7(CX)┤
           └─► T1.5 (CX) ──────────┘         │
                         T1.9(CX)─► T1.8(CC+CX 🔁)─► T1.10(CC)─►T1.11(CC)─►T1.12(CC+CX)
```
- **Critical path:** G0/CP0 → T1.1 → T1.6 → T1.8 → T1.10 → T1.11 → T1.12
- **ขนานได้:** T1.2/T1.3/T1.4/T1.5 หลัง T1.1 · T1.9 คู่กับ B
- **CC โฟกัส:** T1.1, T1.6, T1.10, T1.11 + ครึ่ง critical (T1.2, T1.8, T1.12)
- **CX โฟกัส:** T1.3, T1.4, T1.5, T1.7, T1.9 + ครึ่ง critical
- **🔁 Cross-check (ห้ามข้าม):** T1.2 (symbol/FX), T1.8 (reconcile) — CC กับ CX เขียนอิสระ ผลต้องตรง ต่าง=สืบ ไม่กลบ

---

## Gotchas เฉพาะ P1 (เตือนล่วงหน้า)
- **adjusted vs raw close** — นิยามให้ชัดแต่แรก (T1.6) ไม่งั้น reconcile จะ flag มั่วเพราะ provider ปรับ split/div ต่างกัน
- **currency** — ติดทุก record (ญี่ปุ่น JPY, ไทย THB, HK HKD...) กัน valuation สับสนภายหลัง
- **rate limit** — cache (T1.7) ต้องมาก่อนดึงเยอะ
- **OpenBB provider config** — ตั้ง provider ฟรีให้ครบก่อน (yfinance/FMP/FRED)
- **swap-in อย่าพัง fork** — T1.11 = ชี้ทาง ไม่ rewrite; ถ้าเริ่มต้อง rewrite เยอะ = หยุด ทบทวน (อาจ wrap แทน)

## Working rules (ย้ำ)
ground ทุกตัวเลขใน layer · ห้ามฮาร์ดโค้ด/เดา · secrets ใน .env เท่านั้น · PR เล็ก single-responsibility · **diff อธิบายไม่ได้ = หยุดถามคน** · ไม่มี auto-trade
