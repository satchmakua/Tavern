from tavern.directives import is_canonical, normalize_intent


def test_positional_match_picks_earliest_intent():
    # "tech ... then push" -> tech (tech keyword comes first)
    assert normalize_intent("tech to tier 2 then push")[0] == "tech_up"
    # "pressure their natural" -> attack (pressure comes before natural)
    assert normalize_intent("pressure their natural")[0] == "attack"


def test_defend_variants():
    assert normalize_intent("defend_gold_mine")[0] == "defend"
    assert normalize_intent("hold our base, fortify")[0] == "defend"


def test_expand_and_creep_and_tech():
    assert normalize_intent("expand_now")[0] == "expand_now"
    assert normalize_intent("take a fast expansion")[0] == "expand_now"
    assert normalize_intent("creep the green camp for hero xp")[0] == "creep_more"


def test_mass_extracts_unit():
    assert normalize_intent("mass grunts")[0] == "mass_grunt"
    assert normalize_intent("build more fiends")[0] == "mass_fiend"
    assert normalize_intent("mass")[0] == "mass"  # no unit -> bare


def test_attack_extracts_known_target():
    intent, target = normalize_intent("attack vex now", players=["Vex", "Grollum"])
    assert intent == "attack_Vex" and target == "Vex"
    # unknown target -> bare attack
    assert normalize_intent("rush them")[0] == "attack"


def test_clean_canonical_passes_through_unchanged():
    # the model already obeyed the vocab — don't blur it
    assert normalize_intent("mass_paladin") == ("mass_paladin", None)
    assert normalize_intent("attack_Vex") == ("attack_Vex", "Vex")
    assert normalize_intent("expand_now")[0] == "expand_now"
    # but multi-underscore prose still maps down
    assert normalize_intent("defend_gold_mine")[0] == "defend"


def test_unmapped_returns_none_not_invented():
    assert normalize_intent("vibe it out")[0] is None
    assert normalize_intent("")[0] is None


def test_is_canonical():
    assert is_canonical("attack_Vex")
    assert is_canonical("mass_grunt")
    assert is_canonical("expand_now")
    assert not is_canonical(None)
    assert not is_canonical("vibes")
