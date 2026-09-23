# 初めて使う方へ

## 準備

Windows、Python 3.11以上（Tkinter、`pyw`ランチャー）、AutoCAD 2027を用意し、AutoCADを通常のユーザーで使える状態にしてください。本版は標準配置の `C:/Program Files/Autodesk/AutoCAD 2027` を前提とします。管理者実行は通常不要です。

フォルダを展開し `Geologic_Section.vbs` をダブルクリック。初回セットアップはボタン操作で `.venv/` に専用環境を作り、必要なライブラリを導入します。既存のPython環境へインストールしません。

## 二点を選び、生成する

1. 「地図で始点A・終点Bを指定」で陸地の二点を選択します。
2. 二点の距離10～500mと方位を確認します。左端がA、右端がBです。
3. 詳細設定は必要な場合だけ開きます。seedは合成生成の条件であり現実の正解を選ぶ番号ではありません。
4. 保存先を確認して生成ボタンを押します。
5. 成功時に「画像を開く」「DWGを開く」「検査結果を開く」で確認します。

表示した円は距離の条件であり、生成成功地域の地図ではありません。公共データ取得に失敗した場合はネットワークも確認してください。

## 拒否されたら

| 表示例 | 意味・確認事項 |
|---|---|
| UnsupportedOrAmbiguousGeologicalDomain | 対応外または混在・不明な地質区分。閾値変更で無理に通さないでください。 |
| AdvancedContactGeometryRejected | 接触形状等の検査に不合格。実行記録を確認してください。 |
| AdvancedDwgContractRejected | 面積・図面契約等に不合格。成功DWGではありません。 |
| native writer prerequisites are missing | AutoCADまたは同梱作図DLLの配置を確認してください。 |

別の場所が成功しても、拒否した地点を検証済みにはできません。Issueにはエラー名・環境・再現手順を添え、非公開の現場座標や図面は投稿しないでください。

## 結果の点検

二点の座標・方位、岩相名と推測注記、目盛、凡例、空白・交差・不要な線を確認します。人間の確認で問題があれば、自動試験の成功だけで採用しないでください。

## 開発者向け

`python tools/check_package.py`：パッケージ整合性。

`python -m pip install -r requirements-dev.txt` の後、`python tools/run_tests.py`：公開版の選択した回帰試験。GUIの実操作やAutoCAD実機検証の代わりではありません。

作図DLLのソースは `app/subprojects/geologic_3d_engine/advanced_v2/native/`。再ビルドには .NET 10 SDKとインストール済みAutoCAD 2027の参照DLLが必要です。AutodeskのDLL自体は同梱しません。
