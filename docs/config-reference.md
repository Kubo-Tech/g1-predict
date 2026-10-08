# configs/{レース名}/ リファレンス

レース1本分の「傾向表に何を出すか」「分析表にどの列を並べるか」を定義する設定ファイル群。Python を触らずにこれらのファイルだけで表現できることを優先している。

- レースごとにディレクトリを作り、用途ごとのファイルを置く。

```
configs/{レース名}/
├── trends.yml   # gen_trend が使う項目名と開催条件（省略可。無ければ見出しだけの記事になる）
└── table.yml    # gen_table が使う（gen_table を使うなら必須）
```

- ディレクトリ名は **DB の競走名本題（`kyosomei_hondai`）と完全一致**させる（例: `configs/宝塚記念/`）。スクリプトはレースコードから引いたレース名でディレクトリを探す。
- ただし `g1_predict/modules/utils/race_name.py` の `RACE_NAME_ABBREVIATIONS` に登録されているレースは、競走名本題ではなく対応表の略称をディレクトリ名にする（例: 競走名本題「スプリンターズステークス」→ `configs/スプリンターズS/`）。この略称は `templates/points/{レース名}.md` の参照、`public/` の出力先ディレクトリ・ファイル名、記事タイトルにも共通して使われる。DB照合には使えないため、競走名本題での照合が必要な処理には対応表変換前の値を渡す。
- 現在ある設定: `東京優駿/` / `安田記念/` / `宝塚記念/` / `スプリンターズS/`。新しいレースは近いものをコピーして作るのが早い。
- 各ファイルの最上位には `trends` / `table` のようなキーを書かず、中身（カテゴリ名やシート名）を直接書く。
- 傾向表の項目の定義は、レース共通の `configs/trends/` に置く（[trends.yml](#trendsyml--傾向分析記事の表)）。

---

# trends.yml — 傾向分析記事の表

傾向表の項目の定義は、カテゴリごとの共有ファイル `configs/trends/*.yml` に置く。各レースの `configs/{レース名}/trends.yml` は、使う項目の名前を並べ、必要な項目にだけ開催条件を注入する。

```
configs/
├── trends/                  # 項目の共有定義（カテゴリごとに1ファイル）
│   ├── 基本項目.yml
│   ├── 前走.yml
│   ├── 実績.yml
│   ├── 世代戦.yml
│   ├── 調教.yml
│   ├── 同年前年レース実績.yml
│   └── 馬以外の属性.yml
└── {レース名}/trends.yml     # 使う項目の名前と開催条件の注入
```

## 共有定義 `configs/trends/{カテゴリ}.yml`

```yaml
name: 基本項目                                   # "## 基本項目" になるカテゴリ名
description: 同じG1レースの過去{years}年における傾向  # カテゴリの説明文。{years} は集計した年数
items:
  人気:                                          # 項目名。"### 人気" と表の1列目見出しになる
    source: {type: popularity}                   # 何を集計するか
    rows: {...}                                  # どう行に分けるか
  枠順:
    conditionable: true                          # 開催条件を注入できる項目
    source: {type: gate_number}
    rows: {...}
```

- 項目に書けるキーは `source` / `rows` / `display_map` / `conditionable` / `note` / `hide_if_empty` で、`rows` は必須。
- `conditionable: true` の項目だけが、レースの `trends.yml` から開催条件を注入できる。
- `note` を書くと、表の直下にその文字列を出す。
- `hide_if_empty: true` を書くと、集計対象に該当馬が1頭もいない場合は表を見出しごと出さない（前走{クラス}着順で使う）。
- ファイル名はカテゴリ名から `/` を除いたもの（`同年/前年レース実績` → `同年前年レース実績.yml`）にする。
- 項目の定義にある `{race_name}`・`{kyori}` は、対象レースの競走名本題・距離（m）に置き換えて使う（例: 父実績の `父{race_name}勝ち`）。

## 各レースの `configs/{レース名}/trends.yml`

```yaml
基本項目:                                  # 共有定義のカテゴリ名
  - 人気                                   # 項目名だけを書くと、共有定義のまま使う
  - 枠順:                                  # 開催条件を注入する項目
      condition: {keibajo_codes: ["09"], kaisai_nichime: [4], babajotai_codes: ["1"]}
  - 所属
前走:
  - 前走レース
```

- カテゴリ名をキーに、項目名を並べる。記事にはこのファイルの並び順でカテゴリと項目を出力する。
- 共有定義に無いカテゴリ名・項目名、`conditionable` でない項目への条件の注入、条件の未知のキーは `ValueError` になる。
- 各カテゴリの末尾には空の `### 比較表` が自動で挿入される（手書き用のプレースホルダ）。

## 集計対象と集計年数

集計対象は既定で「対象レースと同じ特別競走番号・同一競馬場・同一距離・同一芝ダの過去10年」。

G1（グレードコード `A`）になったのが過去10年以内のレースは、G1として行われた最初の年から前年までを集計する。G1になった年は、競馬場・距離・芝ダによらず特別競走番号だけで判定し、G1でない開催がある場合は最後のG1でない開催より後の最初のG1の年とする。G1になった後に行われなかった年や別の競馬場で行われた年があっても、集計期間は縮めない。たとえば大阪杯はG1になった2017年から集計し、2026年の記事では9年分になる。

記事タイトルの直後に、集計対象を次の形式で注記する。回数は条件に合うレースの数で、別の競馬場で行われた年などは含まれないため年数より少なくなることがある。

```
※集計対象は、過去10年（2016〜2025年）に中山芝1200mで行われたスプリンターズS（10回）。
※集計対象は、G1になった2017年から前年まで（2017〜2025年）に阪神芝2000mで行われた大阪杯（9回）。
```

カテゴリの説明文の `{years}` には、実際に集計した年数が入る。

## condition — 開催条件の注入

```yaml
condition:
  keibajo_codes: ["09"]      # 競馬場コード
  course_kubun: B            # コース区分（A〜E）
  course_days: [4]           # そのコース区分になってから何日目か
  kaisai_nichime: [4]        # 開催日目（「3回阪神8日目」の8）
  babajotai_codes: ["1"]     # 馬場状態（1=良 2=稍重 3=重 4=不良）
```

注入した条件は、既定の集計対象をさらに絞り込む。指定できるキーはこの5つだけで、少なくとも1つ指定する。

- `keibajo_codes` は既定の集計対象の競馬場に含まれる値だけを指定できる。
- `course_days` は、同じ競馬場・同じ年の開催日を日付順に並べ、コース区分が前の開催日から変わった日、または前の開催日から14日以上空いた日を1日目として数える。開催日目とは異なり、たとえば宝塚記念は2014〜2019年が3回阪神8日目だが、5日目からBコースに替わるためBコース4日目になる。
- `course_kubun`・`course_days` は、条件に合う過去の開催がひとつも無いと `ValueError` になる。

条件を注入した項目は、表の直下に開催条件の注記が出る。

```
※阪神・4日目・Bコース7・8日目・良のみ
```

宝塚記念のように開催場・開催日目が年によって変わるレースで、展開に関わる項目は阪神4日目の良馬場のみ、それ以外は阪神開催すべてのように、項目ごとに集計範囲を変えるための仕組み。

## rows — 行の作り方

### `type: fixed`

`items` で行を固定する。

```yaml
rows:
  type: fixed
  hide_empty: true          # 任意。頭数が0の行を出さない
  items:
    - {label: "1人気", op: "==", value: 1}
    - {label: "4-6人気", op: "in", value: [4, 5, 6]}
    - {label: "2-5番手", op: between, value: [2, 5]}
    - {label: "10人気以下", op: ">=", value: 10}
```

**使える `op` は `source.type` によって異なる**（集計を DB 側でやるか Python 側でやるかが違うため）。

| `source.type` のグループ | 使える `op` |
| --- | --- |
| `race_col` 系 / `prev_race_grade` / `prev_race_finish` / `prev_race_finish_by_grade` / `tokubetsu_race_finish` | `==` `!=` `>=` `<=` `>` `<` `in` `not_in` `between` |
| `past_race_top_n_count` / `career_count` / `prev_race_name` / `debut_venue` / `jockey_continuity` / `prev_race_col` | `==` `>=` `<=` `>` `<` `between`（`in` は `ValueError`。`!=` `not_in` は無視され、その行は常に `0-0-0-0` になる） |
| `chokyo_match_days` | `any_match` `none_match` `empty`（それ以外の `op` は `ValueError`。`value` は不要） |

`value` は数値・文字列のどちらも指定できる。数値として解釈できる場合は数値比較、できない場合は文字列比較になる。`between` の `value` は `[下限, 上限]` で、両端を含む。

上段は Python 側で集計結果をグループ化するため演算子の自由度が高く、下段は DB 側（`analytics` の `GroupBy(kind="fixed")`）に行定義を渡すため制約がある。`prev_race_grade` などは内部で `prev_race_col` へ変換されるが、集計は Python 側で行うので上段の扱いになる。

### `type: dynamic`

集計結果から自動で行を作る。3着内数（1着+2着+3着）の多い順に並ぶ。

```yaml
rows:
  type: dynamic
  top_n: 10                             # 任意。上位N件（同数は同順位扱いで全件残る）
  always_include_grades: ["A", "B", "C"] # 任意。重賞は上位外でも必ず表示する
```

- `top_n` または `source.allowed_values` を指定した場合、表の最後に残りをまとめた `その他` 行が付く。
- `always_include_grades` は `prev_race_name`（前走レース）向け。指定グレードのレース名を、上位に入らなくても行として残す。
- `source.allowed_values` を書くと、そこに無いラベルを表から除外できる（例: `debut_venue` で JRA 10場のみ表示）。

### `type: boolean_multi`

「条件を満たす種牡馬の産駒」をまとめた行を作る特殊型。`items` ごとに `source` を持つ。

```yaml
父実績:
  note: ※父の実績は過去30年のレースで判定
  rows:
    type: boolean_multi
    items:
      - label: "父{race_name}勝ち"
        source: {type: sire_race_condition_finisher, race_name: "{race_name}", years: 30}
      - label: "父{kyori}mG1勝ち"
        source: {type: sire_race_condition_finisher, grade_codes: ["A"], kyori: "{kyori}", years: 30}
```

`sire_race_condition_finisher` のパラメータ:

| キー | 既定 | 内容 |
| --- | --- | --- |
| `race_name` | − | 対象レース名（競走名本題） |
| `grade_codes` | − | グレードコード（`A`=G1, `B`=G2, `C`=G3 …） |
| `kyori` | − | 距離（m） |
| `years` | 30 | 遡る年数。集計年数とは別に数える |
| `top_n` | 1 | 何着以内を「好走」とみなすか |

条件に一致するレースで `top_n` 着以内に入った馬の名前を集め、その馬を父に持つ集計対象の出走馬の着度数を合算する。

## trends で使える source.type

### 集計対象レースの出走馬属性（`race_col` 系）

| `type` | 集計対象 |
| --- | --- |
| `gate_number` | 枠番 |
| `popularity` | 単勝人気順 |
| `running_style` | 脚質判定コード（`1`逃 `2`先 `3`差 `4`追） |
| `affiliation` | 東西所属コード（`1`美浦 `2`栗東 `3`地方 `4`海外） |
| `horse_age` | 馬齢 |
| `sex` | 性別コード（`1`牡 `2`牝 `3`セン） |
| `agari_3f_rank` | そのレース内での上がり3F順位（同レース内で `kohan_3f` 昇順にランク付け） |
| `corner4_juni` | 4角通過順位（数字でない値と0は対象外） |
| `horse_weight` | 馬体重（kg。計量前と計量不能は対象外） |
| `birth_month` | 誕生月（`kyosoba_master2.seinengappi` の月） |

### 集計対象レースの出走馬の過去走から求める `race_col` 系

集計対象レースに出走した馬の過去走から値を求める。「前走」は、そのレースより前に出走した過去走（着順が数字2桁で00でないもの）のうち開催日が最も新しい1走を指す。

| `type` | パラメータ | 集計対象 |
| --- | --- | --- |
| `prev_corner4_juni` | − | 前走の4角通過順位 |
| `prev_distance_diff` | − | 前走の距離から集計対象レースの距離を引いた差（m）。負なら距離延長、0なら同距離、正なら距離短縮 |
| `prev_race_class` | − | 前走のクラス。グレードコード A/B/C/L を G1/G2/G3/リステッドとし、D（グレードの無い重賞）はオープンとする。それ以外は競走条件コード（年齢別の5列の最大値）で 999=オープン、016=3勝クラス、010=2勝クラス、005=1勝クラス、703=未勝利、701=新馬とする。どれにも当たらない前走は、競馬場コードが数字（30〜61）なら地方、英字を含むなら海外。それ以外は集計対象外 |
| `prev_race_finish_by_class` | `race_class` | 前走が `race_class`（`prev_race_class` のクラス名）だった馬に限った前走の着順 |
| `transport` | − | `輸送なし` / `輸送あり` / `初輸送`。栗東所属で阪神・京都・中京、または美浦所属で中山・東京のレースは輸送なし、それ以外は輸送あり。輸送ありのうち、それより前に輸送ありのレースへ出走したことが無い馬は初輸送。過去のレースの輸送の有無は、そのレース時点の所属（そのレースの `tozai_shozoku_code`）で判定する |
| `good_baba_top3_count` | − | 集計対象レースより前に、良馬場で3着以内に入った回数 |
| `soft_baba_top3_count` | − | 集計対象レースより前に、稍重・重・不良の馬場で3着以内に入った回数 |
| `debut_month` | − | その馬が最初に出走したレースの月 |

馬場状態は、芝のレースは芝、ダートのレースはダートの馬場状態を使う。

### 集計主体（`Subject` 系）

| `type` | 集計対象 |
| --- | --- |
| `jockey_name` | 騎手名略称 |
| `sire_name` | 父馬名 |
| `breeder_name` | 生産者名 |

集計対象（対象G1の過去の出走馬）の騎手・種牡馬・生産者を行にする。`rows: {type: dynamic, top_n: 10}` で3着内数の多い上位10件と `その他` を並べる。

### 過去走・履歴系

| `type` | パラメータ | 内容 |
| --- | --- | --- |
| `past_race_top_n_count` | `keibajo_codes` / `grade_codes` / `top_n` / `filters` | 対象レースより前の出走のうち、条件に一致し `top_n` 着以内だった回数。`top_n` 未指定なら単なる該当レース数（キャリア） |
| `career_count` | − | 出走数 |
| `prev_race_name` | `overseas_label` | 前走のレース名。重賞（グレードコード `A`/`B`/`C`/`D`/`F`/`G`/`H`）かつJRA開催（競馬場コードが数字）で特別競走番号が `0000` 以外のレースは、同じ特別競走番号を持つ重賞レースのうち開催日が最も新しいレースの競走名本題に統一する（例: セントウルステークス → 産経賞セントウルステークス） |
| `debut_venue` | `allowed_values` | デビュー競馬場コード |
| `jockey_continuity` | − | `継続` / `乗り戻り` / `テン乗り` |
| `prev_race_col` | `column` | 前走の任意カラム。実績のある値は `kyakushitsu_hantei`（前走脚質）、`kohan_3f_jun`（前走上がり順位） |
| `prev_race_grade` | − | 前走のグレードコード（`A`/`B`/`C`/その他） |
| `prev_race_finish` | − | 前走の確定着順 |
| `prev_race_finish_by_grade` | `grade_codes` **または** `exclude_grade_codes` | 前走が指定グレード（または指定グレード以外）だった馬に限った前走着順。両方指定すると `ValueError` |
| `tokubetsu_race_finish` | `tokubetsu_kyoso_bango` / `year_offset` / `absent_label` | 対象レースから `year_offset` 年前（0=同年、1=前年）に行われた、特別競走番号が `tokubetsu_kyoso_bango` のレースでの着順。未出走は `absent_label` の値。`tokubetsu_kyoso_bango` を省略すると、対象レースの特別競走番号を使う（リピーター） |
| `chokyo_match_days` | `chokyo_condition` / `days_from` / `days_to` | 対象レース日の `days_to` 日前〜`days_from` 日前（両端含む）に行われた、対象コースの有効な調教記録それぞれについて、レース何日前かと調教閾値条件（`ChokyoThreshold` 形式のリスト。`course` はすべて同一にする）を満たすかを判定した結果。属性値は `[[何日前, 該当bool], ...]` 形式のJSON配列テキスト（記録なしは `[]`） |

未対応の `source.type` を書くと `ValueError` になる。集計に失敗した場合は `RuntimeError` になり、空の表は出力されない。

`past_race_top_n_count` の `filters` は「過去走を絞り込む追加条件」。`field` に指定できるのは以下だけで、他を書くと `ValueError` になる。

| `field` | 対応する DB カラム |
| --- | --- |
| `確定着順` | `kakutei_chakujun` |
| `グレードコード` | `grade_code` |
| `競馬場コード` | `keibajo_code` |
| `距離` | `kyori_int` |
| `脚質判定コード` | `kyakushitsu_hantei` |
| `特別競走番号` | `tokubetsu_kyoso_bango` |

```yaml
# 例: 阪神の重賞で3着以内に入った回数
阪神重賞好走実績:
  source:
    type: past_race_top_n_count
    keibajo_codes: ["09"]
    grade_codes: ["A", "B", "C"]
    top_n: 3
  rows:
    type: fixed
    items:
      - {label: "0回", op: "==", value: 0}
      - {label: "1回", op: "==", value: 1}
      - {label: "2回", op: "==", value: 2}
      - {label: "3回以上", op: ">=", value: 3}
```

## display_map

行ラベルの表示だけを差し替える。行の判定には影響しない。

```yaml
display_map:
  "01": 札幌
  "05": 東京
```

---

# table.yml — 出走馬分析表（Excel）

```yaml
出走馬:              # シート名。任意個のシートを定義できる
  - name: 枠勝率     # 列見出し
    source: {...}    # 値の取得方法
    display_map: {}  # 任意。表示だけ差し替える
    color_rules: []  # 任意。条件付き書式
騎手:
  - ...
```

- 各シートの先頭には `枠` / `馬番` / `馬名` の3列が自動で付く（YAML に書く必要はない）。
- 行は出走表の並び順（`entry_df` の順）。
- 実際の運用では `出走馬` / `騎手` / `生産者` / `種牡馬` の4シート構成にしている。

## color_rules — 条件付き書式

```yaml
color_rules:
  - condition: {op: ">=", value: 0.125}
    color: yellow
  - condition: {op: "==", value: "有馬記念"}
    color: gray
```

- 先頭から評価し、**最初に一致したルール**の色で塗る。
- 値が `None` / `NaN` の場合はどのルールにも一致しない。
- `枠` 列だけは例外で、`color_rules` ではなく枠番に対応した JRA の枠色で塗られる。

使える `op`:

| `op` | 内容 |
| --- | --- |
| `==` `!=` `>=` `<=` `>` `<` | 通常の比較 |
| `in` / `not_in` | `value` のリストに含まれるか |
| `contains` | `value` の文字列がセル値に含まれるか |
| `grade_finish_within` | `prev_race_grade_finish` 専用。`{G1: 9, G2: 2, G3: 1}` のようにグレードごとの着順上限を指定し、`"G1 5着"` 形式の値を判定する |

使える `color`: `green` / `yellow` / `blue` / `red` / `orange` / `gray`

## filters — 過去走の絞り込み

`past_field` / `debut_field` / `past_best` / `past_race_top_n_count` で使える共通オプション。

```yaml
filters:
  - field: 異常区分コード
    op: not_in
    value: ["1", "2", "3"]
```

`field` には**過去成績 DataFrame の日本語カラム名**（`確定着順` / `競馬場コード` / `距離` / `グレードコード` / `異常区分コード` / `競走名本題` など）を指定する。`op` は `color_rules` と同じものが使える。

> trends 側の `past_race_top_n_count` の `filters` は指定できる `field` が限定される（[前掲の表](#過去走履歴系)）。table 側は DataFrame に存在する列であれば指定できる。

## table で使える source.type

### 出走表・マスタからそのまま取る

| `type` | パラメータ | 内容 |
| --- | --- | --- |
| `entry_field` | `field` | 出走表の列（日本語）。例: `所属コード` `馬齢` `性別コード` `騎手名略称` |
| `kyosoba_field` | `field` | 競走馬マスタ2の列（英語）。例: `seisanshamei_hojinkaku_nashi` |
| `umagoto_field` | `field` | 今回レースの馬ごと情報（コード変換済み） |
| `recent_umagoto_field` | `field` | 直近走の馬ごと情報。例: `kyakushitsu`（前走脚質） |

### 過去成績から取る

| `type` | パラメータ | 内容 |
| --- | --- | --- |
| `past_field` | `field` / `filters` / `index`（既定 0） | 新しい順に `index` 番目の過去走の値。`index: 0` が前走 |
| `debut_field` | `field` / `filters` | 最も古い過去走の値（デビュー戦） |
| `past_best` | `field` / `agg`（`min`\|`max`） / `filters` | 過去走の最小値または最大値 |
| `past_race_top_n_count` | `keibajo_codes` / `grade_codes` / `top_n` / `filters` | 条件に一致する過去走のうち `top_n` 着以内だった回数。`top_n` 省略で該当レース数 |
| `prev_race_name` | `overseas_label` | 前走レース名。海外レースは `overseas_label` の値に置き換える。重賞（グレードコード `A`/`B`/`C`/`D`/`F`/`G`/`H`）かつJRA開催（競馬場コードが数字）で特別競走番号が `0000` 以外のレースは、同じ特別競走番号を持つ重賞レースのうち開催日が最も新しいレースの競走名本題に統一する |
| `prev_race_grade_finish` | − | 前走を `"G1 5着"` 形式で返す（`A`→G1, `B`→G2, `C`→G3, その他→`非重賞`）。中止等で着順が取れない場合は空 |
| `prev_race_kohan_3f_rank` | − | 前走の上がり3F順位（同レース出走馬中） |
| `tokubetsu_race_finish` | `tokubetsu_kyoso_bango` / `year_offset` / `absent_label` | 対象レースから `year_offset` 年前（0=同年、1=前年）に行われた、特別競走番号が `tokubetsu_kyoso_bango` のレースでの着順。未出走なら `absent_label` |
| `kishu_continuity` | − | `継続` / `乗り戻り` / `テン乗り` |
| `chokyo_match_days` | `chokyo_condition` / `days_from` / `days_to` | 対象レース日の `days_to` 日前〜`days_from` 日前（両端含む）に行われた、対象コースの調教のうち調教閾値条件（`chokyo_condition`。`ChokyoThreshold` 形式のリストで `course` はすべて同一にする）に該当した本数（int）。確定着順の有無を問わず出走馬を対象にする。期間内に対象コースの調教記録が1本も無い場合は空セル（None） |

### 統計値（`stat` を指定する）

`stat` は `wins`（勝利数） / `top3`（3着内数） / `win_rate`（勝率） / `top3_rate`（複勝率）。率は小数（Excel 側で書式設定する）。

| `type` | パラメータ | 内容 |
| --- | --- | --- |
| `waku_stat` | `stat` / `keibajo_code` / `track`(`shiba`\|`dirt`) / `kyori` / `years` / `course_kubun` / `week` | その馬の枠番の、指定コースでの成績。`course_kubun` は A〜E のコース区分。`week` は「その開催回でそのレースのコース区分が使われ始めた日から数えた暦週」（`(開催日 − 同一開催回・同一コース区分の最初の開催日).days // 7 + 1`）で、`course_kubun` の指定有無に関わらず適用される。`course_kubun` 未指定時はコース区分ごとに週を数えたうえで絞り込む |
| `kishu_course_stat` | `stat` / `keibajo_code` / `track` / `kyori` / `years` | 騎手の指定コース成績 |
| `sire_course_stat` | `stat` / `keibajo_code` / `track` / `kyori` / `years` / `track_condition` | 父の産駒の指定コース成績。`track_condition` は馬場状態コード |
| `sire_race_stat` | `stat`（`name` も可） / `race_name_for_history` / `years` | 父の産駒の指定レース成績。`stat: name` のときは種牡馬名を返す |
| `seisansha_race_stat` | `stat` / `race_name_for_history` / `years` | 生産者の指定レース成績 |
| `sire_race_chakujun` | `race_name_for_history` / `years` | 父自身がそのレースに出走したときの着順（例: 父のダービー着順） |
| `kishu_venue_stat` / `kishu_kyori_stat` / `seisansha_stat` | `field` / `period` | 出走別データ（JRA-VAN の出走別騎手・生産者情報）の列をそのまま取る。列名は `{field}_{period}` で解決する |

未対応の `type` を書いた場合は `ValueError: 不明なsource type: ...` で落ちる。

---

# 新しいレースの設定を作る手順

1. 近いレースのディレクトリをコピーする（開催場が変わるレースなら `宝塚記念/`、素直なレースなら `安田記念/`）。
2. ディレクトリ名を新しいレースの競走名本題に合わせる。`g1_predict/modules/utils/race_name.py` の `RACE_NAME_ABBREVIATIONS` に登録するレースなら、その略称をディレクトリ名にする。
3. `trends.yml` は、使う項目の名前を `configs/trends/` のカテゴリごとに選ぶ。`table.yml` は、距離・競馬場コードを含む箇所（`kyori` / `keibajo_code` / `keibajo_codes` など）を書き換える。
4. `race_name_for_history` を新しいレースの競走名本題にする（DB照合に使うため、略称ではなく競走名本題を書く）。
5. 開催条件が年によって変わるレースなら、`trends.yml` の `conditionable` な項目に `condition` を注入する。
6. `templates/points/{レース名}.md` にそのレースの狙い・格言を見出し無しの本文で書いておく（`gen_predict` が `## ポイント` 見出しの下に流し込む）。
7. `python -m scripts.gen_trend --race-code ...` で表が欠損なく出るか確認する。動作確認で生成した記事はコミットしない。

`source.type` で表現できない集計が必要になったときは、`_trend_stats.py`（trends 側）または `table_context.py` / `table_stat.py`（table 側）に新しい type を追加する。追加の進め方は [development.md](development.md) を参照。
