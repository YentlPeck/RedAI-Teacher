"""R11 harness tests: synthetic states/logs and a fake Game only; never open PyBoy."""
import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch, Mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARENA_SRC = HERE.parent / 'arena'
sys.path[:0] = [str(ARENA_SRC), str(HERE.parent / 'tools')]
import settings  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = load('r11_play', ARENA_SRC / 'play.py')
M = load('r11_prompt', ARENA_SRC / 'make_prompt.py')
S = load('r11_score', ARENA_SRC / 'score_r12.py')
NAMES = {1: 'VIRIDIAN_CITY', 2: 'PEWTER_CITY', 3: 'CERULEAN_CITY', 15: 'ROUTE_4',
         59: 'MT_MOON_1F', 60: 'MT_MOON_B1F', 61: 'MT_MOON_B2F', 65: 'CERULEAN_GYM'}


def provenance(budget):
    return S.WAVE_STARTS['segment' if budget == 650 else 'full']


def edge(source=(60, 27, 3), destination=(15, 24, 5), cause='doorway'):
    return dict(source=list(source), destination=list(destination), cause=cause)


def row(n, map_id=2, cmd='press', badges=1, edges=()):
    return dict(n=n, cmd=cmd, map=NAMES[map_id], map_id=map_id, done=[],
                badges_byte=badges, map_transitions=list(edges))


def init(budget, map_id=2):
    start, sha = provenance(budget)
    return dict(row(0, map_id, 'start'), budget=budget, start=start, start_sha256=sha)


def marker(used, budget, last):
    return dict(n=used, cmd='resume', accepted_commands=used, resume_index=1, budget=budget,
                map=last['map'], done=last['done'], message=S.RESUME_MESSAGE.format(budget=budget),
                player_ref='same-session', stop_ref='saved-first-final')


def write_log(folder, rows):
    (folder / 'log.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')


class Output(io.StringIO):
    def reconfigure(self, **kwargs):
        pass


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(tmp.cleanup)
        self.arena = Path(tmp.name)

    def game(self, budget=650, group='plain', model='test-model', name='g', rows=None, start=None):
        folder = self.arena / name
        folder.mkdir()
        default_start, sha = provenance(budget)
        meta = dict(group=group, model=model, budget=budget, start=start or default_start, start_sha256=sha)
        (folder / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
        (folder / 'game.state').write_bytes(b'synthetic saved game')
        write_log(folder, rows if rows is not None else [init(budget), row(1)])
        return folder

    def main(self, args):
        out = Output()
        with patch.object(P, 'ARENA', self.arena), patch.object(sys, 'argv', ['play.py'] + args), redirect_stdout(out):
            P.main()
        return out.getvalue()


class Harness(TempCase):
    def test_start_state_hash_path_and_init_budget(self):
        for budget in (650, 1200):
            with self.subTest(budget=budget):
                state = self.arena / f'input-{budget}.state'
                state.write_bytes(b'fake state, never an emulator state')
                s = dict(place=dict(map='PEWTER_CITY', map_id=2), story=dict(done=['badge1']))
                with patch.object(P, 'Game') as fake, patch.object(P, 'view', return_value=(s, 'COMMON VIEW')):
                    out = self.main(['start', f'g{budget}', '--group', 'plain', '--budget', str(budget), '--start-state', str(state)])
                folder = self.arena / f'g{budget}'
                meta = json.loads((folder / 'meta.json').read_text())
                first = P.history_rows(folder)[0]
                self.assertEqual(meta['start'], str(state.relative_to(ROOT)))
                self.assertEqual(meta['start_sha256'], hashlib.sha256(state.read_bytes()).hexdigest())
                self.assertEqual({k: first[k] for k in ('start', 'start_sha256', 'budget')},
                                 {k: meta[k] for k in ('start', 'start_sha256', 'budget')})
                self.assertEqual(out, f'COMMON VIEW\nCommands used: 0 of {budget}\n')
                fake.return_value.tick.assert_called_once_with(300)
                self.assertEqual((folder / 'game.state').read_bytes(), state.read_bytes())

    def test_default_start_stays_live_without_copying_it(self):
        self.assertEqual(P.START, settings.START_STATE)
        self.assertFalse((ARENA_SRC / 'start.state').exists())
        # Intercept the read: no real state bytes are copied by this test.
        original = Path.read_bytes
        calls = []
        def read(path):
            if path == P.START:
                calls.append(path)
                return b'dummy default'
            return original(path)
        s = dict(place=dict(map='PEWTER_CITY', map_id=2), story=dict(done=[]))
        with patch.object(Path, 'read_bytes', read), patch.object(P, 'Game') as game, \
                patch.object(P, 'view', return_value=(s, 'VIEW')):
            game.return_value.m = bytearray(0x10000)
            self.main(['start', 'g', '--group', 'plain', '--budget', '1200'])
        # R16: no --start-state = fresh power-on boot; the room start is no longer read (was [P.START]).
        self.assertEqual(calls, [])
        self.assertEqual(json.loads((self.arena / 'g' / 'meta.json').read_text())['start'], 'power-on')

    def test_count_and_hard_stop_use_run_budget_without_game(self):
        for budget in (650, 1200):
            with self.subTest(budget=budget):
                d = self.game(budget, name=f'g{budget}', rows=[init(budget)] + [row(n) for n in range(1, budget + 1)])
                out = Output()
                before = (d / 'log.jsonl').read_bytes()
                with patch.object(P, 'Game') as fake, redirect_stdout(out):
                    with self.assertRaisesRegex(SystemExit, f'^Your {budget} commands are used up. Stop and write your report.$'):
                        P.play(argparse.Namespace(cmd='look', rest=[]), d)
                fake.assert_not_called()
                self.assertEqual(out.getvalue(), f'Commands used: {budget} of {budget}\n')
                self.assertEqual(before, (d / 'log.jsonl').read_bytes())

    def test_last_command_is_accepted_and_logs_badge_and_map(self):
        for budget in (650, 1200):
            with self.subTest(budget=budget):
                d = self.game(budget, name=f'g{budget}', rows=[init(budget)] + [row(n) for n in range(1, budget)])
                mem = bytearray(0x10000)               # R16: play.py also reads the milestone bytes
                mem[P.R.A('wObtainedBadges')] = 3
                g = Mock(m=mem, map_transitions=[])
                g.where.return_value = (3, 1, 2)
                s = dict(place=dict(map='CERULEAN_CITY', map_id=3, x=1, y=2), story=dict(done=['badge2']),
                         money=100, team=[], battle=None)
                with patch.object(P, 'Game', return_value=g), patch.object(P, 'view', return_value=(s, 'VIEW')), redirect_stdout(Output()) as out:
                    P.play(argparse.Namespace(cmd='look', rest=[]), d)
                self.assertEqual(out.getvalue(), f'VIEW\nCommands used: {budget} of {budget}\n')
                last = P.history_rows(d)[-1]
                self.assertEqual((last['n'], last['map_id'], last['badges_byte']), (budget, 3, 3))

    def test_press_logs_eastern_exit_within_command(self):
        d = self.game()
        # Real frame observer; fake memory/ticks only. Two map changes and a later
        # step occur in one press, so neither final coordinates nor button edges suffice.
        g = P.Game.__new__(P.Game)
        g.m = bytearray(0x10000)
        g.map_transitions, g.transition_cause = [], None
        def position(p):
            g.m[0xD35E], g.m[0xD362], g.m[0xD361] = p
        position((61, 5, 7))
        frames = iter([(60, 27, 3), (15, 27, 3), (15, 24, 5), (15, 24, 6)])
        def tick(*args):
            position(next(frames, g.where()))
            if g.where()[0] == 15:
                g.m[P.R.A('wWarpedFromWhichMap')] = 60
                g.m[P.R.A('wWarpedFromWhichWarp')] = 7
                g.m[P.R.A('wDestinationWarpID')] = 2
        g.gb = Mock()
        g.gb.tick.side_effect = tick
        g.m[P.R.A('wObtainedBadges')] = 1
        g._press = lambda button: g.tick(4)
        g.close = Mock()
        s = dict(place=dict(map='ROUTE_4', map_id=15, x=24, y=6), story=dict(done=[]), money=100, team=[], battle=None)
        with patch.object(P, 'Game', return_value=g), patch.object(P, 'view', return_value=(s, 'VIEW')), redirect_stdout(Output()):
            P.play(argparse.Namespace(cmd='press', rest=['down']), d)
        logged = P.history_rows(d)[-1]['map_transitions']
        self.assertEqual(logged[0], edge((61, 5, 7), (60, 27, 3), None))
        self.assertEqual(logged[1], dict(edge(), observed_source=[60, 27, 3], observed_destination=[15, 27, 3]))
        self.assertEqual(g.where(), (15, 24, 6))
        self.assertEqual(S.score_game(dict(run='g', group='plain', model='test-model'), self.arena,
                                      'g: stopped')['after']['T1'], 2)
        self.assertEqual(g.gb.tick.call_count, 64)  # four existing frames + original fade wait

    def test_frame_observer_marks_rope_and_blackout_not_doorway(self):
        for cause in ('escape_warp', 'blackout', None):
            with self.subTest(cause=cause):
                g = P.Game.__new__(P.Game)
                g.m = bytearray(0x10000)
                g.map_transitions, g.transition_cause = [], None
                g.m[0xD35E], g.m[0xD362], g.m[0xD361] = (60, 27, 3)
                g.m[P.R.A('wWarpedFromWhichMap')] = 60  # stale doorway registers
                g.m[P.R.A('wWarpedFromWhichWarp')] = 7
                g.m[P.R.A('wDestinationWarpID')] = 2
                flags = P.R.A('wStatusFlags6' if 'wStatusFlags6' in P.R.SYM else 'wd732')
                g.m[flags] = 1 << 6 if cause == 'escape_warp' else 0
                g.m[P.R.A('wIsInBattle')] = 0xFF if cause == 'blackout' else 0
                def tick(*args):
                    g.m[flags] = g.m[P.R.A('wIsInBattle')] = 0
                    g.m[0xD35E], g.m[0xD362], g.m[0xD361] = (15, 24, 5) if cause is None else (15, 11, 6)
                g.gb = Mock()
                g.gb.tick.side_effect = tick
                g.tick()
                self.assertEqual(g.map_transitions,
                                 [edge(destination=(15, 24, 5) if cause is None else (15, 11, 6), cause=cause)])

    def test_start_requires_budget_before_creating_game(self):
        # R16 (PokeBench rules): the budget defaults to 1000 (was: start refused without --budget).
        s = dict(place=dict(map='PALLET_TOWN', map_id=0), story=dict(done=[]))
        with patch.object(P, 'Game') as game, patch.object(Path, 'read_bytes') as read, \
                patch.object(P, 'view', return_value=(s, 'VIEW')):
            game.return_value.m = bytearray(0x10000)
            out = self.main(['start', 'new', '--group', 'plain'])
        read.assert_not_called()
        self.assertEqual(json.loads((self.arena / 'new' / 'meta.json').read_text())['budget'], 1000)
        self.assertEqual(out, 'VIEW' + chr(10) + 'Commands used: 0 of 1000' + chr(10))

    def test_rom_side_save_refusal_is_neutral_and_free(self):
        d = self.game()
        before = (d / 'log.jsonl').read_bytes()
        count = P.commands_used(P.history_rows(d))
        original = Path.exists
        def exists(path):
            return True if path == P.ROM_RAM else original(path)
        with patch.object(Path, 'exists', exists), patch.object(P, 'Game') as game, \
                patch.object(P.guard, 'check') as guard, redirect_stdout(Output()) as out:
            with self.assertRaises(SystemExit) as stopped:
                self.main(['look', 'g'])
        self.assertEqual(str(stopped.exception), 'Game tool unavailable. No command was used.')
        self.assertNotRegex(out.getvalue()+str(stopped.exception),
                            r'(?i)\b(test|leader|coordinator|round|experiment)\b|teacher group|plain group|red\.gb')
        game.assert_not_called()
        guard.assert_not_called()
        self.assertEqual(before, (d / 'log.jsonl').read_bytes())
        self.assertEqual(count, P.commands_used(P.history_rows(d)))

    def test_ask_logs_raw_badge_before_close(self):
        import advise
        d = self.game(group='teacher')
        mem = bytearray(0x10000)                       # R16: play.py also reads the milestone bytes
        mem[P.R.A('wObtainedBadges')] = 3
        g = Mock(m=mem)
        s = dict(place=dict(map='CERULEAN_GYM', map_id=65), story=dict(done=[]))
        def close(**kwargs):
            g.m.clear()
        g.close.side_effect = close
        with patch.object(P, 'Game', return_value=g), patch.object(P.R, 'state_from_pyboy', return_value=s), \
                patch.object(P, 'teacher_state', return_value=s), patch.object(advise, 'answer', return_value={'do': 'reply'}), \
                patch.object(advise, 'text', return_value='reply'), redirect_stdout(Output()):
            P.play(argparse.Namespace(cmd='ask', rest=[]), d)
        self.assertEqual(P.history_rows(d)[-1]['badges_byte'], 3)

    def test_resume_is_neutral_one_free_command_and_preserves_files(self):
        for budget in (650, 1200):
            with self.subTest(budget=budget):
                d = self.game(budget, name=f'g{budget}')
                (d / 'last_call.json').write_bytes(b'cooldown sentinel')
                before = {p.name: p.read_bytes() for p in d.iterdir() if p.name not in ('log.jsonl', 'busy.lock')}
                out = self.main(['resume', d.name, '--player-ref', 'same-session', '--stop-ref', 'saved-first-final'])
                self.assertEqual(out, f'Continue playing with the same commands until all {budget} commands are used.\nCommands used: 1 of {budget}\n')
                rows = P.history_rows(d)
                self.assertEqual(rows[-1], dict(rows[-1], **marker(1, budget, rows[-2])))
                self.assertEqual(P.commands_used(rows), 1)
                self.assertEqual(before, {p.name: p.read_bytes() for p in d.iterdir() if p.name not in ('log.jsonl', 'busy.lock')})
                self.assertNotIn(d / 'busy.lock', P.guard._held)
                with redirect_stdout(Output()), self.assertRaisesRegex(SystemExit, 'already recorded'):
                    P.resume(d, 'same-session', 'saved-first-final')

    def test_resume_requires_refs_unfinished_game_and_free_lock(self):
        for condition in ('refs', 'finished', 'busy'):
            with self.subTest(condition=condition):
                budget = 650
                rows = [init(budget)] + [row(n) for n in range(1, budget + 1)] if condition == 'finished' else None
                d = self.game(rows=rows, name=condition)
                before = (d / 'log.jsonl').read_bytes()
                if condition == 'busy':
                    with patch.object(P.guard, '_take_lock', return_value=False), redirect_stdout(Output()), self.assertRaisesRegex(SystemExit, 'command is running'):
                        P.resume(d, 'player', 'stop')
                else:
                    with redirect_stdout(Output()), self.assertRaises(SystemExit):
                        P.resume(d, None if condition == 'refs' else 'player', 'stop')
                self.assertEqual(before, (d / 'log.jsonl').read_bytes())

    def test_guard_refusal_and_release_stay_before_game(self):
        d = self.game()
        before = (d / 'log.jsonl').read_bytes()
        with patch.object(P.guard, 'shell_key', return_value='key'), \
                patch.object(P.guard, 'check', side_effect=P.guard.Blocked('blocked')) as check, \
                patch.object(P, 'Game') as game, self.assertRaises(P.guard.Blocked):
            self.main(['look', 'g'])
        check.assert_called_once_with(d, key='key')
        game.assert_not_called()
        self.assertEqual(before, (d / 'log.jsonl').read_bytes())
        with patch.object(P.guard, 'shell_key', return_value='key'), patch.object(P.guard, 'check'), \
                patch.object(P.guard, 'release') as release, patch.object(P, 'play', side_effect=SystemExit('stop')), self.assertRaises(SystemExit):
            self.main(['look', 'g'])
        release.assert_called_once_with(d, key='key')


class Prompts(TempCase):
    def test_run_budget_and_arm_equality_for_both_waves(self):
        for budget, start in ((650, 'teacher/dev-r23/states/post_brock_pewter.state'), (1200, str(M.START))):
            with self.subTest(budget=budget):
                outputs = []
                for group in ('plain', 'teacher'):
                    d = self.game(budget, group, name=f'{group}{budget}', start=start)
                    with patch.object(M, 'ARENA', self.arena):
                        outputs.append(M.prompt(d.name))
                plain, teacher = outputs
                normalized = '\n'.join(line for line in teacher.split('\n') if 'arena/play.py ask ' not in line)
                normalized = normalized.replace(', ask', '').replace(f'teacher{budget}', f'plain{budget}')
                self.assertEqual(plain, normalized)
                for text in outputs:
                    self.assertIn(f'You have {budget} commands in total', text)
                    # R16 (Sol R16 B1): stop on Done or budget (was "The ONLY reason to stop is ...").
                    self.assertIn(f'Stop only when the tool says the game is done or all {budget} commands are used.', text)
                    self.assertIn('arena/play.py', text)
                    self.assertNotIn('600', text)
                    self.assertNotIn('MISTY_PLAN', text)
                    self.assertEqual('saved game in progress' in text, budget == 650)
                    self.assertNotIn('post_brock', text)

    def test_prompt_cannot_override_metadata(self):
        self.game()
        with patch.object(M, 'ARENA', self.arena):
            with self.assertRaisesRegex(ValueError, 'budget differs'):
                M.prompt('g', 'plain', 1200)
            with self.assertRaisesRegex(ValueError, 'group differs'):
                M.prompt('g', 'teacher', 650)
            self.assertEqual(M.prompt('g'), M.prompt('g', 'plain', 650))


class Scoring(TempCase):
    def score(self, rows, budget=650, notes='g: stopped', name='g'):
        self.game(budget, name=name, rows=rows)
        return S.score_game(dict(run=name, group='plain', model='test-model'), self.arena, notes, budget)

    def test_first_route4_exit_city_and_raw_badge(self):
        rows = [init(650), row(1, 15), row(2, 59), row(3, 15, edges=[edge((59, 14, 35), (15, 18, 5), None)]),
                row(4, 61), row(5, 15, edges=[edge((61, 5, 7), (60, 23, 3), None), edge()]),
                row(6, 3, cmd='ask'), row(7, 65), row(8, 65, cmd='look', badges=3), row(9, 3)]
        rows[7]['done'] = ['badge2']  # milestone alone is not raw badge evidence
        result = self.score(rows)['after']
        self.assertEqual((result['T1'], result['T2'], result['T3'], result['C']), (5, 6, 8, 19 / 3))
        self.assertTrue(result['badge_by_cap'])
        self.assertEqual(result['asks'], 1)

    def test_rope_blackout_unknown_and_wrong_tiles_never_earn_exit(self):
        cases = [edge(destination=(15, 11, 6), cause=cause) for cause in ('escape_warp', 'blackout', None)]
        cases += [edge(cause=cause) for cause in ('escape_warp', 'blackout', None)]
        cases += [edge(source=(60, 26, 3)), edge(destination=(15, 24, 6))]
        for i, transition in enumerate(cases):
            with self.subTest(edge=transition):
                rows = [init(650), row(1, 60), dict(row(2, 15, edges=[transition]), x=11, y=6)]
                name = f'no-exit-{i}'
                self.assertEqual(self.score(rows, name=name, notes=f'{name}: stopped')['after']['T1'], 650)

    def test_historical_map_only_edges_are_rejected_without_fallback(self):
        with self.assertRaisesRegex(ValueError, 'ambiguous map transitions'):
            self.score([init(650), row(1, 60), row(2, 15, edges=[[60, 15]])])
        rows = [init(650), row(1, 60), row(2, 15)]
        del rows[-1]['map_transitions']
        self.assertEqual(self.score(rows, name='no-evidence', notes='no-evidence: stopped')['after']['T1'], 650)

    def test_verified_exit_then_another_map_inside_batch(self):
        rows = [init(650), row(1, 60), row(2, 3, edges=[edge(), edge((15, 89, 6), (3, 0, 6), None)])]
        result = self.score(rows)['after']
        self.assertEqual((result['T1'], result['T2']), (2, 2))

    def test_wrong_wave_start_rejected_even_when_meta_and_init_agree(self):
        for budget, other in ((1200, 'segment'), (650, 'full')):
            name = f'wrong-{budget}'
            rows = [init(budget), row(1, 65, badges=3)]
            rows[0].update(start=S.WAVE_STARTS[other][0], start_sha256=S.WAVE_STARTS[other][1])
            d = self.game(budget, name=name, rows=rows)
            meta = json.loads((d / 'meta.json').read_text())
            meta.update(start=rows[0]['start'], start_sha256=rows[0]['start_sha256'])
            (d / 'meta.json').write_text(json.dumps(meta))
            with patch.object(S, 'progress') as progress, self.assertRaisesRegex(ValueError, 'wave start provenance'):
                S.score_game(dict(run=name, group='plain', model='test-model'), self.arena)
            progress.assert_not_called()

    def test_frozen_hashes_and_paths_match_validated_manifest(self):
        manifest = json.loads(settings.fixture('post_brock_pewter.json').read_text())
        # The manifest is historical (written for dev-r11); dev-r23 uses the identical bytes in its own folder.
        historical = manifest['state_path'].replace('\\', '/')
        self.assertEqual(historical, 'teacher/dev-r11/states/post_brock_pewter.state')
        self.assertEqual(S.WAVE_STARTS['segment'], (historical.replace('dev-r11', 'dev-r23'), manifest['state_sha256']))
        self.assertEqual(hashlib.sha256(settings.fixture('post_brock_pewter.state').read_bytes()).hexdigest(),
                         manifest['state_sha256'])
        self.assertEqual(S.WAVE_STARTS['full'], (manifest['start_state_path'].replace('\\', '/'), manifest['start_state_sha256']))
        for budget in (650, 1200):
            path, sha = provenance(budget)
            S.validate_start(dict(start=path.replace('/', '\\'), start_sha256=sha), 'segment' if budget == 650 else 'full')
            S.validate_start(dict(start=str(ROOT / path), start_sha256=sha), 'segment' if budget == 650 else 'full')

    def test_start_does_not_count_arrivals_or_badge(self):
        start = init(650, 3)
        start['badges_byte'] = 3
        result = self.score([start, row(1, 2)])['after']
        self.assertEqual((result['T1'], result['T2'], result['T3'], result['C']), (650, 650, 650, 650))
        self.assertFalse(result['badge_by_cap'])

    def test_b1f_retreat_via_1f_is_not_eastern_exit(self):
        rows = [init(650), row(1, 60), row(2, 15, edges=[edge((60, 5, 5), (59, 5, 5), None),
                                                     edge((59, 14, 35), (15, 18, 5), None)])]
        result = self.score(rows)['after']
        self.assertEqual(result['T1'], 650)

    def test_caps_at_each_budget_badge_at_cap_not_beyond(self):
        for budget in (650, 1200):
            with self.subTest(budget=budget):
                rows = [init(budget)] + [row(n) for n in range(1, budget)] + [row(budget, 65, badges=3), row(budget + 1, 3)]
                a = self.score(rows, budget, notes='', name=f'g{budget}')['after']
                self.assertEqual((a['T1'], a['T2'], a['T3'], a['C']), (budget, budget, budget, budget))
                self.assertTrue(a['badge_by_cap'])
                self.assertEqual(a['commands_used'], budget)
                self.assertEqual(a['commands_logged'], budget + 1)
                rows[-2] = row(budget, 65)
                rows[-1] = row(budget + 1, 65, badges=3)
                a = self.score(rows, budget, notes='', name=f'h{budget}')['after']
                self.assertFalse(a['badge_by_cap'])

    def test_unfinished_and_voluntary_early_stop(self):
        self.game(rows=[init(650), row(1, 3)])
        game = dict(run='g', group='plain', model='test-model')
        unfinished = S.score_game(game, self.arena)['after']
        self.assertEqual((unfinished['T1'], unfinished['T2'], unfinished['C']), (None, 1, None))
        final = S.score_game(game, self.arena, 'g: voluntarily stopped')['after']
        self.assertEqual((final['T1'], final['T2'], final['T3']), (650, 1, 650))
        self.assertTrue(final['early_stop'])

    def test_before_after_resume_and_completion_evidence(self):
        for budget in (650, 1200):
            with self.subTest(budget=budget):
                rows = [init(budget), row(1, 60)]
                rows += [marker(1, budget, rows[-1]), row(2, 15, edges=[edge()]), row(3, 3), row(4, 65, badges=3)]
                name = f'g{budget}'
                self.game(budget, name=name, rows=rows)
                game = dict(run=name, group='plain', model='test-model')
                result = S.score_game(game, self.arena, f'{name}: stopped')
                self.assertEqual(result['before']['C'], budget)
                self.assertIsNone(result['after']['C'])
                result = S.score_game(game, self.arena, f'{name}: AFTER resume finished; early final')
                self.assertEqual(result['before']['commands_used'], 1)
                self.assertEqual(result['after']['commands_used'], 4)
                self.assertEqual(result['after']['C'], 3)

    def test_resume_validation_and_rejected_rows(self):
        first = [init(650), row(1)]
        valid = marker(1, 650, first[-1])
        invalid = [dict(valid, n=2), dict(valid, budget=1200), dict(valid, message='Continue with a hint'),
                   dict(valid, stop_ref=''), dict(valid, map='ROUTE_4')]
        for i, bad in enumerate(invalid):
            d = self.game(name=f'g{i}', rows=first + [bad])
            with self.subTest(i=i), self.assertRaises(ValueError):
                S.read_segments(d / 'log.jsonl', 650)
        for i, rows in enumerate((first + [valid, valid], [valid] + first,
                                  first + [dict(row(2), cmd='blocked')], first + [row(3)])):
            d = self.game(name=f'h{i}', rows=rows)
            with self.subTest(i=i), self.assertRaises(ValueError):
                S.read_segments(d / 'log.jsonl', 650)

    def test_partial_tail_pending_interior_damage_fails(self):
        d = self.game()
        with (d / 'log.jsonl').open('a', encoding='utf-8') as f:
            f.write('{"n":')
        game = dict(run='g', group='plain', model='test-model')
        result = S.score_game(game, self.arena, 'g: stopped')
        self.assertIsNone(result['after']['C'])
        self.assertTrue(result['after']['warnings'])
        with (d / 'log.jsonl').open('a', encoding='utf-8') as f:
            f.write('\n' + json.dumps(row(2)) + '\n')
        with self.assertRaises(ValueError):
            S.score_game(game, self.arena)

    def test_missing_log_has_no_measurements(self):
        d = self.game()
        (d / 'log.jsonl').unlink()
        result = S.score_game(dict(run='g', group='plain', model='test-model'), self.arena)
        self.assertEqual(result['after']['status'], 'missing')
        self.assertIsNone(result['after']['C'])

    def test_meta_budget_model_and_init_provenance_are_checked(self):
        d = self.game()
        game = dict(run='g', group='plain', model='test-model')
        for changed in (dict(game, model='wrong'), dict(game, group='teacher')):
            with self.assertRaises(ValueError):
                S.score_game(changed, self.arena)
        with self.assertRaises(ValueError):
            S.score_game(game, self.arena, expected_budget=1200)
        write_log(d, [dict(init(650), start_sha256='wrong'), row(1)])
        with self.assertRaises(ValueError):
            S.score_game(game, self.arena)

    def wave(self, budget=650):
        games = []
        for pair in range(4):
            for group in ('plain', 'teacher'):
                name = f'g{budget}-{pair}-{group}'
                # Teacher wins 3 pairs, ties the fourth; one teacher badge exactly.
                c = 100 if group == 'teacher' and pair < 3 else 300
                data = dict(status='complete', C=c, badge_by_cap=group == 'teacher' and pair == 0)
                games.append(dict(run=name, group=group, model=f'model-{pair // 2}', budget=budget,
                                  start=provenance(budget)[0], start_sha256=provenance(budget)[1],
                                  before=dict(data), after=dict(data), resume=None))
        return games

    def test_keep_pair_wins_ties_badges_and_threshold_parameters(self):
        games = self.wave()
        report = S.make_report(games, 'segment')
        self.assertEqual(report['verdict'], 'KEEP')
        self.assertEqual(report['after']['teacher_pair_wins'], 3)
        self.assertEqual(report['after']['teacher_badges_by_cap'], 1)
        self.assertEqual(report['after']['teacher_mean_C'], 150)
        for kwargs in (dict(mean_c_max=149), dict(pair_wins_min=4), dict(teacher_badges_min=2)):
            self.assertEqual(S.make_report(games, 'segment', **kwargs)['verdict'], 'REWORK/DROP')
        games[0]['after']['status'] = 'in progress'
        self.assertEqual(S.make_report(games, 'segment')['verdict'], 'PENDING')

    def test_unequal_pair_and_relabelled_segment_rejected_before_summary(self):
        games = self.wave()
        games[1]['start_sha256'] = '0' * 64
        with patch.object(S, 'summarize') as summary, self.assertRaisesRegex(ValueError, 'unequal starting states'):
            S.make_report(games, 'segment')
        summary.assert_not_called()
        games = self.wave()
        for g in games:
            g['budget'] = 1200  # changing the cap cannot promote segment badges
            g['after']['badge_by_cap'] = g['group'] == 'teacher'
        with patch.object(S, 'summarize') as summary, self.assertRaisesRegex(ValueError, 'full wave start provenance'):
            S.make_report(games, 'full')
        summary.assert_not_called()

    def test_wrong_hash_or_registered_path_rejected_before_summary(self):
        for field, value in (('start_sha256', '0'*64), ('start', 'other.state')):
            games = self.wave()
            for g in games:
                g[field] = value
            with patch.object(S, 'summarize') as summary, self.assertRaisesRegex(ValueError, 'wave start provenance'):
                S.make_report(games, 'segment')
            summary.assert_not_called()

    def test_segment_and_full_threshold_inclusive_boundaries(self):
        for wave, budget, threshold in (('segment', 650, 500), ('full', 1200, 950)):
            games = self.wave(budget)
            for g in games:
                g['after']['C'] = threshold if g['group'] == 'teacher' else threshold + 1
            self.assertEqual(S.make_report(games, wave)['verdict'], 'KEEP')
            games[1]['after']['C'] += 1
            self.assertEqual(S.make_report(games, wave)['verdict'], 'REWORK/DROP')
        with self.assertRaises(ValueError):
            S.make_report(self.wave(), 'full')

    def test_cli_synthetic_wave_read_only(self):
        lines = []
        for pair in range(4):
            for group in ('plain', 'teacher'):
                name = f'pair{pair}-{group}'
                rows = [init(650), row(1, 60), row(2, 15, edges=[edge()]), row(3, 3), row(4, 65, badges=3 if group == 'teacher' else 1)]
                self.game(group=group, name=name, rows=rows)
                lines.append(f'{name} {group} test-model')
        order = self.arena / 'synthetic_order.txt'
        order.write_text('\n'.join(lines), encoding='utf-8')
        (self.arena / 'synthetic_notes.txt').write_text('\n'.join(f'{line.split()[0]}: stopped' for line in lines), encoding='utf-8')
        before = {str(p): p.read_bytes() for p in self.arena.rglob('*') if p.is_file()}
        proc = subprocess.run([sys.executable, '-B', str(ARENA_SRC / 'score_r12.py'), str(order), '--wave', 'segment', '--arena', str(self.arena)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report['verdict'], 'KEEP')
        self.assertEqual(report['after']['teacher_pair_wins'], 4)
        self.assertEqual(report['after']['teacher_badges_by_cap'], 4)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.arena.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
