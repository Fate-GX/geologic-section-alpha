# 地質関連イベント・人物・公的データ調査

確認基準日: 2026-08-22（日本時間）

## 1. 時系列の扱い

- `Published`: 論文・要旨・データが公開済みで内容を確認できる。
- `Announced`: 開催・発表予定だけが公開され、成果本文は未確認。
- `Watch`: 本プロジェクトとの関連性が高く、公開後に追跡する。

予定発表の題名だけから生成規則を作らない。新しいことと、検証済みであることを区別する。

## 2. 2026年の主要イベント

### 日本応用地質学会 2026年度研究発表会

- 日程: 2026-11-10～13
- 会場: アオーレ長岡
- 状態: `Announced`
- 2026-07-24版プログラムを確認
- URL: https://www.jseg.or.jp/event/
- Program: https://www.jseg.or.jp/wp-content/uploads/2026/07/JSEG_2026%E7%A0%94%E7%A9%B6%E7%99%BA%E8%A1%A8%E4%BC%9A%EF%BC%88%E9%95%B7%E5%B2%A1%EF%BC%89%E3%83%97%E3%83%AD%E3%82%B0%E3%83%A9%E3%83%A00724.pdf

追跡対象:

| 発表 | 人物・所属 | 本プロジェクトとの接点 | 状態 |
|---|---|---|---|
| 3D地盤モデルを用いた地質構造の可視化 | 渡邊剛・目黒喜之・石山慧（国交省北陸地方整備局飯豊山系砂防事務所）、高澤忠司ほか（興和） | 国の事業における3D地盤モデルと表示・説明 | Watch |
| 山岳トンネルの事前地質調査と施工実績の乖離要因 | 吉良洋美・赤澤正彦・外山真（鉄道・運輸機構）、林宏一（京都大学）ほか | 事前断面と実績の差を教師データ化できる可能性 | Watch |
| 地質・地盤リスクマネジメント | 長谷海王・赤澤正彦・外山真（鉄道・運輸機構） | 不確実性とレビュー工程 | Watch |
| ボーリングコア破砕度の画像判定 | 古木宏和（日本工営） | コア画像特徴の構造化 | Watch |
| 岩盤ボーリングコアのハイパースペクトルAI解析 | 福岡航治ほか | 岩相・変質判定の補助特徴 | Watch |
| 都市域の地盤地質と災害リスク | 竹下徹（東北大学） | 都市柱状図からリスク説明への接続 | Watch |

講演前のため、現時点では題名・発表者・所属だけを研究探索に使い、方法や結論は採用しない。

### GEOINFORUM 2026

- 日程: 2026-06-18～19
- 会場: 北海道大学
- 状態: `PublishedProgram`
- URL: https://www.jsgi.org/pdf/GEOINFORUM2026.pdf

最重要追跡対象:

| 発表 | 人物・所属 | 反映候補 |
|---|---|---|
| 信頼性評価を活用した地層対比支援システムの開発 | 櫻井健一（大阪公立大学・産業技術短期大学）、米澤剛・根本達也（大阪公立大学） | 各対比の信頼度、候補提示、人による修正UI |
| 二次元地形図を三次元的に表現する際の留意点 | 中田文雄 | 2D/3D変換時の誤認防止 |
| 地形面変化に基づく斜面崩壊地形の数学表現 | 植田允教・根本達也ほか | 地形イベントの数理表現 |
| Tensor Votingとハフ変換によるリニアメント抽出 | 根本達也ほか | 構造線候補の抽出。地層境界とは分離 |

プログラムだけでは手法詳細を検証できない。講演要旨または後続論文を取得後、既存の順序保存相関と比較する。

### 日本応用地質学会 令和8年度シンポジウム

- 日程: 2026-06-19
- テーマ: 災害を知る・識る・備える
- 状態: `Held`; 予稿集はパスワード保護のため本文未確認
- 大学報告者: 山﨑新太郎（京都大学防災研究所）、菊地輝行（公立諏訪東京理科大学）、野々村敦子（香川大学）
- 反映範囲: 人物・研究室・公開論文を探す入口。非公開予稿の内容を推測しない。

### その他の追跡先

- 日本地質学会 2026金沢大会: https://geosociety.jp/academic/convention/
- JpGU-AGU 2026: https://www.jpgu.org/meeting_j2026/program.php
- GSJ地質調査研修: https://d36btl2l9lx9np.cloudfront.net/geoschool/geotraining/index.html
- 物理探査学会 令和8年度物理探査セミナー: https://segj.or.jp/event/geoseminar2026.html

## 3. 最新の公的データ

### GSJ「都市域の地質地盤図」2026-03-31更新

- 千葉県北部延長域・千葉県中央部について、基準ボーリング、平面図、境界面等高線、立体図を公開。
- 千葉県環境研究センターとの共同研究。
- 埼玉県南東部は埼玉県環境科学国際センター、東京都区部は東京都土木技術支援・人材育成センターとの共同研究。
- URL: https://gbank.gsj.jp/urbangeol/

採用優先度: `Highest`

用途:

1. 基準柱状図と解釈済み地層単元の教師ペア
2. 境界面等高線と任意断面の比較
3. 地域別岩相・N値・層序パターン
4. 完成モデルから柱状図位置を逆照合する検証

### 東京都「東京の地盤（GIS版）」

- 東京都建設局・東京都土木技術支援センター
- ボーリング柱状図を公開
- オープンデータカタログ上の最終更新: 2026-01-27 UTC
- ライセンス表示: CC BY
- URL: https://catalog.data.metro.tokyo.lg.jp/dataset/t000014d2000000032

用途: 東京都区部の一般工事柱状図。GSJの解釈済みモデルと組み合わせ、一般柱状図→地層単元の教師候補を作る。

### 千葉市

- 2026-04-01以降に千葉市が実施した公共事業の柱状図を国土地盤情報DBで公開する案内。
- URL: https://www.city.chiba.jp/kensetsu/doboku/gijutsukanri/jibanjoho.html

用途: 今後追加される地域柱状図の供給源。GSJ千葉モデルとの時系列差を確認する。

### 静岡県オープンデータ

- 県実施ボーリングのPDF・XML
- CC BY表示
- ページ更新: 2024-05-13
- URL: https://opendata.pref.shizuoka.jp/dataset/fuji-173.html

用途: BED XML読込試験、地域外検証。千葉で学習した分類器の外部検証に使い、再学習なしの性能を測る。

### 防災科研 Geo-Station

- ボーリング交換用XML、PDF、N値、孔内水位、各種検層、地質時代・地層岩体区分を検索可能。
- 125mメッシュの模式柱状図は統計モデルであり、実測孔と区別する。
- URL: https://www.geo-stn.bosai.go.jp/mapping_page.html
- 品質確認・表示ソフト: https://www.geo-stn.bosai.go.jp/software/boring/phtmls/download.php

用途:

- XMLパーサー互換性試験
- 欠測パターンと品質検査
- 実測柱状図と模式柱状図を混同しない分類

### 国土地盤情報データベース/KuniJiban

- 国土交通省等の道路・河川・港湾事業の柱状図・土質試験結果を集約。
- 概要: https://www.mlit.go.jp/page/content/05_200626_shiryou2.pdf

用途: 全国規模の原柱状図候補。ただし地層名教師がない一般工事柱状図を、自己教師として安易に使わない。

## 4. 最新データ反映規則

データセットごとに以下を保存する。

```text
DatasetId
Publisher
ReleaseDate
LastVerifiedAt
SpatialExtent
CRS
VerticalDatum
FormatVersion
License
ObservationOrModel
InterpretationVersion
SourceURL
Checksum
```

更新処理:

1. `ReleaseDate`ではなく配布物の実際の版・更新履歴を確認する。
2. 新版を別DatasetVersionとして取り込み、旧版を上書きしない。
3. 同じボーリングの重複をBoreholeId、座標、孔長、原資料IDで検出する。
4. 新版で地層解釈が変更された場合、差分を教師ラベルの改訂として保存する。
5. 新研究を導入した後は、固定人工ケースと過去DWGを回帰試験する。
6. 最新という理由だけで、査読済み旧手法より優先しない。

## 5. 人物からデータへたどる手順

```text
event program
  -> presenter and affiliation
  -> ORCID / institutional profile
  -> peer-reviewed papers and public reports
  -> supplementary data / public dataset
  -> method reproduction
  -> project rule candidate
  -> artificial-data validation
  -> adoption
```

人物名自体を権威として採用しない。公開された方法、データ、再現性を評価する。

## 6. 現時点で生成器へ反映する変更

- `DatasetVersion`と`LastVerifiedAt`を必須化する。
- 対比結果に単一Confidenceではなく、データ品質・分類確率・空間拘束・論理整合の内訳を持たせる。
- 実測柱状図、基準柱状図、模式柱状図、解釈済みモデルを明示的に型分けする。
- 千葉2026データを最初の高品質教師候補、東京を近接検証、静岡を地域外検証にする。
- 2026年講演予定はWatchlistに置き、要旨・論文公開後に再評価する。

