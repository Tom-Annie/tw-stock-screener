# tw-stock-screener 專案補充資訊

## 外部排程器:Windows Task Scheduler「台股TG Bot」

- **頻率**:每 5 分鐘
- **執行指令**:
  ```
  conhost.exe --headless wsl.exe -e bash -c "python3 /mnt/c/Users/User/tw-stock-screener/scripts/tg_bot.py --once >> /tmp/tg_bot.log 2>&1"
  ```
- **模式**:`tg_bot.py --once`(執行一次就退出,非常駐)
- **Log 位置**:`/tmp/tg_bot.log`
- **執行路徑**:Windows Task Scheduler → `conhost --headless` → `wsl.exe` → WSL bash → python3

修改/測試 `scripts/tg_bot.py` 時務必注意:每 5 分鐘會有一次外部自動觸發,避免測試跑到一半被打斷或雙跑導致狀態衝突。

## 排程執行規則(強制)

**凡是新增 Windows 端排程呼叫 WSL/CMD/PowerShell,一律採用背景、無視窗模式,嚴禁彈出黑色命令列視窗干擾使用者。**

實作方式(擇一):
1. `conhost.exe --headless <原指令>`(目前採用,最簡單)
2. 工作排程器任務勾選「不論使用者登入與否均執行」
3. 改用 WSL 內部 cron / systemd timer(完全脫離 Windows 層)

新增或修改排程時請依此規則設定。
