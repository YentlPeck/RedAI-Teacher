"""R13 regressions: the round 12 weak spots, each from a real t16 log situation.
From real game logs (not in the repo): t16-2-haiku-teacher, t16-4-luna-teacher, t16-5-haiku-teacher.
States are the decoded post-Brock state moved to the tile (helpers of test_r12.py). No emulator is opened here."""
import re
import sys
import unittest
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DEV / 'tools'), str(DEV / 'arena'), str(DEV / 'tests')]
import advise as A
import r13_advice as T
import test_r12 as H

META = re.compile(r'(?i)\b(test|tests|tested|round|coordinator|experiment|plain)\b|teacher group')
CENTER_THANKS = ['Thank you!', 'Your POKéMO']          # t16-4: the screen it stood on for ~640 commands
SIGN = ['Are you storing your', 'POKéMON on PC? Each BOX', 'can hold 20 POKéMON!']     # t16-2 / t16-5 Route 3 sign
COMMANDS = dict(phase='commands', cursor=(9, 14), cursor_count=1, submitted=False, move_index=0,
                rows=H.screen((14, '     FIGHT PKMN'), (16, '     ITEM  RUN')))


def text_state(map_, xy, rows, cursor=False, **kw):
    return H.state(map_, xy, text_box=True, teacher_screen=dict(rows=rows, cursor=cursor), **kw)


def wartortle(s, hp=None, tackle=8, water=21):
    w = A._wild_mon('WARTORTLE', 16)
    s['team'][0].update(species='WARTORTLE', level=16, max_hp=w['max_hp'], hp=w['max_hp'] if hp is None else hp,
                        stats=w['stats'])
    s['team'][0]['moves'] = [dict(move='TACKLE', pp=tackle), dict(move='WATER_GUN', pp=water),
                             dict(move='TAIL_WHIP', pp=30), dict(move='BUBBLE', pp=26)]
    return s


class OpenTextBox(unittest.TestCase):
    def test_t16_4_center_text_quotes_screen_presses_a_and_walks_to_the_door(self):
        # Old (x3 / x2): "Press A once to read the waiting dialogue, then look..." / "Stop repeating the same input."
        s = text_state('PEWTER_POKECENTER', (3, 3), CENTER_THANKS, hp=31)
        a = A.answer(s, 'What next?', context={})
        self.assertIn('The text box says "Thank you! / Your POK', a['do'])
        self.assertIn('Press A to go on', a['do'])
        self.assertIn('down 4 to (3,7)', a['do'])
        self.assertNotRegex(a['do'], r'(?i)stop repeating|then look before|look once')

    def test_t16_4_heal_question_says_yes_with_a(self):
        s = text_state('PEWTER_POKECENTER', (3, 3), ['Shall we heal your', 'POKéMON?', 'YES'], cursor=True)
        a = A.answer(s, 'What should I do now?', context={})
        self.assertIn('heal question', a['do'])
        self.assertIn('press A to say YES', a['do'])
        self.assertIn('walk to the door: down 4 to (3,7)', a['do'])

    def test_t16_4_same_screen_again_gives_a_concrete_press(self):
        # 591 looks and 7 asks in a row on one screen: the third identical answer becomes a key sequence.
        s = text_state('PEWTER_POKECENTER', (3, 3), CENTER_THANKS, hp=31)
        ctx, out = {}, None
        for _ in range(4):
            out = A.answer(s, 'What is happening?', context=ctx)
        self.assertRegex(out['do'], r'press these in ONE command: b\*3 down\*3')   # R16: max 6 presses (was down*4)
        self.assertNotRegex(out['do'], r'(?i)stop repeating')

    def test_t16_5_route3_pc_sign_loop_gets_quote_press_and_next_step(self):
        # t16-2 n393 (13,4): the 'Are you storing your POKeMON on PC?' text kept coming back; old: "Stop repeating..."
        s = text_state('ROUTE_3', (13, 4), SIGN, hp=31, events=H.beaten(0, 1))
        a = A.answer(s, 'A text box keeps repeating: Are you storing your POKeMON on PC?', context={})
        self.assertIn('The text box says "Are you storing your / POK', a['do'])
        self.assertIn('Press A to go on (B closes a finished box)', a['do'])
        self.assertIn('next toward Mt. Moon entrance', a['do'])
        loop = A.answer(s, 'Stop?', context={'text_loop': {'repeats': 3, 'recent': [], 'at': None}})
        self.assertIn('Press B once now to close it, and do NOT press A again', loop['do'])
        self.assertIn('Then walk away: Next toward', loop['do'])
        self.assertNotRegex(loop['do'], r'(?i)stop repeating')

    def test_yes_no_name_and_number_boxes_get_a_button(self):
        yes = A.answer(text_state('ROUTE_3', (13, 4), ['Do you want it?', 'YES'], True, hp=31), 'what?', context={})
        self.assertIn('Press B to say NO', yes['do'])
        name = A.answer(text_state('ROUTE_3', (13, 4), ['Your NAME?', 'A B C D E'], True, hp=31), 'what?', context={})
        self.assertIn('press START', name['do'])
        many = A.answer(text_state('ROUTE_3', (13, 4), ['HOW MANY?', 'x02'], True, hp=31), 'what?', context={})
        self.assertIn('up or down', many['do'])

    def test_readiness_question_with_text_open_keeps_the_verdict(self):
        s = text_state('ROUTE_3', (11, 6), SIGN, hp=31)
        a = A.answer(s, 'How can I pass without losing Pokémon?', context={})
        self.assertIn('The text box says', a['do'])
        self.assertIn('has seen you: the fight cannot be avoided now. Press A to read on.', a['do'])

    def test_no_meta_words_in_text_answers(self):
        for rows in (CENTER_THANKS, SIGN, ['Do you want it?', 'YES']):
            s = text_state('ROUTE_3', (13, 4), rows, True, hp=31)
            ctx = {}
            for _ in range(4):
                a = A.answer(s, 'what?', context=ctx)
                self.assertIsNone(META.search(A.text(a)), A.text(a))


class BeatenTrainers(unittest.TestCase):
    def lass_east(self):
        # t16-2 n125/n261: Route 3 (15,9), the Lass:1 (event 2) stands at (16,9) after the fight.
        s = H.state('ROUTE_3', (15, 9), hp=31, events=H.beaten(0, 1, 2), bag=[dict(item='POTION', count=5)])
        s['teacher_objects'] = {'ROUTE_3': [dict(id=4, x=16, y=9, hidden=False, facing='LEFT')]}
        return s

    def test_beaten_lass_is_a_wall_not_a_fight(self):
        q = ("I'm on ROUTE_3 at (15,9), facing down. The beaten Lass is standing at (16,9) east of me. "
             "East is blocked. Which tile can I step to?")
        a = A.answer(self.lass_east(), q, context={})
        self.assertNotIn('has seen you', a['do'])
        self.assertNotIn('battle is starting', a['do'])
        self.assertTrue(a['do'].startswith("You are at (15,9); going right is blocked. Detour: Next toward"), a['do'])
        self.assertIn('already beaten', a['why'])
        self.assertIn('walk around them', a['why'])

    def test_unbeaten_lass_still_starts_a_fight(self):
        # t16-5 n324: Mt. Moon 1F (30,7) in sight of the UNBEATEN Lass at (30,4) (flags unbeaten, 4 blackouts followed).
        a = A.answer(H.state('MT_MOON_1F', (30, 7), level=16), "I'm at (30,7) facing up; going up is blocked.",
                     context={})
        self.assertTrue(a['do'].startswith('A trainer has seen you: the Lass at (30,4)'), a['do'])

    def test_beaten_mt_moon_lass_standing_below_her_post_is_a_wall(self):
        s = H.state('MT_MOON_1F', (30, 7), level=16, events={'EVENT_BEAT_MT_MOON_1_TRAINER_2': True})
        s['teacher_objects'] = {'MT_MOON_1F': [dict(id=3, x=30, y=6, hidden=False, facing='DOWN')]}
        a = A.answer(s, "I'm in MT_MOON_1F at (30,7) facing up; going up is blocked. Where is the way east?", context={})
        self.assertNotIn('has seen you', a['do'])
        self.assertIn('A person stands on (30,6): the Lass, already beaten', a['why'])
        self.assertIn('going up is blocked. Detour: Next toward', a['do'])

    def test_beaten_flags_are_read_for_every_checked_trainer(self):
        import read_state as R
        import r11_maps as M
        self.assertEqual([e for e in M.events() if e not in R.EVENTS], [])

    def test_facing_word_does_not_choose_the_blocked_direction(self):
        # t16-2 n440: "facing down. East is blocked" was answered as "going down is blocked".
        self.assertEqual(T.blocked_direction("i am on route_3 at (19,4), facing down. east is blocked: a beaten lass"), 'right')
        self.assertEqual(T.blocked_direction("i'm on route_4 at (19,6), blocked going right."), 'right')
        self.assertEqual(T.blocked_direction("i'm at (30,7) facing up; going up is blocked"), 'up')
        self.assertEqual(T.blocked_direction("the path to the south is stuck"), 'down')


class PureDetours(unittest.TestCase):
    def test_t16_2_n440_detour_has_no_readiness_text(self):
        # Old: "going down is blocked. Detour: Not ready: heal at the Pewter Center first. Then the Bug Catcher ..."
        s = H.state('ROUTE_3', (19, 4), level=14, hp=14, events=H.beaten(0, 1, 4), bag=[dict(item='POTION', count=2)])
        s['teacher_objects'] = {'ROUTE_3': [dict(id=6, x=20, y=4, hidden=False, facing='LEFT')]}
        q = "I am on ROUTE_3 at (19,4), facing down. East is blocked: a beaten Lass stands at (20,4)."
        a = A.answer(s, q, context={})
        self.assertIn('going right is blocked. Detour: Next toward', a['do'])
        for bad in ('Not ready', 'Ready:', 'heal', 'likely win', 'likely loss', 'Potion'):
            self.assertNotIn(bad, a['do'])
        for line in a['details']:
            self.assertNotRegex(line, r'^(Heal first|Not ready|Fight plan)')

    def test_t16_5_n310_ledge_detour_stays_pure(self):
        s = H.state('ROUTE_4', (19, 6), level=16, hp=47, events=H.beaten(0, 1, 2, 3, 4, 5, 6, 7))
        a = A.answer(s, "I'm on ROUTE_4 at (19,6), blocked going right. Which way leads east to Cerulean City?",
                     context={})
        self.assertIn('going right is blocked. Detour: ', a['do'])
        self.assertNotRegex(a['do'], r'Not ready|likely (win|loss)|Heal first')

    def test_unconfirmed_tile_first_answer_way_is_pure(self):
        s = H.state('ROUTE_3', (27, 6), level=15, hp=26, events=H.beaten(0, 1, 2, 3))
        a = A.answer(s, 'The path east looks blocked. What now? I am blocked going down', context={})
        self.assertNotRegex(A.text(a), r'Way: (Not ready|Ready)')


class HealingChoice(unittest.TestCase):
    def route3(self, xy, hp, potions, events, level=14):
        return H.state('ROUTE_3', xy, level=level, hp=hp, events=events,
                       bag=[dict(item='POTION', count=potions)] if potions else [])

    def test_t16_2_n261_potions_before_a_center_trip(self):
        # Squirtle L12 21/33 HP, 2 Potions, Route 3 (15,9): sent back to Pewter (about 100 commands) in round 12.
        s = self.route3((15, 9), 21, 2, H.beaten(0, 1, 2), level=12)
        a = A.answer(s, 'I won the Lass battle. Should I go back to the Pewter Center to heal?', context={})
        self.assertTrue(a['do'].startswith('No Center trip is needed: you have 2 Potions.'), a['do'])
        self.assertNotIn('Next toward PEWTER', a['do'])
        self.assertIn('If you still want the Center: Next toward the Pewter Center', ' '.join(a['details']))

    def test_low_hp_uses_potions_from_the_menu_then_goes_on(self):
        s = self.route3((19, 4), 6, 3, H.beaten(0, 1))
        a = A.answer(s, 'Am I ready for the next trainer?', context={})
        self.assertRegex(a['do'], r'^Use \d Potions? now instead of walking to a Center')
        self.assertIn('press START, pick ITEM, press A on POTION, press A on USE, pick SQUIRTLE, press A', a['do'])
        self.assertIn('Then the Bug Catcher at (24,6) is a likely win (estimate)', a['do'])

    def test_no_potions_before_the_middle_heal_in_pewter(self):
        a = A.answer(self.route3((19, 4), 14, 0, H.beaten(0, 1)), 'Where should I heal?', context={})
        self.assertIn('heal at the Pewter Center', a['do'])

    def test_no_potions_past_the_middle_heal_at_the_route_4_center(self):
        for events in (H.beaten(0, 1, 6), H.beaten(0, 1)):          # with and without the last needed fight beaten
            a = A.answer(self.route3((33, 8), 14, 0, events), 'Where should I heal?', context={})
            self.assertIn('Route 4 Center by Mt. Moon', a['do'])
            self.assertNotIn('Pewter Center', a['do'])
        self.assertEqual(T.nearest_center(A, self.route3((33, 8), 14, 0, H.beaten(0, 1))), 'MT_MOON_POKECENTER')
        self.assertEqual(T.nearest_center(A, self.route3((19, 4), 14, 0, H.beaten(0, 1))), 'PEWTER_POKECENTER')

    def test_fight_model_calibration_is_unchanged(self):
        # Same outcomes as the R12 checks (t15 real fights): healed L11 beats the Bug Catcher, L12 loses to the Youngster.
        def run(key, level, hp, pots=0):
            s = H.state(level=level)
            s['team'][0]['hp'] = hp
            win, left = T.outcome(A, T.mons(A, s), [key], pots)
            return win and left >= T.MARGIN
        self.assertTrue(run('BugCatcher:4', 11, 31))
        self.assertFalse(run('BugCatcher:4', 11, 15))
        self.assertFalse(run('Youngster:1', 12, 34))
        self.assertTrue(run('Youngster:1', 12, 34, pots=3))

    def test_potion_plan_is_skipped_when_the_fight_is_lost_even_with_potions(self):
        s = self.route3((13, 5), 8, 1, H.beaten(0), level=12)         # the Youngster beats L12 even with one Potion
        a = A.answer(s, 'Should I go back to the Pewter Center?', context={})
        self.assertIn('Next toward the Pewter Center', a['do'])


class BattleHelp(unittest.TestCase):
    def fight(self, foe, hp=None, tackle=8, bag=None):
        s = wartortle(H.state('MT_MOON_1F', (30, 7)), hp=hp, tackle=tackle)
        if bag is not None:
            s['bag'] = bag
        return H.in_battle(s, foe, 11, ui=COMMANDS)

    def test_t16_5_resisted_water_gun_is_named_and_tackle_menu_given(self):
        # Mt. Moon 1F Lass: ODDISH / BELLSPROUT (Grass): Water Gun and Bubble do half damage.
        for foe in ('ODDISH', 'BELLSPROUT'):
            a = A.answer(self.fight(foe), 'what move?', context={})
            text = ' '.join(a['details'])
            self.assertIn('Best move now: TACKLE', text)
            self.assertIn('Menu: FIGHT is top-left: press A on FIGHT', text)
            self.assertIn(f'Skip WATER_GUN and BUBBLE: {foe} resists them (half damage)', text)
            self.assertTrue(a['do'].startswith('Press A once to open FIGHT, then pick TACKLE'), a['do'])

    def test_low_pp_names_the_next_best_move_and_slot(self):
        a = A.answer(self.fight('ODDISH', hp=20, tackle=2), 'which move?', context={})
        text = ' '.join(a['details'])
        self.assertIn('TACKLE is nearly out of PP (2 left). Next best: WATER_GUN', text)
        self.assertIn('move 2 of 4 in the list', text)

    def test_potion_line_and_no_potion_switch_line(self):
        with_potion = A.answer(self.fight('ODDISH', bag=[dict(item='POTION', count=2)]), 'help', context={})
        self.assertRegex(' '.join(with_potion['details']), r'Use a Potion when WARTORTLE is below 16 HP \(ITEM, pick it, A')
        none = A.answer(self.fight('ODDISH', bag=[]), 'help', context={})
        self.assertIn('No Potion: if WARTORTLE falls below 16 HP, switch to CATERPIE (PKMN, pick it, A, SWITCH, A)',
                      ' '.join(none['details']))

    def test_close_race_the_lead_keeps_fighting_instead_of_switching_to_a_weak_backup(self):
        # L16 Squirtle vs ODDISH L11 is a coin flip for the old "safe play" (it said: switch to CATERPIE L5).
        s = H.in_battle(H.state('MT_MOON_1F', (30, 7), level=16), 'ODDISH', 11, ui=COMMANDS)
        a = A.answer(s, 'what move?', context={})
        self.assertNotIn('Switch to', a['details'][0])
        self.assertIn('should win this fight (estimate)', a['why'])
        self.assertIn('pick TACKLE', a['do'])

    def test_no_meta_words_in_battle_help(self):
        a = A.answer(self.fight('ODDISH', hp=20, tackle=2), 'which move?', context={})
        self.assertIsNone(META.search(A.text(a)), A.text(a))


if __name__ == '__main__':
    unittest.main()
