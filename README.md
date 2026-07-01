# PDF 解鎖工具

一個 Windows／macOS 桌面小工具，用來批次移除自己有權限 PDF 的開啟密碼或權限限制，並另存成不加密的新 PDF。

## 功能

- 拖拉單一 PDF、多個 PDF，或整個資料夾到視窗處理。
- 支援批次處理資料夾，包含子資料夾與中文檔名。
- 支援權限限制 PDF，開啟不需密碼但禁止列印、複製或編輯的檔案通常可直接處理。
- 支援需要開啟密碼的 PDF，但必須輸入正確密碼。
- 原始檔不會被修改，輸出預設放在 `unlocked` 資料夾。
- 內建桌面 GUI，Windows 可打包成 `.exe`，macOS 可打包成 `.app`。

## 重要界線

本工具只用於處理你有合法權限的 PDF。  
它不會破解未知密碼，也不提供暴力猜密碼功能。

## 安裝開發環境

```powershell
python -m pip install -r requirements.txt
```

## 執行

```powershell
python pdf_unlocker.py
```

也可以用命令列處理整個資料夾：

```powershell
python pdf_unlocker.py "D:\檔案"
```

## 建置 Windows exe

```powershell
.\scripts\build_windows.ps1
```

完成後會產生：

```text
dist\PDFUnlocker.exe
```

## 建置 macOS app

macOS 版本需要在 Mac 或 GitHub Actions 的 macOS runner 上建置。

```bash
bash scripts/build_macos.sh
```

完成後會產生：

```text
dist/PDFUnlocker.app
dist/PDFUnlocker-macOS.zip
```

## GitHub Actions

專案內建 `.github/workflows/build.yml`。推上 GitHub 後，Actions 會自動：

- 在 Windows runner 跑測試並建置 `PDFUnlocker.exe`。
- 在 macOS runner 跑測試並建置 `PDFUnlocker.app`，再壓成 `PDFUnlocker-macOS.zip`。

Artifacts 可直接下載，或放到 GitHub Releases。

## 測試

```powershell
python tests\test_pdf_unlocker.py
```

## 作者與相關連結

由 [Frank Chiu](https://frankchiu.io) 製作。

更多工具、文章與專案筆記可參考 [frankchiu.io](https://frankchiu.io)。

## 授權

本專案原始碼使用 MIT License。第三方套件授權請見 `THIRD_PARTY_NOTICES.md`。
