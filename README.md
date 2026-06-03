# FinCouncil
### ระบบวิจัยหุ้น multi-agent หลายตลาด ที่ตัวเลข verify ได้
*(โค้ดเนมเปลี่ยนได้) · research-only · No live trading*

---

## คืออะไร
ป้อน ticker (US/ญี่ปุ่น/จีน/ฮ่องกง/ไทย/global) → ระบบดึงข้อมูล **verified หลายแหล่ง** → ทีม AI agents (analyst + persona นักลงทุน) วิเคราะห์ + debate → valuation + risk → ออกเป็น **บทวิเคราะห์/thesis ที่อ้างอิงแหล่งได้** → คน/Claude review ก่อนใช้

> **คูเมือง = ชั้นข้อมูลที่แม่นและ verify ได้** ไม่ใช่ตัว agent

## แนวทาง: FORK & EXTEND (ไม่สร้างใหม่จากศูนย์)
```
   TradingAgents (fork = ฐาน: council+debate+backtest+CLI, GLM native, multi-market)
              │
              ├── เปลี่ยน data layer ของมัน → DATA LAYER ของเรา (คูเมือง)
              │      OpenBB + AkShare + J-Quants + EDINET + Finnhub/AV + FRED + reconcile
              ├── PORT personas ←  ai-hedge-fund (Damodaran/Graham/Burry/Ackman...)
              ├── PORT valuation+report ←  FinRobot
              ├── เพิ่ม eval gates ของเรา (Nidec-test / asset-play)
              ├── เพิ่ม model routing (zai/Claude/Gemini)
              └── เพิ่ม MCP exposure + judgment gate
```

## โครงสร้าง repo (เป้าหมาย)
```
fincouncil/                     # fork ของ TradingAgents
├── tradingagents/ cli/ ...      # โครงเดิมของ fork (ต่อยอด ไม่ rewrite)
├── fincouncil/                  # ส่วนที่เราเพิ่ม
│   ├── data/  (adapters/ normalize/ store/ reconcile/)
│   ├── agents/personas/         # ported จาก ai-hedge-fund
│   ├── valuation/               # จาก FinRobot
│   ├── evalgates/               # Nidec-test, asset-play
│   ├── routing/                 # model routing
│   └── mcp/                     # MCP ของ data + council
├── docs/  (AGENTS.md, CLAUDE.md, PROJECT_SETUP.md, DATA_SOURCES.md,
│           ROADMAP_AND_CHECKPOINTS.md, asset-model-routing-strategy.md, cases/)
├── .env.example                 # ชื่อ key ที่ต้องใช้ (ไม่มี secret จริง)
└── README.md
```

## เริ่มยังไง
1. อ่าน `AGENTS.md` (กฎ + ขอบเขต) — ป้อนให้ Claude Code/Codex
2. ทำตาม `PROJECT_SETUP.md` (fork + ตั้งค่า + baseline)
3. build ตาม `ROADMAP_AND_CHECKPOINTS.md` ทีละ Phase ผ่าน checkpoint ก่อนไปต่อ

## Doc map
| ไฟล์ | หน้าที่ |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | spec หลัก + กฎ agents |
| `PROJECT_SETUP.md` | bootstrap: fork อะไร ตั้งค่าอะไร โครงไฟล์ env keys |
| `DATA_SOURCES.md` | แหล่งข้อมูลครบ (ตลาด×ประเภท) + ข้อจำกัด |
| `ROADMAP_AND_CHECKPOINTS.md` | เฟส P0–P8 + ด่านตรวจ + DoD + kill conditions |
| `asset-model-routing-strategy.md` | routing zai/Claude/Codex/Gemini |
| `cases/fuji`, `cases/nidec` | ตัวอย่างกรอบ → ป้อน eval gate |

## Disclaimer
research/การศึกษาเท่านั้น — ไม่ใช่คำแนะนำลงทุน ผลลัพธ์ = สมมติฐานที่ต้อง verify + คนตัดสินใจเสมอ ไม่มีการส่งคำสั่งซื้อขายอัตโนมัติ
