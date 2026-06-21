#!/usr/bin/env python3
"""
麻雀 何切る問題ジェネレーター
牌効率（有効牌枚数最大化）・向聴数最小化に基づいて最適打牌を計算・解説します

使い方:
  python3 mahjong_nankiru.py            # 通常問題5問（一向聴）
  python3 mahjong_nankiru.py easy 3     # 簡単問題3問（二〜三向聴）
  python3 mahjong_nankiru.py hard 5     # 難しい問題5問（テンパイ形）
  python3 mahjong_nankiru.py demo       # デモ問題
"""

import random
import sys

# ============================================================
# 牌定義
# 0-8  : 1m〜9m (一萬〜九萬)
# 9-17 : 1p〜9p (一筒〜九筒)
# 18-26: 1s〜9s (一索〜九索)
# 27-33: 東南西北白発中
# ============================================================

_HONORS = ['東', '南', '西', '北', '白', '発', '中']
_NUMS_JP = ['一', '二', '三', '四', '五', '六', '七', '八', '九']
_YAOCHUUHAI_IDX = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]


def tile_name(t: int) -> str:
    """牌番号 → 短縮表記 (例: 1m, 5p, 3s, 東)"""
    if t < 9:
        return f"{t + 1}m"
    elif t < 18:
        return f"{t - 8}p"
    elif t < 27:
        return f"{t - 17}s"
    else:
        return _HONORS[t - 27]


def tile_name_jp(t: int) -> str:
    """牌番号 → 日本語表記 (例: 一萬, 五筒, 三索, 東)"""
    if t < 9:
        return _NUMS_JP[t] + '萬'
    elif t < 18:
        return f"{t - 8}筒"
    elif t < 27:
        return f"{t - 17}索"
    else:
        return _HONORS[t - 27]


def hand_str(tiles: list) -> str:
    """手牌リスト → 表示用文字列"""
    s = sorted(tiles)
    parts = []
    man = [str(t + 1) for t in s if t < 9]
    if man:
        parts.append(''.join(man) + 'm')
    pin = [str(t - 8) for t in s if 9 <= t < 18]
    if pin:
        parts.append(''.join(pin) + 'p')
    sou = [str(t - 17) for t in s if 18 <= t < 27]
    if sou:
        parts.append(''.join(sou) + 's')
    hon = [_HONORS[t - 27] for t in s if t >= 27]
    if hon:
        parts.append(' '.join(hon))
    return ' '.join(parts)


def shanten_str(s: int) -> str:
    return {
        -1: 'あがり',
        0:  'テンパイ',
        1:  '一向聴',
        2:  '二向聴',
        3:  '三向聴',
        4:  '四向聴',
    }.get(s, f'{s}向聴')


# ============================================================
# 向聴数計算（シャンテン数）
#
# 公式: shanten = 8 - 2×面子数 - 搭子数 - 雀頭(1/0)
#   ・面子+搭子 <= 4 という制約付き
#   ・通常手・七対子・国士無双の最小値を返す
# ============================================================

def shanten(hand: list) -> int:
    """手牌リストの向聴数を返す（13枚基準）"""
    counts = [0] * 34
    for t in hand:
        counts[t] += 1
    return _shanten_all(counts)


def _shanten_all(counts: list) -> int:
    return min(
        _shanten_regular(list(counts)),
        _shanten_chiitoitsu(counts),
        _shanten_kokushi(counts),
    )


def _shanten_chiitoitsu(counts: list) -> int:
    """七対子: 7種の対子が必要。今の対子数を引いた値が向聴数"""
    pairs = sum(1 for c in counts if c >= 2)
    return 6 - pairs


def _shanten_kokushi(counts: list) -> int:
    """国士無双: 13種の么九牌が必要 + 1枚の雀頭"""
    has = sum(1 for t in _YAOCHUUHAI_IDX if counts[t] > 0)
    pair = any(counts[t] >= 2 for t in _YAOCHUUHAI_IDX)
    return 13 - has - (1 if pair else 0)


def _shanten_regular(counts: list) -> int:
    """
    通常手の向聴数をバックトラッキングで計算。
    各牌について: 雀頭・順子・刻子・嵌張・両面・辺張・孤立 のいずれかとして試す。
    """
    best = [8]

    def update(mentsu: int, taatsu: int, jantai: int) -> None:
        t = min(taatsu, 4 - mentsu)
        s = 8 - 2 * mentsu - t - jantai
        if s < best[0]:
            best[0] = s

    def search(i: int, mentsu: int, taatsu: int, jantai: int) -> None:
        while i < 34 and counts[i] == 0:
            i += 1

        update(mentsu, taatsu, jantai)

        if i >= 34 or best[0] == -1:
            return

        orig = counts[i]

        # ── 雀頭候補（対子として使う）──
        if jantai == 0 and counts[i] >= 2:
            counts[i] -= 2
            search(i, mentsu, taatsu, 1)
            counts[i] += 2

        if i < 27:  # 数牌のみ順子・嵌張・両面
            n = i % 9  # 0-indexed の数字 (0=1, 8=9)

            # ── 順子（面子）: i, i+1, i+2 ──
            if n <= 6 and counts[i + 1] > 0 and counts[i + 2] > 0:
                counts[i] -= 1
                counts[i + 1] -= 1
                counts[i + 2] -= 1
                search(i, mentsu + 1, taatsu, jantai)
                counts[i] += 1
                counts[i + 1] += 1
                counts[i + 2] += 1

            # ── 嵌張搭子: i, i+2（間が1枚空いている）──
            if n <= 6 and counts[i + 2] > 0:
                counts[i] -= 1
                counts[i + 2] -= 1
                search(i, mentsu, taatsu + 1, jantai)
                counts[i] += 1
                counts[i + 2] += 1

            # ── 両面/辺張搭子: i, i+1 ──
            if n <= 7 and counts[i + 1] > 0:
                counts[i] -= 1
                counts[i + 1] -= 1
                search(i, mentsu, taatsu + 1, jantai)
                counts[i] += 1
                counts[i + 1] += 1

        # ── 刻子（面子）: i×3 ──
        if counts[i] >= 3:
            counts[i] -= 3
            search(i, mentsu + 1, taatsu, jantai)
            counts[i] += 3

        # ── 対子搭子: i×2（雀頭でなく搭子として使う）──
        if counts[i] >= 2:
            counts[i] -= 2
            search(i, mentsu, taatsu + 1, jantai)
            counts[i] += 2

        # ── 孤立牌: すべて除外してスキップ ──
        counts[i] = 0
        search(i + 1, mentsu, taatsu, jantai)
        counts[i] = orig

    search(0, 0, 0, 0)
    return best[0]


# ============================================================
# あがり判定（14枚）
# ============================================================

def is_winning_hand(counts: list) -> bool:
    """14枚手牌があがりかどうかを判定"""
    # 七対子
    pairs = sum(1 for c in counts if c >= 2)
    kinds = sum(1 for c in counts if c == 2)
    if pairs == 7 and kinds == 7:
        return True
    # 国士無双
    ymc = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    if all(counts[t] >= 1 for t in ymc) and any(counts[t] >= 2 for t in ymc):
        if sum(counts) == 14:
            return True
    # 通常手
    return _shanten_regular(list(counts)) == -1


# ============================================================
# 有効牌（向聴数を下げる牌）の計算
# ============================================================

def get_effective_tiles(counts_12: list, current_shanten: int, used: list) -> dict:
    """
    12枚手牌に有効牌を1枚加えたとき向聴数が下がる牌をすべて返す。
    used: 自分の手・捨て牌等で使用済みの枚数（山の残り = 4 - used[t]）
    """
    effective = {}
    for t in range(34):
        if counts_12[t] >= 4:
            continue
        counts_12[t] += 1
        new_s = _shanten_all(counts_12)
        counts_12[t] -= 1
        if new_s < current_shanten:
            remaining = 4 - used[t]
            if remaining > 0:
                effective[t] = remaining
    return effective


def get_winning_tiles(counts_13: list, used: list) -> dict:
    """テンパイ(13枚)手牌のあがり牌と残り枚数を返す"""
    winning = {}
    for t in range(34):
        if counts_13[t] >= 4:
            continue
        counts_13[t] += 1
        if is_winning_hand(counts_13):
            remaining = 4 - used[t]
            if remaining > 0:
                winning[t] = remaining
        counts_13[t] -= 1
    return winning


# ============================================================
# 最適打牌の計算
# ============================================================

def find_best_discards(hand: list) -> list:
    """
    13枚手牌の各打牌候補を評価して返す。
    ソート: 向聴数昇順 → 有効牌枚数降順
    """
    counts = [0] * 34
    for t in hand:
        counts[t] += 1
    used = list(counts)

    results = []
    seen = set()

    for t in sorted(set(hand)):
        if t in seen:
            continue
        seen.add(t)

        counts[t] -= 1
        s = _shanten_all(counts)
        eff = get_effective_tiles(counts, s, used)
        eff_count = sum(eff.values())
        results.append({
            'tile': t,
            'shanten': s,
            'effective': eff,
            'eff_count': eff_count,
        })
        counts[t] += 1

    results.sort(key=lambda x: (x['shanten'], -x['eff_count']))
    return results


# ============================================================
# 待ち牌の種類を判定
# ============================================================

def classify_wait(wait_tiles: list, hand_12: list) -> str:
    """待ちの種類（両面/嵌張/辺張/単騎/シャンポン）を判定"""
    if not wait_tiles:
        return 'なし'
    n = len(wait_tiles)
    if n == 1:
        t = wait_tiles[0]
        counts = [0] * 34
        for x in hand_12:
            counts[x] += 1
        if counts[t] == 1:
            return f'{tile_name_jp(t)}の単騎待ち'
        return f'{tile_name_jp(t)}の待ち'
    if n == 2:
        t1, t2 = sorted(wait_tiles)
        if t1 < 27 and t2 < 27 and t1 // 9 == t2 // 9:
            diff = t2 % 9 - t1 % 9
            if diff == 2:
                mid = t1 + 1
                return f'{tile_name_jp(mid)}の嵌張待ち'
            if diff == 1:
                n1 = t1 % 9 + 1
                n2 = t2 % 9 + 1
                if n1 == 1 or n2 == 9:
                    return f'{tile_name_jp(t1)}・{tile_name_jp(t2)}の辺張待ち'
                return f'{tile_name_jp(t1)}・{tile_name_jp(t2)}の両面待ち'
        return f'{tile_name_jp(t1)}・{tile_name_jp(t2)}のシャンポン待ち'
    tiles_str = '・'.join(tile_name_jp(t) for t in sorted(wait_tiles))
    return f'{tiles_str}の{n}面待ち（多面張）'


# ============================================================
# 有効牌のグルーピング（表示用）
# ============================================================

def _group_tiles(tile_dict: dict) -> list:
    """牌辞書を {表示文字列: 枚数} のリストに整形"""
    groups = []
    for suit_start, suffix in [(0, 'm'), (9, 'p'), (18, 's')]:
        in_suit = [(t, tile_dict[t]) for t in range(suit_start, suit_start + 9) if t in tile_dict]
        if in_suit:
            nums = ''.join(str(t % 9 + 1) for t, _ in in_suit)
            total = sum(c for _, c in in_suit)
            groups.append((f'{nums}{suffix}', total))
    for t, c in tile_dict.items():
        if t >= 27:
            groups.append((tile_name_jp(t), c))
    return groups


# ============================================================
# 手牌構造の解析（解説用）
# ============================================================

def _detect_blocks(counts: list) -> dict:
    """手牌から面子・搭子・孤立牌を検出して返す（グリーディ）"""
    c = list(counts)
    mentsu, taatsu, isolated = [], [], []

    for suit_start in [0, 9, 18]:
        for i in range(suit_start, suit_start + 9):
            # 刻子
            while c[i] >= 3:
                mentsu.append(f'{tile_name(i)}×3')
                c[i] -= 3
            # 順子
            while i + 2 < suit_start + 9 and c[i] > 0 and c[i + 1] > 0 and c[i + 2] > 0:
                mentsu.append(f'{tile_name(i)}{tile_name(i+1)}{tile_name(i+2)}')
                c[i] -= 1; c[i + 1] -= 1; c[i + 2] -= 1
        # 搭子（残り）
        for i in range(suit_start, suit_start + 9):
            while c[i] >= 2:
                taatsu.append(f'{tile_name(i)}×2')
                c[i] -= 2
            if i + 1 < suit_start + 9 and c[i] > 0 and c[i + 1] > 0:
                taatsu.append(f'{tile_name(i)}{tile_name(i+1)}')
                c[i] -= 1; c[i + 1] -= 1
            if i + 2 < suit_start + 9 and c[i] > 0 and c[i + 2] > 0:
                taatsu.append(f'{tile_name(i)}{tile_name(i+2)}')
                c[i] -= 1; c[i + 2] -= 1

    for i in range(27, 34):
        while c[i] >= 3:
            mentsu.append(f'{tile_name(i)}×3')
            c[i] -= 3
        while c[i] >= 2:
            taatsu.append(f'{tile_name(i)}×2')
            c[i] -= 2

    for i in range(34):
        while c[i] > 0:
            isolated.append(tile_name(i))
            c[i] -= 1

    return {'mentsu': mentsu, 'taatsu': taatsu, 'isolated': isolated}


# ============================================================
# 牌効率のアドバイス生成
# ============================================================

def _efficiency_tips(hand: list, best_tile: int, results: list) -> list:
    tips = []
    best = results[0]

    # 向聴数が変わる候補がある場合
    shantens = {r['shanten'] for r in results}
    if len(shantens) > 1:
        tips.append('向聴数を下げない打牌を選ぶのが基本（向聴数最優先）')

    # 有効牌数の差
    if len(results) >= 2:
        second = results[1]
        if best['shanten'] == second['shanten']:
            diff = best['eff_count'] - second['eff_count']
            if diff > 4:
                tips.append(
                    f'{tile_name_jp(best_tile)}切りは'
                    f'{tile_name_jp(second["tile"])}切りより有効牌が{diff}枚多い'
                )
            elif diff == 0:
                tips.append('有効牌枚数が同等のときは、役・ドラ・安全度を考慮する')

    # 孤立字牌の優先処理
    counts = [0] * 34
    for t in hand:
        counts[t] += 1
    iso_hon = [t for t in range(27, 34) if counts[t] == 1]
    if iso_hon:
        tips.append(
            '孤立字牌（' + '・'.join(tile_name_jp(t) for t in iso_hon) +
            '）は面子になれないため、通常は先に切る'
        )

    # 両面搭子の優位性
    has_ryanmen = False
    for suit_start in [0, 9, 18]:
        for i in range(suit_start, suit_start + 8):
            n = i % 9
            if counts[i] > 0 and counts[i + 1] > 0 and 0 < n < 7:
                has_ryanmen = True
    if has_ryanmen:
        tips.append('両面搭子（例: 34→25か67待ち）は有効牌2種×各4枚=最大8枚と効率が高い')

    # 嵌張・辺張の弱点
    has_weak = False
    for suit_start in [0, 9, 18]:
        for i in range(suit_start, suit_start + 9):
            n = i % 9
            if counts[i] > 0:
                if n == 0 and i + 1 < suit_start + 9 and counts[i + 1] > 0:
                    has_weak = True  # 12 辺張
                if n == 7 and i + 1 < suit_start + 9 and counts[i + 1] > 0:
                    has_weak = True  # 89 辺張
    if has_weak:
        tips.append('辺張（12待ちの3、89待ちの7）は有効牌1種×最大4枚と弱い')

    # テンパイ時の多面張
    if best['shanten'] == 0 and best['eff_count'] >= 8:
        tips.append(f'有効牌{best["eff_count"]}枚は多面張待ちで非常に有利')

    if not tips:
        tips.append('有効牌枚数が多い打牌を選ぶのが牌効率の基本')

    return tips


# ============================================================
# 解説文の生成
# ============================================================

def generate_explanation(hand: list, results: list) -> str:
    best = results[0]
    tile = best['tile']
    s = best['shanten']
    eff = best['effective']
    eff_count = best['eff_count']

    lines = []
    lines.append('━' * 54)
    lines.append('【答え】')

    # あがり牌（テンパイ後打牌の場合）
    if s == 0:
        lines.append(f'  打 {tile_name_jp(tile)}  →  テンパイ！')
        wait_tiles = sorted(eff.keys())
        wait_desc = classify_wait(wait_tiles, [t for t in hand if t != tile])
        lines.append(f'  待ち: {wait_desc}  ／  あがり牌 {eff_count}枚')
    else:
        lines.append(f'  打 {tile_name_jp(tile)}  →  {shanten_str(s)}  ／  有効牌 {eff_count}枚')

    lines.append('')

    # ── 有効牌の内訳 ──
    if eff:
        label = 'あがり牌' if s == 0 else '有効牌（ツモで向聴が進む牌）'
        lines.append(f'【{label}】')
        for group_str, count in _group_tiles(eff):
            lines.append(f'  {group_str}  ({count}枚)')
        lines.append('')

    # ── 手牌構造の解析 ──
    lines.append('【手牌の構造（打牌後）】')
    remaining = [t for t in hand if t != tile]
    r_counts = [0] * 34
    for t in remaining:
        r_counts[t] += 1
    blocks = _detect_blocks(r_counts)

    if blocks['mentsu']:
        lines.append('  面子: ' + '　'.join(blocks['mentsu']))
    if blocks['taatsu']:
        lines.append('  搭子: ' + '　'.join(blocks['taatsu']))
    if blocks['isolated']:
        lines.append('  孤立: ' + '　'.join(blocks['isolated']))
    lines.append('')

    # ── 考え方 ──
    lines.append('【考え方】')

    if tile >= 27:
        lines.append(f'  ・{tile_name_jp(tile)}は孤立字牌。他の牌と連携できず面子に発展しない')
    else:
        n = tile % 9 + 1
        suit = ['萬子', '筒子', '索子'][tile // 9]
        if n in (1, 9):
            lines.append(f'  ・{tile_name_jp(tile)}は{suit}の端牌（老頭牌）。搭子・面子になりにくい')
        elif n in (2, 8):
            lines.append(f'  ・{tile_name_jp(tile)}は端寄りの牌。関連する搭子がなければ効率が低い')
        else:
            lines.append(f'  ・{tile_name_jp(tile)}は{suit}の中張牌。本来は面子になりやすいが孤立している')

    lines.append('')
    if s == 0:
        wait_tiles = sorted(eff.keys())
        wait_desc = classify_wait(wait_tiles, remaining)
        lines.append(f'  → この打牌でテンパイ。{wait_desc}')
        if eff_count >= 8:
            lines.append('  → 有効牌が8枚以上の好テンパイです！')
    elif s == 1:
        lines.append('  → 一向聴になります。次のツモで有効牌を引けばテンパイです。')
    else:
        lines.append(f'  → {shanten_str(s)}になります。有効牌を引いて手を進めましょう。')

    # ── 他の候補との比較 ──
    if len(results) > 1:
        lines.append('')
        lines.append('【他の選択肢との比較】')
        for r in results[:7]:
            marker = '★ ' if r['tile'] == tile else '  '
            s2 = r['shanten']
            if s2 == 0:
                wt = sorted(r['effective'].keys())
                wd = classify_wait(wt, [t for t in hand if t != r['tile']])
                desc = f'テンパイ / {wd}（{r["eff_count"]}枚）'
            else:
                desc = f'{shanten_str(s2)} / 有効牌 {r["eff_count"]}枚'
            lines.append(f'{marker}{tile_name_jp(r["tile"])}切り → {desc}')

    # ── 牌効率のポイント ──
    tips = _efficiency_tips(hand, tile, results)
    if tips:
        lines.append('')
        lines.append('【牌効率のポイント】')
        for tip in tips:
            lines.append(f'  ・{tip}')

    lines.append('━' * 54)
    return '\n'.join(lines)


# ============================================================
# テンパイ手牌の解説（13枚でテンパイの場合）
# ============================================================

def generate_tenpai_explanation(hand: list) -> str:
    """13枚テンパイ手牌の解説：あがり牌と待ちの種類を表示"""
    counts = [0] * 34
    for t in hand:
        counts[t] += 1
    used = list(counts)
    winning = get_winning_tiles(counts, used)

    lines = []
    lines.append('━' * 54)
    lines.append('【テンパイ！あがり牌の解説】')
    lines.append('')

    if winning:
        total = sum(winning.values())
        wait_tiles = sorted(winning.keys())
        wait_desc = classify_wait(wait_tiles, hand)
        lines.append(f'  待ち: {wait_desc}')
        lines.append(f'  あがり牌: {total}枚')
        lines.append('')
        lines.append('【あがり牌の内訳】')
        for group_str, count in _group_tiles(winning):
            lines.append(f'  {group_str}  ({count}枚)')
    else:
        lines.append('  ※ 山に残るあがり牌なし（フリテン？）')

    lines.append('')
    lines.append('【手牌の構造】')
    blocks = _detect_blocks(counts)
    if blocks['mentsu']:
        lines.append('  面子: ' + '　'.join(blocks['mentsu']))
    if blocks['taatsu']:
        lines.append('  搭子（待ち形）: ' + '　'.join(blocks['taatsu']))
    if blocks['isolated']:
        lines.append('  孤立: ' + '　'.join(blocks['isolated']))

    lines.append('━' * 54)
    return '\n'.join(lines)


# ============================================================
# 問題の生成
# ============================================================

def _build_mentsu(deck_counts: list) -> list | None:
    """デッキから面子1つをランダムに取り出す。取れなければNone"""
    candidates = []
    # 順子
    for suit_start in [0, 9, 18]:
        for i in range(suit_start, suit_start + 7):
            if deck_counts[i] > 0 and deck_counts[i+1] > 0 and deck_counts[i+2] > 0:
                candidates.append(('seq', i))
    # 刻子
    for i in range(34):
        if deck_counts[i] >= 3:
            candidates.append(('tri', i))
    if not candidates:
        return None
    kind, i = random.choice(candidates)
    if kind == 'seq':
        deck_counts[i] -= 1; deck_counts[i+1] -= 1; deck_counts[i+2] -= 1
        return [i, i+1, i+2]
    else:
        deck_counts[i] -= 3
        return [i, i, i]


def _generate_tenpai_hand() -> list:
    """
    テンパイ手牌（13枚・向聴数0）を構築して返す。
    完成形（4面子+1雀頭=14枚）から1枚除いて待ちを作る。
    """
    for _ in range(500):
        deck_counts = [4] * 34
        hand = []

        # 面子を4つ取る
        ok = True
        for _ in range(4):
            m = _build_mentsu(deck_counts)
            if m is None:
                ok = False; break
            hand.extend(m)

        if not ok:
            continue

        # 雀頭を取る
        pairs = [i for i in range(34) if deck_counts[i] >= 2]
        if not pairs:
            continue
        jantai = random.choice(pairs)
        deck_counts[jantai] -= 2
        hand.extend([jantai, jantai])

        # 14枚の完成形ができた。1枚除いて13枚テンパイに
        # どの牌を除くかランダムに選ぶ（ただしシャンテン数0になるものを探す）
        random.shuffle(hand)
        for idx in range(len(hand)):
            candidate = hand[:idx] + hand[idx+1:]
            if shanten(candidate) == 0:
                return sorted(candidate)

    # フォールバック: 既知テンパイ手
    return sorted([0, 1, 2, 9, 10, 11, 18, 19, 20, 3, 4, 27, 27])


def generate_hand_and_tsumo(difficulty: str = 'normal') -> tuple:
    """
    手牌13枚とツモ牌1枚（計14枚）を生成して返す。
    戻り値: (hand_13: list, tsumo: int)
      hand_13 … ツモ前の手牌（ソート済み13枚）
      tsumo   … ツモ牌（1枚）
    difficulty:
      'easy'   → ツモ後14枚が二〜三向聴
      'normal' → ツモ後14枚が一向聴
      'hard'   → ツモ後14枚がテンパイ（向聴数0）
    """
    if difficulty == 'hard':
        # テンパイ形: 14枚完成形の1枚をツモ牌として扱う
        full = _generate_tenpai_hand()   # 13枚テンパイ
        # その手牌に有効牌（あがり牌）を1枚ツモる
        counts = [0] * 34
        for t in full:
            counts[t] += 1
        winning = [t for t in range(34) if counts[t] < 4]
        # ランダムなあがり牌を探す
        random.shuffle(winning)
        for w in winning:
            counts[w] += 1
            if is_winning_hand(counts):
                return (full, w)
            counts[w] -= 1
        # フォールバック: テンパイ手をそのままツモ牌なしで返す
        return (full, full[-1])

    target = {
        'easy':   (2, 3),
        'normal': (1, 1),
    }.get(difficulty, (1, 1))

    deck = list(range(34)) * 4
    for _ in range(500):
        random.shuffle(deck)
        full14 = deck[:14]
        # 14枚のシャンテン数で判定（13枚手牌として扱う）
        s = shanten(full14[:13])  # 13枚で判定
        # ツモ込み14枚でのシャンテン数を簡易評価
        s14 = shanten(full14)
        if target[0] <= s14 <= target[1]:
            hand13 = sorted(full14[:13])
            tsumo = full14[13]
            return (hand13, tsumo)

    # フォールバック
    random.shuffle(deck)
    return (sorted(deck[:13]), deck[13])


# ============================================================
# 問題の表示と解答
# ============================================================

def print_problem(hand13: list, tsumo: int, show_answer: bool = False, interactive: bool = True) -> None:
    """
    hand13: ツモ前の手牌13枚
    tsumo:  ツモ牌1枚
    14枚合計を表示し、何を切るか問う。
    """
    full14 = hand13 + [tsumo]
    s = shanten(full14)

    print()
    print('━' * 54)
    print('  麻雀 何切る問題')
    print('━' * 54)
    print(f'  【手牌】  {hand_str(hand13)}')
    print(f'  【ツモ】  {tile_name_jp(tsumo)}')
    print(f'  【状況】  {shanten_str(s)}')
    print()

    if s == -1:
        print('  ツモあがり！')
    else:
        print('  Q: 何を切りますか？（手牌13枚＋ツモ牌の計14枚から1枚選ぶ）')
    print()

    if interactive and not show_answer and s != -1:
        try:
            input('  → Enter を押すと答えを表示します... ')
        except (EOFError, KeyboardInterrupt):
            pass
        print()

    if show_answer or interactive:
        if s == -1:
            print('  おめでとうございます！ツモあがりです。')
        elif s == 0:
            # テンパイ維持が前提 → 打牌を探す
            results = find_best_discards(full14)
            print(generate_explanation(full14, results))
        else:
            results = find_best_discards(full14)
            print(generate_explanation(full14, results))


# ============================================================
# 複数問題モード
# ============================================================

def run_quiz(n: int = 5, difficulty: str = 'normal') -> None:
    diff_label = {'easy': '簡単（二〜三向聴）', 'normal': '普通（一向聴）', 'hard': '難しい（テンパイ形）'}
    print()
    print('=' * 54)
    print('  麻雀 何切る問題ジェネレーター')
    print(f'  難易度: {diff_label.get(difficulty, difficulty)}  ／  {n}問')
    print('=' * 54)

    for i in range(1, n + 1):
        print(f'\n【第{i}問】')
        hand13, tsumo = generate_hand_and_tsumo(difficulty)
        print_problem(hand13, tsumo, interactive=True)
        if i < n:
            try:
                cont = input('\n次の問題へ進みますか？ (Enter / q で終了): ')
                if cont.lower().strip() == 'q':
                    break
            except (EOFError, KeyboardInterrupt):
                break

    print('\n以上です。お疲れ様でした！')


# ============================================================
# デモ問題（解説確認用）
# ============================================================

# (hand13, tsumo) の形式
_DEMO = [
    ('一向聴・字牌を切る',
     [0, 1, 2, 9, 10, 11, 18, 19, 20, 3, 4, 27, 28], 5),
    ('一向聴・孤立牌 vs 搭子',
     [0, 1, 2, 9, 10, 11, 18, 19, 20, 4, 5, 7, 9], 6),
    ('テンパイ・両面待ち',
     [0, 1, 2, 9, 10, 11, 18, 19, 20, 3, 4, 27, 27], 3),
    ('テンパイ・字牌を切ってテンパイ',
     [0, 0, 1, 2, 9, 10, 11, 18, 19, 20, 3, 3, 27], 5),
]


def run_demo() -> None:
    print()
    print('=' * 54)
    print('  麻雀 何切る問題ジェネレーター  ─  デモ')
    print('=' * 54)

    for i, (desc, hand13, tsumo) in enumerate(_DEMO, 1):
        print(f'\n【デモ問題 {i}】{desc}')
        print_problem(hand13, tsumo, show_answer=True, interactive=False)
        if i < len(_DEMO):
            try:
                input('\n次へ → Enter: ')
            except (EOFError, KeyboardInterrupt):
                break

    print('\nデモ終了。続いてランダム問題を出題します。')
    run_quiz(n=3, difficulty='normal')


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == '__main__':
    args = sys.argv[1:]

    difficulty = 'normal'
    n_problems = 5
    demo_mode = False
    show_all = False

    for arg in args:
        if arg in ('easy', 'normal', 'hard'):
            difficulty = arg
        elif arg == 'demo':
            demo_mode = True
        elif arg == '--all':
            show_all = True
        elif arg.isdigit():
            n_problems = int(arg)

    if demo_mode:
        run_demo()
    elif show_all:
        # 全答え表示モード（パイプ等で使用）
        for _ in range(n_problems):
            hand13, tsumo = generate_hand_and_tsumo(difficulty)
            full14 = hand13 + [tsumo]
            s = shanten(full14)
            print(f'\n手牌: {hand_str(hand13)}  ツモ: {tile_name_jp(tsumo)}  ({shanten_str(s)})')
            results = find_best_discards(full14)
            print(generate_explanation(full14, results))
    else:
        run_quiz(n=n_problems, difficulty=difficulty)
