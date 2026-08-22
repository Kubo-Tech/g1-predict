# configs/{レース名}.yml リファレンス

レース1本分の「傾向表に何を出すか」「分析表にどの列を並べるか」を定義する設定ファイル。Python を触らずにこのファイルだけで表現できることを優先している。

- ファイル名は **DB の競走名本題（`kyosomei_hondai`）と完全一致**させる（例: `configs/宝塚記念.yml`）。スクリプトはレースコードから引いたレース名でファイルを探す。
- 現在ある設定: `東京優駿.yml` / `安田記念.yml` / `宝塚記念.yml`。新しいレースは近いものをコピーして作るのが早い。

```yaml
race_name: 宝塚記念   # メモ用。スクリプトからは参照していない

trends:               # gen_trend が使う（省略可。無ければ見出しだけの記事になる）
  カテゴリ名:
    - name: ...
      ...

table:                # gen_table が使う（gen_table を使うなら必須）
  シート名:
    - name: ...
      ...
```

---

# trends — 傾向分析記事の表

```yaml
trends:
  出走馬傾向:          # カテゴリ名。そのまま "## 出走馬傾向" になる
    - name: 枠順       # metric 名。"### 枠順" と表の1列目見出しになる
      condition: {...} # 任意。集計対象の開催条件
      source: {...}    # 何を集計するか
      rows: {...}      # どう行に分けるか
      display_map: {}  # 任意。行ラベルの表示名変換
  騎手傾向:
    - ...
```

集計対象は既定で「**対象レースと同じ特別競走番号・同一競馬場・同一距離・同一芝ダの過去10年**」。`condition` を書くとこの範囲を metric ごとに上書きできる。

各カテゴリの末尾には空の `### 比較表` が自動で挿入される（手書き用のプレースホルダ）。

## condition — 開催条件の絞り込み

```yaml
condition:
  years: 10                  # 対象レース年の前年から何年分か（既定 10、1未満は ValueError）
  keibajo_codes: ["09"]      # 競馬場コード
  kaisai_nichime: [4]        # 開催日目
  babajotai_codes: ["1"]     # 馬場状態（1=良 2=稍重 3=重 4=不良）
```

省略したキーは基本条件（同一コース・過去10年）の値が引き継がれる。指定すると表の直下に注記が出る。

```
※過去10年阪神4日目良馬場のみ
```

宝塚記念のように開催場・開催日目が年によって変わるレースで、「展開に関わる項目は阪神4日目良馬場のみ」「それ以外は阪神開催すべて」のように metric ごとに集計範囲を変えるために用意した仕組み。

## rows — 行の作り方

### `type: fixed`

`items` で行を固定する。

```yaml
rows:
  type: fixed
  items:
    - {label: "1人気", op: "==", value: 1}
    - {label: "4-6人気", op: "in", value: [4, 5, 6]}
    - {label: "10人気以下", op: ">=", value: 10}
```

**使える `op` は `source.type` によって異なる**（集計を DB 側でやるか Python 側でやるかが違うため）。

| `source.type` のグループ | 使える `op` |
| --- | --- |
| `race_col` 系 / `prev_race_grade` / `prev_race_finish` / `prev_race_finish_by_grade` / `same_race_prev_year_finish` | `==` `!=` `>=` `<=` `>` `<` `in` `not_in` |
| `past_race_top_n_count` / `career_count` / `prev_race_name` / `debut_venue` / `jockey_continuity` / `prev_race_col` | `==` `>=` `<=` `>` `<`（`in` は `ValueError`。`!=` `not_in` は無視され、その行は常に `0-0-0-0` になる） |

`value` は数値・文字列のどちらも指定できる。数値として解釈できる場合は数値比較、できない場合は文字列比較になる。

上段は Python 側で集計結果をグループ化するため演算子の自由度が高く、下段は DB 側（`analytics` の `GroupBy(kind="fixed")`）に行定義を渡すため制約がある。`prev_race_grade` などは内部で `prev_race_col` へ変換されるが、集計は Python 側で行うので上段の扱いになる。

### `type: dynamic`

集計結果から自動で行を作る。3着内数（1着+2着+3着）の多い順に並ぶ。

```yaml
rows:
  type: dynamic
  top_n: 5                              # 任意。上位N件（同数は同順位扱いで全件残る）
  always_include_grades: ["A", "B", "C"] # 任意。重賞は上位外でも必ず表示する
```

- `top_n` または `source.allowed_values` を指定した場合、表の最後に残りをまとめた `その他` 行が付く。
- `always_include_grades` は `prev_race_name`（前走レース）向け。指定グレードのレース名を、上位に入らなくても行として残す。
- `source.allowed_values` を書くと、そこに無いラベルを表から除外できる（例: `debut_venue` で JRA 10場のみ表示）。

### `type: all_entries`

**今回出走する**騎手・種牡馬・生産者をすべて行として並べる。`source.type` は `jockey_name` / `sire_name` / `breeder_name` のいずれかである必要がある（他は `ValueError`）。

```yaml
- name: 騎手
  condition: {years: 10, keibajo_codes: ["09"]}
  source: {type: jockey_name}
  rows: {type: all_entries}
```

並び順は 1着数降順 → 2着数降順 → 3着数降順 → 着外数昇順 → 馬番昇順。同じラベルの馬が複数いる場合は最小馬番をソートキーにする。

### `type: boolean_multi`

「条件を満たす種牡馬の産駒」をまとめた行を作る特殊型。`items` ごとに `source` を持つ。

```yaml
- name: 父実績
  rows:
    type: boolean_multi
    items:
      - label: "父ダービー勝ち"
        source: {type: sire_race_condition_finisher, race_name: "東京優駿", years: 30}
      - label: "父2400mG1勝ち"
        source: {type: sire_race_condition_finisher, grade_codes: ["A"], kyori: 2400, years: 30}
```

`sire_race_condition_finisher` のパラメータ:

| キー | 既定 | 内容 |
| --- | --- | --- |
| `race_name` | − | 対象レース名（競走名本題） |
| `grade_codes` | − | グレードコード（`A`=G1, `B`=G2, `C`=G3 …） |
| `kyori` | − | 距離（m） |
| `years` | 30 | 遡る年数 |
| `top_n` | 1 | 何着以内を「好走」とみなすか |

条件に一致するレースで `top_n` 着以内に入った馬の名前を集め、その馬を父に持つ出走馬の着度数を合算する。

## trends で使える source.type

### 今回レースの出走馬属性（`race_col` 系）

| `type` | 集計対象 |
| --- | --- |
| `gate_number` | 枠番 |
| `popularity` | 単勝人気順 |
| `running_style` | 脚質判定コード（`1`逃 `2`先 `3`差 `4`追） |
| `affiliation` | 東西所属コード（`1`美浦 `2`栗東 `3`地方 `4`海外） |
| `horse_age` | 馬齢 |
| `sex` | 性別コード（`1`牡 `2`牝 `3`セン） |
| `agari_3f_rank` | そのレース内での上がり3F順位（同レース内で `kohan_3f` 昇順にランク付け） |

### 集計主体（`Subject` 系）

| `type` | 集計対象 |
| --- | --- |
| `jockey_name` | 騎手名略称 |
| `sire_name` | 父馬名 |
| `breeder_name` | 生産者名 |

`rows: {type: dynamic}` で上位N件、`rows: {type: all_entries}` で今回出走分を全表示。

### 過去走・履歴系

| `type` | パラメータ | 内容 |
| --- | --- | --- |
| `past_race_top_n_count` | `keibajo_codes` / `grade_codes` / `top_n` / `filters` | 対象レースより前の出走のうち、条件に一致し `top_n` 着以内だった回数。`top_n` 未指定なら単なる該当レース数（キャリア） |
| `career_count` | − | 出走数 |
| `prev_race_name` | `overseas_label` | 前走のレース名 |
| `debut_venue` | `allowed_values` | デビュー競馬場コード |
| `jockey_continuity` | − | `継続` / `乗り戻り` / `テン乗り` |
| `prev_race_col` | `column` | 前走の任意カラム。実績のある値は `kyakushitsu_hantei`（前走脚質）、`kohan_3f_jun`（前走上がり順位）、`kyori`（前走距離） |
| `prev_race_grade` | − | 前走のグレードコード（`A`/`B`/`C`/その他） |
| `prev_race_finish` | − | 前走の確定着順 |
| `prev_race_finish_by_grade` | `grade_codes` **または** `exclude_grade_codes` | 前走が指定グレード（または指定グレード以外）だった馬に限った前走着順。両方指定すると `ValueError` |
| `same_race_prev_year_finish` | `tokubetsu_kyoso_bango` / `absent_label` | 前年の同一レースでの着順。未出走は `absent_label` の値 |

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
- name: 阪神重賞好走実績
  condition: {years: 10, keibajo_codes: ["09"]}
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

# table — 出走馬分析表（Excel）

```yaml
table:
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
| `prev_race_name` | `overseas_label` | 前走レース名。海外レースは `overseas_label` の値に置き換える |
| `prev_race_grade_finish` | − | 前走を `"G1 5着"` 形式で返す（`A`→G1, `B`→G2, `C`→G3, その他→`非重賞`）。中止等で着順が取れない場合は空 |
| `prev_race_kohan_3f_rank` | − | 前走の上がり3F順位（同レース出走馬中） |
| `same_race_prev_year_finish` | `tokubetsu_kyoso_bango` / `absent_label` | 前年の同一レースでの着順。未出走なら `absent_label` |
| `kishu_continuity` | − | `継続` / `乗り戻り` / `テン乗り` |

### 統計値（`stat` を指定する）

`stat` は `wins`（勝利数） / `top3`（3着内数） / `win_rate`（勝率） / `top3_rate`（複勝率）。率は小数（Excel 側で書式設定する）。

| `type` | パラメータ | 内容 |
| --- | --- | --- |
| `waku_stat` | `stat` / `keibajo_code` / `track`(`shiba`\|`dirt`) / `kyori` / `years` / `course_kubun` / `week` | その馬の枠番の、指定コースでの成績。`course_kubun` は A〜E のコース区分、`week` は各開催回のコース区分内での週（1週=2日） |
| `kishu_course_stat` | `stat` / `keibajo_code` / `track` / `kyori` / `years` | 騎手の指定コース成績 |
| `sire_course_stat` | `stat` / `keibajo_code` / `track` / `kyori` / `years` / `track_condition` | 父の産駒の指定コース成績。`track_condition` は馬場状態コード |
| `sire_race_stat` | `stat`（`name` も可） / `race_name_for_history` / `years` | 父の産駒の指定レース成績。`stat: name` のときは種牡馬名を返す |
| `seisansha_race_stat` | `stat` / `race_name_for_history` / `years` | 生産者の指定レース成績 |
| `sire_race_chakujun` | `race_name_for_history` / `years` | 父自身がそのレースに出走したときの着順（例: 父のダービー着順） |
| `kishu_venue_stat` / `kishu_kyori_stat` / `seisansha_stat` | `field` / `period` | 出走別データ（JRA-VAN の出走別騎手・生産者情報）の列をそのまま取る。列名は `{field}_{period}` で解決する |

未対応の `type` を書いた場合は `ValueError: 不明なsource type: ...` で落ちる。

---

# 新しいレースの設定を作る手順

1. 近いレースの YAML をコピーする（開催場が変わるレースなら `宝塚記念.yml`、素直なレースなら `安田記念.yml`）。
2. ファイル名を新しいレースの競走名本題に合わせる。
3. `race_name` と、距離・競馬場コードを含む箇所（`kyori` / `keibajo_code` / `keibajo_codes` / 前走距離の閾値など）を書き換える。
4. `race_name_for_history` を新しいレース名にする。
5. 開催条件が年によって変わるレースなら、metric ごとに `condition` を付ける。
6. `templates/points/{レース名}.md` にそのレースの狙い・格言を書いておく（`gen_predict` が `## ポイント` に流し込む）。
7. `python -m scripts.gen_trend --race-code ...` で表が欠損なく出るか確認する。動作確認で生成した記事はコミットしない。

`source.type` で表現できない集計が必要になったときは、`_trend_stats.py`（trends 側）または `table_context.py` / `table_stat.py`（table 側）に新しい type を追加する。追加の進め方は [development.md](development.md) を参照。
