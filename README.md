# fifa-analysts — Football Analytics

真實足球分析網站：**勝率與對戰紀錄（H2H）、積分榜、Elo 排名、勝負預測**，同時涵蓋
**國際賽（1872 至今約 4.9 萬場）** 與 **五大聯賽（英超/西甲/德甲/義甲/法甲，2010-11 賽季至今）**。

- 後端：Python FastAPI + SQLite（`backend/`）
- 前端：React + Vite + TypeScript + Tailwind + Recharts（`frontend/`）

## 資料來源（免費、CC0、無需 API key）

| 來源 | 內容 |
|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | 國際賽逐場比分、賽事類型、是否中立場地；另含 4.8 萬筆進球者紀錄 |
| [openfootball/football.json](https://github.com/openfootball/football.json) | 五大聯賽逐場比分 |
| [statsbomb/open-data](https://github.com/statsbomb/open-data) | 射門事件含 xG（世界盃 2022、歐國盃 2024、美洲盃 2024）；`python -m app.etl.cli statsbomb` 抓取 |
| [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets)（CC0） | 球隊市值（**沙盒網路擋住**；部署後跑 `python -m app.etl.cli transfermarkt` 啟用，ML 市值特徵自動生效） |

資料源介面是可插拔的（`backend/app/etl/base.py`）：之後要接即時 API（如
football-data.org）只需新增一個 `fetch()` 實作並在 `cli.py` 註冊。

## 快速開始

```bash
# 1) 後端：安裝依賴、抓資料（含 Elo 重建與模型回測）、啟動 API
cd backend
pip install -r requirements.txt
python -m app.etl.cli refresh        # 下載約 7.5 萬場比賽，1 分鐘內完成
uvicorn app.main:app --port 8000     # API 文件在 http://localhost:8000/docs

# 2) 前端（另開終端機）
cd frontend
npm install
npm run dev                          # http://localhost:5173（/api 會 proxy 到 8000）
```

單機部署：`npm run build` 之後 FastAPI 會自動 serve `frontend/dist`，
只需要跑 uvicorn 一個服務。

資料更新：再跑一次 `python -m app.etl.cli refresh` 即可（國際賽資料源每次
國際比賽日後更新；聯賽資料源每輪後更新）。

## 功能與模型

- **勝率 / H2H**：總勝率、主客場拆分、近況 form、兩隊歷史交手。
- **積分榜**：由原始賽果計算（勝 3 和 1 負 0，淨球數、進球數為 tie-breaker）。
- **Elo 排名**：依 eloratings.net 慣例——K 值按賽事重要性加權（世界盃 60、
  洲際賽 50、資格賽/國家聯賽 40、友誼賽 20）、中立場地不計主場優勢、
  淨勝球加成；各聯賽獨立 Elo 池（K=20）。每場比賽後的 rating 快照都入庫，供走勢圖。
- **預測（三模型 ensemble）**：
  - *Dixon-Coles (1997)*：時間衰減加權 MLE 擬合每隊攻擊/防守強度
    （近期比賽權重高，聯賽半衰期約 8 個月、國際賽約 19 個月）、全域主場係數、
    低比分相關性修正 ρ，輸出比分機率矩陣與勝/和/負機率。
  - *梯度提升樹*（scikit-learn HistGradientBoosting）：特徵含雙方 Elo、
    近 5 場積分、近 10 場攻防均值、休息天數、中立場地、賽事重要性；
    特徵嚴格 walk-forward 生成（不洩漏未來）。
  - *Ensemble*：兩者機率平均，為網站預設輸出；隊伍資料不足時退回
    Elo+Poisson 簡單混合。
- **回測**：四個模型（Elo 基線 / Dixon-Coles / ML / Ensemble）在**同一批
  比賽**上 walk-forward 評測（最近兩年；DC 每 30 天用當時可得的資料重擬合）。
  參考結果：國際賽命中率約 60.5–60.8%、五大聯賽 52–56%，都明顯優於
  「永遠猜主隊」基準線；Dixon-Coles/Ensemble 的 Brier（機率校準）最佳
  （國際賽 0.496 vs Elo 基線 0.517）。結果顯示在預測頁的模型比較表。

## 球員與 xG 專區

- **Players 頁**：國際賽射手榜（可依國家/年代篩選）、球員檔案（進球分鐘分布、
  最愛對手、點球數）、球隊進球集中度（頭號射手佔比、HHI 指數、點球依賴度）。
- **xG Lab 頁**：三屆大賽的球隊 xG 攻防表與 finishing ±（進球減 xG，正值=把握力
  強或運氣好）、球員 goals vs xG 榜、單場射門地圖（點的大小=xG、實心=進球，
  PK 大戰已排除）。
- **市值特徵**：ML 模型內建 `mv_log_ratio` 特徵（雙方陣容市值對數比）。
  沙盒中該欄為缺值、模型自動忽略；部署後跑 transfermarkt 指令再 `refresh`
  重訓，特徵即生效。

## 測試

```bash
cd backend && python -m pytest tests
```

涵蓋 Elo（零和、爆冷加權、主場優勢、K 分類）、Poisson（機率總和、對稱性、
強弱隊 λ）、積分榜（積分與 tie-breaker）、ETL 解析（跳過未賽場次、隊名正規化）。

## API 一覽

| Endpoint | 說明 |
|---|---|
| `GET /api/meta` | 賽事清單、賽季、資料量 |
| `GET /api/teams?group=` | 球隊清單（含 Elo） |
| `GET /api/teams/{team}/stats?group=` | 勝率、主客拆分、form、進球分布 |
| `GET /api/teams/{team}/elo-history?group=` | Elo 走勢 |
| `GET /api/h2h?team1=&team2=&group=` | 對戰紀錄 |
| `GET /api/standings/{group}/{season}` | 積分榜 |
| `GET /api/rankings/elo?group=` | Elo 排名 |
| `GET /api/predict?home=&away=&group=&neutral=` | 勝/和/負機率 + 比分矩陣 |
| `GET /api/model/backtest` | 模型回測指標 |

`group` 為 `international`、`en.1`、`es.1`、`de.1`、`it.1`、`fr.1` 之一。
