# 日本の地価公示 3Dマップ（静的サイト）

このフォルダーの `site/` をそのまま静的ホスティングへ配置できます。ブラウザー実行時はCARTO等の背景地図、外部GeoJSON、CDN、APIを利用しません。背景地図タイルを外し、ローカルのdeck.gl、地価JSON、都道府県GeoJSONだけで表示します。出典リンクは利用者がクリックした場合だけ外部ページへ移動します。

## 公開用ファイル

- `site/index.html` — アプリ本体（3D ColumnLayer、Bloom、年操作、フィルター、詳細グラフ）
- `site/data/land_price.json` — 25,565地点、1983〜2026年の履歴・属性を含む
- `site/data/prefectures.geojson` — 日本の47都道府県境界
- `site/vendor/deck.gl.min.js` — deck.gl standalone UMD（9.3.11）
- `site/vendor/deck.gl.LICENSE.txt` — deck.gl MIT License
- `site/licenses/THIRD_PARTY_NOTICES.txt` — 同梱JavaScriptの第三者表示

GitHub Pagesのデプロイ対象は `site/` だけです。`.github/workflows/pages.yml` はそのディレクトリを検査してPagesへ配置します。

## データの出典と条件

### 地価

正式名称: 国土数値情報（地価公示）（令和8年）
提供元: 国土交通省
元ページ: <https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2026.html>
利用条件: 公式ページでは2019年以降をオープンデータ（CC BY 4.0）としています。属性・座標の一部をJSON化し、年ごとの表示用形式へ加工しています。
画面の出典表記: 「国土数値情報（地価公示）（令和8年）」（国土交通省）を加工して作成
利用規約: <https://nlftp.mlit.go.jp/ksj/other/agreement.html>

### 都道府県境界

正式名称: Natural Earth 1:10m Admin 1 – States, Provinces, version 5.1.1
提供元: Natural Earth
元ページ: <https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/>
利用条件: Natural Earth公式Terms of Useにより同サイトのベクターデータはパブリックドメインです。許諾・クレジットは必須ではありませんが、画面には推奨表記 “Made with Natural Earth.” を掲載しています。
条件: <https://www.naturalearthdata.com/about/terms-of-use/>
詳細: `licenses/DATA_SOURCES.txt`
加工内容: 元のShapefileから `admin=Japan` の47件を抽出し、日本語の都道府県名と境界形状だけにしぼり、EPSG:4326 GeoJSONへ変換しました。簡略化は行っていません。Natural Earth自身がAdmin 1テーマをベータと注記しており、測量上の法定境界ではなく地図用の境界データです。国土地理院の境界データではなく、国土地理院の承認を要しないNatural Earthデータを採用しています。

## ビルドし直す場合

Python 3.11以降を用意し、次の入力を置きます。

- 国土交通省の公式2026年地価公示データZIP: プロジェクト直下の `L01-26_GML.zip`
- Natural Earth 5.1.1 Admin 1のShapefile一式（配布元README.htmlのみ除外）: `source-data/ne_10m_admin_1_states_provinces_data.zip`

依存関係を入れて、プロジェクト直下で次を実行します。

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python build.py
```

`build.py` が `map.py` から `site/` を作り直し、最後に外部依存検査を実行します。 Natural Earthの元ZIPはローカルに保持し、README.htmlを除いたShapefile一式をリポジトリ用入力として使います。元ZIPは `.gitignore` でGit対象外です。deck.glのJavaScriptは配布元にアクセスせず、既存の `site/vendor/deck.gl.min.js` を使います。元の地価ZIPは利用者のブラウザーへ配布されません。

## 公開前チェック

```powershell
python tools/check_external_dependencies.py --site site
```

検査は実際の公開HTML、同梱JS/CSS、静的リクエスト先、CSP、ローカル参照ファイルを確認します。出典を示す通常のリンクはクリック時の遷移であり、アプリ実行に必要な通信ではないため対象外です。

## GitHub Pagesへ公開

1. プロジェクトのソースと `site/` をGitHubリポジトリへpushします（地価原本 `L01-26_GML.zip` は含めないでください）。
2. GitHubのリポジトリで **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にします。
3. `main` へpushするか、**Actions → Deploy GitHub Pages → Run workflow** を実行します。
4. Actionsの成功後、**Settings → Pages** に表示されるURLを開きます。

`.github/workflows/pages.yml` は `site/` の外部依存検査に合格した後、その内容だけをデプロイします。