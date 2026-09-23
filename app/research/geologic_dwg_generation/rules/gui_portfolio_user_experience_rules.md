# GitHub公開版GUI・ユーザー体験規則

Status: Adopted foundation  
Scope: Global / all present and future geological-section GUIs  
Last checked: 2026-09-14

## 利用者の主要目的

初見の利用者が、内部の地質計算を理解していなくても次の順序を見失わないことを最優先とする。

1. 地域または地域設定を選ぶ。
2. 測線を指定する。
3. 出力先を指定する。
4. PNG/DWGまたは中立データを生成する。
5. 成功・警告・拒否理由と検証記録を確認する。

この5群を常時表示する。図面範囲、目盛、DEM取得方式、証拠JSON、ボーリング、構造観測、診断機能は「詳細設定」に配置する。

## 採用規則

- `GUI-UX-001`: 二次設定は初期状態で折りたたむ。展開ボタンは現在状態と次の操作を文字で表す。
- `GUI-UX-002`: 展開領域は他の内容へ重ねず、下方向へ押し出す。長い画面はスクロール可能にする。
- `GUI-UX-003`: 視覚順とTab移動順を、地域→測線→主要生成→詳細→出力→検証状態の論理順に保つ。
- `GUI-UX-004`: マウスなしで詳細表示を切替可能にする。現在は `Alt+D` を補助ショートカットとする。
- `GUI-UX-005`: 処理中は入力と展開切替を無効化し、完了後はComboboxの `readonly` を含む元状態へ戻す。
- `GUI-UX-006`: 成功・警告・拒否を色だけで伝えず、日本語の状態文、理由、成果物パスで伝える。
- `GUI-UX-007`: 初期フォーカスは地域選択とし、破壊的操作や外部出力操作には置かない。
- `GUI-UX-008`: 高度機能を隠すことは機能削除を意味しない。GUIと計算サービスの境界を維持する。
- `GUI-UX-009`: 200%表示倍率、狭い画面、キーボードのみ、高コントラスト相当の視認性を公開前に人手確認する。
- `GUI-UX-010`: GUIの成功表示は、対応する検証ゲートの結果だけから作る。計算開始やファイル存在だけで完成扱いしない。

## 今回の実装境界

TkinterでWinUIの `Expander` と同じ情報設計を再現した。GUIフレームワークの全面変更は行わず、計算経路、Beta 0.1.0、地質判定規則を変更していない。実行時のスクリーンリーダー互換性、Windows表示倍率200%、高コントラストは、実機による公開前ゲートとして残る。

## 根拠

1. Microsoft, [Expander](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/expander): 主要内容を常時表示し、関連する重要度の低い内容を展開する用途。
2. Microsoft, [Navigation design basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics): 一貫性、単純さ、明確さ、および重要項目を優先する原則。
3. Microsoft, [Keyboard interactions](https://learn.microsoft.com/en-us/windows/apps/design/input/keyboard-interactions): 論理的で予測可能なTab順、視覚順との一致、初期フォーカス。
4. Microsoft, [Windows app development best practices](https://learn.microsoft.com/en-us/windows/apps/get-started/best-practices): キーボード操作、可視フォーカス、200%テキスト倍率、色だけに依存しない状態伝達。
5. W3C WAI, [Understanding Error Identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification): 入力エラーを文字または同等の代替手段で識別可能にする原則。

## 再調査条件

GUIフレームワークを変更する、地図選択を主要画面へ追加する、アクセシビリティ監査で不合格になる、または公式Windows/WCAG指針が改訂された場合に再開する。
