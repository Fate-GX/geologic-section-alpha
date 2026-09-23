# 地質モデル→DWGパイプライン 高速化・精度向上記録

作成日: 2026-08-23 (Asia/Tokyo)  
対象: pyBadlands → 2D断面 → 岩相推定 → GemPy/LoopStructural → トポロジー → AutoCAD DWG

## 1. 今回「遅く、途中で止まった」主因

### 1.1 実行環境の選択順が悪かった

pyBadlandsはC/C++/Fortran・HDF5を含むため、Windowsネイティブの試行は依存関係の組合せ探索を増やした。公式リポジトリ自身もDockerfileを依存関係の有力な資料として案内している。今回最終的に安定したのはWSL2上のLinux環境だった。

**次回規則**

1. 既に検証済みの専用WSL2環境を最初から使う（開発端末固有のパスは公開版では省略）。
2. Python、NumPy、h5py、HDF5、コンパイラ、pyBadlandsコミットをロックファイルへ記録する。
3. Windowsネイティブ再ビルドは、Linux基準系が通った後の移植試験としてのみ行う。
4. 最初に拡張モジュールimport、10ステップ程度のsmoke test、HDF5全ファイル再読込を行う。

根拠: pyBadlands公式リポジトリは公式コードのclone方法とDockerfileを依存関係資料として案内している。h5py公式資料は、HDF5とh5pyの世代不整合、特に新しすぎるHDF5や実験的な奇数minorを避けるよう注意している。

### 1.2 長時間計算を早すぎる段階で試した

20万年計算を、短い基準試験とチェックポイント解析を十分に分離する前に実行したため、15.5～16万年付近のabort調査に時間を使った。10万年計算は正常であり、パイプライン開発には十分だった。

**次回規則**

- Gate A: importテスト
- Gate B: 5,000年smoke test
- Gate C: 100,000年の代表試験
- Gate D: 断面・層序・トポロジー・DWGのend-to-end試験
- Gate E: 長時間・大規模stress test

Gate Dが完成するまでGate Eを実行しない。長時間計算は別の品質軸であり、DWGパイプライン成立条件と混同しない。

### 1.3 `layElev` と `layDepth` の意味確認が遅れた

最初の抽出は `layElev` を現在の境界形状と誤解した。ソース確認後、現在形状は上面から残存厚を累積した `layDepth`、`layElev` は堆積時標高の証拠として扱うよう修正した。この意味論確認を抽出コード作成前に行うべきだった。

**次回規則**

各外部データセットについて、コードを書く前に次を作る。

| 項目 | 必須確認 |
|---|---|
| dataset名 | producer側ソースの代入箇所 |
| 単位 | source/document/example |
| 時制 | 現在値・堆積時値・累積値 |
| 欠損表現 | NaN、0、sentinel、重複面 |
| 幾何学的意味 | 上面、下面、厚さ、標高、深度 |
| 不変条件 | 非負厚、Y/X順、面の非交差など |

抽出直後に、有限値、単調X、非負厚、境界順序、重複面を自動検査する。

### 1.4 GemPyとLoopStructuralの役割を混同しかけた

GemPyとLoopStructuralはいずれも暗黙的地質モデリングを扱うが、同じ入力から同じ数値解を返す保証はない。LoopStructural公式資料では、補間器、正則化、制約形式、解像度が結果に関与し、解くには複数の固有値制約またはnorm制約が必要とされる。今回のRMSE 0.512は「失敗」だけではなく、モデル仮定が一致していない証拠である。

**次回規則**

- authoritative geometry: pyBadlandsの保存済み現在境界
- structural representation check: GemPy
- independent sensitivity/comparison: LoopStructural
- DWGへの採用判定: トポロジー合格済みauthoritative geometry

LoopStructural一致を必須ゲートにしない。比較器には同値性ではなく、有限性、順序保存、交差、RMSE、最大偏差を記録させる。

GemPyでは、公式資料どおりsurface pointが層の下面を表すこと、StructuralFrame内のgroup/element順を入力CSV名だけでなく生成後オブジェクトから検査する。

### 1.5 AutoCAD工程を最後に残しすぎた

DWG化を全地質処理後に直列配置したため、第7段階まで成功しても成果物がDWGにならなかった。地質計算とDWGライタは、固定した小型ポリゴンfixtureを使って並行して検証できる。

**次回規則**

開始時に次の2系統を独立に成立させる。

1. geology lane: 入力 → 地層ポリゴンJSON
2. AutoCAD lane: 小型fixture JSON → native DWG → reopen validation

合流点のJSON schemaを最初に固定する。AutoCAD標準.NET APIを第一選択とし、閉じたPolylineをDBへ追加後、`Hatch.AppendLoop()`、`Hatch.EvaluateHatch()`を使う。保存後はCore Consoleで再度開き、Polyline/Hatch数、閉鎖状態、SOLID pattern、関連付け、レイヤ、TrueColor、DWG versionを検査する。

### 1.6 進捗報告の終端判定が不十分だった

ユーザーが「作業結果」を求めた時点で、WSLプロンプトの説明だけを返し、8段階全体の完了状態を先に提示しなかった。

**次回規則**

各返答の冒頭に必ず次を出す。

- 完了段階 / 全段階
- 現在の合否
- 未完了の成果物
- 次に実行する1工程

「コマンドが成功した」と「目的成果物が完成した」を分離する。DWGは再オープン検証まで完了扱いにしない。

## 2. 次回の高速実行順

1. `preflight`: WSL、env、package version、native extension import、AutoCAD/Core Console、.NET DLLを一括検査。
2. 既存の100,000年/50,000年HDF5を再利用。入力hashが同じなら再計算しない。
3. HDF5 schema inspectionを先に実行し、意味論manifestと一致しない場合は停止。
4. section抽出、岩相proxy、GemPy変換、topology検証を一つのdriverから実行。
5. 各工程をcontent hashでキャッシュし、入力・コード・設定が同じなら既存成果を採用。
6. LoopStructuralは独立比較として並行実行可能だが、DWG laneを止めない。
7. topology合格JSONをAutoCAD .NETライタへ渡す。
8. Core Consoleで作成、再オープン、native entity auditを自動実行。
9. 全レポートを一つのrun manifestへ集約し、`Accepted / Experimental / Rejected`を付ける。

## 3. 必須の早期停止条件

- HDF5ファイルが一つでも再読込不能
- datasetのshape/schemaがmanifestと不一致
- 非有限座標
- X順序不正
- 通常堆積層の負厚または境界交差
- ポリゴン未閉鎖、自己交差、面積0以下、意図しない重複
- GemPy生成後のsurface順不一致
- AutoCAD Hatchが非SOLID、未評価、境界未関連付け
- 保存DWGの再オープン失敗またはentity count不一致

## 4. 次回追加する自動化

- `pipeline_preflight.ps1`: Windows/WSL/AutoCAD/.NET/Pythonの一括診断
- `pipeline_manifest.json`: version、commit、hash、schema、座標系、単位、時制
- `run_pipeline.py`: Stage 2～7の一括実行とキャッシュ
- AutoCAD .NET native DWG writer + validator
- `final_run_report.md`: 各gateの合否と採用成果物へのリンク

## 5. 調査ソース

1. pyBadlands official repository, installation/getting started and Docker guidance: https://github.com/brmather/pyBadlands
2. h5py official installation guidance and HDF5 compatibility: https://docs.h5py.org/en/3.10.0/build.html
3. h5py official file-format version bounds: https://docs.h5py.org/en/3.15.0/high/file.html
4. GemPy official modeling API tutorial: https://docs.gempy.org/tutorials/b_fundamentals/a01_basics.html
5. GemPy official StructuralFrame reference: https://docs.gempy.org/Modeling%20Classes/gempy.core.data.StructuralFrame.html
6. LoopStructural official data preparation/interpolator constraints: https://loop3d.org/LoopStructural/_auto_examples/1_basic/plot_1_data_prepration.html
7. LoopStructural official design documentation: https://loop3d.org/LoopStructural/getting_started/loopstructural_design.html
8. Autodesk official .NET guide, hatch boundaries and EvaluateHatch: https://help.autodesk.com/cloudhelp/2027/ENU/OARX-DevGuide-Managed/files/GUID-01A47A4F-9FC5-4DB6-8C3E-B72D75688965.htm

## 6. 判定

今回の技術成果は第7段階まで有効だが、end-to-end成果物であるnative DWGが未生成なので、全体判定は **Experimental / Incomplete** とする。次回は地質laneとAutoCAD laneを最初から並行準備し、DWG再オープン検証を最終完了条件にする。
