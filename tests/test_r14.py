"""R14 regressions: Mt. Moon, Route 4, Cerulean and Misty, each from a real
log situation where one exists. From real game logs (not in the repo): t16-2-haiku-teacher (n540),
t16-5-haiku-teacher (n295, n310, n316, n375, n648), t15-2-haiku-teacher (n402), t15-5-haiku-teacher (n545, n613).
States are the decoded post-Brock state moved to the tile (helpers of test_r12.py / test_r13.py). No emulator here.
Game facts are checked against reference/pokered and the map walker (walk_to)."""
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

DEV = Path(__file__).resolve().parents[1]
ROOT = DEV
sys.path[:0] = [str(DEV / 'tools'), str(DEV / 'arena'), str(DEV / 'tests')]
import settings  # noqa: E402
POKERED = settings.POKERED
import advise as A
import r11_maps as M
import r13_advice as T
import r14_advice as X
import test_r12 as H
import test_r13 as H3

META = H3.META
ROCKET = {'EVENT_BEAT_MT_MOON_3_TRAINER_0': True}
NERD = dict(ROCKET, EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD=True)
LEG = re.compile(r'(up|down|left|right) (\d+) to \((\d+),(\d+)\)')
ANSWERS = []          # every new answer, for the meta-word check


def wart(map_, xy, hp=None, pots=0, events=None, tackle=8, **kw):
    s = H3.wartortle(H.state(map_, xy, events=events, **kw), hp=hp, tackle=tackle)
    s['bag'] = [dict(item='POTION', count=pots)] if pots else []
    return s


def cerulean(level, pots=0, map_='CERULEAN_CITY', xy=(19, 18), hp=None, events=None):
    """Wartortle at `level` after the cave (Super Nerd beaten), Misty next."""
    s = wart(map_, xy, events=dict(NERD, **(events or {})))
    if level > 16:
        w = A._scaled(dict(A._party_mon(s['team'][0])), level)
        s['team'][0].update(species=w['species'], level=level, max_hp=w['max_hp'], hp=w['max_hp'], stats=w['stats'])
        s['team'][0]['moves'] = [dict(move=m['move'], pp=A.MOVES[m['move']]['pp']) for m in w['moves']]
    if hp is not None:
        s['team'][0]['hp'] = hp
    s['bag'] = [dict(item='POTION', count=pots)] if pots else []
    s['story'] = dict(s['story'], done=s['story']['done'] + ['mt_moon'],
                      next=dict(id='badge2', goal='Beat Misty (Cascade Badge)', done=False, part=3))
    s['part'] = 3
    return s


def ask(s, q=None, ctx=None):
    a = A.answer(s, q, context={} if ctx is None else ctx)
    ANSWERS.append(A.text(a))
    return a


def tiles(text, start):
    """Every tile a walk answer steps on (legs 'dir n to (x,y)'), from start."""
    out, (x, y) = [], start
    for d, n, tx, ty in LEG.findall(text):
        dx, dy = T.DIRS[d]
        for _ in range(int(n)):
            x, y = x + dx, y + dy
            out.append((x, y))
        x, y = int(tx), int(ty)
    return out


class MtMoonFloors(unittest.TestCase):
    def test_1_super_nerd_ask_on_1f_gets_the_floor_and_the_ladder(self):
        # Old (4x, always 1F (30,8)/(30,9)): "You may fight the Super Nerd: stand at (12,9), face up, press A once."
        cases = [((30, 8), 26, 0, "I'm in MT_MOON_1F at (30,8), facing up, Wartortle L16 26/47, Caterpie L5 20/20, no "
                                  "Potions left, money 1046. Where are the stairs/ladder to the next Mt. Moon floor and "
                                  "the Super Nerd/trainers? Give exact tiles from here."),              # t16-2 n540
                 ((30, 8), 47, 0, "I'm in Mt. Moon 1F at x=30 y=8 facing up, Wartortle L16 47/47 and Caterpie L5. "
                                  "Next: where is the Super Nerd and the way to the Mt. Moon exit / fossil?"),  # t15-2 n402
                 ((30, 8), 33, 1, "I'm in MT_MOON_1F at x=30 y=8 facing up, Wartortle L16 33/47, Caterpie L6, 1 "
                                  "Potion, money 873. What is next (the Super Nerd / fossil / exit to Route 4 and "
                                  "Cerulean)?"),                                                        # t15-5 n545
                 ((30, 9), 46, 0, "I'm MT_MOON_1F x=30 y=9 facing up with Wartortle L16 46/47, Caterpie L6 22/22, 1 "
                                  "Poke Ball, money 436. Where is the Super Nerd and the fossil, and is it safe to go "
                                  "on?")]                                                               # t15-5 n613
        for xy, hp, pots, q in cases:
            with self.subTest(xy=xy, hp=hp):
                a = ask(wart('MT_MOON_1F', xy, hp, pots), q)
                text = A.text(a)
                self.assertIn('B2F', a['do'])
                self.assertIn('(5,5)', a['do'])
                self.assertNotIn('stand at (12,9)', text)
                self.assertNotIn('You may fight', text)
                self.assertFalse(set(tiles(a['do'], xy)) & set(X.LASS_SIGHT), a['do'])     # the walk goes around

    def test_2_entrance_walk_never_enters_the_lass_sight(self):
        # t16-5 n285 arrived at 1F (14,35); old walk ended "up 2 to (30,8). Then stop before the trainer".
        s = wart('MT_MOON_1F', (14, 35))
        a = ask(s)
        text = A.text(a)
        self.assertIn('(31,3)', text)
        self.assertNotIn('stop before the trainer', text)
        walked = tiles(a['do'] + ' ' + ' '.join(a['details']), (14, 35))
        self.assertTrue(walked and walked[-1] == (5, 5), walked[-3:])
        self.assertFalse(set(walked) & set(X.LASS_SIGHT))

    def test_3_below_the_lass_go_around(self):
        # t16-5 n294 (30,8): five blackouts vs this Lass followed (n325-552).
        a = ask(wart('MT_MOON_1F', (30, 8)), 'Which way?')
        self.assertIn('Do not walk up: the Lass at (30,4) sees (30,5)-(30,7). Go around', a['do'])
        self.assertIn('right 1 to (31,8)', a['do'])
        self.assertIn('up 5 to (31,3)', a['do'])
        fight = ask(wart('MT_MOON_1F', (30, 8)), 'Can I fight the Lass for EXP?')
        self.assertIn('Never WATER GUN or BUBBLE', A.text(fight))

    def test_4_side_ladder_warning(self):
        # t16-5 n648: took 1F (17,11) -> B1F (25,9), the Mega Punch pocket (game ended there at n649).
        a = ask(wart('MT_MOON_1F', (17, 10), 47), 'Which ladder now?')
        self.assertIn('side room', a['do'])
        self.assertIn('(5,5)', a['do'])
        b = ask(wart('MT_MOON_B1F', (23, 11), 47), 'where now?')       # t16-5 n649 position
        self.assertIn('side branch', b['do'])
        self.assertIn('(25,9)', b['do'])
        c = ask(wart('MT_MOON_1F', (25, 14), 47), 'Which ladder now?')
        self.assertIn('Not the ladder at (25,15)', c['do'])

    def test_5_b1f_to_the_b2f_ladder(self):
        a = ask(wart('MT_MOON_B1F', (5, 6)), 'Where now?')
        self.assertIn('(21,17)', a['do'])
        self.assertIn('down 11 to (5,17), right 16 to (21,17)', a['do'])

    def test_6_b2f_long_loop_to_the_needed_rocket(self):
        a = ask(wart('MT_MOON_B2F', (21, 17)), 'Where now?')
        self.assertIn('(11,21)', a['do'])
        self.assertIn('Rocket at (11,16)', a['do'])
        self.assertIn('needed', a['do'])
        self.assertTrue(a['do'].count(' to (') >= 11, a['do'])
        at = ask(wart('MT_MOON_B2F', (11, 21)), 'Am I ready for this Rocket?')
        self.assertRegex(at['do'], r'^Ready: the Rocket at \(11,16\)')
        self.assertIn('Step up 1 to (11,20)', at['do'])

    def test_7_super_nerd_at_his_tile(self):
        a = ask(wart('MT_MOON_B2F', (12, 9), events=ROCKET), 'Can I beat the Super Nerd?')
        self.assertIn('Super Nerd', a['do'])
        self.assertRegex(a['do'], r'(?i)face up')
        self.assertIn('press A', a['do'])
        self.assertIn('likely win', a['do'])
        self.assertIn('right 1 to (13,9), up 2 to (13,7)', A.text(a))

    def test_8_fossil_box_says_yes(self):
        s = H3.text_state('MT_MOON_B2F', (13, 7), ['You want the', 'HELIX FOSSIL?', 'YES', 'NO'], True, events=NERD)
        a = ask(s, 'What do I press?')
        self.assertIn('Press A for YES', a['do'])
        self.assertNotIn('Press B to say NO', A.text(a))
        self.assertIn('(5,7)', a['do'])
        ctx, out = {}, None
        for _ in range(3):
            out = ask(s, 'What now?', ctx)
        self.assertIn('press A once now', out['do'])
        self.assertNotRegex(out['do'], r'press these in ONE command: b')
        dome = H3.text_state('MT_MOON_B2F', (12, 7), ['You want the', 'DOME FOSSIL?'], True, events=NERD)
        self.assertIn('Press A for YES', ask(dome, 'what?')['do'])

    def test_9_with_the_fossil_the_way_out(self):
        s = wart('MT_MOON_B2F', (12, 9), events=dict(NERD, EVENT_GOT_HELIX_FOSSIL=True))
        s['bag'] = [dict(item='HELIX_FOSSIL', count=1), dict(item='ESCAPE_ROPE', count=1)]
        text = A.text(ask(s, 'What now?'))
        self.assertIn('(5,7)', text)
        self.assertIn('(27,3)', text)
        self.assertNotRegex(text, r'(?<!not )\b[Uu]se (your |an )?Escape Rope')
        b1 = wart('MT_MOON_B1F', (23, 3), events=dict(NERD, EVENT_GOT_HELIX_FOSSIL=True))
        b1['bag'] = [dict(item='HELIX_FOSSIL', count=1)]
        self.assertIn('right 4 to (27,3)', ask(b1, 'Where is the exit?')['do'])


class CaveHealing(unittest.TestCase):
    def test_10_enough_hp_means_no_center_trip(self):
        # t16-5 n295: 34/47, 1 Potion, Tackle 8 PP -> old answer walked back to the Center (n303-308).
        q = ("I'm in MT_MOON_1F at (30,8). Wartortle L16 34/47 HP with 8 Tackle PP, Caterpie L5, 1 Potion, 697 money. "
             "What's the next step through Mt. Moon toward the exit to Cerulean, and should I heal first?")
        a = ask(wart('MT_MOON_1F', (30, 8), 34, 1), q)
        self.assertIn('No need', a['do'])
        self.assertIn('34/47', a['do'])
        self.assertIn('right 1 to (31,8)', a['do'])
        self.assertNotIn('POKECENTER', A.text(a))

    def test_11_lost_at_full_hp_gets_the_ladder_not_the_rope(self):
        s = wart('MT_MOON_B1F', (5, 6))
        s['bag'] = [dict(item='ESCAPE_ROPE', count=1)]
        a = ask(s, "I'm lost, where is the next ladder?")
        self.assertIn('(21,17)', a['do'])
        self.assertNotIn('Escape Rope', A.text(a))
        self.assertNotIn('POKECENTER', A.text(a))

    def test_12_low_hp_no_potions_goes_back_to_the_route_4_center(self):
        a = ask(wart('MT_MOON_B1F', (5, 6), 10), 'Should I heal?')
        self.assertIn('Route 4 Center', a['do'])
        self.assertIn('(11,5)', a['do'])

    def test_13_low_hp_with_potions_uses_them(self):
        a = ask(wart('MT_MOON_B1F', (5, 6), 10, 2), 'Should I heal?')
        self.assertRegex(a['do'], r'^Use 1 Potion now')
        self.assertIn('POTION', a['do'])
        self.assertNotIn('Route 4 Center', a['do'])


class Route4(unittest.TestCase):
    def test_14_west_route_4_has_no_way_east(self):
        for xy, q in [((19, 6), "I'm on ROUTE_4 at (19,6), blocked going right. Wartortle L16 47/47, Caterpie L5, 1 "
                                "Potion, 697 money. Which way leads east to Cerulean City, and what is the next step "
                                "toward the Cerulean Gym?"),                                            # t16-5 n310
                      ((19, 15), "I'm on ROUTE_4 at (19,15), walled off to the east. Which exact path on Route 4 gets "
                                 "me east to Cerulean City, avoiding the rock wall?"),                   # t16-5 n316
                      ((19, 6), "I'm on ROUTE_4 at (19,6). Going right is blocked by a ledge. I want to reach "
                                "CERULEAN_CITY. Give me the exact tile route.")]:                        # t16-5 n375
            with self.subTest(xy=xy):
                a = ask(wart('ROUTE_4', xy, 47, 1), q)
                for word in ('only way', 'Mt. Moon', '(18,5)', '(24,5)'):
                    self.assertIn(word, a['do'])
                self.assertNotIn('Leave Pewter east', A.text(a))

    def test_15_heal_at_the_route_4_center_before_the_cave(self):
        # t16-2 entered at 26/47 without healing there; its blackout (n586) sent it back to Pewter.
        s = wart('ROUTE_4', (12, 6), 30)
        s['last_heal_map'] = 'PEWTER_CITY'
        a = ask(s, 'What next?')
        for word in ('Heal at the Center first', '(11,5)', 'blackout', 'not to Pewter'):
            self.assertIn(word, a['do'])
        full = wart('ROUTE_4', (12, 6))
        full['last_heal_map'] = 'PEWTER_CITY'
        self.assertIn('Heal at the Center first', ask(full, 'What next?')['do'])
        done = wart('ROUTE_4', (12, 6))
        done['last_heal_map'] = 'ROUTE_4'
        self.assertNotIn('Heal at the Center first', ask(done, 'What next?')['do'])

    def test_16_east_route_4_ledges_to_cerulean(self):
        a = ask(wart('ROUTE_4', (24, 6), events=NERD))
        for word in ('(24,10)', 'Cerulean', 'one-way'):
            self.assertIn(word, a['do'])


class CeruleanMisty(unittest.TestCase):
    def test_17_hurt_arrival_heals_at_the_center(self):
        a = ask(cerulean(16, hp=20))
        self.assertIn('(19,17)', a['do'])
        self.assertIn('ready for Misty', a['do'])

    def test_18_misty_not_ready_gives_a_level_and_a_place(self):
        a = ask(cerulean(16), 'Am I ready for Misty?')
        self.assertIn('Not ready', a['do'])
        self.assertIn('L25', a['do'])
        self.assertIn('Route 4 grass', a['do'])
        self.assertIn('Do not switch in CATERPIE', a['do'])
        self.assertIn('L24', ask(cerulean(16, pots=3), 'Am I ready for Misty?')['do'])
        b = ask(cerulean(20), 'Where should I train before Misty?')
        self.assertIn('rival', b['do'])
        self.assertIn('Nugget Bridge', b['do'])
        self.assertNotIn('Oddish is optional', b['do'])

    def test_19_misty_ready(self):
        a = ask(cerulean(25), 'Am I ready for Misty?')
        self.assertTrue(a['do'].startswith('Ready'), a['do'])
        self.assertIn('BITE', a['do'])
        self.assertIn('Never WATER GUN', a['do'])
        self.assertIn('(30,19)', a['do'])

    def test_20_one_fight_model(self):
        # The verdict and every "likely" line come from r13_advice.outcome; the old A.fight is never called.
        with patch.object(A, 'fight', side_effect=AssertionError('old fight model used')):
            for lv, pots in ((16, 0), (22, 8), (25, 0)):
                s = cerulean(lv, pots)
                a = ask(s, 'Am I ready for Misty?')
                keys, _ = X.gym_keys(A, s)
                win = X.ok(T.outcome(A, T.mons(A, s, True), keys, pots))
                self.assertEqual(a['do'].startswith('Ready'), win, (lv, pots, a['do']))
                self.assertIn('Misty: likely ' + ('win' if win else 'loss'), A.text(a))
                ask(s, 'Can I beat the rival?')

    def test_21_rival_readiness(self):
        self.assertIn('Not ready', ask(cerulean(18), 'Can I beat the rival?')['do'])
        self.assertIn('likely win', ask(cerulean(20), 'Can I beat the rival?')['do'])

    def test_22_cerulean_mart(self):
        text = A.text(ask(cerulean(16), 'What does the Cerulean Mart sell?'))
        for word in ('300', 'No Super Potions', 'Repel 350', '(25,25)'):
            self.assertIn(word, text)

    def test_catch_questions_say_levels_help_more(self):
        for map_, xy, q, why in [('CERULEAN_CITY', (19, 18), 'Should I catch Oddish?', 'past the rival'),
                                 ('ROUTE_4', (30, 10), 'Should I go catch a Pikachu for Misty?', 'Viridian Forest'),
                                 ('MT_MOON_1F', (20, 20), 'Should I catch Paras?', 'no Grass attack')]:
            with self.subTest(q=q):
                s = cerulean(16, map_=map_, xy=xy) if map_ != 'MT_MOON_1F' else wart(map_, xy)
                a = ask(s, q)
                self.assertIn('Not needed for Misty', a['do'])
                self.assertIn(why, a['do'])


class Battle(unittest.TestCase):
    def test_23_wild_paras_do_and_best_move_agree(self):
        s = H.in_battle(wart('MT_MOON_1F', (20, 20)), 'PARAS', 10, kind='wild')
        a = ask(s, 'Which move?')
        self.assertTrue(a['do'].startswith('Use TACKLE'), a['do'])
        best = next(d for d in a['details'] if d.startswith('Best move now'))
        self.assertIn('TACKLE', best)

    def test_24_misty_battle_never_picks_water(self):
        for lv, foe, foe_lv in ((16, 'STARMIE', 21), (25, 'STARMIE', 21), (16, 'STARYU', 18)):
            with self.subTest(lv=lv, foe=foe):
                s = H.in_battle(cerulean(lv, map_='CERULEAN_GYM', xy=(4, 3)), foe, foe_lv)
                a = ask(s, 'Which move?')
                self.assertNotRegex(a['do'], r'WATER_GUN|BUBBLE')
                self.assertTrue(any('faster' in d and 'Speed' in d for d in a['details']), a['details'])
        self.assertIn('BITE', ask(H.in_battle(cerulean(25, map_='CERULEAN_GYM', xy=(4, 3)), 'STARMIE', 21),
                                  'move?')['do'])


class Facts(unittest.TestCase):
    def test_25_no_confusion_l10_anywhere(self):
        for f in [DEV / 'kb/kb.json', DEV / 'kb/KB.md', DEV / 'kb/parts/03-cerulean-misty.md',
                  DEV / 'tools/r11_advice.py']:
            self.assertNotIn('Confusion L10', f.read_text(encoding='utf-8'), f)
        evos = (POKERED / 'data/pokemon/evos_moves.asm').read_text(encoding='utf-8')
        butterfree = evos.split('ButterfreeEvosMoves:')[1].split('EvosMoves:')[0]
        self.assertIn('db 12, CONFUSION', butterfree)
        self.assertNotIn('Confusion L10', A.text(A.answer(cerulean(16), 'Should I catch Oddish?')))

    def test_mt_moon_needed_fights_and_pockets_match_the_map(self):
        s = wart('MT_MOON_1F', (14, 35))
        self.assertIsNotNone(A.walk_to(s, L_goal('MT_MOON_1F', (5, 5)), max_maps=0, fallback=False))   # no 1F fight
        for i in range(4):
            b2 = wart('MT_MOON_B2F', (21, 17), events={f'EVENT_BEAT_MT_MOON_3_TRAINER_{i}': True})
            r = A.walk_to(b2, L_goal('MT_MOON_B2F', (12, 9)), max_maps=0, fallback=False)
            self.assertEqual(r is not None, i == 0, i)            # only the Rocket at (11,16) is needed
        nerd = wart('MT_MOON_B2F', (12, 9), events=NERD)
        self.assertIsNone(A.walk_to(nerd, L_goal('MT_MOON_B2F', (5, 7)), max_maps=0, fallback=False))
        nerd['bag'] = [dict(item='HELIX_FOSSIL', count=1)]
        self.assertIsNotNone(A.walk_to(nerd, L_goal('MT_MOON_B2F', (5, 7)), max_maps=0, fallback=False))
        pockets = {('MT_MOON_B1F', (25, 9)): [(17, 11), (25, 9)], ('MT_MOON_B1F', (25, 15)): [(25, 15), (13, 27)],
                   ('MT_MOON_B1F', (5, 5)): [(5, 5), (21, 17)], ('MT_MOON_B2F', (25, 9)): [(25, 9)],
                   ('MT_MOON_B2F', (15, 27)): [(15, 27)], ('MT_MOON_B2F', (21, 17)): [(21, 17)]}
        for (m, xy), warps in pockets.items():
            with self.subTest(m=m, xy=xy):
                self.assertEqual(sorted(X.pocket(A, wart(m, xy))), sorted(warps))
        self.assertEqual(M.sight(wart('MT_MOON_1F', (14, 35)), 'MT_MOON_1F') & {(30, y) for y in range(3, 10)},
                         set(X.LASS_SIGHT))

    def test_route_4_west_cannot_reach_the_east_side(self):
        for xy in ((19, 6), (19, 15), (12, 6)):
            s = wart('ROUTE_4', xy, events={e: True for e in M.events()})
            self.assertIsNone(A.walk_to(s, lambda m, p: m == 'ROUTE_4' and p[0] >= 22, max_maps=0, fallback=False))

    def test_blackout_and_escape_rope_go_to_the_last_center_town(self):
        center = (POKERED / 'engine/events/pokecenter.asm').read_text(encoding='utf-8')
        self.assertLess(center.index('jr nz, .declinedHealing'), center.index('call SetLastBlackoutMap'))
        self.assertIn('ld a, [wLastMap]\n\tld [wLastBlackoutMap], a',
                      (POKERED / 'engine/events/set_blackout_map.asm').read_text(encoding='utf-8'))
        self.assertIn('.Route4:         fly_warp ROUTE_4,         11,  6',
                      (POKERED / 'data/maps/special_warps.asm').read_text(encoding='utf-8'))
        self.assertIn('bit BIT_ESCAPE_WARP, [hl]\n\tres BIT_ESCAPE_WARP, [hl]\n\tjr z, .otherDestination\n'
                      '\tld a, [wLastBlackoutMap]',
                      (POKERED / 'engine/overworld/special_warps.asm').read_text(encoding='utf-8'))

    def test_marts_wild_and_misty_facts(self):
        marts = (POKERED / 'data/items/marts.asm').read_text(encoding='utf-8')
        pewter = marts.split('PewterMartClerkText::')[1].split('\n\n')[0]
        cerulean_ = marts.split('CeruleanMartClerkText::')[1].split('\n\n')[0]
        self.assertNotIn('REPEL', pewter)
        self.assertIn('REPEL', cerulean_)
        self.assertNotIn('SUPER_POTION', marts.split('VermilionMartClerkText::')[0])
        self.assertIn('SUPER_POTION', marts.split('VermilionMartClerkText::')[1].split('\n\n')[0])
        self.assertIn('bcd3 350   ; REPEL', (POKERED / 'data/items/prices.asm').read_text(encoding='utf-8'))
        self.assertEqual(A.TEAMS['Misty:1']['party'][1]['moves'], ['TACKLE', 'WATER_GUN', 'BUBBLEBEAM'])
        forest = (POKERED / 'data/wild/maps/ViridianForest.asm').read_text(encoding='utf-8')
        self.assertIn('PIKACHU', forest)
        self.assertNotIn('PIKACHU', ''.join((POKERED / f'data/wild/maps/{m}.asm').read_text(encoding='utf-8')
                                            for m in ('Route3', 'Route4', 'MtMoon1F', 'MtMoonB1F', 'MtMoonB2F',
                                                      'Route24', 'Route25')))
        grass = T.grass_tiles(A, 'ROUTE_24') | T.grass_tiles(A, 'ROUTE_25')
        goal = lambda m, p: m in ('ROUTE_24', 'ROUTE_25') and p in grass
        self.assertIsNone(A.walk_to(cerulean(16), goal, max_maps=3, fallback=False))
        everyone = cerulean(16, events={e: True for e in M.events()})
        self.assertIsNotNone(A.walk_to(everyone, goal, max_maps=3, fallback=False))

    def test_exp_numbers_follow_the_game_formula(self):
        self.assertEqual(X.trainer_exp(A, 'Swimmer:1'), 614)                 # Horsea 83, Shellder 97, L16, x1.5
        self.assertEqual(X.trainer_exp(A, 'Rival1:8'), 1084)
        self.assertEqual(X.trainer_exp(A, 'Swimmer:1') + X.trainer_exp(A, 'JrTrainerF:1'), 1065)
        self.assertEqual(len(X.bridge_keys(A)), 6)

    def test_26_no_meta_words_in_new_answers(self):
        cases = [(wart('MT_MOON_1F', (30, 8), 26), 'Where is the Super Nerd?'), (wart('MT_MOON_B2F', (21, 17)), None),
                 (wart('MT_MOON_B1F', (5, 6), 10), 'should I heal?'), (wart('ROUTE_4', (19, 6)), 'way east blocked'),
                 (cerulean(16), 'Am I ready for Misty?'), (cerulean(25), 'Am I ready for Misty?'),
                 (cerulean(18), 'Can I beat the rival?'), (cerulean(16), 'Should I catch Oddish?')]
        for s, q in cases:
            ask(s, q)
        for text in ANSWERS:
            self.assertIsNone(META.search(text), text)


def menu(s, rows):
    """The same state with the START menu / bag screen open (rows as play.py screen_text reads them in round 15/16)."""
    return dict(s, text_box=True, teacher_screen=dict(rows=rows, cursor=True))


class SolR14Fixes(unittest.TestCase):
    """Review R14, both blocking cases. Menu flow: reference/pokered engine/menus/start_sub_menus.asm
    (after a Potion `jp StartMenu_Item` reopens the bag; B in the bag -> START menu), home/start_menu.asm (B closes it),
    engine/items/item_effects.asm (the "recovered by" text waits for A or B)."""

    def test_sol_b1_potion_answer_says_how_to_close_the_menu(self):
        # Sol case: B1F (5,6), Wartortle L16 10/47, two Potions -> "Use 1 Potion".
        a = ask(wart('MT_MOON_B1F', (5, 6), 10, pots=2), 'I have 10/47 HP, should I heal?')
        self.assertRegex(a['do'], r'^Use 1 Potion now')
        self.assertIn('then A to close the "recovered by" text', a['do'])
        self.assertIn('Then press B until the menu is closed (2 times: the bag, then the START menu); only then walk',
                      a['do'])
        # After the recovery: "What next?" used to say "Press A to go on ... Then down 11 ..." (A reopens the bag,
        # and the directions only move the menu arrow).
        after = menu(wart('MT_MOON_B1F', (5, 6), 30, pots=1), ['WARTORTLE   16', 'WARTORTLE', 'recovered by 20!'])
        b = ask(after, 'What next?')
        self.assertNotIn('Press A to go on', b['do'])
        self.assertIn('Press A once to close this text: you are back in the bag', b['do'])
        self.assertNotIn('more Potion', b['do'])                       # 30/47: no second Potion needed
        close, walk = b['do'].index('press B until the menu is closed'), b['do'].index('down 11 to (5,17)')
        self.assertLess(close, walk)
        self.assertIn('Only then walk', b['do'])
        # Two Potions planned (3/47): after the first one the next comes from the open bag, then B, then walk.
        two = ask(wart('MT_MOON_B1F', (5, 6), 3, pots=2), 'should I heal?')
        self.assertRegex(two['do'], r'^Use 2 Potions now')
        self.assertIn('the bag stays open, so repeat from A on POTION until you used 2', two['do'])
        mid = ask(menu(wart('MT_MOON_B1F', (5, 6), 23, pots=1), ['WARTORTLE   16', 'WARTORTLE', 'recovered by 20!']),
                  'What next?')
        self.assertIn('Use 1 more Potion now: the arrow is still on POTION: press A on POTION, press A on USE, pick '
                      'WARTORTLE, press A', mid['do'])
        self.assertLess(mid['do'].index('more Potion'), mid['do'].index('press B until the menu is closed'))
        for text in (A.text(a), A.text(b), A.text(two), A.text(mid)):
            self.assertIsNone(META.search(text), text)

    def test_sol_b1_open_menu_walk_answers_close_it_with_b_first(self):
        s = wart('MT_MOON_B1F', (5, 6), 30, pots=1)
        for rows, press in [(['POKéDEX', 'POKéMON', 'ITEM', 'SAVE', 'OPTION', 'EXIT'], 'Press B once to close it'),
                            (['POTION', 'CANCEL', 'EXIT'], 'Press B until the menu is closed'),
                            (['POTION', 'CANCEL', 'USE', 'TOSS'], 'Press B until the menu is closed'),
                            (['WARTORTLE   16', 'Use item on which', 'POKéMON?'], 'Press B until the menu is closed')]:
            with self.subTest(rows=rows):
                a = ask(menu(s, rows), 'Where now?')
                self.assertNotIn('Press A to go on', a['do'])
                self.assertLess(a['do'].index(press), a['do'].index('down 11 to (5,17)'))
                self.assertIsNone(META.search(A.text(a)))
        # Not a bag: the Center heal box and shop menus keep their own answers.
        self.assertIsNone(T.menu_kind(menu(s, ['HEAL', 'CANCEL', 'POKéMON back to', 'perfect health!'])))
        self.assertIsNone(T.menu_kind(menu(s, ['BUY', 'SELL', 'QUIT'])))

    def test_sol_b2_misty_from_her_talk_tile_ignores_the_bypassed_swimmer(self):
        # Sol case: Gym (4,3), Goldeen trainer beaten, Swimmer unbeaten, healthy Wartortle L24 + Caterpie L5, 1 Potion.
        # Old: "Not ready... L25" plus rival / Nugget Bridge training (the walker rejects a zero-step goal).
        s = cerulean(24, pots=1, map_='CERULEAN_GYM', xy=(4, 3), events={'EVENT_BEAT_CERULEAN_GYM_TRAINER_0': True})
        self.assertEqual([(t['species'], t['level'], t['hp'] == t['max_hp']) for t in s['team']],
                         [('WARTORTLE', 24, True), ('CATERPIE', 5, True)])
        self.assertFalse(M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_1'))
        self.assertEqual(X.gym_keys(A, s)[0], ['Misty:1'])
        a = ask(s, 'Am I ready for Misty?')
        text = A.text(a)
        self.assertRegex(a['do'], r'^Ready \(estimate\): you stand next to Misty\. Face up and press A')
        for word in ('Not ready', 'L25', 'Nugget', 'rival', 'Swimmer (Horsea'):
            self.assertNotIn(word, a['do'])
        self.assertIn('healed first: Misty: likely win.', text)
        self.assertEqual(a['verdict'], 'ready')
        self.assertIsNone(META.search(text), text)
        # One step away the walker still decides; the Swimmer stays out because the bypass walk exists.
        near = cerulean(24, pots=1, map_='CERULEAN_GYM', xy=(4, 4), events={'EVENT_BEAT_CERULEAN_GYM_TRAINER_0': True})
        self.assertEqual(X.gym_keys(A, near)[0], ['Misty:1'])


def L_goal(map_, xy):
    return lambda m, p: m == map_ and p == xy


if __name__ == '__main__':
    unittest.main()
