# configs/{レース名}/ リファレンス

レース1本分の「傾向表に何を出すか」「出走馬の比較表にどの項目を並べるか」を定義する設定ファイル群。Python を触らずにこれらのファイルだけで表現できることを優先している。

- レースごとにディレクトリを作り、用途ごとのファイルを置く。

```
configs/{レース名}/
├── trends.yml   # gen_trend が使う項目名と開催条件（省略可。無ければ見出しだけの記事になる）
└── table.yml    # gen_trend の --with-entries が使う比較表の定義（--with-entries を使うなら必須）
```

- ディレクトリ名は **DB の競走名本題（`kyosomei_hondai`）と完全一致**させる（例: `configs/宝塚記念/`）。スクリプトはレースコードから引いたレース名でディレクトリを探す。
- ただし `g1_predict/modules/utils/race_name.py` の `RACE_NAME_ABBREVIATIONS` に登録されているレースは、競走名本題ではなく対応表の略称をディレクトリ名にする（例: 競走名本題「スプリンターズステークス」→ `configs/スプリンターズS/`）。この略称は `templates/points/{レース名}.md` の参照、`public/` の出力先ディレクトリ・ファイル名、記事タイトルにも共通して使われる。DB照合には使えないため、競走名本題での照合が必要な処理には対応表変換前の値を渡す。
- 現在ある設定: `東京優駿/` / `安田記念/` / `宝塚記念/` / `スプリンターズS/`。新しいレースは近いものをコピーして作るのが早い。
- 各ファイルの最上位には `trends` / `table` のようなキーを書かず、中身（カテゴリ名）を直接書く。
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

- 項目に書けるキーは `source` / `rows` / `display_map` / `conditionable` / `uses_race_result` / `hide_entry_column` / `class_label` / `note` / `hide_if_empty` で、`rows` は必須。
- `conditionable: true` の項目だけが、レースの `trends.yml` から開催条件を注入できる。
- `uses_race_result: true` は、今走の結果で値が決まる項目（脚質・4角通過順位・上がり3F順位）に付ける。出走馬の確定後でもレース前には値が無いため、`--with-entries` でも該当馬列を付けず、table.yml にも載せられない。
- `hide_entry_column: true` を書くと、`--with-entries` でも記事の表に該当馬列を付けない（人気・枠順で使う）。table.yml には載せられる。
- `class_label` は、前走のクラス別の着順の項目（前走G1着順〜前走新馬着順、前走非重賞着順）に付けるクラスの略称（`G1` / `L` / `OP` / `3勝` / `未勝利` / `非重賞` など）。比較表の「前走クラス着順」列で値の前に付ける（[table.yml](#tableyml--出走馬の比較表)）。
- `note` を書くと、表の直下にその文字列を出す。
- `hide_if_empty: true` を書くと、集計対象にも今回の出走馬にも該当馬が1頭もいない場合は表を見出しごと出さない（前走{クラス}着順で使う）。
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
- `--with-entries` を付けると、各表の右端に今回の出走馬の馬番を書く「該当馬」列が付く。さらに、記事の最後に `## 比較表` と出走馬の比較表の画像が付く（[table.yml](#tableyml--出走馬の比較表)）。付けない場合はどちらも出さない。

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
  hide_empty: true          # 任意。頭数が0の行を出さない（今回の出走馬が当たる行は出す）
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
  exclude_no_top3: true                 # 任意。3着内数が0の要素は上位に入れず、その他にまとめる
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

集計対象（対象G1の過去の出走馬）の騎手・種牡馬・生産者を行にする。`rows: {type: dynamic, top_n: 10, exclude_no_top3: true}` で3着内数の多い上位10件と `その他` を並べる。3着内数が0の要素は上位10件に入れない。

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

# table.yml — 出走馬の比較表

`python -m scripts.gen_trend --race-code ... --with-entries` で、今回の出走馬を項目ごとに見比べる比較表の画像を作るための定義。trends.yml と同じくカテゴリ名をキーに、比較表に載せる項目を並べる。比較表は全カテゴリの項目を並べた1枚の画像で、記事の最後の `## 比較表` に載せる。

```yaml
基本項目:
  - 枠順:
      color_rules:
        - {metric: 複勝率, op: ">=", value: 30, color: yellow}
  - 前走脚質:
      color_rules:
        - {labels: [逃げ, 先行], color: yellow}
  - 所属
前走:
  - 前走レース
  - 前走クラス:
      color_rules:
        - {metric: 複勝率, op: ">=", value: 30, color: yellow}
        - {metric: 複勝率, op: "==", value: 0, color: gray}
馬以外の属性:
  - 騎手:
      color_rules:
        - {metric: 勝率, op: ">=", value: 10, color: yellow}
```

- 項目は、そのレースの trends.yml の同じカテゴリにある項目から選ぶ。
- 前走のクラス別の着順の項目（`class_label` を持つ項目）は、前走の馬はどれか1つのクラスにしか当たらないため、個別に書かず `前走クラス着順` の1列にまとめる。`前走クラス着順` は、そのカテゴリの trends.yml にある `class_label` を持つ項目をまとめた列で、セルには `G1 1着` のようにクラスの略称と着順を書く。行の名前のルールもこの形で書く（例: `{labels: [G1 1着, G1 2着, G3 1着], color: yellow}`）。個別の項目を書いた場合は `ValueError` になる。table.yml に書いたカテゴリの順、カテゴリ内の項目の順が、比較表の列の順になる。
- 画像は `img/trend_table/比較表.png` に保存する。記事に表が出ない項目（`hide_if_empty` で隠れた項目と、今回の出走馬が1頭も当たらない項目、全頭が同じ1つの行だけに当たる項目）は、比較表にも載せない。載せる項目が1つも無い場合は `## 比較表` を出さない。
- そのレースの trends.yml に無いカテゴリ・項目、今走の結果で決まる項目（`uses_race_result: true`）、未知の `metric`・`op`・`color`、`color_rules` のキーの不足は `ValueError` になる。
- `--with-entries` を付けたときに table.yml が無い場合は、例外で止まる。

## 比較表の見た目

```
| 枠 | 馬番 | 馬名 | 枠順 | 前走脚質 | 所属 | ... | 好データ |
```

- 行は今回の出走馬を馬番順に並べる。出走取消・発走除外・競走除外の馬は含めない。
- 各セルには、その馬が当たる行の名前（`display_map` があれば表示名）を書く。dynamic の項目で記事の表では「その他」行に入る馬も、騎手名などの値そのものを書く。値が求まらない馬（前走が無いなど）は「-」とする。父実績のように複数の行に当たる馬は「・」でつないで書く。ただし `fixed` の項目（リピーターの前年3着以内・前年5着以内のように行の範囲が重なる項目）は、当たる行のうち表の上にある行だけを書く。
- 右端の `好データ` 列には、その馬の項目の列のうち黄色（`yellow`）で塗ったセルの数を書く。数が多い順に1位から3位までを、展開評価値のグラフの順位と同じ色（netkeiba の人気・上がり順位の色）で塗る。同じ数の馬は同じ順位とし、次の数を次の順位とする（7・5・5・5・4・4 なら 7 が1位、5 の3頭が2位、4 の2頭が3位）。0 は塗らない。
- 見出し行は灰色で、`枠` 列は JRA の枠の色で塗る。

## 出走馬が当たる行

出走馬がどの行に当たるかは、項目ごとに過去の集計と同じ `GroupBy` で `mykeibadb.analytics.get_race_entry_groups` から値を得て、過去の集計と同じ行の割り当て（`fixed` の `op`、`dynamic` の行名、`chokyo_match_days` の `op` など）で決める。

- `dynamic` の項目（前走レース・騎手・生産者・種牡馬など）で、表に出ている行のどれにも当たらない馬は「その他」行に入る。
- `boolean_multi`（父実績）は、出走馬の父がその行の条件を満たす種牡馬なら当たる。1頭が複数の行に当たることがある。
- 値が求まらない馬はどの行にも入らない。
- 今走の結果で決まる項目（脚質・4角通過順位・上がり3F順位）はレース前に値が無いため、該当馬は求めない。馬体重のように当日に決まる値は、DB に入る前は空になる。
- 項目に開催条件を注入していても、出走馬の判定には条件を使わない。条件は過去の集計対象を絞るためのもの。

## color_rules — セルの色付け

`color_rules` は任意。先頭から評価し、最初に当てはまったルールの色でセルを塗る。次の2種類のルールを混ぜて書ける。

| 種類 | キー | 内容 |
| --- | --- | --- |
| 指標と基準値 | `metric` / `op` / `value` / `color`（任意で `min_total`） | 出走馬が当たる記事の表の行（dynamic の項目で表に出ていない値は「その他」行）の、過去の集計の指標で判定する。行の頭数が0の場合と、`min_total` に満たない場合は判定しない |
| 行の名前 | `labels` / `color` | セルに書く値（`display_map` があれば表示名）が `labels` に含まれれば塗る。dynamic の項目では「その他」行に入る馬の値（騎手名など）も指定できる |

- `metric` は `勝率` / `複勝率` / `単回` / `複回` / `3着内数`。率と回収率は記事の表に出ている整数の%（四捨五入後）で、`3着内数` は着度数の1〜3着の合計の頭数で比べる。
- `op` は `>=` `<=` `>` `<` `==`。`value` は%の数値（`3着内数` は頭数）。
- `min_total` は行の頭数の下限（1以上の整数）。頭数が少なく率が当てにならない行を塗らないために使う（例: `{metric: 複勝率, op: ">=", value: 30, min_total: 10, color: yellow}` は、頭数10頭以上で複勝率30%以上の行だけを塗る）。
- 使える `color`: `green` / `yellow` / `blue` / `red` / `orange` / `gray`
- 複数の行に当たる馬は、当たった行のうち先にルールに当てはまった行の色で塗る。

---

# 新しいレースの設定を作る手順

1. 近いレースのディレクトリをコピーする（開催場が変わるレースなら `宝塚記念/`、素直なレースなら `安田記念/`）。
2. ディレクトリ名を新しいレースの競走名本題に合わせる。`g1_predict/modules/utils/race_name.py` の `RACE_NAME_ABBREVIATIONS` に登録するレースなら、その略称をディレクトリ名にする。
3. `trends.yml` は、使う項目の名前を `configs/trends/` のカテゴリごとに選ぶ。`table.yml` は、trends.yml の項目から比較表に載せるものを選び、色付けの基準を書く。
4. 開催条件が年によって変わるレースなら、`trends.yml` の `conditionable` な項目に `condition` を注入する。
5. `templates/points/{レース名}.md` にそのレースの狙い・格言を見出し無しの本文で書いておく（`gen_predict` が `## ポイント` 見出しの下に流し込む）。
6. `python -m scripts.gen_trend --race-code ...` で表が欠損なく出るか確認する。出走馬が確定していれば `--with-entries` も付けて、該当馬列と比較表も確認する。動作確認で生成した記事はコミットしない。

`source.type` で表現できない集計が必要になったときは、`_trend_stats.py`（trends 側）または `table_context.py` / `table_stat.py`（table 側）に新しい type を追加する。追加の進め方は [development.md](development.md) を参照。
