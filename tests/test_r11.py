"""R11 static/source and decoded-memory regressions. Never opens a ROM or save state."""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stdout
from unittest.mock import patch

DEV = Path(__file__).resolve().parents[1]
ROOT = DEV
sys.path[:0] = [str(DEV/'tools'), str(DEV/'arena')]
import settings  # noqa: E402
import advise as A
import read_state as R
import r11_maps as M
import r11_advice as L
import play as P
import guard as G


def state(map_='CERULEAN_CITY', xy=(19,18), species='IVYSAUR', level=24):
    s=R.state_from_wram((settings.fixture('record-1831000065-v2/split-03.wram')).read_bytes())
    s.update(team=[A._wild_mon(species,level)], bag=[], badges=['Boulder'], battle=None, text_box=False,
             teacher_objects={}, teacher_events={}, money=1200, part=3)
    s['place'].update(map=map_,map_id=next(i for i,n in R.MAPS.items() if n==map_),x=xy[0],y=xy[1],
                      last_map='ROUTE_4' if map_.startswith('MT_MOON') else 'CERULEAN_CITY')
    s['story']=dict(done=['oak','starter','parcel','pokedex','badge1','mt_moon'],
                    next=dict(id='badge2',goal='Beat Misty (Cascade Badge)',part=3,done=False))
    return s


class R11(unittest.TestCase):
    def test_explicit_misty_readiness_precedes_healing_and_travel(self):
        for map_ in ('PEWTER_CITY', 'PEWTER_MART', 'ROUTE_3', 'MT_MOON_1F', 'ROUTE_4'):
            for question in ('Am I ready for Misty?', 'Can I beat Misty?', 'ready for the gym'):
                for hurt in (False, True):
                    with self.subTest(map=map_, question=question, hurt=hurt):
                        s=state(map_,(16,20),species='SQUIRTLE',level=11)
                        if hurt:s['team'][0]['hp']=2
                        a=A.answer(s,question);text=A.text(a)
                        self.assertIn('Not ready for Misty',a['do'])
                        self.assertRegex(a['do'],r'you need (about|more than) L\d+ with 0 Potions');self.assertIn('Train',a['do'])  # R14: level target replaces 'train or add a backup'
                        self.assertIn('HP and PP carried',text)
                        self.assertIn('likely loss',text)
                        self.assertNotIn('Next toward',a['do'])
                        if hurt:self.assertEqual(a['do'].splitlines()[0],'Heal first; your team is hurt.')

    def test_saved_post_brock_party_needs_more_than_healing_for_misty(self):
        # Exact decoded fixture from the validated saved state; no ROM open.
        s=json.loads(settings.fixture('post_brock_pewter.json').read_text(encoding='utf-8'))['checked_state']
        self.assertEqual([(t['species'],t['level'],t['hp']) for t in s['team']],
                         [('SQUIRTLE',11,15),('CATERPIE',5,20)])
        for healed in (False, True):
            with self.subTest(healed=healed):
                if healed:
                    for t in s['team']:t['hp']=t['max_hp']
                a=A.answer(s,'Am I ready for Misty?');text=A.text(a)
                for required in ('Not ready for Misty','you need more than L21',
                                 'Train:','forecast does not safely clear','likely loss',
                                 'Water resists Water both ways','Bite at L24','BubbleBeam'):
                    self.assertIn(required,text)
                self.assertNotIn('Next toward',text)

    def test_misty_readiness_keeps_urgent_recovery_on_first_line(self):
        for condition,first in (('all fainted','Your team has fainted.'),
                                ('one fainted','A teammate has fainted;'),
                                ('low hp','Heal first; your team is hurt.'),
                                ('poison','Cure poison and heal before walking;'),
                                ('antidote','Use an Antidote now,')):
            with self.subTest(condition=condition):
                s=state('PEWTER_CITY',(16,20),species='SQUIRTLE',level=11)
                if condition=='all fainted':s['team'][0]['hp']=0
                if condition=='one fainted':
                    s['team'].append(A._wild_mon('CATERPIE',5));s['team'][1]['hp']=0
                if condition=='low hp':s['team'][0]['hp']=1
                if condition in ('poison','antidote'):s['team'][0]['status']='poisoned'
                if condition=='antidote':s['bag']=[dict(item='ANTIDOTE',count=1)]
                a=A.answer(s,'Can I beat Misty?');lines=a['do'].splitlines()
                self.assertEqual(len(lines),2)
                self.assertTrue(lines[0].startswith(first),lines)
                self.assertIn('Not ready for Misty',lines[1])
                self.assertIn('HP and PP carried',A.text(a))

    def test_healthy_ready_party_gets_readiness_even_in_pewter(self):
        s=state('PEWTER_CITY',(16,20))
        a=A.answer(s,'ready for the gym')
        self.assertEqual(a['do'],L.misty_advice(A,s)['do'])
        self.assertIn('HP and PP carried',A.text(a))
        self.assertNotIn('Next toward',a['do'])

    @unittest.skipUnless(os.environ.get('ARENA_EMULATOR_TESTS')=='1','emulator test: saved-state CLI')
    def test_saved_post_brock_state_cli_answers_misty_readiness(self):
        # main() opens one headless emulator, reads without ticking and closes it.
        out=io.StringIO()
        with patch.object(sys,'argv',['advise.py',str(settings.fixture('post_brock_pewter.state')),
                                      'Am I ready for Misty?']), redirect_stdout(out):
            A.main()
        text=out.getvalue()
        for required in ('SQUIRTLE','CATERPIE','Not ready for Misty','you need more than L21',
                         'forecast does not safely clear','likely loss','Bite at L24'):
            self.assertIn(required,text)
        self.assertIn('DO NOW: Heal first; your team is hurt.\nNot ready for Misty',text)
        self.assertNotIn('Next toward',text)

    def test_healthy_pewter_purchases_precede_travel_and_escape_recovery(self):
        for map_, xy in (('PEWTER_CITY', (16,20)), ('PEWTER_MART', (4,7))):
            for question in ('Should I buy Potions?', 'Should I buy an Escape Rope?'):
                with self.subTest(map=map_, question=question):
                    s=state(map_,xy)
                    self.assertEqual(s['team'][0]['hp'],s['team'][0]['max_hp'])
                    a=A.answer(s,question)
                    text=A.text(a)
                    for required in ('BUY','(2,5)','press left','quantity','Pewter','Potion 300',
                                     'Escape Rope 550','Antidote 100','Poke Ball 200','Burn Heal 250',
                                     'Awakening 200','Parlyz Heal 200','1200','buying it does not use it'):
                        self.assertIn(required,text)
                    self.assertNotIn('Mt. Moon entrance',a['do'])
                    self.assertNotIn('Center',a['do'])
                    if map_=='PEWTER_CITY':
                        self.assertIn('Pewter Mart',a['do'])
                        self.assertIn('(23,17)',text)

    def test_pewter_mart_local_default_and_using_rope_remain_distinct(self):
        s=state('PEWTER_MART',(2,5))
        self.assertIn('choose BUY',A.answer(s)['do'])
        s=state('MT_MOON_B1F',(27,3))
        s['bag']=[dict(item='ESCAPE_ROPE',count=1)]
        s['last_heal_map']='PEWTER_CITY'
        text=A.text(A.answer(s,'Should I use an Escape Rope?'))
        self.assertIn('PEWTER_CITY',text)
        self.assertNotIn('choose BUY',text)

    def test_imports_and_data_are_dev(self):
        for mod in (A,R,M,L,P,G):
            self.assertTrue(Path(mod.__file__).resolve().is_relative_to(DEV),mod.__file__)
        self.assertTrue(R.KB.is_relative_to(DEV))
        self.assertEqual(A.FACTS,json.loads((DEV/'kb/game_facts.json').read_text(encoding='utf-8')))
        self.assertEqual(A.W.P,settings.POKERED)

    def test_all_cave_warps(self):
        expected={
            'MT_MOON_1F': [('ROUTE_4',(18,5)),('ROUTE_4',(18,5)),('MT_MOON_B1F',(5,5)),('MT_MOON_B1F',(25,9)),('MT_MOON_B1F',(25,15))],
            'MT_MOON_B1F':[('MT_MOON_1F',(5,5)),('MT_MOON_B2F',(25,9)),('MT_MOON_1F',(17,11)),('MT_MOON_1F',(25,15)),('MT_MOON_B2F',(21,17)),('MT_MOON_B2F',(15,27)),('MT_MOON_B2F',(5,7)),('ROUTE_4',(24,5))],
            'MT_MOON_B2F':[('MT_MOON_B1F',(17,11)),('MT_MOON_B1F',(21,17)),('MT_MOON_B1F',(13,27)),('MT_MOON_B1F',(23,3))]}
        for m,dest in expected.items():
            self.assertEqual([A._warp_dest(m,w,'ROUTE_4') for w in A._warps(m)],dest)

    def test_record_floor_order_is_item_detour(self):
        floors=[v['map'] for v in A.WALKS if v['map'] in L.CAVE]
        self.assertEqual(floors,['MT_MOON_1F','MT_MOON_B1F','MT_MOON_B2F','MT_MOON_B1F','MT_MOON_1F','MT_MOON_B1F','MT_MOON_B2F','MT_MOON_B1F'])

    def test_item_balls_and_fossil_positions(self):
        expected={'MT_MOON_1F':{(2,20):'POTION',(2,2):'MOON_STONE',(35,31):'RARE_CANDY',(36,23):'ESCAPE_ROPE',(20,33):'POTION',(5,32):'TM_WATER_GUN'},
                  'MT_MOON_B2F':{(25,21):'HP_UP',(29,5):'TM_MEGA_PUNCH'}}
        for m,items in expected.items():
            self.assertEqual({(r['x'],r['y']):r['item'] for r in M.maps()[m]['objects'] if 'item' in r},items)
        fossils=[(r['x'],r['y']) for r in M.maps()['MT_MOON_B2F']['objects'] if r['sprite']=='SPRITE_FOSSIL']
        self.assertEqual(fossils,[(12,6),(13,6)])

    def test_each_fossil_exits_without_restarting(self):
        for fossil in ('DOME_FOSSIL','HELIX_FOSSIL'):
            s=state('MT_MOON_B2F',(13,7));s['bag']=[dict(item=fossil,count=1)]
            s['teacher_events']={'EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD':True,'EVENT_GOT_'+fossil:True}
            r=A.walk_to(s,L.goal_at('ROUTE_4',(24,5)),fallback=False,max_maps=8)
            self.assertIsNotNone(r)
            self.assertEqual(r['maps'],['MT_MOON_B2F','MT_MOON_B1F','ROUTE_4'])
            answer=A.text(A.answer(s,'What now after the fossil?'))
            for text in ('5,7','23,3','27,3','24,5','Do not restart','unverified'):
                self.assertIn(text,answer)

    def test_nerd_beaten_does_not_mean_fossil_taken(self):
        s=state('MT_MOON_B2F',(13,7));s['teacher_events']['EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD']=True
        a=A.answer(s)
        self.assertIn('HELIX_FOSSIL',a['do']);self.assertIn('press A once',a['do'])
        self.assertNotIn('Fossil taken',A.text(a))
        self.assertIn('HELIX_FOSSIL',A.answer(s,'Can I beat the Super Nerd?')['do'])

    def test_fossil_choice_full_bag_and_hidden_pickup(self):
        s=state('MT_MOON_B2F',(13,7));s['teacher_events']['EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD']=True
        s['bag']=[dict(item='item'+str(i),count=1) for i in range(20)]
        self.assertIn('bag slot',A.answer(s)['do'])
        s=state('MT_MOON_1F',(3,2));s['teacher_objects']={'MT_MOON_1F':[dict(id=9,x=2,y=2,hidden=True)]}
        self.assertIn('already been collected',A.answer(s,'Where is the Moon Stone?')['do'])

    def test_b1f_checkpoint_uses_correct_warp(self):
        for xy,target in [((5,5),'MT_MOON_B2F'),((25,9),'MT_MOON_1F'),((17,11),'MT_MOON_1F')]:
            s=state('MT_MOON_B1F',xy);s['teacher_events']={e:True for e in M.events() if not e.startswith('EVENT_GOT_')}
            r=A.walk_to(s,L.goal_at('MT_MOON_B2F',(12,9)),fallback=False,max_maps=8)
            self.assertIsNotNone(r);self.assertEqual(r['exit'][1],target)

    def test_poison_antidote_precedes_walking(self):
        s=state('MT_MOON_B2F',(21,17));s['team'][0].update(hp=2,status='poisoned')
        s['bag']=[dict(item='ANTIDOTE',count=1)]
        self.assertIn('Use an Antidote now',A.answer(s,'how do I escape/heal?')['do'])

    def test_poison_without_cure_never_promises_long_safe_retreat(self):
        s=state('MT_MOON_B2F',(21,17));s['team'][0].update(hp=2,status='poisoned')
        self.assertIn('poison may black out',A.answer(s,'heal')['do'])

    def test_escape_rope_returns_last_healing_place(self):
        s=state('MT_MOON_B2F',(21,17));s['bag']=[dict(item='ESCAPE_ROPE',count=1),dict(item='HELIX_FOSSIL',count=1)]
        s['last_heal_map']='PEWTER_CITY'
        a=A.text(A.answer(s,'How do I escape?'))
        self.assertIn('PEWTER_CITY',a);self.assertIn('fossil stays',a);self.assertNotIn('entrance Center at Route 4',a)

    def test_no_pp_asks_for_center(self):
        s=state('MT_MOON_1F',(14,34))
        for move in s['team'][0]['moves']:move['pp']=0
        a=A.text(A.answer(s,'Which ladder next?'))
        self.assertIn('PP',a);self.assertNotIn('fossil guard checkpoint',a)

    def test_blackout_recovery_uses_new_location(self):
        s=state('MT_MOON_B2F',(13,7));s['team'][0]['hp']=0
        self.assertIn('blackout',A.answer(s)['do'])
        s=state('CERULEAN_POKECENTER',(5,6));a=A.answer(s,'heal')
        self.assertIn('nurse',a['do']);self.assertNotIn('ladder',A.text(a))

    def test_bill_is_after_badge2_but_still_needed_later(self):
        ids=[i for i,*_ in R.MILESTONES];self.assertLess(ids.index('badge2'),ids.index('ss_ticket'))
        raw=bytearray((settings.fixture('record-1831000065-v2/split-07.wram')).read_bytes())
        bit=R.EVENTS['EVENT_GOT_SS_TICKET'];raw[R.A('wEventFlags')-0xc000+bit//8]&=~(1<<(bit%8))
        s=R.state_from_wram(raw);self.assertEqual(s['story']['next']['id'],'badge2')
        raw[R.A('wObtainedBadges')-0xc000]|=2
        self.assertEqual(R.state_from_wram(raw)['story']['next']['id'],'ss_ticket')

    def test_actual_rival_starter_for_all_player_starters(self):
        for player,rival,key in [('BULBASAUR','CHARMANDER','Rival1:9'),('CHARMANDER','SQUIRTLE','Rival1:7'),('SQUIRTLE','BULBASAUR','Rival1:8')]:
            s=state(species=player,level=25);s['rival_starter']=rival
            a=A.text(A.answer(s,'Can I face the rival now, and which starter does he have?'))
            self.assertIn(rival+' L17',a);self.assertEqual(A.TEAMS[key]['party'][-1]['species'],rival)
            for text in ('Pidgeotto L18','Abra L15','Rattata L15'):self.assertIn(text,a)

    def test_unknown_rival_and_low_hp_do_not_send_player_north(self):
        s=state();s['rival_starter']=None
        self.assertIn('not known',A.answer(s,'rival?')['do'])
        s['rival_starter']='SQUIRTLE';s['team'][0]['hp']=2
        a=A.answer(s,'Can I face the rival?');self.assertNotIn('may beat',a['do']);self.assertNotIn('row 6',a['do'])

    def test_mankey_red_locations_from_wild_tables(self):
        def species(map_):return {r['species'] for r in A.FACTS['wild'][map_]['grass']['mons']}
        for m in ('Route3','Route4','Route22'):self.assertNotIn('MANKEY',species(m))
        self.assertIn('MANKEY',species('Route5'))
        self.assertIn('Route 5',A.answer(state(),'Should I catch Mankey?')['do'])

    def test_oddish_is_red_l12_14_and_optional(self):
        for m in ('Route24','Route25'):
            mon=next(r for r in A.FACTS['wild'][m]['grass']['mons'] if r['species']=='ODDISH')
            self.assertEqual(mon['levels'],[12,13,14])
        a=A.text(A.answer(state(species='CHARMELEON'),'Should I use Nugget Bridge/Route 25 for levels or Oddish?'))
        for text in ('optional','Absorb','is an estimate','rival'):self.assertIn(text,a)  # R12 review B2: "untested guess" is shown as "estimate"

    def test_misty_exact_team_and_moves(self):
        self.assertEqual([(m['species'],m['level'],m['moves']) for m in A.TEAMS['Misty:1']['party']],
                         [('STARYU',18,['TACKLE','WATER_GUN']),('STARMIE',21,['TACKLE','WATER_GUN','BUBBLEBEAM'])])
        self.assertEqual(A.TEAMS['Misty:1']['party'][1]['stats']['spd'],56)

    def test_starter_specific_misty_answers(self):
        for species,level,words in [('IVYSAUR',24,('Vine Whip','L20-24')),('CHARMELEON',24,('Fire is weak','Oddish','L18-22')),('WARTORTLE',24,('Bite','Normal in Red','L24+'))]:
            a=A.text(A.answer(state(species=species,level=level),'Am I ready for both gym fights?'))
            for word in words+('is an estimate','HP and PP carried','BubbleBeam','critical','Speed 56','optional'):
                self.assertIn(word,a)

    def test_two_fights_really_carry_hp_pp(self):
        s=state(species='WARTORTLE',level=28);original=copy.deepcopy(s)
        g,bypass=L.gym_plan(A,s)
        self.assertIsNotNone(bypass);self.assertEqual(g['keys'],['JrTrainerF:1','Misty:1'])
        combined=A.TEAMS['JrTrainerF:1']['party']+A.TEAMS['Misty:1']['party']
        win,left,_,end=A.fight(L.team(A,s),combined,carry=True)
        self.assertEqual(g['left'],left);self.assertEqual(g['team'],end)
        self.assertLess(sum(m['pp'] for m in end[0]['moves']),sum(m['pp'] for m in original['team'][0]['moves']))
        self.assertLess(end[0]['hp'],original['team'][0]['hp']);self.assertEqual(s,original)

    def test_swimmer_included_if_no_bypass_is_checked(self):
        with patch.object(A,'walk_to',return_value=None):
            g,_=L.gym_plan(A,state())
        self.assertEqual(g['keys'],['Swimmer:1','JrTrainerF:1','Misty:1'])

    def test_gym_trainer_beaten_does_not_cost_hp_again(self):
        s=state();s['teacher_events']['EVENT_BEAT_CERULEAN_GYM_TRAINER_0']=True
        self.assertEqual(L.gym_plan(A,s)[0]['keys'],['Misty:1'])

    def test_named_backups_and_water_weakness(self):
        for species in ('BUTTERFREE','PIDGEY','NIDORAN_M','NIDORINO','NIDOKING','ODDISH'):
            s=state(species=species,level=24)
            if species=='BUTTERFREE':s['team'][0]['moves']=[dict(move='CONFUSION',pp=25),dict(move='SLEEP_POWDER',pp=15)]
            if species=='ODDISH':s['team'][0]['moves']=[dict(move='ABSORB',pp=25),dict(move='SLEEP_POWDER',pp=15)]
            a=A.text(A.answer(s,'ready for Misty?'))
            self.assertIn('critical',a)
            if species=='NIDOKING':self.assertIn('super effective on NIDOKING',a)
        a=A.text(A.answer(state(),'Should I catch Oddish?'))
        for word in ('Butterfree','Confusion L12','Sleep Powder L17','Pidgey','Quick Attack L12'):self.assertIn(word,a)

    def test_center_mart_gym_doors(self):
        doors={(r['x'],r['y']):r['target'] for r in M.maps()['CERULEAN_CITY']['warps']}
        self.assertEqual([doors[p] for p in [(19,17),(25,25),(30,19)]],['CERULEAN_POKECENTER','CERULEAN_MART','CERULEAN_GYM'])
        for xy in ((24,6),(60,8)):
            s=state('ROUTE_4',xy);self.assertIn('19,17',A.text(A.answer(s,'Where is the Center?')))

    def test_text_boxes_precede_fossils_items_and_readiness(self):
        for map_,q in [('MT_MOON_B2F','Which fossil should I take?'),('CERULEAN_MART','Should I buy Potions?'),('CERULEAN_GYM','Am I ready for Misty?')]:
            s=state(map_);s['text_box']=True;s['teacher_screen']=dict(rows=['YES NO'],cursor=True)
            a=A.answer(s,q);self.assertEqual(a['kind'],'text');self.assertIn('visible choices',a['do']);self.assertNotIn('Next toward',a['do'])

    def test_sight_ranges_and_defeated_flags(self):
        cases=[('ROUTE_3',(12,6),'EVENT_BEAT_ROUTE_3_TRAINER_0'),('MT_MOON_1F',(13,16),'EVENT_BEAT_MT_MOON_1_TRAINER_1'),('MT_MOON_B2F',(11,20),'EVENT_BEAT_MT_MOON_3_TRAINER_0'),('CERULEAN_GYM',(4,3),'EVENT_BEAT_CERULEAN_GYM_TRAINER_0'),('CERULEAN_CITY',(20,6),'EVENT_BEAT_CERULEAN_RIVAL')]
        for m,p,e in cases:
            s=state(m);self.assertIn(p,M.sight(s,m));s['teacher_events'][e]=True;self.assertNotIn(p,M.sight(s,m))

    def test_nerd_trigger_independent_of_normal_sight(self):
        s=state('MT_MOON_B2F');self.assertIn((13,8),M.sight(s,'MT_MOON_B2F'))
        s['teacher_events']['EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD']=True
        self.assertNotIn((13,8),M.sight(s,'MT_MOON_B2F'))

    def test_local_routes_never_cross_unbeaten_sight(self):
        for map_,xy,goal in [('ROUTE_3',(0,10),L.goal_at('ROUTE_4',(18,5))),('MT_MOON_1F',(14,34),L.goal_at('MT_MOON_B2F',(12,9))),('CERULEAN_CITY',(19,18),lambda m,p:m=='CERULEAN_POKECENTER')]:
            s=state(map_,xy);r=A.walk_to(s,goal,fallback=False,max_maps=8)
            if r:
                for m,p in [x[0] for x in r['steps'][1:]]+[r['target']]:self.assertNotIn(p,M.sight(s,m))
            else:
                a=A.text(L.walk(A,s,goal,'checkpoint'));self.assertTrue('stop before' in a or 'Stop here' in a or 'no checked safe walk' in a)

    def test_visible_moving_people_and_collected_balls(self):
        s=state('CERULEAN_CITY',(15,19));base=A._grid('CERULEAN_CITY')
        s['teacher_objects']={'CERULEAN_CITY':[dict(id=4,x=15,y=19,hidden=False,facing='DOWN')]}
        g=M.grid(s,'CERULEAN_CITY',base);self.assertIn((15,19),g['people']);self.assertNotIn((15,18),g['people'])
        s=state('MT_MOON_1F');base=A._grid('MT_MOON_1F')
        for hidden in (False,True):
            s['teacher_objects']={'MT_MOON_1F':[dict(id=9,x=2,y=2,hidden=hidden)]}
            self.assertEqual((2,2) in M.grid(s,'MT_MOON_1F',base)['balls'],not hidden)

    def test_sprite_memory_uses_current_position_facing_and_hidden_bit(self):
        raw=bytearray((settings.fixture("start.wram")).read_bytes());m=R.Wram(raw)
        def put(name,offset,value):raw[R.A(name)-0xc000+offset]=value
        put('wCurMap',0,next(i for i,n in R.MAPS.items() if n=='CERULEAN_CITY'));put('wNumSprites',0,4)
        put('wSpriteStateData1',16*4,1);put('wSpriteStateData1',16*4+9,8)
        put('wSpriteStateData2',16*4+4,24);put('wSpriteStateData2',16*4+5,19)
        put('wMissableObjectList',0,4);put('wMissableObjectList',1,3);put('wMissableObjectList',2,255)
        put('wMissableObjectFlags',0,8)
        # Wram owns immutable bytes: construct a fresh reader after editing the local fixture.
        live=M.memory(R.Wram(raw),R,state('CERULEAN_CITY'))['teacher_objects']['CERULEAN_CITY']
        self.assertIn(dict(id=4,x=15,y=20,hidden=True,facing='LEFT'),live)

    def test_blocker_memory_survives_sidestep_then_expires(self):
        ctx={};i=next(i for i,n in R.MAPS.items() if n=='CERULEAN_CITY')
        P.observe_walk(ctx,(i,15,19),(i,15,19),'up',True);P.observe_walk(ctx,(i,15,19),(i,15,19),'up',True)
        P.observe_walk(ctx,(i,15,19),(i,16,19),'right',True)
        self.assertEqual(ctx['walk_occupancy'][0]['tile'],[15,18])
        for n in range(6):P.observe_walk(ctx,(i,16+n,19),(i,17+n,19),'right',True)
        self.assertFalse(ctx['walk_occupancy'])

    def test_guard_and_press_refusals_never_open_game_or_spend_command(self):
        with tempfile.TemporaryDirectory(dir=DEV/'tests') as tmp:
            d=Path(tmp);(d/'meta.json').write_text(json.dumps(dict(group='teacher',budget=20)))
            row=dict(n=0,cmd='start',map='CERULEAN_CITY',done=[])
            (d/'log.jsonl').write_text(json.dumps(row)+'\n');before=(d/'log.jsonl').read_bytes()
            with patch.object(P,'Game') as game:
                with self.assertRaises(SystemExit):P._play(SimpleNamespace(cmd='press',rest=['up*7']),d)  # R16: was up*21
                with self.assertRaises(SystemExit):P._play(SimpleNamespace(cmd='press',rest=['bad']),d)
                game.assert_not_called()
            G.check(d,now=100,key='one')
            with self.assertRaises(G.Blocked):G.check(d,now=101,key='two')
            G.release(d,now=102,key='one')
            with self.assertRaises(G.Blocked):G.check(d,now=104,key='one')
            self.assertEqual((d/'log.jsonl').read_bytes(),before);self.assertEqual(P.commands_used(P.history_rows(d)),0)
            self.assertEqual(P.MAX_PRESSES,6);self.assertEqual(len(P.parse_buttons(['up*6'])),6)  # R16: PokeBench limit (was 20)

    def test_pewter_healing_uses_local_center_not_route3(self):
        s=state('PEWTER_CITY',(13,26));s['team'][0]['hp']=1
        a=A.text(A.answer(s,'heal'))
        self.assertIn('PEWTER POKECENTER',a);self.assertIn('up 1 to (13,25)',a)
        self.assertNotIn('ROUTE_3',a)
        s=state('ROUTE_3',(0,10));s['team'][0]['hp']=1
        self.assertIn('PEWTER',A.text(A.answer(s,'heal')))

    def test_thief_trigger_blocks_healing_and_has_defeated_flag(self):
        s=state('CERULEAN_CITY',(29,7))
        for xy in ((30,7),(30,9)):self.assertIn(xy,M.sight(s,'CERULEAN_CITY'))
        r=A.walk_to(s,lambda mm,p:mm=='CERULEAN_POKECENTER',fallback=False)
        if r:
            for m,p in [x[0] for x in r['steps'][1:]]+[r['target']]:
                if m=='CERULEAN_CITY':self.assertNotIn(p,((30,7),(30,9)))
        s['teacher_events']['EVENT_BEAT_CERULEAN_ROCKET_THIEF']=True
        for xy in ((30,7),(30,9)):self.assertNotIn(xy,M.sight(s,'CERULEAN_CITY'))

    def test_gym_walk_uses_same_swimmer_bypass_as_readiness(self):
        for xy in ((4,12),(5,8)):
            s=state('CERULEAN_GYM',xy);a=L.gym_walk(A,s)
            self.assertNotIn('starts Swimmer',a['do']);self.assertIn('left',a['do'])
            self.assertIn('left path around the Swimmer',A.text(a))
        s=state('CERULEAN_GYM',(4,3));self.assertIn('press A once',L.gym_walk(A,s)['do'])

    def test_support_pp_does_not_hide_empty_attack_pp(self):
        s=state('MT_MOON_1F',(14,34),species='BUTTERFREE',level=18)
        s['team'][0]['moves']=[dict(move='CONFUSION',pp=0),dict(move='STRING_SHOT',pp=10),dict(move='STUN_SPORE',pp=10),dict(move='SLEEP_POWDER',pp=10)]
        self.assertIn('Restore PP',L.recovery_reason(A,s))
        self.assertNotIn('fossil guard checkpoint',A.text(A.answer(s,'Which ladder next?')))

    def test_moving_sprite_observation_clears_old_blocker(self):
        s=state('CERULEAN_CITY');s['teacher_objects']={'CERULEAN_CITY':[dict(id=4,x=15,y=19,hidden=False)]}
        ctx=dict(sprite_positions={'CERULEAN_CITY':[dict(id=4,x=15,y=18,hidden=False)]},
                 walk_occupancy=[dict(map='CERULEAN_CITY',tile=[15,18],ttl=6)],
                 walk_block=dict(map='CERULEAN_CITY',tile=[15,18],count=2))
        M.refresh_context(s,ctx);self.assertFalse(ctx['walk_occupancy']);self.assertNotIn('walk_block',ctx)

    def test_late_text_without_screen_does_not_blindly_confirm_fossil(self):
        s=state('MT_MOON_B2F',(13,7));s['text_box']=True
        a=A.answer(s,'which fossil should I take?')
        self.assertEqual(a['kind'],'text');self.assertIn('visible text or choices',a['do'])

    def test_route4_lass_has_three_high_level_mons(self):
        self.assertEqual([(p['species'],p['level']) for p in A.TEAMS['Lass:4']['party']],
                         [('PARAS',31),('PARAS',31),('PARASECT',31)])


if __name__=='__main__':
    unittest.main()
