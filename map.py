import io
import json
import re
import tempfile
import zipfile
from pathlib import Path
from html import escape as html_escape

import geopandas as gpd
import pandas as pd
import pydeck as pdk


# ==========================================
# 基本設定
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
ZIP_PATH = BASE_DIR / "L01-26_GML.zip"
BOUNDARY_ZIP_PATH = (
    BASE_DIR
    / "source-data"
    / "ne_10m_admin_1_states_provinces_data.zip"
)

SITE_DIR = BASE_DIR / "site"
SITE_DATA_DIR = SITE_DIR / "data"
SITE_VENDOR_DIR = SITE_DIR / "vendor"
for directory in (SITE_DIR, SITE_DATA_DIR, SITE_VENDOR_DIR):
    directory.mkdir(parents=True, exist_ok=True)

OUTPUT_HTML = SITE_DIR / "index.html"
LAND_PRICE_JSON_PATH = SITE_DATA_DIR / "land_price.json"
PREFECTURE_GEOJSON_PATH = SITE_DATA_DIR / "prefectures.geojson"
DECKGL_BUNDLE_PATH = SITE_VENDOR_DIR / "deck.gl.min.js"


# ==========================================
# データ読み込み
# ==========================================

print("データを読み込んでいます...")

all_gdfs = []

with zipfile.ZipFile(ZIP_PATH, "r") as main_zip:

    members = main_zip.namelist()
    direct_geojsons = [
        name
        for name in members
        if name.lower().endswith((".geojson", ".json"))
    ]
    nested_zips = [
        name
        for name in members
        if name.lower().endswith(".zip")
    ]

    print(f"\u5185\u90e8ZIP: {len(nested_zips)}")

    if direct_geojsons:
        for geojson_name in direct_geojsons:
            try:
                geojson_data = main_zip.read(geojson_name)
                gdf = gpd.read_file(io.BytesIO(geojson_data))
                all_gdfs.append(gdf)
            except Exception as e:
                print(f"\u8aad\u307f\u8fbc\u307f\u5931\u6557: {geojson_name}")
                print(e)
    else:
        for nested_name in nested_zips:
            nested_data = main_zip.read(nested_name)

            with zipfile.ZipFile(io.BytesIO(nested_data), "r") as nested_zip:
                geojson_files = [
                    name
                    for name in nested_zip.namelist()
                    if name.lower().endswith((".geojson", ".json"))
                ]

                for geojson_name in geojson_files:
                    try:
                        geojson_data = nested_zip.read(geojson_name)
                        gdf = gpd.read_file(io.BytesIO(geojson_data))
                        all_gdfs.append(gdf)
                    except Exception as e:
                        print(f"\u8aad\u307f\u8fbc\u307f\u5931\u6557: {nested_name}")
                        print(e)


if not all_gdfs:
    raise RuntimeError("GeoJSON\u30c7\u30fc\u30bf\u3092\u8aad\u307f\u8fbc\u3081\u307e\u305b\u3093\u3067\u3057\u305f.")


gdf = gpd.GeoDataFrame(
    pd.concat(all_gdfs, ignore_index=True),
    crs=all_gdfs[0].crs
)

required_columns = [
    "L01_001", "L01_008", "L01_009", "L01_024", "L01_025", "L01_028"
] + [
    f"L01_{i:03d}"
    for i in range(62, 106)
]
missing_columns = [column for column in required_columns if column not in gdf.columns]
if missing_columns:
    raise RuntimeError(f"\u5fc5\u8981\u306a\u9805\u76ee\u304c\u3042\u308a\u307e\u305b\u3093: {missing_columns}")

gdf = gdf[required_columns + ["geometry"]].copy()
gdf = gdf.to_crs(epsg=4326)

print(f"読み込み地点数: {len(gdf):,}")


# ==========================================
# 緯度・経度
# ==========================================

gdf["lon"] = gdf.geometry.x
gdf["lat"] = gdf.geometry.y

# 都道府県（行政区域コードの先頭2桁）
prefecture_names = {
    "01": "\u5317\u6d77\u9053", "02": "\u9752\u68ee\u770c", "03": "\u5ca9\u624b\u770c",
    "04": "\u5bae\u57ce\u770c", "05": "\u79cb\u7530\u770c", "06": "\u5c71\u5f62\u770c",
    "07": "\u798f\u5cf6\u770c", "08": "\u8328\u57ce\u770c", "09": "\u6803\u6728\u770c",
    "10": "\u7fa4\u99ac\u770c", "11": "\u57fc\u7389\u770c", "12": "\u5343\u8449\u770c",
    "13": "\u6771\u4eac\u90fd", "14": "\u795e\u5948\u5ddd\u770c", "15": "\u65b0\u6f5f\u770c",
    "16": "\u5bcc\u5c71\u770c", "17": "\u77f3\u5ddd\u770c", "18": "\u798f\u4e95\u770c",
    "19": "\u5c71\u68a8\u770c", "20": "\u9577\u91ce\u770c", "21": "\u5c90\u961c\u770c",
    "22": "\u9759\u5ca1\u770c", "23": "\u611b\u77e5\u770c", "24": "\u4e09\u91cd\u770c",
    "25": "\u6ecb\u8cc0\u770c", "26": "\u4eac\u90fd\u5e9c", "27": "\u5927\u962a\u5e9c",
    "28": "\u5175\u5eab\u770c", "29": "\u5948\u826f\u770c", "30": "\u548c\u6b4c\u5c71\u770c",
    "31": "\u9ce5\u53d6\u770c", "32": "\u5cf6\u6839\u770c", "33": "\u5ca1\u5c71\u770c",
    "34": "\u5e83\u5cf6\u770c", "35": "\u5c71\u53e3\u770c", "36": "\u5fb3\u5cf6\u770c",
    "37": "\u9999\u5ddd\u770c", "38": "\u611b\u5a9b\u770c", "39": "\u9ad8\u77e5\u770c",
    "40": "\u798f\u5ca1\u770c", "41": "\u4f50\u8cc0\u770c", "42": "\u9577\u5d0e\u770c",
    "43": "\u718a\u672c\u770c", "44": "\u5927\u5206\u770c", "45": "\u5bae\u5d0e\u770c",
    "46": "\u9e7f\u5150\u5cf6\u770c", "47": "\u6c96\u7e04\u770c",
}
gdf["prefecture_code"] = (
    gdf["L01_001"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5).str[:2]
)
gdf["prefecture"] = gdf["prefecture_code"].map(prefecture_names).fillna("その他")
prefecture_order = {
    name: index for index, name in enumerate(prefecture_names.values())
}
prefecture_options = sorted(
    gdf["prefecture"].dropna().unique().tolist(),
    key=lambda name: (prefecture_order.get(name, len(prefecture_order)), name)
)
region_prefectures = {
    "北海道": ["北海道"],
    "東北": ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"],
    "関東": ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"],
    "中部": ["新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県"],
    "近畿": ["三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"],
    "中国": ["鳥取県", "島根県", "岡山県", "広島県", "山口県"],
    "四国": ["徳島県", "香川県", "愛媛県", "高知県"],
    "九州・沖縄": ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"],
}
prefecture_checkboxes = "\n".join(
    '<section class="prefecture-region" data-region="{}">'
    '<label class="region-check">'
    '<input class="prefecture-region-toggle" type="checkbox" checked>'
    '<span>{}</span></label>'
    '<div class="prefecture-checks">{}</div></section>'.format(
        html_escape(region, quote=True),
        html_escape(region),
        "".join(
            '<label class="prefecture-check">'
            f'<input type="checkbox" value="{html_escape(name, quote=True)}" checked>'
            f'<span>{html_escape(name)}</span></label>'
            for name in region_prefectures[region]
            if name in prefecture_options
        ),
    )
    for region in region_prefectures
    if any(name in prefecture_options for name in region_prefectures[region])
)



# ==========================================
# 現在価格・前年比
# ==========================================

price_column = "L01_008"
change_column = "L01_009"

if price_column not in gdf.columns:
    raise RuntimeError("L01_008 が見つかりません。")

if change_column not in gdf.columns:
    raise RuntimeError("L01_009 が見つかりません。")


gdf["price"] = pd.to_numeric(
    gdf[price_column],
    errors="coerce"
)

gdf["change"] = pd.to_numeric(
    gdf[change_column],
    errors="coerce"
)


# ==========================================
# 不要データ除外
# ==========================================

gdf = gdf.dropna(
    subset=["lon", "lat", "price"]
)

gdf = gdf[gdf["price"] > 0].copy()


# ==========================================
# 3D高さ
# ==========================================

# 今ちょうど良いので変更しない
gdf["elevation"] = (gdf["price"] ** 0.58) * 8


# ==========================================
# 色
# ==========================================

def change_to_color(change):

    if pd.isna(change):
        return [255, 255, 255, 150]

    # -30%以下 → 青
    if change <= -30:
        return [70, 145, 255, 150]

    # -30% ～ 0% → 青 → 白
    elif change < 0:

        t = (change + 30) / 30

        return [
            int(70 + 185 * t),
            int(145 + 110 * t),
            255,
            150
        ]

    # 0% ～ +5% → 白 → 赤
    elif change <= 5:

        t = change / 5

        return [
            255,
            int(255 - 185 * t),
            int(255 - 185 * t),
            150
        ]

    # +5% ～ +30%以上 → 赤 → 紫
    else:

        t = min((change - 5) / 25, 1)

        return [
            int(255 - 155 * t),
            int(70 - 50 * t),
            int(70 - 24 * t),
            150
        ]


gdf["color"] = gdf["change"].apply(
    change_to_color
)


# ==========================================
# 表示用文字
# ==========================================

gdf["price_display"] = gdf["price"].map(
    lambda x: f"{x:,.0f} 円/m²"
)

gdf["change_display"] = gdf["change"].map(
    lambda x: f"{x:+.1f}%"
)


# ==========================================
# 過去価格データ
#
# L01_062 = 1983
# L01_063 = 1984
# ...
# L01_104 = 2025
# L01_105 = 2026
# ==========================================

years = list(range(1983, 2027))

history_columns = [
    "L01_062"
] + [
    f"L01_{i:03d}"
    for i in range(63, 106)
]


# ==========================================
# JavaScriptへ渡すデータを作成
# ==========================================

history_records = []


for _, row in gdf.iterrows():

    prices = []

    for col in history_columns:

        value = pd.to_numeric(
            row[col],
            errors="coerce"
        )

        if pd.isna(value):
            value = 0

        prices.append(int(value))


    history_records.append({

        "lon": float(row["lon"]),

        "lat": float(row["lat"]),

        "prefecture": str(row["prefecture"]),

        "city": str(row["L01_024"]),

        "address": str(row["L01_025"]),

        "use": str(row["L01_028"]),

        "prices": prices,

        # 2026だけは公式の前年比を保持
        "official_change_2026": (
            float(row["L01_009"])
            if pd.notna(row["L01_009"])
            else None
        )

    })


history_json = json.dumps(
    history_records,
    ensure_ascii=False,
    separators=(",", ":")
)
LAND_PRICE_JSON_PATH.write_text(history_json, encoding="utf-8")


def build_local_prefecture_geojson():
    """Convert Natural Earth's official Admin-1 shapefile to a local GeoJSON."""
    if not BOUNDARY_ZIP_PATH.is_file():
        raise FileNotFoundError(
            "Natural Earth boundary source archive is missing: "
            f"{BOUNDARY_ZIP_PATH}"
        )

    shapefile_parts = {
        "ne_10m_admin_1_states_provinces.shp",
        "ne_10m_admin_1_states_provinces.shx",
        "ne_10m_admin_1_states_provinces.dbf",
        "ne_10m_admin_1_states_provinces.prj",
        "ne_10m_admin_1_states_provinces.cpg",
    }

    with tempfile.TemporaryDirectory(prefix="japan-prefectures-") as temp_dir:
        extraction_dir = Path(temp_dir)
        with zipfile.ZipFile(BOUNDARY_ZIP_PATH, "r") as archive:
            for member in archive.infolist():
                member_name = Path(member.filename).name
                if member_name not in shapefile_parts:
                    continue
                (extraction_dir / member_name).write_bytes(
                    archive.read(member)
                )

        shapefile_path = (
            extraction_dir / "ne_10m_admin_1_states_provinces.shp"
        )
        if not shapefile_path.is_file():
            raise ValueError("Natural Earth shapefile is incomplete")

        admin1 = gpd.read_file(shapefile_path)
        japan = admin1.loc[admin1["admin"] == "Japan"].copy()
        if len(japan) != 47:
            raise ValueError(
                "Expected 47 Japanese prefectures in Natural Earth data, "
                f"found {len(japan)}"
            )

        japan = japan[["name_ja", "geometry"]].rename(
            columns={"name_ja": "prefecture"}
        )
        if japan["prefecture"].isna().any() or not japan.geometry.is_valid.all():
            raise ValueError("Natural Earth prefecture names/geometries are invalid")
        japan = japan.to_crs("EPSG:4326")
        geojson = json.loads(japan.to_json(drop_id=True))

    PREFECTURE_GEOJSON_PATH.write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"ローカル都道府県境界: {len(geojson['features'])}")


build_local_prefecture_geojson()


# ==========================================
# 3D Column Layer
# ==========================================

layer = pdk.Layer(
    "ColumnLayer",

    # The browser loads local history JSON after the local deck.gl standalone
    # script is ready; keep point data out of HTML to avoid embedding it twice.
    data=[],

    get_position="[lon, lat]",

    get_elevation="elevation",

    elevation_scale=0.7,

    radius=50,

    get_fill_color="color",

    pickable=True,

    auto_highlight=True,
)


# ==========================================
# カメラ
# ==========================================

view_state = pdk.ViewState(

    latitude=36.39,

    longitude=137.39,

    zoom=6.16,

    pitch=53.5,

    bearing=-14.1,
)


# ==========================================
# 初期Tooltip
# ==========================================

tooltip = {

    "html": """
    <div style="
        font-family: Arial, sans-serif;
        padding: 4px;
        min-width: 240px;
    ">

        <div style="
            font-size: 17px;
            font-weight: bold;
            margin-bottom: 4px;
        ">
            {L01_024}
        </div>

        <div style="
            font-size: 13px;
            opacity: 0.9;
            line-height: 1.5;
        ">
            {L01_025}
        </div>

        <hr style="
            border: 0;
            border-top: 1px solid rgba(255,255,255,0.25);
            margin: 8px 0;
        ">

        <div style="
            font-size: 14px;
            line-height: 1.8;
        ">

            <b>地価</b>　{price_display}<br/>

            <b>前年比</b>　{change_display}<br/>

            <b>用途</b>　{L01_028}

        </div>

    </div>
    """,

    "style": {
        "backgroundColor": "rgba(5, 8, 15, 0.92)",
        "color": "white",
        "border": "1px solid rgba(255,255,255,0.15)",
        "borderRadius": "8px",
        "boxShadow": "0 4px 20px rgba(0,0,0,0.5)",
    }
}


# ==========================================
# 地図
# ==========================================
# 都道府県境界はNatural Earth公式配布データから生成したローカルGeoJSON。

deck = pdk.Deck(

    layers=[layer],

    initial_view_state=view_state,

    tooltip=tooltip,

    # No remote basemap: the map is rendered by deck.gl over a neutral canvas.
    map_style=None,
    map_provider=None,
)


# ==========================================
# HTML生成
# ==========================================

html = deck.to_html(
    as_string=True,
    notebook_display=False,
    offline=True,
)

# Generate the pydeck HTML skeleton in offline mode, then replace its bundled
# Jupyter/widget bootstrap with the standalone deck.gl UMD build committed in
# site/vendor/. The pydeck widget bundle contains unused Mapbox/MapLibre code
# and a default CARTO style URL, so it is intentionally not shipped.
if not DECKGL_BUNDLE_PATH.is_file():
    raise FileNotFoundError(
        f"deck.gl standalone asset is missing: {DECKGL_BUNDLE_PATH}"
    )

bundle_match = re.search(
    r"<script\s+type=['\"]text/javascript['\"]>([\s\S]*?)</script>",
    html,
    flags=re.IGNORECASE,
)
if not bundle_match:
    raise RuntimeError("pydeck offline bundle was not embedded in generated HTML")
html = (
    html[:bundle_match.start()]
    + '<script src="vendor/deck.gl.min.js"></script>'
    + html[bundle_match.end():]
)

# Discard pydeck's createDeck() bootstrap, which serializes its default
# provider configuration. Start the local deck.gl runtime directly instead.
deck_bootstrap_pattern = re.compile(
    r"<script>\s*const container = document\.getElementById\(['\"]deck-container['\"]\);"
    r"[\s\S]*?const deckInstance = createDeck\([\s\S]*?\);\s*</script>",
    flags=re.IGNORECASE,
)
initial_state_json = json.dumps(
    {
        "latitude": view_state.latitude,
        "longitude": view_state.longitude,
        "zoom": view_state.zoom,
        "pitch": view_state.pitch,
        "bearing": view_state.bearing,
    }
)
direct_deck_bootstrap = f"""<script>
let currentViewState = {initial_state_json};
const deckInstance = new deck.Deck({{
    parent: document.getElementById("deck-container"),
    views: [new deck.MapView({{id: "map-view", controller: true}})],
    viewState: currentViewState,
    controller: {{minPitch: 0, maxPitch: 60}},
    onViewStateChange: ({{viewState}}) => {{
        currentViewState = viewState;
        deckInstance.setProps({{viewState}});
    }},
    layers: [],
    useDevicePixels: true
}});
</script>"""
html, replaced_bootstraps = deck_bootstrap_pattern.subn(
    lambda _match: direct_deck_bootstrap,
    html,
    count=1,
)
if replaced_bootstraps != 1:
    raise RuntimeError("could not replace pydeck createDeck() bootstrap")
html = re.sub(
    r"<script\b(?=[^>]*\bsrc\s*=\s*['\"]?https?://)[^>]*>[\s\S]*?</script\s*>",
    "",
    html,
    flags=re.IGNORECASE,
)
html = re.sub(
    r"<link\b(?=[^>]*\bhref\s*=\s*['\"]?https?://)[^>]*>",
    "",
    html,
    flags=re.IGNORECASE,
)
html = html.replace(
    '<meta http-equiv="content-type" content="text/html; charset=UTF-8" />',
    '<meta http-equiv="content-type" content="text/html; charset=UTF-8" />\n'
    '<meta http-equiv="Content-Security-Policy" content="'
    "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' blob:; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "connect-src 'self'; font-src 'self' data:; worker-src 'self' blob:; "
    "object-src 'none'; base-uri 'self'"
    '">',
)
OUTPUT_HTML.write_text(html, encoding="utf-8")


# ==========================================
# UI
# ==========================================

html = OUTPUT_HTML.read_text(
    encoding="utf-8"
)


custom_ui = r"""
<style>

body {
    margin: 0;
    overflow: hidden;
    background: #585B66;
    font-family: Arial, sans-serif;
}

#deck-container {
    position: relative;
}

#deck-container #selection-bloom-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    mix-blend-mode: plus-lighter;
}

#deck-container #selection-bloom-canvas {
    z-index: 3;
}


/* ==========================================
   タイトル
   ========================================== */

#map-title {

    position: fixed;

    top: 20px;
    left: 20px;

    z-index: 9999;

    padding: 12px 18px;

    background: rgba(5, 8, 15, 0.80);

    border: 1px solid rgba(255,255,255,0.18);

    border-radius: 8px;

    color: white;

    box-shadow:
        0 0 18px rgba(0,255,255,0.08);

    backdrop-filter: blur(6px);
}

#map-title-main {

    font-size: 18px;

    font-weight: bold;

    letter-spacing: 2px;
}

#map-title-sub {

    margin-top: 4px;

    font-size: 11px;

    opacity: 0.65;

    letter-spacing: 1px;
}


/* ==========================================
   凡例
   ========================================== */

#legend {

    position: fixed;

    left: 20px;
    bottom: 82px;

    z-index: 9999;

    width: 260px;

    padding: 14px 16px;

    background: rgba(5, 8, 15, 0.84);

    border: 1px solid rgba(255,255,255,0.16);

    border-radius: 8px;

    color: white;

    box-shadow:
        0 0 18px rgba(0,255,255,0.08);

    backdrop-filter: blur(6px);
}

#legend-title {

    font-size: 12px;

    letter-spacing: 1px;

    margin-bottom: 8px;

    opacity: 0.9;
}

#legend-bar {

    width: 100%;

    height: 12px;

    border-radius: 6px;

    background: linear-gradient(
        to right,
        rgb(70,145,255) 0%,
        rgb(255,255,255) 50%,
        rgb(255,70,70) 58.333%,
        rgb(170,50,255) 100%
    );

    border: 1px solid rgba(255,255,255,0.25);
}

#legend-labels {

    position: relative;

    margin-top: 5px;

    font-size: 10px;

    opacity: 0.75;

    height: 12px;
}

#legend-labels span {
    position: absolute;
    transform: translateX(-50%);
}

#legend-labels span:first-child {
    left: 0;
    transform: none;
}

#legend-labels span:last-child {
    right: 0;
    transform: none;
}


/* ==========================================
   タイムスライダー
   ========================================== */

#timeline {

    position: fixed;

    left: 50%;

    bottom: 22px;

    transform: translateX(-50%);

    z-index: 9999;

    width: min(520px, calc(100vw - 360px));

    padding: 14px 18px;

    background: rgba(5, 8, 15, 0.88);

    border: 1px solid rgba(255,255,255,0.16);

    border-radius: 10px;

    color: white;

    box-shadow:
        0 0 24px rgba(0,255,255,0.08);

    backdrop-filter: blur(8px);
}

#timeline-top {

    display: flex;

    align-items: center;

    justify-content: space-between;

    margin-bottom: 8px;
}

#timeline-year {

    font-size: 26px;

    font-weight: bold;

    letter-spacing: 2px;
}

#play-button {

    padding: 6px 12px;

    border: 1px solid rgba(255,255,255,0.25);

    border-radius: 6px;

    background: rgba(255,255,255,0.08);

    color: white;

    cursor: pointer;

    font-size: 12px;
}

#timeline-slider-row {
    display: flex;
    align-items: center;
    gap: 10px;
}

#year-slider {
    flex: 1;
    width: 100%;
    cursor: pointer;
}

.year-step-button {
    flex: 0 0 auto;
    width: 30px;
    height: 30px;
    padding: 0;
    border: 1px solid rgba(255,255,255,0.20);
    border-radius: 6px;
    background: rgba(255,255,255,0.06);
    color: rgba(255,255,255,0.85);
    font-family: "Consolas", "Courier New", monospace;
    font-size: 15px;
    line-height: 28px;
    cursor: pointer;
    transition: background .15s ease, border-color .15s ease, transform .08s ease;
}

.year-step-button:hover {
    background: rgba(0,255,255,0.10);
    border-color: rgba(0,255,255,0.35);
}

.year-step-button:active {
    transform: scale(0.94);
}

#timeline-years {

    display: flex;

    justify-content: space-between;

    font-size: 10px;

    opacity: 0.6;

    margin-top: 3px;
}


/* ==========================================
   都道府県フィルター
   ========================================== */

#display-controls {
    position: fixed;
    top: 132px;
    right: 20px;
    z-index: 9999;
    width: 250px;
    padding: 11px 12px;
    background: rgba(5, 8, 15, 0.88);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 8px;
    color: white;
    backdrop-filter: blur(8px);
    box-sizing: border-box;
}

#display-controls-title {
    font-size: 11px;
    letter-spacing: 1px;
    opacity: 0.8;
    margin-bottom: 9px;
}

.display-control-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    align-items: center;
    gap: 8px;
    margin-top: 7px;
    font-size: 11px;
}

.display-control-row select {
    width: 100%;
    padding: 5px 7px;
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 5px;
    background: #111a27;
    color: white;
    font-size: 11px;
}

#prefecture-filter {
    position: fixed;
    top: 244px;
    right: 20px;
    z-index: 9999;
    width: 250px;
    max-height: calc(100vh - 264px);
    overflow-y: auto;
    background: rgba(5, 8, 15, 0.9);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 8px;
    color: white;
    backdrop-filter: blur(8px);
    box-sizing: border-box;
}

#prefecture-filter summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
    cursor: pointer;
    list-style: none;
}

#prefecture-filter summary::-webkit-details-marker {
    display: none;
}

#prefecture-filter summary::after {
    content: "+";
    font-size: 16px;
    opacity: 0.7;
}

#prefecture-filter[open] summary::after {
    content: "−";
}

#prefecture-filter-title {
    font-size: 11px;
    letter-spacing: 1px;
    white-space: nowrap;
}

#prefecture-filter-content {
    padding: 0 12px 10px;
}

#prefecture-status {
    font-size: 9px;
    opacity: 0.55;
    margin: 0;
    white-space: nowrap;
}

.prefecture-actions {
    display: flex;
    gap: 6px;
    margin-bottom: 7px;
}

.prefecture-action {
    border: 1px solid rgba(255,255,255,0.18);
    background: rgba(255,255,255,0.06);
    color: white;
    border-radius: 5px;
    padding: 4px 7px;
    font-size: 10px;
    cursor: pointer;
}

.prefecture-checks {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5px 8px;
    padding: 7px 0 2px 18px;
}

.prefecture-region {
    padding: 7px 0 5px;
    border-top: 1px solid rgba(255,255,255,0.1);
}

.region-check {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    font-weight: bold;
    cursor: pointer;
}

.prefecture-check {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    white-space: nowrap;
    cursor: pointer;
}

.prefecture-check input {
    margin: 0;
    accent-color: #00ffff;
}

#source-license {
    position: fixed;
    top: auto;
    bottom: 20px;
    left: 20px;
    z-index: 9997;
    width: min(360px, calc(100vw - 40px));
    max-height: 42vh;
    overflow-y: auto;
    background: rgba(5, 8, 15, 0.9);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 8px;
    color: white;
    backdrop-filter: blur(8px);
    box-sizing: border-box;
    font-size: 10px;
}

#source-license summary {
    padding: 8px 10px;
    cursor: pointer;
    letter-spacing: .3px;
}

#source-license-content {
    padding: 0 10px 10px;
    line-height: 1.6;
    opacity: .84;
}

#source-license-content p {
    margin: 5px 0;
}

#source-license-content a {
    color: #80dfff;
}

.region-check input {
    margin: 0;
    accent-color: #00ffff;
}

/* ==========================================
   地点詳細パネル
   ========================================== */

#detail-panel {
    position: fixed;
    top: 294px;
    left: auto;
    right: 20px;
    transform: none;
    z-index: 10000;
    width: min(370px, calc(100vw - 24px));
    max-height: calc(100vh - 314px);
    overflow-y: auto;
    padding: 16px;
    box-sizing: border-box;
    background: rgba(5, 8, 15, 0.94);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 10px;
    color: white;
    box-shadow: 0 0 24px rgba(0,255,255,0.08);
    backdrop-filter: blur(10px);
    display: none;
}

#detail-close {
    float: right;
    border: 0;
    background: transparent;
    color: rgba(255,255,255,0.65);
    font-size: 20px;
    cursor: pointer;
}

#detail-title {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 3px;
}

#detail-address {
    font-size: 12px;
    opacity: 0.7;
    line-height: 1.5;
    margin-bottom: 10px;
}

#detail-current {
    font-size: 13px;
    line-height: 1.8;
    padding: 8px 10px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
}

#detail-chart {
    width: 100%;
    height: 150px;
}

#detail-years {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    opacity: 0.55;
    margin-top: -3px;
}

#detail-hint {
    margin-top: 8px;
    font-size: 10px;
    opacity: 0.5;
}

/* ==========================================
   サイバー演出：起動アニメーション
   ========================================== */

#boot-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    background:
        radial-gradient(circle at center, rgba(0,255,255,.09), transparent 35%),
        rgba(2, 6, 12, 0.97);
    color: #eaffff;
    font-family: "Consolas", "Courier New", monospace;
    letter-spacing: 1px;
    transition: opacity .45s ease, visibility .45s ease;
}

#boot-overlay.boot-complete {
    opacity: 0;
    visibility: hidden;
}

#boot-panel {
    width: min(540px, calc(100vw - 48px));
    padding: 24px;
    border: 1px solid rgba(0,255,255,.38);
    background: rgba(4, 11, 19, .90);
    box-shadow: 0 0 45px rgba(0,255,255,.12);
    position: relative;
    overflow: hidden;
}

#boot-panel::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,255,255,.9), transparent);
    animation: bootScan 1.0s linear infinite;
}

#boot-title {
    font-size: 19px;
    font-weight: 700;
    margin-bottom: 12px;
}

#boot-status {
    font-size: 11px;
    line-height: 1.9;
    min-height: 62px;
    color: rgba(230,255,255,.72);
}

#boot-progress {
    margin-top: 12px;
    height: 6px;
    border: 1px solid rgba(0,255,255,.26);
    background: rgba(255,255,255,.03);
}

#boot-progress-bar {
    width: 0%;
    height: 100%;
    background: linear-gradient(90deg, rgba(0,180,255,.55), rgba(0,255,255,.95));
    box-shadow: 0 0 14px rgba(0,255,255,.45);
    transition: width .18s linear;
}

@keyframes bootScan {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

/* ==========================================
   サイバー演出：右上システム情報
   ========================================== */

#system-monitor {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    width: 250px;
    padding: 10px 12px;
    box-sizing: border-box;
    background: rgba(5, 8, 15, 0.82);
    border: 1px solid rgba(0,255,255,.20);
    color: rgba(235,255,255,.90);
    box-shadow: 0 0 18px rgba(0,255,255,.06);
    backdrop-filter: blur(7px);
    font-family: "Consolas", "Courier New", monospace;
}

#system-monitor-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 10px;
    letter-spacing: 1.2px;
    opacity: .78;
}

#system-online {
    color: #7dffff;
    text-shadow: 0 0 8px rgba(0,255,255,.45);
}

.system-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5px 12px;
    font-size: 10px;
    line-height: 1.45;
}

.system-cell {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    white-space: nowrap;
}

.system-label {
    opacity: .45;
}

.system-value {
    color: #f2ffff;
}

/* グラフの現在点を操作できることを明示 */
#detail-chart {
    cursor: ew-resize;
    touch-action: none;
    outline: none;
}

/* ==========================================
   モバイル
   ========================================== */

@media (max-width: 1050px) {
    #system-monitor {
        right: 20px;
        top: 20px;
        width: 230px;
    }
}

@media (max-width: 950px) {
    #source-license {
        top: auto;
        bottom: 20px;
        left: 20px;
        width: min(360px, calc(100vw - 40px));
    }
}

@media (max-width: 700px) {

    #timeline {

        width: calc(100vw - 40px);

        bottom: 20px;

    }

    #legend {
        display: none;
    }

    #system-monitor {
        top: 180px;
        right: 12px;
        width: min(250px, calc(100vw - 24px));
    }

    #display-controls {
        top: 292px;
        right: 12px;
        width: min(250px, calc(100vw - 24px));
    }

    #prefecture-filter {
        top: 404px;
        right: 12px;
        width: min(250px, calc(100vw - 24px));
        max-height: calc(100vh - 424px);
    }

    #source-license {
        top: auto;
        left: 12px;
        bottom: 12px;
        width: calc(100vw - 24px);
        max-height: 90px;
    }

    #detail-panel {
        top: 516px;
        left: auto;
        right: 12px;
        transform: none;
        width: min(370px, calc(100vw - 24px));
        max-height: calc(100vh - 536px);
    }

}

</style>

<div id="boot-overlay">
    <div id="boot-panel">
        <div id="boot-title">JAPAN LAND PRICE // SYSTEM BOOT</div>
        <div id="boot-status">
            &gt; INITIALIZING VISUAL CORE...
        </div>
        <div id="boot-progress"><div id="boot-progress-bar"></div></div>
    </div>
</div>

<div id="system-monitor">
    <div id="system-monitor-title">
        <span>SYSTEM TELEMETRY</span>
        <span id="system-online">● ONLINE</span>
    </div>
    <div class="system-grid">
        <div class="system-cell"><span class="system-label">PITCH</span><span id="sys-pitch" class="system-value">45.0°</span></div>
        <div class="system-cell"><span class="system-label">BEARING</span><span id="sys-bearing" class="system-value">-15.0°</span></div>
        <div class="system-cell"><span class="system-label">ZOOM</span><span id="sys-zoom" class="system-value">3.70</span></div>
        <div class="system-cell"><span class="system-label">YEAR</span><span id="sys-year" class="system-value">2026</span></div>
        <div class="system-cell"><span class="system-label">LAT</span><span id="sys-lat" class="system-value">35.00</span></div>
        <div class="system-cell"><span class="system-label">LON</span><span id="sys-lon" class="system-value">137.00</span></div>
    </div>
</div>

<div id="map-title">

    <div id="map-title-main">
        JAPAN LAND PRICE
    </div>

    <div id="map-title-sub">
        1983～2026
    </div>

</div>


<div id="legend">

    <div id="legend-title">前年比</div>

    <div id="legend-bar"></div>

    <div id="legend-labels">

        <span>−30%以下</span>

        <span style="left:50%">0%</span>

        <span style="left:58.333%">+5%</span>

        <span>+30%以上</span>

    </div>

</div>


<div id="display-controls">
    <div id="display-controls-title">3D棒グラフの表示項目</div>
    <label class="display-control-row" for="height-metric">
        <span>棒グラフの高さ</span>
        <select id="height-metric">
            <option value="price" selected>地価</option>
            <option value="change">前年比</option>
        </select>
    </label>
    <label class="display-control-row" for="color-metric">
        <span>棒グラフの色</span>
        <select id="color-metric">
            <option value="change" selected>前年比</option>
            <option value="price">地価</option>
        </select>
    </label>
</div>

<details id="prefecture-filter">
    <summary>
        <span id="prefecture-filter-title">都道府県フィルター</span>
        <span id="prefecture-status">__PREFECTURE_STATUS__</span>
    </summary>
    <div id="prefecture-filter-content">
        <div class="prefecture-actions">
            <button class="prefecture-action" id="prefecture-all">全選択</button>
            <button class="prefecture-action" id="prefecture-none">全解除</button>
        </div>
        __PREFECTURE_CHECKBOXES__
    </div>
</details>

<details id="source-license">
    <summary>出典・ライセンス</summary>
    <div id="source-license-content">
        <p>
            「国土数値情報（地価公示）（令和8年）」（国土交通省）を加工して作成。
            地価・位置等のデータはCC BY 4.0です。
            <a href="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2026.html" target="_blank" rel="noopener">公式データ</a> ·
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a> ·
            <a href="https://nlftp.mlit.go.jp/ksj/other/agreement.html" target="_blank" rel="noopener">利用規約</a>
        </p>
        <p>
            都道府県境界: Natural Earth Admin 1 – States, Provinces (1:10m), version 5.1.1。
            日本の都道府県のみ抽出してGeoJSON化。
            Made with Natural Earth.
            <a href="https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/" target="_blank" rel="noopener">データ出典</a> ·
            <a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noopener">利用条件</a>
        </p>
        <p><a href="licenses/DATA_SOURCES.txt">データ加工内容</a> · <a href="licenses/THIRD_PARTY_NOTICES.txt">同梱ライブラリのライセンス</a></p>
    </div>
</details>

<div id="detail-panel">
    <button id="detail-close" type="button">×</button>
    <div id="detail-title"></div>
    <div id="detail-address"></div>
    <div id="detail-current"></div>
    <svg id="detail-chart" viewBox="0 0 310 150" preserveAspectRatio="none"></svg>
    <div id="detail-years"><span>1983</span><span>2026</span></div>
    <div id="detail-hint">グラフの現在点を左右にドラッグして年を変更できます　//　柱をクリックで地点切替</div>
</div>

<div id="timeline">

    <div id="timeline-top">

        <div id="timeline-year">
            2026
        </div>

        <button id="play-button">
            ▶ 再生
        </button>

    </div>

    <div id="timeline-slider-row">
        <button id="year-prev" class="year-step-button" type="button" aria-label="前年">&lt;-</button>
        <input
            id="year-slider"
            type="range"
            min="1983"
            max="2026"
            value="2026"
            step="1"
        >
        <button id="year-next" class="year-step-button" type="button" aria-label="翌年">-&gt;</button>
    </div>

    <div id="timeline-years">

        <span>1983</span>

        <span>2026</span>

    </div>

</div>
"""

custom_ui = custom_ui.replace(
    "__PREFECTURE_STATUS__",
    f"{len(prefecture_options)}\u90fd\u9053\u5e9c\u770c\u3059\u3079\u3066\u9078\u629e\u4e2d"
).replace(
    "__PREFECTURE_CHECKBOXES__",
    prefecture_checkboxes
)



html = html.replace(
    "<body>",
    "<body>" + custom_ui
)


# ==========================================
# タイムスライダー用JavaScript
# ==========================================

custom_script = f"""
<script>
let historyRecords = [];
const YEARS = {json.dumps(years)};

/* ==========================================
   カメラ可動範囲
   ========================================== */
if (typeof deckInstance !== "undefined" && deckInstance?.setProps) {{
    deckInstance.setProps({{
        controller: {{
            minPitch: 0,
            maxPitch: 60
        }}
    }});
}}

/* ==========================================
   色
   ========================================== */
function changeToColor(change) {{
    if (
        change === null ||
        change === undefined ||
        !Number.isFinite(change)
    ) {{
        return [255, 255, 255, 150];
    }}

    const stops = [
        {{ value: -30, color: [8, 48, 107] }},   // 濃い青
        {{ value: -10, color: [33, 113, 181] }}, // 青
        {{ value: 0, color: [255, 255, 255] }},  // 白
        {{ value: 5, color: [215, 48, 39] }},    // 赤
        {{ value: 30, color: [100, 20, 46] }}    // 赤寄りの濃い赤紫
    ];
    const value = Math.max(-30, Math.min(30, change));
    let lower = stops[0];
    let upper = stops[stops.length - 1];
    for (let i = 0; i < stops.length - 1; i++) {{
        if (value <= stops[i + 1].value) {{
            lower = stops[i];
            upper = stops[i + 1];
            break;
        }}
    }}
    const t = (value - lower.value) / (upper.value - lower.value);
    return [
        Math.round(lower.color[0] + (upper.color[0] - lower.color[0]) * t),
        Math.round(lower.color[1] + (upper.color[1] - lower.color[1]) * t),
        Math.round(lower.color[2] + (upper.color[2] - lower.color[2]) * t),
        150
    ];
}}

function priceToColor(price) {{
    if (!Number.isFinite(price) || price <= 0) {{
        return [255, 255, 255, 150];
    }}

    const minLog = Math.log(1000);
    const maxLog = Math.log(10000000);
    const t = Math.max(
        0,
        Math.min(1, (Math.log(price) - minLog) / (maxLog - minLog))
    );
    const color = t <= 0.5
        ? (() => {{
            const mix = t * 2;
            return [Math.round(255 * mix), Math.round(255 * mix), 255];
        }})()
        : (() => {{
            const redStart = 0.82;
            if (t <= redStart) {{
                const mix = (t - 0.5) / (redStart - 0.5);
                return [255, Math.round(255 * (1 - mix)), Math.round(255 * (1 - mix))];
            }}
            const mix = (t - redStart) / (1 - redStart);
            return [
                Math.round(255 - 145 * mix),
                0,
                0
            ];
        }})();
    return [
        color[0],
        color[1],
        color[2],
        150
    ];
}}

function updateMetricLegend() {{
    const legendTitle = document.getElementById("legend-title");
    const legendBar = document.getElementById("legend-bar");
    const legendLabels = document.getElementById("legend-labels");

    if (document.getElementById("color-metric").value === "price") {{
        legendTitle.textContent = "地価（対数目盛）";
        legendBar.style.background =
            "linear-gradient(to right, #0000ff 0%, #ffffff 50%, #ff0000 82%, #6e0000 100%)";
        legendLabels.innerHTML =
            '<span>¥1,000</span>' +
            '<span style="left:50%">¥100,000</span>' +
            '<span>¥10,000,000</span>';
    }} else {{
        legendTitle.textContent = "前年比";
        legendBar.style.background =
            "linear-gradient(to right, #08306b 0%, #2171b5 33.333%, #ffffff 50%, #d73027 58.333%, #64142e 100%)";
        legendLabels.innerHTML =
            '<span>−30%以下</span>' +
            '<span style="left:50%">0%</span>' +
            '<span style="left:58.333%">+5%</span>' +
            '<span>+30%以上</span>';
    }}
}}

/* ==========================================
   HTMLエスケープ
   ========================================== */
function escapeHtml(value) {{
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}}

/* ==========================================
   年別データ生成
   ========================================== */
function createYearData(year) {{
    const yearIndex = YEARS.indexOf(year);
    if (yearIndex < 0) {{
        return [];
    }}

    const data = [];

    for (const record of historyRecords) {{
        if (!selectedPrefectures.has(record.prefecture)) {{
            continue;
        }}

        const price = Number(record.prices[yearIndex]);
        const validPrice =
            Number.isFinite(price) && price > 0 ? price : 0;

        let change = null;

        if (
            validPrice > 0 &&
            year === 2026 &&
            Number.isFinite(record.official_change_2026)
        ) {{
            change = Number(record.official_change_2026);
        }} else if (validPrice > 0 && yearIndex > 0) {{
            const previousPrice = Number(record.prices[yearIndex - 1]);
            if (
                Number.isFinite(previousPrice) &&
                previousPrice > 0
            ) {{
                change =
                    ((validPrice - previousPrice) / previousPrice) * 100;
            }}
        }}

        const heightMetric =
            document.getElementById("height-metric").value;
        const colorMetric =
            document.getElementById("color-metric").value;

        const elevation = heightMetric === "price"
            ? (validPrice > 0 ? Math.pow(validPrice, 0.58) * 8 : 0)
            : (Number.isFinite(change) ? Math.abs(change) * 1000 : 0);

        const color = validPrice > 0
            ? (colorMetric === "price"
                ? priceToColor(validPrice)
                : changeToColor(change))
            : [255, 255, 255, 0];

        data.push({{
            id: record.lon + "_" + record.lat,
            prefecture: record.prefecture,
            year: year,
            lon: record.lon,
            lat: record.lat,
            city: record.city,
            address: record.address,
            use: record.use,
            price: validPrice,
            change: change,
            elevation: elevation,
            color: color
        }});
    }}

    return data;
}}

/* ==========================================
   デッキ描画
   ========================================== */
let baseColumnLayer = null;
let currentMapData = [];
let currentMapYear = null;

/* 都道府県境は固定レイヤー。年変更のたびに再生成しない。 */
const prefectureBoundaryLayer = new deck.GeoJsonLayer({{
    id: "prefecture-boundaries",
    data: "data/prefectures.geojson",
    filled: true,
    stroked: true,
    pickable: false,
    getFillColor: [5, 8, 15, 255],
    lineWidthMinPixels: 1.1,
    getLineColor: [54, 20, 66, 220],
    getLineWidth: 1.1,
    lineWidthUnits: "pixels",
    parameters: {{
        depthTest: false
    }}
}});

function updateMap(year, transitionDuration = 90) {{
    const data = createYearData(year);

    currentMapData = data;
    currentMapYear = year;

    renderLayers(transitionDuration);

    deckInstance.setProps({{
        controller: {{
            minPitch: 0,
            maxPitch: 60
        }},
        onViewStateChange: ({{ viewState }}) => {{
            currentViewState = viewState;
            deckInstance.setProps({{viewState}});
            updateSystemMonitor(viewState);
            syncSelectionBloomViewState(viewState);
        }},
        onClick: info => {{
            if (info && info.object) {{
                showDetail(info.object);
            }} else {{
                selectAllPrefectures();
            }}
        }},
        getTooltip: ({{
            object
        }}) => {{
            if (!object || object.price <= 0) {{
                return null;
            }}

            const changeText =
                object.change === null ||
                !Number.isFinite(object.change)
                    ? "—"
                    : (
                        object.change >= 0 ? "+" : ""
                    ) + object.change.toFixed(1) + "%";

            return {{
                html: `
                    <div style="
                        font-family: Arial, sans-serif;
                        padding: 5px;
                        min-width: 250px;
                    ">
                        <div style="
                            font-size: 17px;
                            font-weight: bold;
                            margin-bottom: 4px;
                        ">
                            ${{escapeHtml(object.city)}}
                        </div>
                        <div style="
                            font-size: 13px;
                            opacity: 0.9;
                            line-height: 1.5;
                        ">
                            ${{escapeHtml(object.address)}}
                        </div>
                        <hr style="
                            border: 0;
                            border-top: 1px solid rgba(255,255,255,0.25);
                            margin: 8px 0;
                        ">
                        <div style="
                            font-size: 14px;
                            line-height: 1.9;
                        ">
                            <b>年度</b>　${{year}}<br>
                            <b>地価</b>　${{object.price.toLocaleString()}} 円/m²<br>
                            <b>前年比</b>　${{changeText}}<br>
                            <b>用途</b>　${{escapeHtml(object.use)}}
                        </div>
                    </div>
                `,
                style: {{
                    backgroundColor: "rgba(5, 8, 15, 0.94)",
                    color: "white",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "8px",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.5)"
                }}
            }};
        }}
    }});
}}

/* ==========================================
   選択地点だけのポストプロセスBloom

   選択ColumnLayerだけを専用Deckの透明framebufferへ描画する。
   bright-pass -> separable Gaussian blur (horizontal / vertical) -> glow出力を
   独立した透明canvasへ加算合成するため、地図レイヤーには効果がかからない。
   ========================================== */
const selectionBloomShader = {{
    props: {{}},
    uniforms: {{}},
    name: "selectionBloom",
    fs: `
uniform selectionBloomUniforms {{
    float threshold;
    float softKnee;
    float radius;
    float intensity;
    int passIndex;
    vec2 direction;
}} selectionBloom;

vec4 selectionBloom_sampleColor(sampler2D source, vec2 texSize, vec2 texCoord) {{
    vec4 sourceColor = texture(source, texCoord);

    // Pass 0: bright-pass extraction. Keep premultiplied color and alpha together.
    if (selectionBloom.passIndex == 0) {{
        float brightness = max(sourceColor.r, max(sourceColor.g, sourceColor.b));
        float bright = smoothstep(
            selectionBloom.threshold - selectionBloom.softKnee,
            selectionBloom.threshold + selectionBloom.softKnee,
            brightness
        );
        return sourceColor * bright;
    }}

    // Pass 1: one axis of a separable 9-tap Gaussian blur.
    if (selectionBloom.passIndex == 1) {{
        const float weights[5] = float[5](
            0.227027,
            0.1945946,
            0.1216216,
            0.054054,
            0.016216
        );
        vec2 stepUV = selectionBloom.direction * selectionBloom.radius / texSize;
        vec4 blurred = sourceColor * weights[0];
        for (int i = 1; i <= 4; i++) {{
            vec2 offset = stepUV * float(i);
            blurred += texture(source, texCoord - offset) * weights[i];
            blurred += texture(source, texCoord + offset) * weights[i];
        }}
        return blurred;
    }}

    // Pass 2: prepare the blurred bright image for additive canvas compositing.
    float glowAlpha = clamp(sourceColor.a * selectionBloom.intensity, 0.0, 1.0);
    return vec4(sourceColor.rgb * selectionBloom.intensity, glowAlpha);
}}
`,
    uniformTypes: {{
        threshold: "f32",
        softKnee: "f32",
        radius: "f32",
        intensity: "f32",
        passIndex: "i32",
        direction: "vec2<f32>"
    }},
    propTypes: {{
        threshold: {{value: 0.42, min: 0.0, max: 1.0}},
        softKnee: {{value: 0.12, min: 0.0, max: 1.0}},
        radius: {{value: 4.0, min: 0.0, max: 32.0}},
        intensity: {{value: 1.45, min: 0.0, max: 4.0}},
        passIndex: {{value: 0, private: true}},
        direction: {{value: [1, 0], private: true}}
    }},
    passes: [
        {{sampler: true, uniforms: {{passIndex: 0}}}},
        {{sampler: true, uniforms: {{passIndex: 1, direction: [1, 0]}}}},
        {{sampler: true, uniforms: {{passIndex: 1, direction: [0, 1]}}}},
        {{sampler: true, uniforms: {{passIndex: 2}}}}
    ]
}};

let selectionBloomDeck = null;
let selectionBloomEffect = null;

if (
    typeof deck !== "undefined" &&
    typeof deck.Deck === "function" &&
    typeof deck.MapView === "function" &&
    typeof deck.PostProcessEffect === "function"
) {{
    try {{
        const supportsPlusLighter =
            typeof CSS !== "undefined" &&
            typeof CSS.supports === "function" &&
            CSS.supports("mix-blend-mode", "plus-lighter");
        const bloomContainer = document.getElementById("deck-container");
        const selectionBloomCanvas = document.createElement("canvas");
        selectionBloomCanvas.id = "selection-bloom-canvas";
        selectionBloomCanvas.style.mixBlendMode = supportsPlusLighter ? "plus-lighter" : "screen";
        bloomContainer.appendChild(selectionBloomCanvas);

        const initialBloomViewState = currentViewState || {{
            latitude: {view_state.latitude},
            longitude: {view_state.longitude},
            zoom: 6.16,
            pitch: 53.5,
            bearing: -14.1
        }};

        selectionBloomEffect = new deck.PostProcessEffect(selectionBloomShader, {{
            threshold: 0.10,
            softKnee: 0.12,
            radius: 5.5 * Math.min(window.devicePixelRatio || 1, 2),
            intensity: 1.8
        }});

        selectionBloomDeck = new deck.Deck({{
            canvas: selectionBloomCanvas,
            views: [new deck.MapView({{id: "map-view", controller: false}})],
            initialViewState: initialBloomViewState,
            controller: false,
            clearColor: [0, 0, 0, 0],
            layers: [],
            effects: []
        }});
    }} catch (error) {{
        console.error("選択柱Bloomの初期化に失敗しました。通常表示を続けます。", error);
        selectionBloomDeck = null;
        selectionBloomEffect = null;
    }}
}}

function syncSelectionBloomViewState(viewState) {{
    if (!selectionBloomDeck) return;
    const state = viewState || currentViewState;
    if (!state) return;

    try {{
        selectionBloomDeck.setProps({{viewState: state}});
    }} catch (error) {{
        console.error("選択柱Bloomカメラの同期に失敗しました。", error);
    }}
}}

function updateSelectionBloom(selected, transitionDuration = 0) {{
    const hasSelectedColumn = selected && selected.elevation > 0;
    if (!selectionBloomDeck) return;
    const layers = hasSelectedColumn
        ? [new deck.ColumnLayer({{
            id: "selected-column-bloom-source",
            data: [selected],
            getPosition: d => [d.lon, d.lat],
            getElevation: d => d.elevation,
            elevationScale: 0.7,
            radius: 90,
            getFillColor: d => [d.color[0], d.color[1], d.color[2], 255],
            material: false,
            pickable: false,
            autoHighlight: false,
            transitions: {{
                getElevation: {{
                    duration: transitionDuration,
                    easing: t => t * t * (3 - 2 * t)
                }},
                getFillColor: {{
                    duration: transitionDuration,
                    easing: t => t * t * (3 - 2 * t)
                }}
            }}
        }})]
        : [];

    try {{
        selectionBloomDeck.setProps({{
            layers,
            effects: hasSelectedColumn ? [selectionBloomEffect] : []
        }});
    }} catch (error) {{
        console.error("選択柱Bloomの更新に失敗しました。", error);
    }}
}}

// 通常レイヤーは常に全柱を保持し、選択中だけ
// 「非選択柱を暗く・少し透明に」した状態で表示する。
// これにより選択解除や年変更でレイヤー自体が消えることを防ぎ、
// 年スライダーでも通常時と同じトランジションを維持する。
function renderLayers(transitionDuration = 0) {{
    const selected = selectedRecordId
        ? currentMapData.find(d => d.id === selectedRecordId)
        : null;

    const dimmedColor = color => [
        Math.round(color[0] * 0.72),
        Math.round(color[1] * 0.72),
        Math.round(color[2] * 0.72),
        90
    ];

    const baseColors = d => {{
        if (selected && d.id !== selected.id) {{
            return dimmedColor(d.color);
        }}

        return [
            d.color[0],
            d.color[1],
            d.color[2],
            selected && d.id === selected.id ? 255 : d.color[3]
        ];
    }};

    // 毎回「全柱」をベースにする。選択状態だけ色計算を変えるため、
    // 空白クリックで通常表示へ戻すときも柱が消えない。
    baseColumnLayer = new deck.ColumnLayer({{
        id: "land-price-columns",
        data: currentMapData,
        getPosition: d => [d.lon, d.lat],
        getElevation: d => d.elevation,
        elevationScale: 0.7,
        radius: 90,
        getFillColor: baseColors,
        pickable: true,
        autoHighlight: true,
        transitions: {{
            getElevation: {{
                duration: transitionDuration,
                easing: t => t * t * (3 - 2 * t)
            }},
            getFillColor: {{
                duration: transitionDuration,
                easing: t => t * t * (3 - 2 * t)
            }}
        }}
    }});

    const layers = [prefectureBoundaryLayer, baseColumnLayer];

    updateSelectionBloom(selected, transitionDuration);

    deckInstance.setProps({{
        layers: layers
    }});
}}



/* ==========================================
   地点詳細グラフ
   ========================================== */
const detailPanel = document.getElementById("detail-panel");
const prefectureFilter = document.getElementById("prefecture-filter");
const detailClose = document.getElementById("detail-close");
const detailTitle = document.getElementById("detail-title");
const detailAddress = document.getElementById("detail-address");
const detailCurrent = document.getElementById("detail-current");
const detailChart = document.getElementById("detail-chart");
const sourceLicensePanel = document.getElementById("source-license");
const legendPanel = document.getElementById("legend");

function updateSourceLegendSpacing() {{
    const sourceHeight = sourceLicensePanel.getBoundingClientRect().height;
    legendPanel.style.bottom = Math.max(82, Math.ceil(sourceHeight + 32)) + "px";
}}

sourceLicensePanel.addEventListener("toggle", updateSourceLegendSpacing);
window.addEventListener("resize", updateSourceLegendSpacing);
updateSourceLegendSpacing();

let selectedRecordId = null;
let selectedRecord = null;
let selectedPrefectures = new Set(
    Array.from(
        document.querySelectorAll(".prefecture-check input:checked"),
        input => input.value
    )
);

function getSelectedRecord() {{
    if (!selectedRecordId) return null;
    return historyRecords.find(
        r => r.lon + "_" + r.lat === selectedRecordId
    ) || null;
}}

function renderDetailChart(record, currentYear) {{
    if (!record) return;

    const prices = record.prices.map(Number);
    const valid = prices.filter(
        v => Number.isFinite(v) && v > 0
    );

    if (!valid.length) {{
        detailChart.innerHTML = "";
        return;
    }}

    const min = Math.min(...valid);
    const max = Math.max(...valid);
    const range = Math.max(max - min, 1);

    const left = 10;
    const right = 300;
    const top = 12;
    const bottom = 132;

    /*
       折れ線：
       欠損年があっても、その区間だけ線を切る。
    */
    let path = "";
    let first = true;

    prices.forEach((price, i) => {{
        if (!Number.isFinite(price) || price <= 0) {{
            first = true;
            return;
        }}

        const x =
            left +
            (i / (YEARS.length - 1)) * (right - left);

        const y =
            bottom -
            ((price - min) / range) * (bottom - top);

        path +=
            (first ? "M" : "L") +
            x.toFixed(1) +
            " " +
            y.toFixed(1) +
            " ";

        first = false;
    }});

    const currentIndex = YEARS.indexOf(currentYear);
    const currentPrice =
        currentIndex >= 0 ? prices[currentIndex] : NaN;

    let currentX = left;
    let marker = "";
    let currentY = bottom;

    if (currentIndex >= 0) {{
        currentX =
            left +
            (currentIndex / (YEARS.length - 1)) *
            (right - left);

        /* 現在年の位置を示す縦線 */
        marker += `
            <line
                x1="${{currentX.toFixed(1)}}"
                y1="${{top}}"
                x2="${{currentX.toFixed(1)}}"
                y2="${{bottom}}"
                stroke="rgb(0,255,255)"
                stroke-width="1.5"
                stroke-dasharray="4 3"
                opacity="0.85"
                pointer-events="none"
            />
        `;

        if (
            Number.isFinite(currentPrice) &&
            currentPrice > 0
        ) {{
            currentY =
                bottom -
                ((currentPrice - min) / range) *
                (bottom - top);

            /* 実際にドラッグする現在点 */
            marker += `
                <circle
                    cx="${{currentX.toFixed(1)}}"
                    cy="${{currentY.toFixed(1)}}"
                    r="6"
                    fill="white"
                    stroke="rgb(0,255,255)"
                    stroke-width="2.5"
                    class="detail-current-point"
                    pointer-events="none"
                />
                <circle
                    cx="${{currentX.toFixed(1)}}"
                    cy="${{currentY.toFixed(1)}}"
                    r="12"
                    fill="transparent"
                    stroke="rgba(0,255,255,.24)"
                    stroke-width="1"
                    class="detail-current-point-hit"
                    pointer-events="none"
                />
            `;
        }} else {{
            marker += `
                <circle
                    cx="${{currentX.toFixed(1)}}"
                    cy="${{(top + bottom) / 2}}"
                    r="6"
                    fill="rgba(0,255,255,.85)"
                    stroke="white"
                    stroke-width="1.5"
                    pointer-events="none"
                />
            `;
        }}
    }}

    detailChart.innerHTML = `
        <line
            x1="${{left}}"
            y1="${{bottom}}"
            x2="${{right}}"
            y2="${{bottom}}"
            stroke="rgba(255,255,255,.15)"
        />

        <line
            x1="${{left}}"
            y1="${{top}}"
            x2="${{left}}"
            y2="${{bottom}}"
            stroke="rgba(255,255,255,.08)"
        />

        <path
            d="${{path}}"
            fill="none"
            stroke="white"
            stroke-width="2"
            stroke-linejoin="round"
            stroke-linecap="round"
            pointer-events="none"
        />

        ${{marker}}

        <!-- グラフ全体を左右操作領域として使う -->
        <rect
            x="${{left - 6}}"
            y="${{top - 6}}"
            width="${{(right - left) + 12}}"
            height="${{(bottom - top) + 12}}"
            fill="transparent"
            pointer-events="all"
            class="detail-chart-hit-area"
        />
    `;

}}

function updateDetailForYear(year) {{
    if (!selectedRecord) {{
        return;
    }}

    const index = YEARS.indexOf(year);
    const price =
        index >= 0
            ? Number(selectedRecord.prices[index])
            : 0;

    detailCurrent.innerHTML =
        "<b>" + year + "年</b>　" +
        (
            Number.isFinite(price) && price > 0
                ? price.toLocaleString() + " 円/m²"
                : "データなし"
        ) +
        "<br>" +
        "<span style='opacity:.65'>" +
        escapeHtml(selectedRecord.use) +
        "</span>";

    renderDetailChart(selectedRecord, year);
}}

function positionDetailPanel() {{
    const compact = window.innerWidth <= 700;
    const filterHeightLimit = Math.max(
        110,
        window.innerHeight * (compact ? 0.20 : 0.28)
    );
    prefectureFilter.style.maxHeight = Math.round(filterHeightLimit) + "px";

    const filterBottom = prefectureFilter.getBoundingClientRect().bottom;
    const panelTop = filterBottom + 10;
    detailPanel.style.top = Math.round(panelTop) + "px";
    detailPanel.style.left = "auto";
    detailPanel.style.right = compact ? "12px" : "20px";
    detailPanel.style.transform = "none";
    detailPanel.style.maxHeight = Math.max(
        100,
        window.innerHeight - panelTop - 20
    ) + "px";
}}

function clearSelection() {{
    detailPanel.style.display = "none";
    detailPanel.style.top = "";
    detailPanel.style.right = "";
    detailPanel.style.maxHeight = "";
    prefectureFilter.style.maxHeight = "";
    selectedRecordId = null;
    selectedRecord = null;
    renderLayers(0);
}}

function showDetail(object) {{
    if (!object) return;

    selectedRecordId = object.id;
    selectedRecord = getSelectedRecord();

    if (!selectedRecord) {{
        return;
    }}

    detailTitle.textContent =
        selectedRecord.city +
        "（" +
        selectedRecord.prefecture +
        "）";

    detailAddress.textContent =
        selectedRecord.address;

    detailPanel.style.display = "block";
    positionDetailPanel();

    // 選択変更は即時反映する。
    renderLayers(0);

    updateDetailForYear(object.year);
}}

detailClose.addEventListener("click", () => {{
    clearSelection();
}});

/* ==========================================
   都道府県フィルター
   ========================================== */
const prefectureChecks = Array.from(
    document.querySelectorAll(".prefecture-check input")
);

const prefectureStatus =
    document.getElementById("prefecture-status");

prefectureFilter.addEventListener("toggle", () => {{
    if (detailPanel.style.display !== "none") {{
        requestAnimationFrame(positionDetailPanel);
    }}
}});
window.addEventListener("resize", () => {{
    if (detailPanel.style.display !== "none") {{
        positionDetailPanel();
    }}
}});

function refreshPrefectureFilter() {{
    selectedPrefectures = new Set(
        prefectureChecks
            .filter(input => input.checked)
            .map(input => input.value)
    );

    updateRegionToggleState();

    const count = selectedPrefectures.size;

    prefectureStatus.textContent =
        count === prefectureChecks.length
            ? prefectureChecks.length + "\u90fd\u9053\u5e9c\u770c\u3059\u3079\u3066\u9078\u629e\u4e2d"
            : count === 0
                ? "\u9078\u629e\u306a\u3057"
                : count + "\u90fd\u9053\u5e9c\u770c\u3092\u9078\u629e\u4e2d";

    const year = Number(slider.value);
    clearSelection();
    updateMap(year, 90);
}}

function updateRegionToggleState() {{
    for (const region of document.querySelectorAll(".prefecture-region")) {{
        const toggle = region.querySelector(".prefecture-region-toggle");
        const children = Array.from(
            region.querySelectorAll(".prefecture-check input")
        );
        const checkedCount = children.filter(input => input.checked).length;

        toggle.checked = children.length > 0 && checkedCount === children.length;
        toggle.indeterminate = checkedCount > 0 && checkedCount < children.length;
    }}
}}

for (const input of prefectureChecks) {{
    input.addEventListener(
        "change",
        refreshPrefectureFilter
    );
}}

for (const region of document.querySelectorAll(".prefecture-region")) {{
    const toggle = region.querySelector(".prefecture-region-toggle");
    toggle.addEventListener("change", () => {{
        for (const input of region.querySelectorAll(".prefecture-check input")) {{
            input.checked = toggle.checked;
        }}
        refreshPrefectureFilter();
    }});
}}

for (const select of [
    document.getElementById("height-metric"),
    document.getElementById("color-metric")
]) {{
    select.addEventListener("change", () => {{
        updateMetricLegend();
        updateMap(Number(slider.value), 90);
    }});
}}

function selectAllPrefectures() {{
    for (const input of prefectureChecks) {{
        input.checked = true;
    }}
    refreshPrefectureFilter();
}}

document.getElementById("prefecture-all")
    .addEventListener("click", selectAllPrefectures);

document.getElementById("prefecture-none")
    .addEventListener("click", () => {{
        for (const input of prefectureChecks) {{
            input.checked = false;
        }}
        refreshPrefectureFilter();
    }});

/* ==========================================
   年変更：スライダーと詳細グラフで共通利用
   ========================================== */
const slider =
    document.getElementById("year-slider");

const yearLabel =
    document.getElementById("timeline-year");

const playButton =
    document.getElementById("play-button");

/* 再生状態 */
let playing = false;
let timer = null;

function setYear(year, transitionDuration = 90, stopPlayback = true) {{
    year = Math.max(1983, Math.min(2026, Math.round(Number(year))));

    if (stopPlayback && playing) {{
        playing = false;
        clearInterval(timer);
        playButton.textContent = "▶ 再生";
    }}

    slider.value = String(year);
    yearLabel.textContent = year;
    updateMap(year, transitionDuration);

    if (selectedRecordId) {{
        const selected =
            createYearData(year).find(
                d => d.id === selectedRecordId
            );

        if (selected) {{
            updateDetailForYear(year);
        }}
    }}

    const sysYear = document.getElementById("sys-year");
    if (sysYear) sysYear.textContent = year;
}}

slider.addEventListener("input", function() {{
    setYear(Number(this.value), 90, true);
}});

const yearPrevButton = document.getElementById("year-prev");
const yearNextButton = document.getElementById("year-next");

yearPrevButton.addEventListener("click", () => {{
    setYear(Number(slider.value) - 1, 90, true);
}});

yearNextButton.addEventListener("click", () => {{
    setYear(Number(slider.value) + 1, 90, true);
}});

/* ==========================================
   詳細グラフの左右ドラッグ／クリック操作
   ========================================== */
let chartDragging = false;
let lastChartYear = null;

function yearFromChartClientX(clientX) {{
    const rect = detailChart.getBoundingClientRect();
    if (!rect.width) return null;

    /* SVG viewBox の X=4〜306 を実画面へ対応させる */
    const leftPx = rect.left + (4 / 310) * rect.width;
    const rightPx = rect.left + (306 / 310) * rect.width;
    const ratio =
        rightPx <= leftPx
            ? 0
            : Math.max(0, Math.min(1, (clientX - leftPx) / (rightPx - leftPx)));

    const index = Math.round(ratio * (YEARS.length - 1));
    return YEARS[index];
}}

function moveChartYear(clientX) {{
    if (!selectedRecord) return;

    const year = yearFromChartClientX(clientX);
    if (year === null || year === lastChartYear) return;

    lastChartYear = year;
    setYear(year, 50, true);
}}

detailChart.addEventListener("pointerdown", event => {{
    if (detailPanel.style.display === "none") return;

    chartDragging = true;
    lastChartYear = null;
    detailChart.setPointerCapture?.(event.pointerId);
    moveChartYear(event.clientX);
    event.preventDefault();
}});

detailChart.addEventListener("pointermove", event => {{
    if (!chartDragging) return;
    moveChartYear(event.clientX);
    event.preventDefault();
}});

function finishChartDrag(event) {{
    if (!chartDragging) return;
    chartDragging = false;
    lastChartYear = null;
    try {{
        detailChart.releasePointerCapture?.(event.pointerId);
    }} catch (e) {{
        /* 既に capture が解除されている場合は無視 */
    }}
}}

detailChart.addEventListener("pointerup", finishChartDrag);
detailChart.addEventListener("pointercancel", finishChartDrag);

/* ==========================================
   再生
   ========================================== */
playButton.addEventListener(
    "click",
    function() {{
        if (playing) {{
            playing = false;
            clearInterval(timer);
            playButton.textContent = "▶ 再生";
            return;
        }}

        playing = true;
        playButton.textContent = "■ 停止";

        if (Number(slider.value) >= 2026) {{
            slider.value = 1983;
        }}

        timer = setInterval(
            function() {{
                let year = Number(slider.value) + 1;

                if (year > 2026) {{
                    clearInterval(timer);
                    playing = false;
                    playButton.textContent = "▶ 再生";
                    return;
                }}

                setYear(year, 700, false);
            }},
            760
        );
    }}
);

/* ==========================================
   リアルタイムシステム情報
   ========================================== */
const sysPitch = document.getElementById("sys-pitch");
const sysBearing = document.getElementById("sys-bearing");
const sysZoom = document.getElementById("sys-zoom");
const sysLat = document.getElementById("sys-lat");
const sysLon = document.getElementById("sys-lon");
const sysYear = document.getElementById("sys-year");

function updateSystemMonitor(state) {{
    if (!state) return;

    if (Number.isFinite(state.pitch)) {{
        sysPitch.textContent = Number(state.pitch).toFixed(1) + "°";
    }}
    if (Number.isFinite(state.bearing)) {{
        sysBearing.textContent = Number(state.bearing).toFixed(1) + "°";
    }}
    if (Number.isFinite(state.zoom)) {{
        sysZoom.textContent = Number(state.zoom).toFixed(2);
    }}
    if (Number.isFinite(state.latitude)) {{
        sysLat.textContent = Number(state.latitude).toFixed(2);
    }}
    if (Number.isFinite(state.longitude)) {{
        sysLon.textContent = Number(state.longitude).toFixed(2);
    }}
    if (Number.isFinite(currentMapYear)) {{
        sysYear.textContent = String(currentMapYear);
    }}
}}

function refreshSystemMonitor() {{
    try {{
        const state = currentViewState || null;
        updateSystemMonitor(state);
    }} catch (e) {{
        // 初期化直後などで viewState が未取得でも継続する。
    }}
    requestAnimationFrame(refreshSystemMonitor);
}}

refreshSystemMonitor();

/* ==========================================
   起動アニメーション
   ========================================== */
const bootOverlay = document.getElementById("boot-overlay");
const bootStatus = document.getElementById("boot-status");
const bootProgressBar = document.getElementById("boot-progress-bar");

const bootMessages = [
    "&gt; INITIALIZING VISUAL CORE...<br>&gt; LOADING LAND PRICE MATRIX...",
    "&gt; LINKING PREFECTURE BOUNDARIES...<br>&gt; CALIBRATING CAMERA TELEMETRY...",
    "&gt; MOUNTING 3D COLUMN ARRAY...<br>&gt; SYNCHRONIZING YEAR INDEX...",
    "&gt; SYSTEM CHECK COMPLETE.<br>&gt; ACCESSING JAPAN LAND PRICE GRID..."
];

bootMessages.forEach((message, index) => {{
    setTimeout(() => {{
        bootStatus.innerHTML = message;
        bootProgressBar.style.width = ((index + 1) / bootMessages.length * 100) + "%";
    }}, 160 + index * 270);
}});

setTimeout(() => {{
    bootOverlay.classList.add("boot-complete");
    setTimeout(() => bootOverlay.remove(), 550);
}}, 1450);
/* ==========================================
   ローカルデータ読込後に初期表示
   ========================================== */
updateMetricLegend();
fetch("data/land_price.json")
    .then(response => {{
        if (!response.ok) {{
            throw new Error(`地価データを読み込めません (${{response.status}})`);
        }}
        return response.json();
    }})
    .then(records => {{
        historyRecords = records;
        updateMap(2026, 0);
    }})
    .catch(error => {{
        console.error("ローカル地価データの読み込みに失敗しました。", error);
        const status = document.getElementById("boot-status");
        if (status) status.textContent = "地価データを読み込めません。サイトをHTTP(S)で開き、data/land_price.jsonを確認してください。";
    }});
</script>
"""


html = html.replace(
    "</html>",
    custom_script + "</html>"
)


# ==========================================
# 保存
# ==========================================

OUTPUT_HTML.write_text(
    html,
    encoding="utf-8"
)


# ==========================================
# 完了
# ==========================================

print("==========================================")
print(" 完了！")
print("==========================================")
print()

print(f"地点数: {len(gdf):,}")
print(f"都道府県境: {PREFECTURE_GEOJSON_PATH}")

print()

print("タイムスライダー:")
print("1983 ～ 2026")

print()

print("出力ファイル:")
print(OUTPUT_HTML)
print(LAND_PRICE_JSON_PATH)
print(DECKGL_BUNDLE_PATH)

print()
