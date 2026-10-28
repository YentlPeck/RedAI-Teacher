"""R12 regressions: each audited bad answer from the t15-4 / t15-7 games and
its fixed answer. States are the decoded saved post-Brock state (states/post_brock_pewter.json) moved to the tile,
HP and beaten trainers read from the t15 press rows before each ask. Only the gated CLI test opens an emulator."""
import io
import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

DEV = Path(__file__).resolve().parents[1]
ROOT = DEV
sys.path[:0] = [str(DEV / 'tools'), str(DEV / 'arena')]
import settings  # noqa: E402
import advise as A
import read_state as R
import r11_maps as M
import r12_advice as T

META = re.compile(r'(?i)\b(test|tests|tested|round|coordinator|experiment|plain)\b|teacher group')
ROUTE3 = [r['event'] for r in M.maps()['ROUTE_3']['objects'] if r.get('event')]


def beaten(*n):
    return {f'EVENT_BEAT_ROUTE_3_TRAINER_{i}': True for i in n}


def state(map_=None, xy=None, hp=None, level=None, events=None, **extra):
    s = json.loads(settings.fixture('post_brock_pewter.json').read_text(encoding='utf-8'))['checked_state']
    s.update(teacher_events=dict(events or {}), teacher_objects={})
    if map_:
        s['place'].update(map=map_, map_id=next(i for i, n in R.MAPS.items() if n == map_), x=xy[0], y=xy[1])
    if level:
        t = A._wild_mon('SQUIRTLE', level)
        s['team'][0].update(level=level, max_hp=t['max_hp'], hp=t['max_hp'], stats=t['stats'])
    if hp is not None:
        s['team'][0]['hp'] = hp
    s.update(extra)
    return s


def in_battle(s, species, level, kind='trainer', ui=None, foe_hp=None):
    foe = A._wild_mon(species, level)
    if foe_hp is not None:
        foe['hp'] = foe_hp
    s['battle'] = dict(kind=kind, yours=dict(A._party_mon(s['team'][0], s['badges']), flags=[]),
                       enemy=dict(foe, flags=[]))
    if ui is not None:
        s['teacher_ui'] = ui
    return s


def screen(*lines):
    rows = [' ' * 20] * 18
    for i, text in lines:
        rows[i] = text.ljust(20)
    return rows


class Readiness(unittest.TestCase):
    def test_route3_fights_needed_on_the_way_match_the_map(self):
        s = state()
        allb = {e: True for e in ROUTE3}
        to_r4 = lambda m, p: m == 'ROUTE_4'
        for e in ROUTE3:
            route = A.walk_to(dict(s, teacher_events={k: v for k, v in allb.items() if k != e}), to_r4,
                              max_maps=6, fallback=False)
            with self.subTest(event=e):
                self.assertEqual(route is None, e in T.ROUTE_ORDER['ROUTE_3'])

    def test_expected_fights_match_t15_outcomes(self):
        # t15 press rows: healed L11 beat the Bug Catcher (10,6) 4/4; L12 lost to the Youngster (14,4) 4/4 without
        # Potions and won with them; low-HP fights ended in blackouts (t15-1 at 15 HP vs the Lass (16,9)).
        def run(key, level, hp, pots=0):
            s = state(level=level)
            s['team'][0]['hp'] = hp
            win, left = T.outcome(A, T.mons(A, s), [key], pots)
            return win and left >= T.MARGIN
        self.assertTrue(run('BugCatcher:4', 11, 31))
        self.assertFalse(run('BugCatcher:4', 11, 15))
        self.assertFalse(run('Youngster:1', 11, 31))
        self.assertFalse(run('Youngster:1', 12, 34))
        self.assertTrue(run('Youngster:1', 12, 34, pots=3))
        self.assertTrue(run('Lass:1', 11, 31))
        self.assertFalse(run('Lass:1', 11, 15))

    def test_route2_training_grass_is_real_tall_grass_by_pewter(self):
        # tileset_headers.asm: Overworld grass tile $52; Route2.asm wild data; Route 2 top edge joins Pewter.
        g = A._grid('ROUTE_2')
        self.assertEqual(g['tile'][(7, 2)], 0x52)
        spot = T.training_spot(A, state())
        self.assertEqual(spot[2]['maps'], ['PEWTER_CITY', 'ROUTE_2'])
        self.assertTrue(spot[0].startswith('the Route 2 grass just south of Pewter'))

    def test_saved_state_four_questions_get_a_verdict(self):
        s = state()
        for q in ('Am I ready for Route 3?', 'Can I beat the trainers on Route 3?', 'Where do I go next?'):
            with self.subTest(q=q):
                a = A.answer(s, q, context={})
                self.assertTrue(a['do'].startswith('Not ready: heal at the Pewter Center first, then buy 3 Potions at '
                                                   'the Pewter Mart (300 each; you have 1672). Then the Bug Catcher at '
                                                   '(10,6) is a likely win (estimate)'), a['do'])
                self.assertIn('use a Potion when HP falls below a third', a['do'])
                self.assertIn('Walk: ', a['do'])
                self.assertIn('Bug Catcher at (10,6) (CATERPIE L10, WEEDLE L10, CATERPIE L10): likely loss now, '
                              'likely win after healing', a['why'])
                self.assertIn('SQUIRTLE L11 15/31 HP', a['why'])
                self.assertNotIn('train', a['do'])
        a = A.answer(s, 'Where should I train?', context={})
        self.assertTrue(a['do'].startswith('You do not need to train first: heal at the Pewter Center first, then buy 3'))
        self.assertIn('For extra levels anyway: the Route 2 grass just south of Pewter', a['do'])
        self.assertIn('In the grass at', A.text(a))

    def test_t15_4_n52_healthy_team_in_pewter_gets_verdict_not_route(self):
        # Old: "Next toward Mt. Moon entrance ... Then stop before the trainer and check readiness."
        # A healed L11 Squirtle won this Bug Catcher fight in 4 of 4 t15 games: the verdict is "go".
        a = A.answer(state('PEWTER_CITY', (28, 18), hp=31), 'Is my team ready?', context={})
        self.assertTrue(a['do'].startswith('Ready: go. Next is the Bug Catcher at (10,6): a likely win'), a['do'])
        self.assertIn('Youngster at (14,4) (RATTATA L11, EKANS L11): likely loss now', a['why'])

    def test_t15_7_n28_ready_question_at_trainer_gets_verdict_not_stop(self):
        # Old: "Stop here: up starts Bug Catcher at (10,6)." with no verdict.
        for q in ('Ready for the trainer?', 'Am I ready for the trainer? Which move?'):
            a = A.answer(state('ROUTE_3', (11, 7), hp=31), q, context={})
            self.assertTrue(a['do'].startswith('Ready: go. Next is the Bug Catcher at (10,6)'), a['do'])
            self.assertIn('Fight plan: lead SQUIRTLE with', A.text(a))

    def test_t15_4_n232_next_trainer_after_first_win(self):
        # Old: "Stop here: right starts Youngster at (14,4)."
        a = A.answer(state('ROUTE_3', (13, 5), level=12, events=beaten(0)), 'Is my team ready for the next trainer?',
                     context={})
        # L12 lost to this Youngster 4 times without Potions in t15; with Potions it won (t15-5, t15-6).
        self.assertTrue(a['do'].startswith('Not ready: buy 3 Potions at the Pewter Mart'), a['do'])
        self.assertIn('Then the Youngster at (14,4) is a likely win (estimate)', a['do'])
        self.assertIn('Walk: ', a['do'])

    def test_three_verdict_forms(self):
        ready = A.answer(state('PEWTER_CITY', (28, 18), level=18), 'Am I ready?', context={})
        self.assertTrue(ready['do'].startswith('Ready: go. Next is the Bug Catcher at (10,6)'), ready['do'])
        self.assertTrue(any(d.startswith('Way on: ') for d in ready['details']))
        heal = A.answer(state('PEWTER_CITY', (28, 18), level=18, hp=10), 'Am I ready?', context={})
        self.assertTrue(heal['do'].startswith('Not ready: heal at the Pewter Center first.'), heal['do'])
        self.assertIn('Walk: down 4 to (28,22)', heal['do'])
        self.assertNotIn('Inside:', heal['do'])  # R15: these three walking legs do not reach the door.
        self.assertIn('ask again at this checkpoint', heal['do'])
        pots = A.answer(state('ROUTE_3', (13, 5), level=12, events=beaten(0)), 'Am I ready?', context={})
        self.assertTrue(pots['do'].startswith('Not ready: buy 3 Potions at the Pewter Mart'))
        broke = state('ROUTE_3', (13, 5), level=12, events=beaten(0), money=100)
        train = A.answer(broke, 'Am I ready?', context={})
        self.assertRegex(train['do'], r'^Not ready: train to about L1[34] \(estimate\) in the Route 2 grass')

    def test_any_readiness_wording_gets_a_verdict(self):
        s = state('ROUTE_3', (9, 8), hp=31)
        for q in ('Can I beat the trainers on Route 3?', 'Should I fight the Bug Catcher?', 'Is it safe to go east?',
                  'Am I strong enough?', 'Will I win against the youngster?', 'Can I pass without losing a Pokemon?',
                  'Check readiness for next trainer.'):
            with self.subTest(q=q):
                self.assertRegex(A.answer(s, q, context={})['do'], r'^(Ready: go|Not ready:)')

    def test_misty_and_gym_questions_keep_the_misty_check(self):
        a = A.answer(state(), 'Am I ready for Misty?', context={})
        self.assertIn('Not ready for Misty', a['do'])

    def test_t15_7_n32_text_open_readiness_question(self):
        # Old: "Press A once to read the waiting dialogue, then look before pressing again."
        s = state('ROUTE_3', (11, 6), hp=31, text_box=True)
        a = A.answer(s, 'How can I pass without losing Pokémon?', context={})
        self.assertIn('has seen you: the fight cannot be avoided now. Press A to read on.', a['do'])
        self.assertIn('likely win', a['do'])
        s['team'][0]['hp'] = 12
        self.assertIn('likely loss', A.answer(s, 'Can I win this?', context={})['do'])


class Warnings(unittest.TestCase):
    def test_route_question_warns_before_unbeaten_trainer(self):
        # Old t15-4 n240/n383: "Next toward Mt. Moon entrance ... Then stop before the trainer and check readiness."
        for q in ('How do I proceed to next route?', 'What next?', None):
            with self.subTest(q=q):
                a = A.answer(state('ROUTE_3', (13, 4), level=12, events=beaten(0)), q, context={})
                self.assertTrue(a['do'].startswith('Not ready: buy 3 Potions at the Pewter Mart'), a['do'])
                self.assertIn('Way to the Mart', A.text(a))
                a = A.answer(state('ROUTE_3', (13, 4), level=12, events=beaten(0), money=100), q, context={})
                self.assertTrue(a['do'].startswith('Not ready: train to about L'), a['do'])
                self.assertIn('Way to the grass', A.text(a))
                self.assertIn('Heal at the Pewter Center when HP is under half', A.text(a))

    def test_warning_still_shows_the_route_last(self):
        a = A.answer(state('ROUTE_3', (13, 4), level=12, events=beaten(0)), 'How do I get to Mt Moon?', context={})
        self.assertTrue(a['do'].startswith('Not ready: buy 3 Potions'))
        self.assertTrue(a['details'][-1].startswith('If you go on anyway: Next toward Mt. Moon entrance'))

    def test_ready_team_gets_the_route(self):
        a = A.answer(state('ROUTE_3', (9, 8), level=18), 'What next?', context={})
        self.assertTrue(a['do'].startswith(('Next toward', 'Ready: step')), a['do'])

    def test_t15_4_n546_stop_here_becomes_a_verdict(self):
        # Old (3x): "Stop here: left starts an unbeaten trainer battle." with no verdict or alternative.
        a = A.answer(state('ROUTE_3', (19, 4), level=13, events=beaten(0, 1)), 'Where next?', context={})
        self.assertNotIn('Stop here', a['do'])
        self.assertRegex(a['do'], r'^(Do not step \w+: that starts the fight with|Ready: step)')

    def test_low_hp_warns_and_gives_way_to_heal(self):
        a = A.answer(state('ROUTE_3', (9, 8), level=18, hp=12), 'Where do I go next?', context={})
        self.assertTrue(a['do'].startswith('Not ready: heal at the Pewter Center first.'), a['do'])
        self.assertNotIn('Inside:', a['do'])  # R15: stop at the outside checkpoint first.
        self.assertIn('ask again at this checkpoint', a['do'])


class Battle(unittest.TestCase):
    def assert_concrete(self, a):
        self.assertNotRegex(a['do'], r'^Look at the screen')
        self.assertNotIn('Look at the screen and ask again', a['do'])
        self.assertRegex(a['do'], r'TACKLE|BUBBLE|RUN|ITEM|PKMN|POTION|FIGHT|press A|Press A')

    def test_t15_7_battle_asks_get_a_move(self):
        # Old: "Look at the screen and ask again..." (11x) and "Press A once to advance the battle text, then ask again" (9x).
        cases = {
            'no screen data': None,
            'text': dict(phase='unknown', rows=screen((14, 'CATERPIE used'), (16, 'STRING SHOT!')), cursor_count=0,
                         submitted=False, move_index=0),
            'fainted text': dict(phase='unknown', rows=screen((14, 'WEEDLE fainted!')), cursor_count=0,
                                 submitted=False, move_index=0),
            'menu without arrow': dict(phase='unknown', rows=screen((14, '          FIGHT PKMN'), (16, '          ITEM  RUN')),
                                       cursor_count=0, submitted=False, move_index=2),
            'odd arrow': dict(phase='unknown', rows=screen((14, 'something')), cursor_count=1, submitted=False),
        }
        for label, ui in cases.items():
            for q in ('Which move should I use now?', 'Current HP and move?', "What's the enemy HP?", 'What is safest?'):
                with self.subTest(label=label, q=q):
                    s = in_battle(state('ROUTE_3', (11, 6), hp=31), 'CATERPIE', 10, ui=ui)
                    a = A.answer(s, q, context={})
                    self.assert_concrete(a)
                    self.assertIn('TACKLE', a['do'] if ui else A.text(a))
                    self.assertIn('FIGHT is top-left', a['do'] if ui else A.text(a))
                    self.assertIn('Now: SQUIRTLE 31/31 HP vs CATERPIE L10 30/30 HP.', a['details'])
        s = in_battle(state('ROUTE_3', (11, 6), hp=31), 'CATERPIE', 10, ui=cases['text'])
        self.assertTrue(A.answer(s, 'What screen should I advance?')['do'].startswith(
            'Press A once to advance the battle text. Then: Use TACKLE'))

    def test_t15_4_n466_open_fight_gives_whole_move_choice(self):
        # Old: "Press A once to open FIGHT; then look and ask again."
        s = in_battle(state('ROUTE_3', (13, 4), level=13), 'RATTATA', 11,
                      ui=dict(phase='commands', cursor=(9, 14), rows=[], cursor_count=1, move_index=0))
        a = A.answer(s, 'What move should I use now?', context={})
        self.assertRegex(a['do'], r'^Press A once to open FIGHT, then pick (TACKLE|BUBBLE)')
        self.assertRegex(a['do'], r'Buttons: a( down)* a \(one command\)')
        self.assertNotIn('ask again', a['do'])

    def test_move_list_and_other_cursor_positions(self):
        s = in_battle(state('ROUTE_3', (11, 6), hp=31), 'CATERPIE', 10,
                      ui=dict(phase='commands', cursor=(15, 16), rows=[], cursor_count=1, move_index=0))
        a = A.answer(s, 'What move?', context={})
        self.assertTrue(a['do'].startswith('Press left once and up once toward FIGHT, then A to open it'))
        self.assertIn('Buttons: left up a a (one command)', a['do'])
        s['teacher_ui'] = dict(phase='moves', cursor=2, rows=[], cursor_count=1)
        a = A.answer(s, 'Best move?', context={})
        self.assertEqual(a['do'], 'Press: up up a (one command): that picks TACKLE.')   # review S4: one sequence

    def test_low_hp_wild_without_potion_runs(self):
        s = state('ROUTE_2', (7, 2), hp=5)
        s['team'][1]['hp'] = 0
        s = in_battle(s, 'PIDGEY', 5, kind='wild', ui=dict(phase='commands', cursor=(9, 14), rows=[], cursor_count=1,
                                                           move_index=0))
        a = A.answer(s, 'What should I do?', context={})
        self.assertIn('toward RUN', a['do'])
        self.assertIn('Buttons: right down a', a['do'])
        self.assertIn('no Potion', a['why'])

    def test_low_hp_trainer_with_potion_uses_item_steps(self):
        s = in_battle(state('ROUTE_3', (13, 4), hp=6, bag=[dict(item='POTION', count=2)]), 'RATTATA', 11,
                      ui=dict(phase='commands', cursor=(9, 14), rows=[], cursor_count=1, move_index=0))
        a = A.answer(s, 'What should I do?', context={})
        self.assertEqual(a['do'], 'Press down once toward ITEM, then A to open it, then pick POTION with up/down, '
                                  'press A, then pick SQUIRTLE and press A.')

    def test_yes_no_switch_question(self):
        s = in_battle(state('ROUTE_3', (11, 6), hp=31), 'WEEDLE', 10,
                      ui=dict(phase='unknown', rows=screen((14, 'Will B change'), (16, 'POKeMON? YES NO')),
                              cursor_count=1, submitted=False))
        a = A.answer(s, 'What now?', context={})
        self.assertIn('Press B to answer NO and keep SQUIRTLE in. Then: Use TACKLE', a['do'])

    def test_any_question_in_battle_is_a_battle_answer(self):
        # Old t15-7 n200 "Where is the healing center?" in battle got a walk.
        s = in_battle(state('ROUTE_3', (11, 6), hp=3), 'CATERPIE', 10,
                      ui=dict(phase='commands', cursor=(9, 14), rows=[], cursor_count=1, move_index=0))
        for q in ('Where is the healing center?', 'Am I ready?', 'Should I train?'):
            with self.subTest(q=q):
                a = A.answer(s, q, context={})
                self.assertEqual(a['kind'], 'battle')
                self.assertNotIn('Next toward', a['do'])


class RepeatsBlockedCenterPlaces(unittest.TestCase):
    def test_t15_4_n14_door_loop_third_answer_is_exact_buttons(self):
        # Old (5x): "Next toward PEWTER POKECENTER ... up 1 to (13,25)" while the player went in and out unhealed.
        s, ctx = state('PEWTER_CITY', (13, 26)), {}
        answers = [A.answer(s, q, context=ctx)['do'] for q in
                   ('What next?', 'How do I get to Route 3 from here?', 'I visited the Pokemon Center. How do I reach Route 3?')]
        self.assertEqual(answers[0], answers[1])
        self.assertNotEqual(answers[2], answers[1])
        self.assertTrue(answers[2].startswith('Same answer three times without moving: press exactly up in one command'))
        self.assertIn('Inside: walk up to the nurse counter', answers[2])
        json.dumps(ctx)

    def test_t15_4_n546_repeat_gives_buttons_to_the_grass(self):
        s, ctx = state('ROUTE_3', (19, 4), level=13, events=beaten(0, 1)), {}
        out = [A.answer(s, q, context=ctx)['do'] for q in ('Where next?', 'What should I do now?', 'How do I get to Mt Moon?')]
        self.assertTrue(out[2].startswith('Same answer three times without moving: press exactly '), out[2])
        self.assertRegex(out[2], r'press exactly (left|down|right|up)')
        self.assertNotEqual(out[1], out[2])

    def test_progress_resets_the_repeat_check(self):
        ctx = {}
        for x in (13, 13, 14):
            a = A.answer(state('PEWTER_CITY', (x, 26)), 'What next?', context=ctx)
        self.assertNotIn('Same answer three times', a['do'])

    def test_t15_7_n329_blocked_at_trainer_and_after_win(self):
        # Old: the same route again ("right 1 to (15,5) ..."), no check of the blocked tile.
        q = 'I am blocked at 14,5. What should I do?'
        a = A.answer(state('ROUTE_3', (14, 5), level=12, events=beaten(0)), q, context={})
        self.assertTrue(a['do'].startswith('A trainer has seen you: the Youngster at (14,4)'))
        ctx = {}
        s = state('ROUTE_3', (14, 5), level=12, events=beaten(0, 1))
        a = A.answer(s, q, context=ctx)
        self.assertTrue(a['do'].startswith('You are at (14,5). Nothing on the map blocks (15,5). Try once: press A'))
        self.assertNotIn('walk_occupancy', ctx)          # review S1: an unconfirmed tile stays open
        a = A.answer(s, q, context=ctx)
        self.assertTrue(a['do'].startswith('You are at (14,5); going right is blocked. Detour: '), a['do'])
        self.assertIn('for your next few steps only', a['why'])
        self.assertEqual(ctx['walk_occupancy'][-1], dict(map='ROUTE_3', tile=[15, 5], ttl=6))

    def test_blocked_reasons_person_ledge_wall(self):
        s = state('ROUTE_3', (14, 5), level=12, events=beaten(0, 1))
        self.assertIn('A person stands on (14,4)', A.answer(s, 'I am stuck, I cannot go up', context={})['why'])
        s = state('ROUTE_3', (13, 8), level=12, events=beaten(0, 1))
        self.assertIn('is a ledge', A.answer(s, 'Blocked going up at 13,8', context={})['why'])
        s = state('ROUTE_3', (16, 8), level=12, events=beaten(0, 1))
        self.assertIn('(17,8) is a wall', A.answer(s, "I can't move east", context={})['why'])

    def test_t15_4_n47_inside_center_talk_to_nurse(self):
        # Old: "Press A once ..." / route answers inside the Center; the player left 6 times unhealed.
        a = A.answer(state('PEWTER_POKECENTER', (3, 7)), 'What route should I take now?', context={})
        self.assertEqual(a['do'], 'Heal first: talk to the nurse behind the counter at (3,1). Walk up to the counter: '
                                  'up 4 to (3,3). Then face up, press A, then press A through the text (it heals your '
                                  'team for free).')
        a = A.answer(state('PEWTER_POKECENTER', (3, 3)), 'What next?', context={})
        self.assertTrue(a['do'].startswith('Heal now: talk to the nurse'))
        self.assertIn('Buttons: up a a a', A.text(a))
        healthy = A.answer(state('PEWTER_POKECENTER', (3, 3), hp=31), 'What next?', context={})
        self.assertNotIn('nurse', healthy['do'])

    def test_heal_walk_says_what_to_do_inside(self):
        a = A.answer(state('PEWTER_CITY', (19, 17)), 'How do I heal?', context={})
        self.assertIn('Inside: walk up to the nurse counter, face up, press A', a['do'])

    def test_t15_7_n229_route4_center_is_the_named_place(self):
        # Old: "Next toward PEWTER POKECENTER ..." (the default Center, not the one asked for).
        a = A.answer(state('ROUTE_3', (13, 5), level=12, events=beaten(0)), 'Where is Route 4 Center?', context={})
        self.assertIn('the Route 4 Center by Mt. Moon', a['why'])
        self.assertIn('door at Route 4 (11,5)', a['why'])
        self.assertNotIn('PEWTER POKECENTER', a['do'])
        east = state('ROUTE_3', (57, 4), level=18, events={e: True for e in ROUTE3})
        a = A.answer(east, 'How do I get to the Route 4 Pokemon Center?', context={})
        self.assertIn('the Route 4 Center by Mt. Moon', a['do'])
        self.assertNotIn('Pewter', a['do'])
        self.assertEqual(T.alias_target('i already visited the pewter center', east), None)


class Words(unittest.TestCase):
    def test_answers_use_player_words(self):
        texts = []
        for s, q in ((state(), 'Am I ready for Route 3?'), (state(), 'Where should I train?'),
                     (state('ROUTE_3', (14, 5), level=12, events=beaten(0, 1)), 'I am blocked at 14,5'),
                     (state('PEWTER_POKECENTER', (3, 7)), 'What now?'),
                     (in_battle(state('ROUTE_3', (11, 6), hp=31), 'CATERPIE', 10,
                                ui=dict(phase='unknown', rows=screen((14, 'CATERPIE used')), cursor_count=0,
                                        submitted=False, move_index=0)), 'Best move?')):
            texts.append(A.text(A.answer(s, q, context={})))
        for t in texts:
            self.assertNotRegex(t, META)


class ReviewFixes(unittest.TestCase):
    """Review findings B1, B2, S1-S4."""

    def test_b1_trapped_asleep_frozen_pass_the_turn_with_fight_never_b(self):
        cases = []
        s = in_battle(state('ROUTE_3', (14, 5), level=12, events=beaten(0)), 'EKANS', 11)
        s['battle']['enemy']['flags'] = ['trapping']
        cases.append(('wrapped', s))
        for status in ('asleep', 'frozen'):
            s = state('ROUTE_3', (14, 5), level=12, events=beaten(0))
            s['team'][0].update(status=status, sleep_turns=3)
            s['team'][1]['hp'] = 0
            cases.append((status, in_battle(s, 'RATTATA', 11)))
        for label, s in cases:
            for cursor, start in (((9, 14), 'Press: a (one command)'), ((15, 16), 'Press: left up a (one command)')):
                with self.subTest(label=label, cursor=cursor):
                    s['teacher_ui'] = dict(phase='commands', cursor=cursor, rows=[], cursor_count=1, move_index=0)
                    ctx = {}
                    for _ in range(3):
                        a = A.answer(s, 'What now?', context=ctx)
                        self.assertIn('press A on FIGHT to pass the turn', a['do'])
                        self.assertIn(start, a['do'])
                        self.assertNotIn('Press B', a['do'])
            s['teacher_ui'] = dict(phase='unknown', rows=screen((14, '          FIGHT PKMN'), (16, '          ITEM  RUN')),
                                   cursor_count=0, submitted=False, move_index=0)
            self.assertNotIn('press B', A.answer(s, 'What now?', context={})['do'].lower())

    def test_b2_no_meta_words_in_any_rendered_answer_note_or_refusal(self):
        import guard as G
        import play as P
        texts = []
        misty = state('CERULEAN_CITY', (19, 18), level=24)
        misty['story'] = dict(done=['oak', 'starter', 'parcel', 'pokedex', 'badge1', 'mt_moon'],
                              next=dict(id='badge2', goal='Beat Misty (Cascade Badge)', part=3, done=False))
        misty['part'] = 3
        fight = in_battle(state('ROUTE_3', (11, 6), hp=31), 'CATERPIE', 10,
                          ui=dict(phase='commands', cursor=(9, 14), rows=[], cursor_count=1, move_index=0))
        states = [state(), state('PEWTER_CITY', (13, 26)), state('PEWTER_POKECENTER', (3, 7)), state('PEWTER_MART', (4, 7)),
                  state('ROUTE_3', (13, 4), level=12, events=beaten(0)), state('ROUTE_3', (9, 8), hp=31), misty, fight,
                  state('ROUTE_3', (28, 8), level=12, events=beaten(0, 1, 6))]
        questions = [None, 'Am I ready?', 'Should I go to Bill before Misty?', 'Am I ready for Misty?',
                     'Should I catch an Oddish?', 'How do I get through Victory Road?', 'Where should I train?',
                     'What next?', 'Which starter should I choose?', 'I am blocked going up', 'Where is Route 4 Center?',
                     'Should I buy Potions?', 'How do I beat Brock?', 'Where is the Moon Stone?']
        for s in states:
            for q in questions:
                a = A.answer(s, q, context={})
                texts += [A.text(a), A.note(a)]
            texts.append(A.text(A.answer(s, None, stuck=8, context={})))
        run = Path(__file__).resolve().parent / '_refusal_tmp'
        run.mkdir(exist_ok=True)
        try:
            for why in ('several play.py calls in one shell command', 'the previous command ended less than 1 second ago'):
                with self.assertRaises(G.Blocked) as e:
                    G._refuse(run, 0, 'k', why)
                texts.append(str(e.exception))
        finally:
            (run / 'blocked.jsonl').unlink(missing_ok=True)
            run.rmdir()
        for bad in (['zz'], ['a*21']):
            with self.assertRaises(SystemExit) as e:
                P.parse_buttons(bad)
            texts.append(str(e.exception))
        texts += ['Game tool unavailable. No command was used.', 'Your 650 commands are used up. Stop and write your report.']
        meta = re.compile(r'(?i)\b(test|tests|tested|untested|round|rounds|coordinator|experiment|plain)\b|teacher group|game tests')
        self.assertGreater(len(texts), 200)
        for text in texts:
            self.assertNotRegex(text, meta)
        self.assertEqual(T.scrub('L18-22 is an untested guess; normal-button game tests'), 'L18-22 is an estimate; real play')

    def test_s1_unconfirmed_door_stays_open_at_pewter_center(self):
        s, ctx = state('PEWTER_CITY', (13, 26)), {}
        for _ in range(2):
            a = A.answer(s, 'I am blocked going up', context=ctx)
            self.assertTrue(a['do'].startswith('You are at (13,26). Nothing on the map blocks the door at (13,25)'))
            self.assertIn('into PEWTER_POKECENTER', a['details'][0])
            self.assertNotIn('VIRIDIAN', A.text(a))
        self.assertNotIn('walk_occupancy', ctx)
        self.assertIn('into PEWTER_POKECENTER', A.answer(s, 'What next?', context=ctx)['do'])

    def test_s2_avoidable_trainers_do_not_gate_and_heal_forward(self):
        # Review repro: events 0/1/6 beaten, L12 Squirtle 25/34, P100; the Jigglypuff Lass (33,10) is avoidable.
        s = state('ROUTE_3', (28, 8), level=12, hp=25, events=beaten(0, 1, 6), money=100)
        a = A.answer(s, 'What next?', context={})
        self.assertTrue(a['do'].startswith('Next toward Mt. Moon entrance'), a['do'])
        self.assertIn('Avoidable: the walk shown goes around', A.text(a))
        self.assertNotIn('Pewter Center', a['do'])
        r = A.answer(s, 'Am I ready?', context={})
        self.assertTrue(r['do'].startswith('Ready: go. No trainer fight is needed on the way.'), r['do'])
        hurt = state('ROUTE_3', (28, 8), level=12, hp=10, events=beaten(0, 1, 6), money=100)
        a = A.answer(hurt, 'What next?', context={})
        self.assertIn('the Route 4 Center by Mt. Moon', a['do'])
        self.assertNotIn('Pewter Center', a['do'])
        self.assertEqual(T.ROUTE_ORDER['MT_MOON_1F'], [])

    def test_s2_mt_moon_1f_needs_no_fight(self):
        s = state('MT_MOON_1F', (14, 34))
        s['place']['last_map'] = 'ROUTE_4'
        self.assertIsNotNone(A.walk_to(s, lambda m, p: m == 'MT_MOON_B1F', max_maps=2, fallback=False))

    def test_s3_one_potion_rule_in_battle_and_forecast(self):
        ui = dict(phase='commands', cursor=(9, 14), rows=[], cursor_count=1, move_index=0)
        high = in_battle(state('ROUTE_3', (14, 5), level=12, hp=23, events=beaten(0),
                               bag=[dict(item='POTION', count=3)]), 'EKANS', 11, ui=dict(ui))
        a = A.answer(high, 'What should I do?', context={})
        self.assertNotIn('POTION', a['do'])
        self.assertIn('above a third', a['why'])
        low = in_battle(state('ROUTE_3', (14, 5), level=12, hp=10, events=beaten(0),
                              bag=[dict(item='POTION', count=3)]), 'EKANS', 11, ui=dict(ui))
        a = A.answer(low, 'What should I do?', context={})
        self.assertIn('POTION', a['do'])
        self.assertTrue(T.potion_now(10, 34, 3, True, False))
        self.assertFalse(T.potion_now(23, 34, 3, True, False))
        self.assertFalse(T.potion_now(10, 34, 3, True, True))


class SavedStateCli(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('ARENA_EMULATOR_TESTS') == '1', 'emulator test: saved-state CLI')
    def test_saved_state_cli_four_questions(self):
        # One headless emulator per call (advise.main opens with ram_file=BytesIO and closes it), one at a time.
        go = 'DO NOW: Not ready: heal at the Pewter Center first, then buy 3 Potions at the Pewter Mart'
        for q, start in (('Am I ready for Route 3?', go), ('Can I beat the trainers on Route 3?', go),
                         ('Where should I train?', 'DO NOW: You do not need to train first: heal at the Pewter Center'),
                         ('Where do I go next?', go), ('Can I beat the Bug Catcher?', go)):
            out = io.StringIO()
            with patch.object(sys, 'argv', ['advise.py', str(settings.fixture('post_brock_pewter.state')), q]), \
                    redirect_stdout(out):
                A.main()
            with self.subTest(q=q):
                self.assertIn(start, out.getvalue())
                self.assertIn('SQUIRTLE', out.getvalue())


if __name__ == '__main__':
    unittest.main()
