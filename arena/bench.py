"""PokéBench's ten milestones (pokebench milestones.py, MIT, copy fetched 27 Oct 2026), read from Red's RAM.

Every address, map id, item id and event bit comes from reference/pokered(.sym) through read_state; nothing here
is a remembered number. Read only: no memory writes.

Like PokéBench's MilestoneTracker: tracking starts once the player is in Red's house (the boot/title screen reads
map 0 = Pallet Town and must not count as "left the house"); a milestone counts the first time its check is true
when a command ends (PokéBench checks once per turn). The game is over at the Boulder Badge.
"""
import read_state as R

MILESTONES = (
    ("left_house", "Left the house"),
    ("got_starter", "Got a starter"),
    ("route_1", "Reached Route 1"),
    ("viridian_city", "Reached Viridian City"),
    ("got_parcel", "Got Oak's Parcel"),
    ("got_pokedex", "Got the Pokédex"),
    ("viridian_forest", "Entered Viridian Forest"),
    ("pewter_city", "Reached Pewter City"),
    ("pewter_gym", "Entered Brock's Gym"),
    ("beat_brock", "Beat Brock (Boulder Badge)"),
)
KEYS = tuple(k for k, _ in MILESTONES)
LABELS = dict(MILESTONES)
FINAL = "beat_brock"


def map_id(name):
    return next(i for i, n in R.MAPS.items() if n == name)


HOUSE = {map_id("REDS_HOUSE_1F"), map_id("REDS_HOUSE_2F")}
MAP_OF = {"route_1": map_id("ROUTE_1"), "viridian_city": map_id("VIRIDIAN_CITY"),
          "viridian_forest": map_id("VIRIDIAN_FOREST"), "pewter_city": map_id("PEWTER_CITY"),
          "pewter_gym": map_id("PEWTER_GYM")}
PARCEL = next(i for i, n in R.ITEMS.items() if n == "OAKS_PARCEL")


def has_parcel(m):
    """OAKS_PARCEL in the bag, or the Mart's EVENT_GOT_OAKS_PARCEL (ViridianMart.asm sets both together;
    the event stays set after Oak takes the Parcel)."""
    n = min(m[R.A("wNumBagItems")], 20)
    bag = any(m[R.A("wBagItems") + 2 * i] == PARCEL and m[R.A("wBagItems") + 2 * i + 1] > 0 for i in range(n))
    return bag or R.event(m, "EVENT_GOT_OAKS_PARCEL")


def checks(m):
    """Which of the ten checks are true in this memory right now (no start gating)."""
    here = m[R.A("wCurMap")]
    now = {
        "left_house": here not in HOUSE and here in R.MAPS,
        "got_starter": 1 <= m[R.A("wPartyCount")] <= 6,
        "got_parcel": has_parcel(m),
        "got_pokedex": R.event(m, "EVENT_GOT_POKEDEX"),        # OaksLab.asm SetEvent EVENT_GOT_POKEDEX
        "beat_brock": bool(m[R.A("wObtainedBadges")] & 1),    # Boulder Badge = bit 0 (BIT_BOULDERBADGE)
    }
    now.update({k: here == v for k, v in MAP_OF.items()})
    return {k for k in KEYS if now[k]}


def fields(m, prev=None):
    """Log fields after a command: started flag and every milestone reached so far, in ladder order."""
    prev = prev or {}
    started = bool(prev.get("bench_started"))
    reached = set(prev.get("bench_milestones", []))
    if not started:
        # PokéBench MilestoneTracker.update: start in Red's house, no checks on that same turn.
        started = m[R.A("wCurMap")] in HOUSE
    else:
        reached |= checks(m)
    return dict(bench_started=started, bench_milestones=[k for k in KEYS if k in reached])


def last_fields(rows):
    """The newest logged bench fields (older logs have none)."""
    return next((dict(bench_started=r.get("bench_started", False), bench_milestones=r["bench_milestones"])
                 for r in reversed(rows) if "bench_milestones" in r), {})


def finished(rows):
    return FINAL in last_fields(rows).get("bench_milestones", [])


DONE_MESSAGE = "Done: you have the Boulder Badge. The game is over: stop and write your report."
