# Products whose declared code looks wrong

Source: the 200 failed/incorrect rows of `product-agent-results-run1.json`, reviewed one by one (see `root-cause-analysis-product-run1.md`). Lead document ids and invoice rows come from `new-test-data/te_hs_codes.json`.

**Nothing has been deleted.** This is a review list: each row needs checking against the declaration before it is dropped from the test set.

"Same code in doc" shows how many products of that lead document carry the same declared code, out of the document's total — a high share is the signature of one code applied to a whole declaration.

## 1. Declared code contradicts the line text — candidates for removal (61 products, 20 lead documents)

The declared code cannot be derived from what the line says, and the agent's own answer is usually the literal tariff fit. **Verify each one against the declaration documents before deleting**: if the declarant had extra information (a spec sheet, a kit made up of parts), the code may be right and the line simply does not carry it.

### Lead document 26014558135580 — 12 flagged of 36 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 2 | 406335951 | DIY Craft Bottle | Fifi Chen | 9503000000 – Tricycles, scooters, pedal cars and similar wheeled toys; do | 13/36 | — | declaration-level toy label (9503) for a craft bottle; material unknown -> no code |
| 4 | 406335953 | Hula Hoop | Fifi Chen | 9503000000 – Tricycles, scooters, pedal cars and similar wheeled toys; do | 13/36 | 9506919000 | declaration-level toy label; hula hoop 'for exercise' -> 9506.91 |
| 7 | 406335956 | Plastic cone roadblocks | Fifi Chen | 9503000000 – Tricycles, scooters, pedal cars and similar wheeled toys; do | 13/36 | 3926909000 | declaration-level toy label; plastic cones -> 3926.90 |
| 8 | 406335957 | plastic ring | Fifi Chen | 9503000000 – Tricycles, scooters, pedal cars and similar wheeled toys; do | 13/36 | 3926909000 | declaration-level toy label; single Milvus leaf 3926.90 |
| 12 | 406335961 | Beeswax Sheets | Hugo Du | 3404900000 – Other | 1/36 | 1521900000 | beeswax sheets: 15.21 (beeswax, whether or not coloured) vs label 34.04 prepared waxes |
| 18 | 406335967 | Flying Plate | Yongjun Shen | 9506990000 – Other | 1/36 | 9503000000 | flying disc: toy (9503) vs outdoor-game equipment (9506.99) |
| 19 | 406335968 | Sun Hat | Mandy Zhu | 9503000000 – Tricycles, scooters, pedal cars and similar wheeled toys; do | 13/36 | 6505009000 | declaration-level toy label; sun hat -> headgear 6505 |
| 23 | 406335972 | Stickers | leo liu | 4811490000 – Other | 1/36 | — | label 4811.49 'gummed/adhesive paper, other than self-adhesive' for stickers; no code |
| 29 | 406335978 | Painting frames | HX Roy | 4419900000 – Other | 1/36 | — | painting frames labelled as wooden tableware (4419.90); material unknown -> no code |
| 33 | 406335982 | Sand Art Painting Card | leanne lin | 4909000000 – Printed or illustrated postcards; printed cards bearing pers | 2/36 | 4823900000 | children's sand-art card labelled as printed greeting cards (4909) |
| 35 | 406335984 | Styrofoam balls | Oliver zhang | 9503000000 – Tricycles, scooters, pedal cars and similar wheeled toys; do | 13/36 | 3926909000 | declaration-level toy label; styrofoam balls -> 3926.90 |
| 36 | 406335985 | Playdough Clay | Sandy ZHANG | 3407009000 – OTHERS | 1/36 | 3407002000 | playdough: 3407.00.20 'modelling pastes' vs label 3407.00.90 'others' (dental waxes) |

### Lead document 26014569415005 — 9 flagged of 33 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 3 | 396680930 | MEN SUIT TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label: a men's suit labelled as trousers (6203.49); plus knit unknown -> no code |
| 8 | 396680935 | MEN JACKET TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label (jacket labelled trousers); knit unknown -> no code |
| 9 | 396680936 | MEN BOXER TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label (boxers labelled trousers); knit unknown -> no code |
| 10 | 396680937 | MEN ATHELETE TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label; 'athlete' (singlet) with knit unknown -> no code |
| 12 | 396680939 | WOMEN BLOUSE TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label (women's blouse labelled men's trousers); knit unknown -> no code |
| 13 | 396680940 | WOMEN DRESS TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label (dress labelled men's trousers); knit unknown -> no code |
| 18 | 396680945 | WOMEN SKIRT TOTAL | ALFA KARGO DIS TICARET LIMIT | 6203490000 – Of other textile materials | 12/33 | — | declaration-level label (skirt labelled men's trousers); knit unknown -> no code |
| 42 | 396680969 | STICKER TOTAL | ALFA KARGO DIS TICARET LIMIT | 4823906000 – Gummed or adhesive paper, in strips or rolls exept self adhe | 1/33 | — | label is 'gummed paper except self-adhesive' for stickers; material unknown -> no code |
| 45 | 396680972 | VISIT CARD TOTAL | ALFA KARGO DIS TICARET LIMIT | 4909000000 – Printed or illustrated postcards; printed cards bearing pers | 1/33 | 4911999000 | business card labelled as greeting/announcement card (4909) |

### Lead document 26014747994277 — 9 flagged of 32 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 470990944 | MFH-PE75 HIGH-SPEED ENERGY-SAVING TWO LAYER PI | JWELL | 8477800000 – Other machinery | 1/32 | 8477200000 | complete extrusion line (functional unit) vs 'extruders' |
| 5 | 471001285 | Encoder + wheel | Changzhou Jwell Pipe Equipme | 8477900000 – Parts | 5/32 | 9031800000 | encoder assembly for the extrusion line labelled as machine parts (8477.90) |
| 9 | 471001289 | PTFE white conduit | Changzhou Jwell Pipe Equipme | 8477900000 – Parts | 5/32 | 3917000000 | spare part for the extrusion line labelled as machine parts; classified by material instead |
| 10 | 471001290 | Mandrel connecting plate and screws | Changzhou Jwell Pipe Equipme | 8424909000 – OTHERS | 8/32 | 8487909000 | shipment-wide spare-parts label 8424909000 (parts of spraying appliances) |
| 11 | 471001291 | 3KW, Vacuum loader (PE granules) | Changzhou Jwell Pipe Equipme | 8424909000 – OTHERS | 8/32 | 8477000000 | shipment-wide spare-parts label 8424909000; vacuum loader stopped at 8477 |
| 12 | 471001292 | Material conveying pipe | Changzhou Jwell Pipe Equipme | 8424909000 – OTHERS | 8/32 | — | shipment-wide spare-parts label 8424909000; material unknown -> no code |
| 13 | 471001293 | Silicone sheet | Changzhou Jwell Pipe Equipme | 8424909000 – OTHERS | 8/32 | 4008000000 | shipment-wide spare-parts label 8424909000; silicone sheet stopped at 4008 |
| 14 | 471001294 | Nylon rollers on coiler | Changzhou Jwell Pipe Equipme | 8424909000 – OTHERS | 8/32 | 3926909000 | shipment-wide spare-parts label 8424909000; nylon rollers -> 3926.90 |
| 15 | 471001295 | Stainless steel pipe, inside vacuum tank | Changzhou Jwell Pipe Equipme | 8424909000 – OTHERS | 8/32 | 7300000000 | shipment-wide spare-parts label 8424909000; seamless vs welded unknown -> chapter 73 |

### Lead document 26014749031557 — 8 flagged of 27 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 33 | 471477922 | BATHBomb Gift | PASA INTERNATIONAL TRADE (YI | 9615110000 – Of hard rubber or plastics | 2/27 | 3307300000 | label is combs/hair-slides for a bath bomb - label looks wrong |
| 35 | 471477924 | Bluetooth remote control | PASA INTERNATIONAL TRADE (YI | 8517699000 – Others | 2/27 | 8526920000 | Bluetooth remote as radio remote control (8526.92) vs label 8517.69 |
| 48 | 471477937 | Sewing machine with usb | PASA INTERNATIONAL TRADE (YI | 8412100000 – Reaction engines other than turbojets | 1/27 | 8452000000 | label is reaction engines (8412.10) for a sewing machine - label looks wrong |
| 49 | 471477938 | Nebulizer with usb | PASA INTERNATIONAL TRADE (YI | 8424201100 – GUNS AND TOOLS, WHERE THE WEIGHT OF EACH ONE DOES NOT EXCEED | 1/27 | 9019200000 | label is spray guns (8424.20) for a nebulizer |
| 55 | 471477944 | Scarves | PASA INTERNATIONAL TRADE (YI | 6106900000 – Of other textile materials | 1/27 | 6214900000 | scarves labelled as knitted women's blouses (6106.90) |
| 70 | 471477959 | Sweeper with gasoline | PASA INTERNATIONAL TRADE (YI | 8433190000 – Other | 1/27 | — | gasoline sweeper labelled as lawn mower (8433.19); 8705/8479 undecided -> no code |
| 71 | 471477960 | 140*140 PVC tablecloth | PASA INTERNATIONAL TRADE (YI | 3926909000 – OTHERS | 2/27 | 3924909000 | PVC tablecloth: 3924.90 (household articles, which names tablecloths) vs label 3926.90 |
| 73 | 471477962 | clear table cover | PASA INTERNATIONAL TRADE (YI | 6302590000 – Of other textile materials | 1/27 | — | 'clear table cover' (plastic) labelled as textile table linen; chapters 39/63 -> no code |

### Lead document 26014757091071 — 5 flagged of 17 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 20 | 479591718 | EYELASH CURLER | YIWU TAOXUAN IMPORT AND EXPO | 9603300000 – Artists brushes, writing brushes and similar brushes for the | 1/17 | 8205599900 | eyelash curler labelled as cosmetic brushes (9603.30) - third different label for eyelash curlers |
| 44 | 479591742 | EYELASH CURLER | YIWU TAOXUAN IMPORT AND EXPO | 9603291900 – OTHERS | 2/17 | 8205599900 | eyelash curler labelled as toilet brushes (9603.29) |
| 70 | 479591768 | HUMIDIFER | YIWU TAOXUAN IMPORT AND EXPO | 3926909000 – OTHERS | 4/17 | — | humidifier labelled as plastic articles (3926.90) - shipment-wide code for Yiwu Taoxuan lines |
| 73 | 479591771 | ROLL PAPER | YIWU TAOXUAN IMPORT AND EXPO | 3926909000 – OTHERS | 4/17 | 4800000000 | 'roll paper' labelled as plastic articles; chapter 48 fan-out ends at 4800000000 |
| 74 | 479591772 | RIBBON | YIWU TAOXUAN IMPORT AND EXPO | 4016999000 – OTHERS | 1/17 | — | gift ribbon labelled as vulcanised-rubber articles; material unknown -> no code |

### Lead document 26014669391783 — 3 flagged of 17 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 10 | 436195937 | Vest | YIWU MATA IMPORT AND EXPORT  | 6211491000 – SHIRTS | 2/17 | — | line/extraction says men's vest; label is women's other garments (shirts); knit unknown -> no code |
| 41 | 436195968 | Bib | YIWU MATA IMPORT AND EXPORT  | 6211491000 – SHIRTS | 2/17 | — | baby bib labelled as women's shirts (6211.49); knit/material unknown -> no code |
| 43 | 436195970 | Nappy | YIWU MATA IMPORT AND EXPORT  | 6209909000 – OTHERS | 1/17 | 9619000000 | label is textile babies' garments; 9619 covers napkins (diapers) of any material |

### Lead document 26044763902154 — 2 flagged of 10 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 2 | 480110430 | Bearing sleeve for radiator rubber support / m | TEILE.COM | 8409999000 – OTHERS | 1/10 | — | label is engine parts (8409); item is a radiator mount bushing; no code |
| 4 | 480110432 | A/C Evaporator / Condenser / radiator, Air con | TEILE.COM | 8708919000 – OTHERS | 3/10 | 8415903100 | prediction is a vehicle-specific A/C evaporator line; label is radiator parts |

### Lead document 26014511454888 — 1 flagged of 6 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 4 | 376858668 | Mortel, MIX 0.4-0.8 (verpakt per 25kg) QMI22 / | Quartzline | 3824990000 – Other | 1/6 | 3824500000 | GIR picked the specific 'non-refractory mortars' line over the label's 'other' |

### Lead document 26014527051488 — 1 flagged of 30 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 26 | 376065056 | EYE MASK | ZHAOQING KEYU TRADING CO., L | 3304200000 – Eye makeup preparations | 2/30 | 3304999000 | skin-care eye mask labelled as eye make-up |

### Lead document 26014621989963 — 1 flagged of 10 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 36 | 419152535 | EYELASH TWEEZER STAINLESS STEEL | YIWU SHUNHANG TRADING CO., L | 8214200000 – Manicure or pedicure sets and instruments (including nail fi | 4/10 | 8203200000 | tweezers are named in 8203.20; label uses 8214.20 |

### Lead document 26014629035702 — 1 flagged of 14 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 11 | 421635900 | SCARF CLIP | YIWU YILAN IMPORT&EXPORT CO. | 9615110000 – Of hard rubber or plastics | 1/14 | — | scarf clip labelled as plastic hair slide; material unknown -> no code |

### Lead document 26014705316703 — 1 flagged of 3 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 26 | 459355630 | SHIFEI NATURAL EXFOLAITION FOOT MASK WITHIN 7  | SHIFEI | 3304999000 – OTHERS | 3/3 | 3304300000 | foot peel mask placed in 'pedicure preparations' (3304.30) vs label 'other' (3304.99) |

### Lead document 26014753797259 — 1 flagged of 12 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 5 | 475830714 | BULB 3.8V | NINGBO FREE TRADE ZONE YONG  | 8539520000 – Lightemitting diode (LED) lamps | 1/12 | 8539200000 | label says LED lamp; line says 'BULB 3.8V' for circuit experiments |

### Lead document 26014776380638 — 1 flagged of 1 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 482270175 | Non Stop Original | Non Stop | 2202100000 – Waters, including mineral waters and aerated waters, contain | 1/1 | 2202990000 | energy drink: 2202.10 (sweetened/flavoured waters) vs 2202.99 (other beverages) |

### Lead document 26014777190390 — 1 flagged of 2 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 2 | 482883116 | DURUM SEMOLINA in 25kg bags | MITSIDES PUBLIC COMPANY LTD | 1101002000 – In packages whose weight exceeds 5.5 KG | 2/2 | 1103110000 | durum semolina: HS names semolina under 1103.11; label uses wheat flour (1101) |

### Lead document 26014786611451 — 1 flagged of 3 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 6 | 486928944 | BENTONITE | H2Oil Wall Services SRL | 3802900000 – Other | 1/3 | 2508100000 | bentonite labelled as activated natural mineral (3802.90) |

### Lead document 26044510481973 — 1 flagged of 3 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 368804166 | EC sensor | ShanghaiLanchangAutomation T | 9031809000 – OTHERS | 1/3 | 9027800000 | evaluator reasoning defensible; sibling never evaluated |

### Lead document 26044610448948 — 1 flagged of 2 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 414447521 | Novastar TB30 controller | Novastar | 8537109000 – :OTHERS | 1/2 | 8471000000 | evaluator's literal reading of 8537 is correct |

### Lead document 26044694115686 — 1 flagged of 2 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 447120847 | Wearable breast pump ABS, PP, silicone Sucking | BIAMBA SMART BABY CARE | 8501319100 – Of a weight not exceeding 12 kg | 2/2 | 8414100000 | label is DC motor (8501.31); product is a breast pump |

### Lead document 26044795218629 — 1 flagged of 1 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 488066093 | HOUR METER | NINGBO JIANGBEI RUN LEADER E | 9102990000 – Other | 1/1 | 9029100000 | label is watches (9102.99); item is an equipment hour meter |

## 2. Code is plausible, the line alone is misleading — probably keep (7 products, 3 lead documents)

Here the declared code is likely correct at declaration level (for example every line on the invoice is a valve spare), but the line in isolation says something else. These test whether the agent can use invoice context, so deleting them removes a real capability gap rather than noise.

### Lead document 26044688476383 — 5 flagged of 9 products — all 5 flagged lines share the declared code **8481909000** (OTHERS)

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 444783614 | Bumper | Aljac | 8481909000 – OTHERS | 5/9 | 8708100000 | line only makes sense in document context (valve parts) |
| 1 | 444783846 | Handle Grip | Aljac | 8481909000 – OTHERS | 5/9 | — | line only makes sense in document context; cross-chapter undecided -> no code |
| 4 | 444783849 | Back up | Aljac | 8481909000 – OTHERS | 5/9 | — | line only makes sense in document context; cross-chapter undecided -> no code |
| 8 | 444783853 | QUAD Ring | Aljac | 8481909000 – OTHERS | 5/9 | 4016000000 | valve-context label; even the text-correct 4016.93 was blocked by over-strict material check |
| 10 | 444783855 | Retainer | Aljac | 8481909000 – OTHERS | 5/9 | 8708000000 | valve-context label; Milvus 8708 at 90 routed to motor-vehicle parts |

### Lead document 26014558135580 — 1 flagged of 36 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 24 | 406335973 | cocoon of wool | sen zhang | 5511300000 – Of artificial staple fibres | 1/36 | 5105000000 | 'cocoon of wool' is a yarn cake of artificial fibre; the name says wool |

### Lead document 26044569977806 — 1 flagged of 1 products

| Row | table_extraction_id | Description | Brand | Declared code | Same code in doc | Agent said | Why it looks wrong |
|---|---|---|---|---|---|---|---|
| 1 | 395427164 | robot dog | WISEMATE TECHNOLOGY TRADING  | 8479500000 – Industrial robots, not elsewhere specified or included | 1/1 | 9503000000 | input metadata says toy; label says industrial robot |

## 3. Same declaration + same code, but scored correct — check these together

These products were **not** in the failure list, yet they carry one of the declaration-wide codes flagged in section 1 (often the agent hit them because Milvus had learned that same code). If a code in section 1 is wrong, it is wrong here too — deleting only the failing lines would raise the score without changing the classifier.

| Lead document | Row | table_extraction_id | Description | Declared code | Agent said | Scored |
|---|---|---|---|---|---|---|
| 26014527051488 | 24 | 376065054 | EYE CREAM | 3304200000 | 3304200000 | correct |
| 26014558135580 | 3 | 406335952 | Plastic stick building blocks | 9503000000 | 9503000000 | correct |
| 26014558135580 | 5 | 406335954 | Bowling toys | 9503000000 | 9503000000 | correct |
| 26014558135580 | 6 | 406335955 | Plastic fruit toys | 9503000000 | 9503000000 | correct |
| 26014558135580 | 15 | 406335964 | Bubble toys | 9503000000 | 9503000000 | correct |
| 26014558135580 | 17 | 406335966 | Small Rubber Ball | 9503000000 | 9503000000 | correct |
| 26014558135580 | 25 | 406335974 | balloons | 9503000000 | 9503000000 | correct |
| 26014558135580 | 34 | 406335983 | Water spray toys | 9503000000 | 9503000000 | correct |
| 26014558135580 | 38 | 406335987 | Greeting cards | 4909000000 | 4909000000 | correct |
| 26014569415005 | 1 | 396680928 | MEN T-SHIRT TOTAL | 6203490000 | 6203490000 | correct |
| 26014569415005 | 2 | 396680929 | MEN TROUSERS TOTAL | 6203490000 | — | failed (other reason) |
| 26014569415005 | 5 | 396680932 | MEN SHORT TOTAL | 6203490000 | — | failed (other reason) |
| 26014569415005 | 6 | 396680933 | MEN SHIRT TOTAL | 6203490000 | 6203490000 | correct |
| 26014569415005 | 7 | 396680934 | MEN PAJAMAS TOTAL | 6203490000 | 6203490000 | correct |
| 26014621989963 | 32 | 419152531 | CUTICLE NIPPERS STAINLESS STEEL | 8214200000 | 8214200000 | correct |
| 26014621989963 | 34 | 419152533 | EYELASH CURLER STAINLESS STEEL | 8214200000 | 8205599900 | failed (other reason) |
| 26014621989963 | 43 | 419152542 | NAIL CLIPPER SET | 8214200000 | 8214200000 | correct |
| 26014705316703 | 7 | 459355611 | SHIFEI ACNE PATCH 24 PCS | 3304999000 | 3004900000 | failed (other reason) |
| 26014705316703 | 25 | 459355629 | SHIFEI DEEP CLEANSING NOSE STRIPS (THAYE | 3304999000 | 3304990000 | correct |
| 26014747994277 | 2 | 471001282 | Calibrator | 8477900000 | 8477900000 | correct |
| 26014747994277 | 4 | 470990947 | SPARE SCREW FOR 60/42 EXTRUDER | 8477900000 | 8477900000 | correct |
| 26014747994277 | 8 | 471001288 | Spray nozzles | 8424909000 | 8424900000 | correct |
| 26014747994277 | 16 | 471001296 | Screen changer for big extruder | 8424909000 | — | failed (other reason) |
| 26014747994277 | 17 | 471001297 | Screen mesh | 8477900000 | 7419800000 | failed (other reason) |
| 26014749031557 | 32 | 471477921 | Door Bell | 8517699000 | — | failed (other reason) |
| 26014749031557 | 78 | 471477967 | Comb | 9615110000 | 9615100000 | correct |
| 26014749031557 | 84 | 471477973 | Watch display stand | 3926909000 | — | failed (other reason) |
| 26014757091071 | 11 | 479591709 | HAIR BRUSH | 9603291900 | 9603291000 | correct |
| 26014757091071 | 50 | 479591748 | PIGGY BANK | 3926909000 | 8303001000 | failed (other reason) |
| 26014757091071 | 72 | 479591770 | GIFT BOX | 3926909000 | — | failed (other reason) |
| 26014777190390 | 1 | 482883115 | DURUM WHEAT FLOUR in 25kg bags | 1101002000 | 1101002000 | correct |
| 26044694115686 | 1 | 454537568 | biamba(logo) 1pcs soft host | 8501319100 | — | failed (other reason) |
| 26044763902154 | 5 | 480110433 | Intercooler | 8708919000 | 8708919000 | correct |
| 26044763902154 | 9 | 480110437 | Air guide/Prowadnica powietrza | 8708919000 | 8708999000 | failed (other reason) |

## If you remove section 1

- Test set today: 442 products, 242 classified correctly (54.8%).
- Removing the 61 section-1 products leaves 381 products, still 242 correct → 63.5%.
- Expect the score to move a lot for a few documents, so check them first: the documents with the most flagged lines are listed at the top of each section.
- Keep the deleted ids somewhere (this file), so a later run can be compared against the same product set.

