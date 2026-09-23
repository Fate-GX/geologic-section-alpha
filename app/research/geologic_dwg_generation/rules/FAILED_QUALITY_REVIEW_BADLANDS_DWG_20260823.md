# pyBadlands由来DWG 品質不合格レビュー

作成日: 2026-08-23  
対象: `dwg/badlands_basin_50000_synthetic_section.dwg`  
品質判定: **Rejected — 地質断面図として評価できる水準に未達**  
技術判定: native DWG persistence testのみPASS

## 1. 判断の訂正

前回の `Accepted as an automated pipeline test artifact` は、ファイル生成技術だけを対象とした限定評価だった。しかし、ユーザーが求める成果は本物に近い疑似岩相断面図である。この目的に照らすと、成果物は品質評価の入口にも達していない。技術的に開けるDWGであることと、地質学的・図面的に価値があることを混同した。

今後、この成果物は **Rejected** と扱う。

## 2. 本物の岩相断面図との主要差分

### 2.1 観測制約がない

公開された実務断面図は、通常、複数のボーリング、コア・カッティング記載、物理検層、地表地質境界、地形、地質構造などを統合する。USGSの断面例では、井戸・岩相柱、層準、対比線、基準面、鉛直誇張が明示される。国交省資料も、柱状図の土質区分だけでは正確な分類が難しいと注意している。

今回のDWGには、ボーリング、地表露頭、姿勢、形成頂面、年代、地質図上の接触、物理探査のいずれもない。従って「断面解釈」ではなく、数値モデルの薄い時間スライス表示にすぎない。

### 2.2 岩相ではなく、全層が同じ簡易proxy

4区間すべてが `OffshoreMud` である。色を4段階に変えても岩相の多様性にはならない。堆積相、粒度、組成、年代、続成、侵食面を分類していない。

簡易分類は堆積時標高と海水準だけで決めた。水深だけでは、泥・シルト・砂、デルタ前縁、河道、氾濫原、海進・海退、供給源変化などを区別できない。

### 2.3 `pyBadlands`の役割を過大評価した

Badlandsは地形発達、侵食、運搬、堆積、海水準などを計算するsource-to-sink／landscape evolutionモデルである。公式資料には水深で定義した堆積環境表示や層序断面抽出があるが、それだけで現場岩相名、formation、層序対比、構造解釈が自動的に得られるわけではない。

公式basinサンプルはソフト動作確認には適するが、「現実のある地域を代表する本格断面」の入力ではない。これをそのまま本番品質生成の地質母集団にしたことが誤り。

### 2.4 GemPyを変換器としてしか使っていない

GemPyは接触点と姿勢データ、層序関係などから暗黙モデルを構築する。本件ではpyBadlands境界をsurface pointsへ写しただけで、独立したorientation、露頭、ボーリング対比、fault/unconformity関係を与えていない。

つまりGemPyはリアリティを追加せず、既存線のデータ形式を変換しただけである。GemPy公式資料が示す「surface points」「orientations」「StructuralFrame」のうち、地質を拘束する情報量が不足していた。

### 2.5 LoopStructuralを品質判定に活用できていない

LoopStructuralは地質イベントの時間順、断層、褶曲、構造フレーム、複数の補間器を扱える。本件では同一接触データに近い単純制約を入れ、RMSEを比較しただけだった。独立モデルが不一致になった理由を、制約密度、正則化、補間器、構造イベントの観点で設計し直していない。

公式論文は、褶曲表現には軸面・褶曲軸・回転角などの追加解釈制約が必要であり、正則化重みと補間法を変えることを通常のワークフローにすべきと説明している。本件はその機能をほぼ使っていない。

### 2.6 表示変換が地質形状を損ねた

- 水平縮尺 `0.02`
- 鉛直誇張 `100x`

という大きな異方性変換を後段で適用した。注記はしたが、元々0～約1 m程度しかない薄層の小変動を100倍に拡大し、視覚的意味を過剰化した。地形線や基準面、距離目盛と一緒に設計していないため、形状を読むための尺度文脈もない。

### 2.7 断面図として必要な図面構成がない

不足しているもの:

- A–A′の方向・端点
- 断面位置図
- 地形面
- ボーリング位置と柱状図
- 水平・鉛直縮尺、datum、鉛直誇張
- 距離目盛・標高目盛
- 地質時代・formation/層序単元
- 地質境界の確実度表現
- 断層、不整合、侵食面、レンズ、尖滅などのイベント分類
- 岩相色・模様・記号の正式な凡例
- 解釈区間とデータ欠如区間の区別
- 日本語／英語のpaper-space layout
- synthetic / assumptions / source provenance

USGSの作図資料はdatumと鉛直誇張の位置を規定し、FGDC標準は接触・断層・確実度などの記号体系を提供する。本件はそれらを持たない。

### 2.8 「非交差・閉ポリゴン」を品質と誤認した

非交差、閉鎖、正面積、SOLID Hatchは必要条件だが十分条件ではない。位相的に正しくても、地質過程、観測証拠、岩相、構造、作図文脈がなければ本物らしい断面にはならない。

## 3. ソフトウェア活用前より悪く見えた理由

以前の手作り生成では、少なくとも地形のうねり、層厚変化、レンズ、河道状形態、色彩、凡例、目盛など「断面図らしい視覚文法」を意図的に入れていた。

今回は再現性とトポロジーだけを優先し、公式basinサンプルのごく薄い4区間へ情報を縮退させた。そのため:

1. 多様性を失った。
2. 地形・ボーリング・イベント履歴を失った。
3. 全層を同一相にした。
4. ソフト間変換を情報追加だと誤認した。
5. 技術検証図を完成図として出した。

つまり、ソフトウェア利用によって入力情報が増えたのではなく、以前あった設計情報を削って単純モデルに置換した。

## 4. 正しいソフトウェア分担

### pyBadlands

用途: 地形発達、侵食・堆積量、流域・河道、海水準変化、堆積時系列の生成。  
使わない用途: 水深だけから最終岩相名やformationを確定すること。

### 岩相・堆積相エンジン（新規に必要）

入力: 水深、流速／運搬能力、堆積速度、粒径供給、河道位置、海水準変化率、侵食・再堆積、空間近傍、前後時刻。  
出力: 確率付きfacies、粒度、形成環境、信頼度。  
役割: Badlands出力と現実の柱状図・地域層序の間を埋める。

### GemPy

用途: 接触点、orientation、層序関係、断層関係を統合した構造モデル。  
条件: 複数ボーリング、地表境界、姿勢または明示的なsynthetic constraintsが必要。

### LoopStructural

用途: fault/fold/unconformityを含む時間順イベントモデル、補間感度比較。  
条件: geological featureごとの制約、補間器、正則化、イベント順を設計する。RMSEだけで採否を決めない。

### QGIS / GemGIS / 公的GIS

用途: 地形、地質図、断面線、ボーリング位置、座標系、地域区分の準備。  
疑似データでも実在地域を模倣する場合の空間文脈を与える。

### AutoCAD

用途: 合格済み幾何を正確なnative entityとして作図・レイアウト・注記・検証する。  
使わない用途: 不足した地質解釈をハッチや曲線の見た目で補うこと。

## 5. 再生成前の新しい必須ゲート

### Gate 0: 生成シナリオ

- 国・地域・地質区
- 地質年代
- 堆積環境
- イベント履歴
- 断面方向
- 観測点／疑似ボーリング配置
- 根拠ソース

### Gate 1: 疑似観測データ

最低3本以上のボーリング柱状図を生成し、各区間に岩相、粒度、色、厚さ、形成環境、標高、信頼度を持たせる。柱状図同士は同じ形成史から生成し、独立乱数で作らない。

### Gate 2: 地質イベントモデル

堆積、侵食、不整合、河道移動、レンズ形成、断層、褶曲などを明示的な順序で定義する。通常堆積境界は共有構造モデルと正厚場から作る。

### Gate 3: 相モデル

単一の水深閾値ではなく、複数変数と時空間連続性でfaciesを決める。地域の実例から事前分布と遷移関係を作る。

### Gate 4: 複数断面比較

少なくとも3つの実在公開断面と、単元数、厚さ変動、横方向連続長、尖滅数、侵食面数、断層数、ボーリング密度、注記構成を比較する。

### Gate 5: 地質・位相・作図の三重検証

1. 地質: 層序・イベント・facies遷移・証拠整合
2. 位相: 非意図交差・閉鎖・重複・尖滅
3. 作図: scale、datum、A–A′、目盛、凡例、layout、文字、表示順

三つ全部が合格するまでDWGを成果物として提示しない。

## 6. 次回実装順

1. 地域シナリオを一つ選定する。
2. GSJ/国交省/USGSの実在資料から、断面と柱状図を対応づけたreference setを作る。
3. reference setから統計量とイベント規則を抽出する。
4. 同じ形成史から疑似ボーリング群を生成する。
5. Badlandsは地形・侵食・堆積の補助場として使う。
6. 新しいfacies engineで岩相確率を求める。
7. GemPy/LoopStructuralへ観測相当制約とイベント順を入力する。
8. 断面線で切り、柱状図との再現誤差とhold-outを評価する。
9. 地質・位相・作図の三重検証を3回通す。
10. AutoCAD .NET APIでnative DWGとpaper-space layoutsを作る。

## 7. 再学習ソース

1. GSJ, 東京低地北部～中川低地南部の模式柱状図モデル: https://www.gsj.jp/publications/pub/openfile/openfile0528.html
2. 国土交通省, ボーリングモデル／地質情報ガイド: https://www.mlit.go.jp/tec/it/pdf/guide01.pdf
3. 国土交通省 中部地方整備局, 地盤調査・地質断面図作成上の注意: https://www.cbr.mlit.go.jp/road/sekkeiyouryou/pdf/cb002_jiban_v201403.pdf
4. USGS, Anadarko Basin lithology cross section G–G′: https://pubs.usgs.gov/dds/dds-069/dds-069-ee/pdf/ch10_plate_07.pdf
5. USGS, Coastal Plain borehole/log controlled section: https://pubs.usgs.gov/of/1982/0156/report.pdf
6. USGS, Borehole lithology characterization: https://pubs.usgs.gov/wri/1998/4183/report.pdf
7. FGDC/USGS, Digital Cartographic Standard for Geologic Map Symbolization: https://pubs.usgs.gov/tm/2006/11A02/
8. USGS draft cartographic/digital standard, datum and vertical exaggeration: https://pubs.usgs.gov/of/1995/ofr95415/pdf/ofr_95-415_c.pdf
9. Badlands official examples, stratigraphic sections and depositional environments: https://badlands.readthedocs.io/en/latest/examples.html
10. Badlands official XML/process parameters: https://badlands.readthedocs.io/en/latest/xml.html
11. GemPy topology and structural uncertainty paper: https://gmd.copernicus.org/articles/14/3899/2021/
12. LoopStructural time-aware geological modelling paper: https://gmd.copernicus.org/articles/14/3915/2021/
13. map2loop automated model construction limitations: https://gmd.copernicus.org/articles/14/5063/2021/index.html

## 8. 結論

今回の問題は曲線の滑らかさやハッチ色ではない。入力地質情報と形成史がほぼ空のまま、複数ソフトを直列に通したことが根本原因である。次回は、先に実在資料から地域シナリオ・疑似ボーリング・イベント履歴・facies遷移を構築し、各ソフトをその固有機能に限定して使用する。
