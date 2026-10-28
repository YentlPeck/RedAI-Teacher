"""Offline regressions for R15_REPLAY items 1-10. R15_TEST_DEV selects the unchanged baseline."""
import os
import re
import sys
import unittest
from pathlib import Path

DEV = Path(os.environ.get('R15_TEST_DEV', Path(__file__).resolve().parents[1]))
sys.path[:0] = [str(DEV / p) for p in ('tools', 'arena', 'tests')]
import settings  # noqa: E402
import advise as A
import test_r12 as H
import test_r14 as X
import play


def decoded_shop(lines, map_='PEWTER_MART', **extra):
    """Use the live, unchanged decoder on synthetic wTileMap bytes, without a game."""
    memory = bytearray(0x10000)
    chars = {c: t for t, c in H.R.CHARS.items() if t >= 0x7f and len(c) == 1}
    for row, text in enumerate(lines):
        for col, char in enumerate(text):
            memory[0xC3A0 + row * 20 + col] = chars.get(char, 0xed if char == '>' else 0x7f)
    rows = play.screen_text(memory)
    return H.state(map_, (2, 5), money=1672, bag=[], text_box=True,
                   teacher_screen=dict(rows=rows, cursor=True), **extra)


def ask(s, q=None, context=None):
    return A.answer(s, q, context={} if context is None else context)


def scrolled_confirmation(mart, n, background):
    """Build the final tile rows from text_4.asm and home/text.asm's two scrolls."""
    tiles = [[' '] * 20 for _ in range(18)]

    def put(row, col, text):
        tiles[row][col:col + len(text)] = text

    put(1, 1, 'MONEY 1672')
    for row, item in zip((3, 5, 7), background):
        put(row, 1, item)
    put(14, 1, 'POTION?')
    put(16, 1, 'That will be')
    # _ContText calls ScrollTextUpOneLine twice; each copies rows 14..16
    # onto 13..15 and clears the text area of row 16. POTION? scrolls away.
    for _ in range(2):
        tiles[13:16] = [row[:] for row in tiles[14:17]]
        tiles[16][1:19] = [' '] * 18
    put(16, 1, f'{300 * n}. OK?')
    # pokemart.asm places the YES/NO menu at (14,7), above the dialogue.
    put(8, 15, 'YES')
    put(10, 15, 'NO')
    return decoded_shop([''.join(row) for row in tiles], mart)


def shop(rows, money=1672, bag=None):
    return H.state('PEWTER_MART', (2, 5), money=money, bag=bag or [], text_box=True,
                   teacher_screen=dict(rows=rows, cursor=True))


class ReplayFixes(unittest.TestCase):
    def test_01_buy_list_selects_potion_before_a(self):
        for cursor, move in [('POKE BALL', 'down 1'), ('ESCAPE ROPE', 'up 1')]:
            rows = ['MONEY 1672'] + [('▶' if x.startswith(cursor) else '') + x for x in
                                    ['POKE BALL 200', 'POTION 300', 'ESCAPE ROPE 550', 'CANCEL']]
            a = ask(shop(rows), 'How many Potions?')['do']
            self.assertIn(move, a)
            self.assertIn('POTION', a)
            self.assertIn('3 Potions (900)', a)
            self.assertRegex(a, r'A.*up 2.*A.*YES')
            self.assertNotIn('highlighted choice', a)

    def test_01_wrong_quantity_and_confirmation_cancel(self):
        for rows in [['ESCAPE ROPE', 'HOW MANY?', 'x03 1650'],
                     ['ESCAPE ROPE?', 'That will be', '1650. OK?', 'YES', 'NO']]:
            a = ask(shop(rows), 'How many Potions?')['do']
            self.assertTrue(a.startswith('Press B'), a)
            self.assertIn('ESCAPE ROPE', a)
            self.assertIn('POTION', a)

    def test_01_sell_rope_uses_bag_count_and_half_price(self):
        a = ask(shop(['MONEY', 'ESCAPE ROPE', 'CANCEL', 'What would you', 'like to sell?'],
                     bag=[dict(item='ESCAPE_ROPE', count=3)]), 'How do I sell all three Escape Ropes?')['do']
        self.assertIn('ESCAPE ROPE', a)
        self.assertIn('up 2', a)
        self.assertIn('825', a)
        self.assertIn('YES', a)
        self.assertNotIn('BUY is the top', a)

    def test_02_healthy_and_healed_do_not_request_center(self):
        for word in ['healthy', 'healed', 'healing done']:
            a = ask(H.state('ROUTE_3', (9, 8), hp=31), f"I'm {word} with full HP. Where is Mt. Moon?")['do']
            self.assertNotIn('toward PEWTER POKECENTER', a)
            self.assertIn('Mt. Moon', a)
        a = ask(H.state('PEWTER_CITY', (13, 26), hp=31),
                'I visited the Pokemon Center. How do I reach Route 3?')['do']
        self.assertIn('ROUTE 3', a)
        self.assertNotIn('toward PEWTER POKECENTER', a)

    def test_02_should_heal_counts_potions(self):
        s = H.state('ROUTE_3', (19, 6), level=15, hp=26, events=H.beaten(*range(8)),
                    bag=[dict(item='POTION', count=3)])
        a = ask(s, 'Where is the Mt. Moon entrance and should I heal first?')['do']
        self.assertNotIn('toward PEWTER POKECENTER', a)
        self.assertRegex(a, r'Potion|No need to heal')

    def test_03_adjacent_unbeaten_bug_catcher_gets_talk_buttons(self):
        for q in [None, 'What should I do?', 'What route can I take from 11,6?',
                  "I'm beside the Bug Catcher. How do I start the battle?"]:
            a = ask(H.state('ROUTE_3', (11, 6), hp=31), q)['do']
            self.assertIn('left once', a)
            self.assertIn('press A', a)
            self.assertNotIn('up 1 to (11,5)', a)

    def test_03_trainer_dialogue_never_walks_away(self):
        s = H.state('ROUTE_3', (11, 6), hp=31, text_box=True,
                    teacher_screen=dict(rows=['Hey! I met you in', 'VIRIDIAN FOREST!'], cursor=False))
        a = ask(s, 'Which move now?')['do']
        self.assertIn('press A once', a)
        self.assertNotIn('up 1 to (11,5)', a)
        self.assertNotIn('sign or person', a)

    def test_04_training_has_target_and_stop(self):
        s = H.state('ROUTE_2', (7, 3), level=12, events=H.beaten(0))
        for q in ['How many levels should I train?', 'Should I keep training?']:
            a = ask(s, q)['do']
            self.assertRegex(a, r'(?:until|to) about L13')
            self.assertIn('then ask', a.lower())

    def test_05_bridge_is_exp_advice(self):
        for q in ['Should I do the bridge before Misty?', 'Is the bridge worth it?']:
            a = ask(X.cerulean(16, map_='ROUTE_24', xy=(11, 33)), q)
            self.assertIn('Nugget Bridge', a['do'])
            self.assertIn('EXP', A.text(a))
            self.assertNotIn('Oddish', a['do'])
            self.assertIn('Misty', A.text(a))

    def test_06_full_hp_center_named_in_history_mart_wins(self):
        a = ask(H.state('PEWTER_POKECENTER', (3, 3), hp=31),
                "I'm healed, standing at (3,3) inside the Pewter Center. Give me the route to the Pewter Mart")['do']
        self.assertIn('MART', a)
        self.assertFalse(a.startswith('To heal:'), a)

    def test_07_mt_moon_readiness_checks_the_rocket(self):
        s = H.state('ROUTE_2', (7, 3), level=12, events=H.beaten(0))
        a = ask(s, 'Is Squirtle ready for Mt. Moon now?')['do']
        self.assertIn('Rocket', a)
        self.assertNotIn('No boss before', a)
        self.assertRegex(a, r'likely win|likely loss|Train|Potion|heal')

    def test_08_truncated_walk_does_not_give_inside_steps(self):
        a = ask(H.state('PEWTER_CITY', (16, 20), hp=10), 'Am I ready?')['do']
        self.assertNotIn('Inside:', a)
        self.assertIn('ask again', a)

    def test_09_nurse_finishes_with_b(self):
        for rows in [['We hope to see', 'you again!'], ['Shall we heal your', 'POKEMON?', 'YES', 'NO'],
                     ['Thank you!', 'Your POKEMON are', 'fighting fit!']]:
            s = H.state('PEWTER_POKECENTER', (3, 3), text_box=True,
                        teacher_screen=dict(rows=rows, cursor=True))
            a = ask(s, 'What next?')['do']
            self.assertIn('press B once', a)
            self.assertNotIn('until the box closes', a)
            self.assertIn('walk', a)

    def test_10_cerulean_shopping_names_amount(self):
        s = dict(X.cerulean(16, map_='CERULEAN_MART', xy=(3, 5)), money=900)
        a = ask(s, 'What should I buy for Misty?')['do']
        self.assertIn('3 Potions (900)', a)
        self.assertIn('POTION', a)

    def test_11_b2f_can_try_rocket_when_model_wins(self):
        s = X.wart('MT_MOON_B2F', (21, 17), hp=20)
        a = ask(s, 'What next? Am I ok?')['do']
        self.assertIn('Rocket', a)
        self.assertIn('likely win', a)
        self.assertNotIn('Go back to the Route 4 Center', a)


class MtMoonFixes(unittest.TestCase):
    def test_12_blocked_question_never_probes_lass_sight(self):
        # t17-5 n380/383, t17-4 n506: a blocked question must keep the safe floor goal.
        s = X.wart('MT_MOON_1F', (30, 8))
        for context in [{}, {'r12_blocked': ['MT_MOON_1F', [30, 7]]}]:
            a = ask(s, 'North is blocked. Where is the ladder to B1F?', context)
            self.assertIn('Go around', a['do'])
            self.assertNotIn('press up once', a['do'])
            self.assertIn('(5,5)', a['do'])
        # Once inside sight the trainer is already engaging; do not offer an escape walk.
        a = ask(X.wart('MT_MOON_1F', (30, 7)), 'North is blocked. Where now?')['do']
        self.assertIn('press A', a)
        self.assertNotIn('Go around', a)

    def test_13_leave_before_fossil_returns_to_entrance(self):
        # t17-7 n639: "leave" must not send the player back to the Lass checkpoint.
        for xy in [(14, 29), (30, 8)]:
            a = ask(X.wart('MT_MOON_1F', xy), 'How do I leave Mt Moon?')['do']
            self.assertIn('Route 4 west', a)
            self.assertNotIn('Next toward the ladder (5,5)', a)
            self.assertRegex(a, r'(?:up|down|left|right) \d+ to')
        # With a fossil, leaving still means the east exit.
        s = X.wart('MT_MOON_B2F', (13, 7), events=X.NERD)
        s['bag'] = [dict(item='HELIX_FOSSIL', count=1)]
        self.assertIn('Route 4 cave exit', ask(s, 'How do I leave Mt Moon?')['do'])

    def test_14_explicit_grass_destination_gets_walk(self):
        # t17-7 n459: the requested grass tile must win over the story destination.
        s = H.state('ROUTE_3', (60, 3), level=15, events=H.beaten(*range(8)))
        a = ask(s, 'Give coordinates to reach the grass at (60,8) from here.')['do']
        self.assertIn('the grass at (60,8)', a)
        self.assertIn('right 1 to (60,8)', a)  # the direct column has a rock; use the checked detour
        self.assertNotIn('off the north edge', a)
        self.assertNotIn('Mt. Moon entrance', a)
        # Early Route 3 grass requests use reachable grass west of the needed fights.
        a = ask(H.state('ROUTE_3', (13, 5), level=13, events=H.beaten(0)),
                'Where is the nearest grass for wild training?')['do']
        self.assertRegex(a, r'(?:up|down|left|right) \d+ to')
        self.assertNotIn('You do not need to train', a)

    def test_15_unavoidable_trainer_bypass_explains_limit(self):
        # t17-2 n325/402, t17-7 n214: no direction into sight when asked to avoid it.
        s = H.state('ROUTE_3', (13, 4), level=13, events=H.beaten(0))
        a = ask(s, 'How do I avoid the Youngster until I am stronger?')['do']
        self.assertIn('cannot bypass', a)
        self.assertIn('Youngster', a)
        self.assertIn('grass', a)
        self.assertNotRegex(a, r'step (?:up|down|left|right) to start')
        # A beaten trainer must not be called unavoidable again.
        s = H.state('ROUTE_3', (19, 4), level=15, events=H.beaten(*range(8)))
        self.assertNotIn('cannot bypass', ask(s, 'Can I avoid the trainers to reach Route 4?')['do'])

    def test_16_heal_and_route_question_answers_both(self):
        # t17-5 n251: a Potion verdict alone omits the requested next checkpoint.
        s = H.state('ROUTE_3', (19, 4), hp=25, level=14, events=H.beaten(0, 1, 4),
                    bag=[dict(item='POTION', count=2)])
        for q in ['What is the exact route to Mt. Moon, and should I heal first?',
                  'What is the exact route to Mt. Moon, and should I heal first at Pewter or the Route 4 center?']:
            a = ask(s, q)['do']
            self.assertRegex(a, r'No Center trip|Potion now')
            self.assertIn('Mt. Moon entrance', a)
            self.assertRegex(a, r'(?:up|down|left|right) \d+ to')

    def test_17_cave_trainer_intro_does_not_say_walk_away(self):
        # t17-4 n555: the Lass is already talking; this is not a repeatable sign.
        for text in [False, True]:
            s = X.wart('MT_MOON_1F', (30, 7))
            s.update(text_box=text, teacher_screen=dict(rows=["Wow! It's"], cursor=False))
            a = ask(s, 'What move?')['do']
            self.assertIn('press A once', a)
            self.assertNotIn('sign or person', a)
            self.assertNotIn('Next toward', a)


class ReviewFixes(unittest.TestCase):
    def test_blocker_1_main_menu_buys_in_both_marts(self):
        for mart in ('PEWTER_MART', 'CERULEAN_MART'):
            for count in (0, 1):
                s = decoded_shop(['MONEY 1672', '>BUY', 'SELL', 'QUIT'], mart)
                s['bag'] = [dict(item='POTION', count=count)] if count else []
                do = ask(s, 'How do I buy Potions?')['do']
                self.assertIn('BUY', do)
                self.assertNotIn('to sell', do)
                self.assertLess(do.index('BUY'), do.index('press A'))

    def test_blocker_2_decoder_hides_quantity_so_reanchor_first(self):
        stock = ['MONEY 1672', '>POKE BALL', 'POTION', 'ESCAPE ROPE']
        listing = decoded_shop(stock)
        number = decoded_shop(stock + ['x03 900'])
        self.assertEqual(listing['teacher_screen']['rows'], number['teacher_screen']['rows'])
        for s in (listing, number):
            do = ask(s, 'How do I buy three Potions?')['do']
            self.assertTrue(do.startswith('Press B'), do)
            self.assertIn('BUY/SELL/QUIT', do)
            self.assertLess(do.index('BUY/SELL/QUIT'), do.index('press A'))
            self.assertIn('down 1', do)
            self.assertIn('up 2', do)

    def test_blocker_3_foreground_confirmation_wins_over_stock(self):
        for mart, other in [('PEWTER_MART', 'ESCAPE ROPE'), ('CERULEAN_MART', 'REPEL')]:
            for foreground, total, accept in [('POTION', 900, True), (other, 900, False),
                                               ('POTION', 600, False)]:
                lines = ['MONEY 1672', 'POKE BALL', 'POTION', other,
                         foreground + '?', 'That will be', f'{total}. OK?', 'YES', 'NO']
                # A price row with only "OK" is filtered by the live decoder. Test
                # explicit totals separately, plus its real decoded confirmation below.
                s = shop(lines)
                s['place']['map'] = mart
                for _ in range(2):
                    do = ask(s, 'How do I buy three Potions?')['do']
                    if accept:
                        self.assertIn('Choose YES', do)
                        self.assertNotIn('cancel', do)
                    else:
                        self.assertTrue(do.startswith('Press B'), do)
            decoded = scrolled_confirmation(mart, 3, ['POKE BALL', 'POTION', other])
            self.assertNotIn('900. OK?', decoded['teacher_screen']['rows'])
            do = ask(decoded, 'How do I buy three Potions?')['do']
            self.assertIn('exactly 900', do)
            self.assertIn('Only if it matches: Choose YES', do)
            self.assertNotIn('cancel POKE BALL', do)
            self.assertNotIn('cancel ' + other, do)
        # A matching number in background money is not the foreground total.
        s = shop(['MONEY 900', 'POTION?', 'That will be', '600. OK?', 'YES', 'NO'])
        self.assertTrue(ask(s, 'Buy Potions')['do'].startswith('Press B'))

    def test_scrolled_confirmations_both_marts_counts_and_retries(self):
        for mart, other in [('PEWTER_MART', 'ESCAPE ROPE'), ('CERULEAN_MART', 'REPEL')]:
            for n in (1, 2, 3):
                for background in (['POKE BALL', 'POTION', other],
                                   ['ANTIDOTE', 'BURN HEAL', 'AWAKENING'],
                                   [other, 'POKE BALL', 'POTION']):
                    with self.subTest(mart=mart, n=n, background=background):
                        s = scrolled_confirmation(mart, n, background)
                        s['bag'] = [dict(item='POTION', count=3 - n)]
                        rows = s['teacher_screen']['rows']
                        self.assertIn('That will be', rows)
                        self.assertIn('YES', rows)
                        self.assertNotIn('POTION?', rows)
                        self.assertNotIn(f'{n * 300}. OK?', rows)
                        ctx = {}
                        for _ in range(2):
                            do = ask(s, 'How do I buy Potions?', ctx)['do']
                            self.assertFalse(do.startswith('Press B'), do)
                            self.assertIn(f'exactly {n * 300}', do)
                            self.assertIn('Only if it matches: Choose YES', do)
                            self.assertIn('press A', do)
                            self.assertNotIn('foreground item is', do)
                            self.assertNotIn('cancel ' + background[-1], do)

    def test_scrolled_visible_price_checks_total_without_background_item(self):
        for mart, other in [('PEWTER_MART', 'ESCAPE ROPE'), ('CERULEAN_MART', 'REPEL')]:
            for n in (1, 2, 3):
                s = shop([other, 'That will be', f'{n * 300}. OK?', 'YES', 'NO'],
                         bag=[dict(item='POTION', count=3 - n)])
                s['place']['map'] = mart
                do = ask(s, 'Buy Potions')['do']
                self.assertIn('Choose YES', do)
                self.assertNotIn('cancel', do)
                s['teacher_screen']['rows'][2] = f'{n * 300 + 300}. OK?'
                self.assertTrue(ask(s, 'Buy Potions')['do'].startswith('Press B'))

    def test_blocker_4_all_scroll_windows_reselect_safely(self):
        data = (settings.POKERED / 'data/items/marts.asm').read_text()
        for city in ('Pewter', 'Cerulean'):
            stock = re.search(city + r'MartClerkText::\s+script_mart ([^\n]+)', data)[1]
            stock = stock.replace('_', ' ').split(', ') + ['CANCEL']
            for start in range(len(stock) - 2):
                s = decoded_shop(['MONEY 1672'] + stock[start:start + 3] + ['Take your time.'],
                                 city.upper() + '_MART')
                do = ask(s, 'How do I buy three Potions?')['do']
                self.assertTrue(do.startswith('Press B'), do)
                self.assertIn('BUY/SELL/QUIT', do)
                self.assertIn('scroll', do.lower())
                self.assertIn('POKE BALL', do)
                self.assertIn('down 1', do)
                self.assertLess(do.index('POTION'), do.index('press A'))
        s = decoded_shop(['MONEY', 'MYSTERY ITEM', 'Take your time.'])
        self.assertTrue(ask(s, 'How do I buy Potions?')['do'].startswith('Press B'))

    def test_blocker_5_retreat_keeps_goal_through_actual_warp_arrivals(self):
        ctx = {}
        for map_, xy, q, next_map in [
                ('MT_MOON_B2F', (21, 17), 'How do I leave Mt Moon?', 'MT_MOON_B1F'),
                ('MT_MOON_B1F', (21, 17), None, 'MT_MOON_1F'),
                ('MT_MOON_1F', (5, 5), 'What next?', 'ROUTE_4')]:
            s = X.wart(map_, xy)
            do = ask(s, q, ctx)['do']
            self.assertIn('Route 4 west', do)
            route = A.walk_to(s, lambda m, p: m == 'ROUTE_4' and p[0] < 22, fallback=False)
            self.assertIsNotNone(route)
            nodes = [step[0] for step in route['steps']] + [route['target']]
            arrival = next(dst for src, dst in zip(nodes, nodes[1:]) if src[0] != dst[0])
            self.assertEqual(arrival[0], next_map)
            if next_map != 'ROUTE_4':
                self.assertEqual(arrival[1], (21, 17) if next_map == 'MT_MOON_B1F' else (5, 5))
        self.assertEqual(ctx.get('r15_retreat'), 'ROUTE_4_WEST')
        arrived = X.wart(*arrival)
        ask(arrived, 'What next?', ctx)
        self.assertNotIn('r15_retreat', ctx)

    def test_retreat_explicit_new_destination_clears_goal(self):
        for q in ('Where is the ladder to B2F?', 'How do I reach Cerulean?',
                  'Where is the fossil?', 'Where is the nearest grass?'):
            ctx = {}
            s = X.wart('MT_MOON_B1F', (21, 17))
            ask(s, 'How do I leave Mt Moon?', ctx)
            self.assertEqual(ctx.get('r15_retreat'), 'ROUTE_4_WEST')
            ask(s, q, ctx)
            self.assertNotIn('r15_retreat', ctx)

    def test_retreat_followup_questions_keep_goal_on_both_floors(self):
        for q in ('Where is the next ladder?', 'Where next from B1F?',
                  'Where is the next ladder on the way out?', 'next ladder on the way out?',
                  'B1F', '1F', 'Where next from 1F?', 'Where is the ladder to 1F?'):
            with self.subTest(question=q):
                ctx = {}
                ask(X.wart('MT_MOON_B2F', (21, 17)), 'How do I leave Mt Moon?', ctx)
                for map_, xy in [('MT_MOON_B1F', (21, 17)), ('MT_MOON_1F', (5, 5))]:
                    do = ask(X.wart(map_, xy), q, ctx)['do']
                    self.assertEqual(ctx.get('r15_retreat'), 'ROUTE_4_WEST')
                    self.assertIn('Route 4 west', do)
                    self.assertNotIn('fossil guard', do)
                ask(X.wart('ROUTE_4', (18, 5)), 'What next?', ctx)
                self.assertNotIn('r15_retreat', ctx)

    def test_explicit_potion_sale_uses_requested_item(self):
        s = decoded_shop(['BUY', 'SELL', 'QUIT'])
        s['bag'] = [dict(item='POTION', count=3), dict(item='ESCAPE_ROPE', count=1)]
        do = ask(s, 'Sell my Potions')['do']
        self.assertIn('Sell 3 POTION for 450', do)
        self.assertIn('Select POTION', do)
        self.assertNotIn('Select ESCAPE ROPE', do)
        active = shop(['POTION', 'ESCAPE ROPE', 'What would you', 'like to sell?'], bag=s['bag'])
        do = ask(active, 'Sell my Potions')['do']
        self.assertIn('Sell 3 POTION for 450', do)
        self.assertTrue(do.startswith('Press B'), do)

    def test_battle_text_has_no_sign_or_walking_warning(self):
        for battle in (False, True):
            s = X.wart('CERULEAN_GYM', (4, 3))
            if battle:
                s = H.in_battle(s, 'STARMIE', 21)
            s.update(text_box=True, teacher_screen=dict(rows=['STARMIE used', 'BUBBLEBEAM!'], cursor=False))
            do = ask(s, 'What next?', {'text_loop': {'repeats': 3}})['do']
            self.assertIn('press A once', do)
            self.assertIn('battle', do.lower())
            self.assertNotRegex(do, r'sign|person|walk|step away')


if __name__ == '__main__':
    unittest.main()
