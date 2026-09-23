# ボーリング柱状図から地質断面区画を組み立てる生成規則

## 1. 適用範囲と限界

この規則は、複数のボーリング柱状図を単一の鉛直断面測線へ投影し、地層境界線と排他的な地質区画を生成するための実装仕様である。

- 柱状図は点の観測であり、孔間の形状は解釈である。
- 同じ入力から複数の妥当な地質解が成立し得る。自動処理は候補と根拠を返し、根拠不足を隠さない。
- 初期実装は、第四紀堆積物などの単純な層序、侵食谷、レンズ、ピンチアウトを対象とする。
- 断層、転倒層、複雑な褶曲、貫入岩は、構造を明示する別モジュールができるまで自動生成しない。
- 疑似データには `Synthetic / Not measured / Not for design` を明記する。

## 2. 根拠となる設計原則

1. 国土交通省のボーリング交換用データは、孔ごとの位置、標高、孔長、工学的地質区分・現場土質名、色調、観察記事、地質時代、地層・岩体区分、N値、水位等を分離して保持する。入力層もこの責務分離を維持する。
2. GSJの3D地質地盤図は、地層対比から境界面の等式・不等式標高データを作り、地質構造の論理モデルと平滑さを考慮して面を推定する。したがって、境界到達点と未到達制約を同じ点データとして扱わない。
3. BGSのGSI3Dは、孔口位置・標高、解釈済み柱状図、一般化鉛直層序を分け、層序の上下順を拘束する。したがって、岩相名一致だけで層序順を入れ替えない。
4. USGSの相関例は、岩相だけでなく高解像度物性ログの形状と空間的層序整合を同時評価する。利用可能なN値、検層、テフラ、化石、年代等は独立した証拠として加点する。

## 3. 正規化入力スキーマ

### 3.1 Borehole

必須:

- `BoreholeId`: 原資料と一意に結び付くID
- `X`, `Y`: 宣言済み座標参照系の平面座標
- `CollarElevation`: 孔口標高
- `TotalDepth`: 総削孔長
- `Intervals[]`: 深度昇順の観測区間
- `SourceFile`, `SourceRecordId`: 来歴

推奨:

- `CRS`, `VerticalDatum`
- `DrillingAzimuth`, `DrillingInclination`
- `TerminationReason`
- `LocationAccuracy`, `ElevationAccuracy`
- `WaterLevels[]`, `Tests[]`, `CoreRecovery[]`
- `DatasetId`, `DatasetVersion`, `LastVerifiedAt`, `License`
- `DataKind`: `ObservedBorehole | ReferenceBorehole | SyntheticLog | StatisticalModelLog`

計算値:

- `Station`: 断面始点から投影点までの距離
- `Offset`: 元の孔位置から断面測線までの水平距離
- `ProjectedPoint`
- `ProjectionState`: `OnSection | Projected | Rejected`

### 3.2 BoreholeInterval

- `TopDepth`, `BottomDepth`
- `TopElevation = CollarElevation - TopDepth`
- `BottomElevation = CollarElevation - BottomDepth`
- `RawLithology`: 原文を無改変で保存
- `NormalizedLithology`: 辞書で正規化した名称
- `StratigraphicUnit`: 判明している場合だけ設定
- `GeologicAge`, `Color`, `Description`
- `NValues[]`, `Markers[]`, `ObservationQuality`
- `SourceRecordId`

`RawLithology` と `NormalizedLithology` は上書き関係にしない。「砂質シルト」と「シルト質砂」のような原記載差を失わない。

### 3.3 HorizonEvidence

- `EvidenceId`, `BoreholeId`, `Elevation`
- `Kind`: `ObservedBoundary | Marker | NonPenetrationUpperBound | SurfaceOutcrop`
- `HorizonId`: 確定時のみ
- `EvidenceStrength`: `Definitive | Strong | Moderate | Weak`
- `Basis`: テフラ、化石、年代、地層名、岩相遷移、検層形状等

掘止めで対象境界へ到達していない場合は、孔底を境界点にしない。例えば基底面なら `boundaryElevation < bottomHoleElevation` という不等式を記録する。

## 4. 前処理

1. 座標参照系と標高基準を統一する。不明なデータは自動相関へ入れない。
2. 深度区間を昇順に並べ、`TopDepth < BottomDepth`、重複なし、許可されない空白なしを検査する。
3. 傾斜孔は孔軸に沿う深度から3D位置を計算する。鉛直孔として扱わない。
4. 断面測線へ投影し、`Station` と `Offset` を必ず保存する。
5. 投影距離の許容値は図面尺度・地質変化・孔密度に依存するため固定値にしない。設定値と実距離を出力へ残す。
6. 全ての境界標高を丸め前の値で保存する。表示用丸め値は別キーにする。

AutoCAD実装では測線を `Curve` として扱い、標準.NET APIの `Curve.GetClosestPointTo()` 等で投影点を求める。Dynamo Geometryで投影処理を再実装しない。

## 5. 相関の優先順位

高い順に固定する。

1. 一意な年代・テフラ・化石・既知の不整合などの確定指標
2. 確定した地層・岩体区分
3. 複数属性が一致する特徴的な層序パターン
4. 岩相遷移、N値・検層曲線形状、色調、観察記事
5. 厚さ比、標高差、隣孔との空間連続性
6. 岩相名だけの一致

同じ岩相が上下に反復するため、岩相名一致だけで遠隔区間を結ばない。地層単元と岩相は別概念として保持する。

## 6. 順序保存型の全体相関

### 6.1 固定アンカー

確定指標を全孔で固定し、アンカー間を独立した相関窓に分割する。固定済み対応は後工程で覆さない。

### 6.2 候補コスト

隣接孔Aの境界 `a_i` と孔Bの境界 `b_j` の候補コストを次で構成する。

`C(i,j) = Wm*MarkerMismatch + Ws*StratigraphicMismatch + Wl*LithologyTransitionCost + Wp*PropertyCurveCost + Wz*PositionPenalty + Wt*ThicknessRatioCost + Wo*OffsetPenalty`

- `MarkerMismatch`: 一意な指標の矛盾は原則 `Infinity`
- `StratigraphicMismatch`: 一般化鉛直層序に反する候補は `Infinity`
- `LithologyTransitionCost`: 境界上下の岩相組合せの互換度
- `PropertyCurveCost`: N値・検層・粒度系列などの局所形状差
- `PositionPenalty`: 期待標高からの距離の二乗を基本とする激重罰金
- `ThicknessRatioCost`: 周辺の対応層厚比と急変しないか
- `OffsetPenalty`: 断面から遠い孔ほど解釈確度を下げる

絶対重みを全案件で固定しない。各項を無次元化し、地質設定別プロファイルとして版管理する。

### 6.3 動的計画法

境界列を標高降順にし、Needleman–Wunsch型の順序保存DPで最小グローバルコストを求める。

状態:

- `Match(i,j)`: 境界同士を対応
- `GapA(i)`: Aにだけ境界がある
- `GapB(j)`: Bにだけ境界がある

Gapは欠測、侵食、非堆積、レンズ端、掘止め未到達を表現する。最近傍への強制対応は禁止する。同一境界の多重利用は、分岐・合流を明示したレンズ／インターフィンガー状態以外では禁止する。

### 6.4 多孔への拡張

1. 情報量の多い孔または基準孔から開始する。
2. 隣接孔対を順に相関し、確定アンカーをグローバルな `HorizonId` に昇格する。
3. 左右から得た対応が矛盾すれば確定せず `Conflict` にする。
4. 全孔を一巡後、各Horizonの標高傾向と層厚を再評価する。
5. Locked対応は覆さず、それ以外だけを再計算する。

## 7. 地質イベント別の区画生成

### 7.1 整合的な堆積層

- 対応する上下境界間を一単元とする。
- 接触線は共有する一つの正準境界から生成する。
- 層厚は正で、急変には証拠または低確度フラグが必要。

### 7.2 側方変化・レンズ・ピンチアウト

- 同じ地層単元内で岩相が変わることを許可する。
- レンズは母層を置換し、重複しない。
- ピンチアウトは上下境界が同じトポロジー頂点に収束する事象として表現する。
- 孔間で突然消えるだけでは侵食か非堆積かを断定せず、候補を複数保持する。

### 7.3 侵食・不整合・埋没谷

- 古い単元を先に構築し、侵食面で切断する。
- 谷底礫層などの基底相は侵食面直上に配置する。
- 若い谷埋め層は侵食面へオンラップさせる。
- 古い境界線を侵食面の上へ連続させない。

### 7.4 未到達と範囲外

- 対象境界未到達孔は不等式拘束として補間へ渡す。
- 最上位・最下位の外挿は、傾向が安定し根拠がある範囲だけ許可する。
- 断面端で証拠が切れる場合、線を確定線のまま延長しない。

## 8. 境界曲線と区画トポロジー

1. 相関済みHorizonごとに、孔位置の等式点、不等式拘束、地表露頭を集める。
2. 補間はデータ充足と滑らかさを両立させる。見た目目的の独立サイン波は禁止する。
3. 2D初期実装は、形状保持区分三次補間または張力付きスプラインを使い、オーバーシュートを検査する。
4. 補間後、全stationで一般化鉛直層序、非交差、正層厚を検査する。
5. 侵食面、断層、ピンチアウトだけが通常の連続関係を変更できる。
6. 地形と境界から共有エッジの正準グラフを作り、その面を区画化する。
7. Hatchは区画ポリゴン検証後にAutoCAD `Hatch.AppendLoop()` と `EvaluateHatch()` で生成する。独立した近似境界からハッチを作らない。

## 9. 確度と来歴

各対応・曲線区間・区画に以下を持たせる。

- `InterpretationState`: `Observed | LockedCorrelation | InferredHigh | InferredMedium | InferredLow | Unresolved`
- `EvidenceIds[]`
- `CorrelationCost` と内訳
- `AlternativeIds[]`
- `RuleVersion`, `WeightProfileId`, `CreatedAt`
- `ReviewerState`: `Unreviewed | Accepted | Rejected | Edited`
- `DataQualityConfidence`, `ClassificationConfidence`, `SpatialConfidence`, `LogicalConsistencyConfidence`

観測位置の確度と地質解釈の確度は別キーにする。

単一の総合Confidenceだけで判断しない。例えば分類確率が高くても、測線から遠い孔や層序違反を含む候補は自動確定しない。

## 10. 必須検証ゲート

### Gate A: 入力

- ID、座標系、標高基準、深度単位が明示されている。
- 区間の負深度・逆転・重複・未説明空白がない。
- 原文と正規化値が両方保存されている。

### Gate B: 相関

- 固定指標の矛盾がない。
- Y順序と一般化鉛直層序が保存される。
- 全一致・Gap・Conflictに根拠とコストがある。
- 一つの局所最近傍だけで全体対応を決めていない。

### Gate C: 幾何・トポロジー

- 通常境界同士の交差が0。
- 負層厚が0。
- ポリゴンの重複、隙間、自己交差が0。
- 全孔位置で生成区画を再サンプリングし、元柱状図との不一致を列挙する。

### Gate D: 公開

- 観測・推定・未解決の線種が区別される。
- 投影距離、縦横縮尺、垂直誇張、座標・標高基準を記載する。
- 疑似データ表示と、設計利用不可の注記がある。

### Gate E: 地質学的性能と空間汎化

- 区間一致率やF1とは別に、単元の地理的分布範囲、層序列、鉛直位置を評価する。
- 同じボーリングの区間を学習用と検証用へ分割しない。
- ランダムな区間分割だけでなく、連続した測線区間または空間blockを隠す検証を行う。
- 孔密集部と疎部の誤差を別に集計する。
- 地域モデルとの一致は参考値とし、観測孔とのround-trip一致と混同しない。
- 観測、断面投影、孔間補間、範囲外外挿を別状態で記録し、外挿を観測線として表示しない。

## 11. 実装順序

1. BED0500 XMLまたは手入力JSONの読込と正規化
2. 断面投影と入力QA
3. 一般化鉛直層序・岩相遷移辞書
4. 固定アンカー抽出
5. 隣接孔の順序保存DP相関
6. 多孔Horizon統合とConflict検出
7. イベント解釈（整合、ピンチアウト、侵食、未到達）
8. 境界補間と非交差検証
9. 正準区画グラフとSOLID Hatch生成
10. DWG再読込検証と証拠ログ出力

### 11.1 Civil 3D／外部地質モデル連携時

1. 原データを変更せず、モデル用DBへ複製・正規化する。
2. 自動TIN地層面を `Candidate` として生成する。
3. 地層面ごとに使用孔・除外孔・除外理由を保存する。
4. profile上で解釈し、FeatureLine/breaklineで地層面を拘束する。
5. 交差断面の同一Horizon位置をsnap検査する。
6. 3D volumeとsection planeの交差から断面contactを得る。
7. DWG/DXF出力時も単元別レイヤとSectionIdを維持する。
8. AutoCAD側でnative entity、閉領域、Hatch、draw order、layoutを検証する。

外部モデルから渡された線を地質学的真値として無条件に採用しない。使用データ、座標系、モデル版、断面plane、補間法、除外孔が追跡できない断面は `UnverifiedExternalInterpretation` とする。

## 12. 非目標

- 柱状図だけから年代、断層、堆積環境を断定すること
- 低品質な岩相名一致で自動的に「正解」を一つ選ぶこと
- 推定線を実測線として表示すること
- CAD表示が綺麗という理由だけで地質妥当性を合格にすること

## 13. AI補助処理の境界

AIは次の候補生成に利用できる。

- 自由記載の岩相語彙正規化
- 地層単元候補と確率
- コア画像・検層からの観察特徴候補
- 複数の層序仮説と不確実性
- 古い地質図のgeoreference・vector化候補

AIは直接、最終contact、Hatch、断層、侵食面を確定しない。出力状態は
`AICandidate`から開始し、一般化鉛直層序、unit connectivity、地質イベント、
空間block検証、孔位置round-trip、非交差・正層厚・排他的polygon検証に合格後、
`CADReady`へ昇格する。

同じ岩相が複数層準へ現れるため、分類器の第一候補だけで地層単元を決めない。
branch-and-pruneで地質的に可能な候補列を保持し、複数孔のtopological consistency、
既存のローカル・グローバルコスト、位置ペナルティで順位付けする。代替解と棄却理由を
削除しない。

### 13.1 AIとJISの接続

AI候補は地質学的検証後、JIS地質属性へのmappingを経てからCADへ渡す。

- AI用語はJIS X 22989を基準にし、地質用語namespaceと分離する。
- AI運用はJIS Q 42001のPDCA、責任、リスク、変更管理を内部設計の参考にする。
- データセットにはISO/IEC 5259 seriesを参考に、来歴、完全性、代表性、欠測、偏り、地域・地質適用範囲、分割方式を記録する。
- AI品質はISO/IEC 25059を参考に、正確性だけでなくrobustness、transparency、controllability、intervenability、traceabilityを評価する。
- 表示候補はJIS A 0204、ベクトル・主題属性品質候補はJIS A 0205、工学地質コード候補はJIS A 0206＋現行追補へ対応付ける。
- mapping不能または複数候補は自動補完せず、`UnmappedJISCode`または`AmbiguousJISCode`にする。
- 規格票の適用範囲、コード、著作権を正式確認するまでJIS適合を表明しない。
