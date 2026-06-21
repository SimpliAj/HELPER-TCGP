import json, re

with open('/tmp/package/dist/cards.json') as f:
    cards = json.load(f)

# PTCGPB rarity labels
RARITY_MAP = {
    'C': 'one diamond',
    'U': 'two diamond',
    'R': 'three diamond',
    'RR': 'four diamond ex',
    'AR': 'one star',
    'SR': 'full art',
    'SAR': 'rainbow',
    'IM': 'immersive',
    'UR': 'crown',
    'S': 'shiny',
    'SSR': 'shiny ex',
}

BASE = 'https://raw.githubusercontent.com/chase-manning/pokemon-tcg-pocket-cards/refs/heads/main/images/cards'

def norm(s): return re.sub(r'\s+', ' ', s).strip().lower()
def norm_pack(s): return re.sub(r'\s+', '', s).strip().lower()

def card_url(set_code, number):
    s = set_code.lower()
    n = str(number).zfill(3)
    return f'{BASE}/{s}-{n}.png'

cardmap = {}

# Track which base+rarity keys we've already seen (first-occurrence wins)
seen_base_rarity = set()

for card in cards:
    raw_rarity = card.get('rarity', '')
    ptcgpb_rarity = RARITY_MAP.get(raw_rarity)
    if not ptcgpb_rarity:
        continue
    
    name = norm(card.get('name', ''))
    if not name:
        continue
    
    set_code = card.get('set', '')
    number = card.get('number')
    packs = [norm_pack(p) for p in card.get('packs', [])]
    
    if not set_code or number is None:
        continue
    
    url = card_url(set_code, number)
    
    # Base name key (first occurrence wins)
    if name not in cardmap:
        cardmap[name] = url
    
    # name__rarity key (first occurrence wins per rarity)
    rarity_key = f'{name}__{ptcgpb_rarity}'
    if rarity_key not in seen_base_rarity:
        seen_base_rarity.add(rarity_key)
        cardmap[rarity_key] = url
    
    # Pack-specific keys (always store all)
    for pack in packs:
        pack_key = f'{name}__{ptcgpb_rarity}__{pack}'
        if pack_key not in cardmap:
            cardmap[pack_key] = url

print(f'Total keys: {len(cardmap)}')
# Check leafeon ex
leafeon = {k: v for k, v in cardmap.items() if 'leafeon' in k}
for k in sorted(leafeon):
    print(k, '->', leafeon[k][-35:])

print('---SAR/rainbow keys:', len([k for k in cardmap if '__rainbow' in k]))
print('---SR/full art keys:', len([k for k in cardmap if '__full art' in k]))

with open('/tmp/cardmap_v3.json', 'w') as f:
    json.dump(cardmap, f, ensure_ascii=False, separators=(',', ':'))
print('Written to /tmp/cardmap_v3.json')
