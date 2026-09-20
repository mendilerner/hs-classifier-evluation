# Root-cause analysis: product-agent-results-run1

Source: `product-agent-results-run1.json`: 442 products, 242 correct, **200 analysed** (86 returned no code, 114 returned wrong digits).

Each row's `full_result` was read individually: Milvus hits, LLM candidates, every chapter/heading/subheading evaluation with its status and reasoning, and the final selection. The expected code was checked against the customs book. Per-row details are in `root-cause-analysis-product-run1.csv`.

## Primary root cause, grouped

| Group | Rows | No code | Wrong digits | Categories |
|---|---|---|---|---|
| A. Label vs. line text | 68 | 22 | 46 | LABEL_NOT_SUPPORTED_BY_TEXT (61), DESCRIPTION_CONFLICTS_LABEL (7) |
| B. Input missing the deciding fact | 57 | 38 | 19 | DESCRIPTION_INSUFFICIENT (54), EXTRACTION_METADATA_WRONG (3) |
| C. Evaluator reasoning | 41 | 20 | 21 | EVAL_WRONG_CONTRADICTION (17), EVAL_OVER_STRICT (11), EVAL_WRONG_MATCH (7), EVAL_DEAD_END (4), EVAL_INCONSISTENT (1), NATIONAL_LINE_ERROR (1) |
| D. Candidate generation | 17 | 4 | 13 | CANDIDATES_MISSED (12), INVOICE_HS_HINT_IGNORED (5) |
| E. Milvus routing / bugs | 14 | 0 | 14 | MILVUS_SHORTCUT_WRONG (11), MILVUS_LEADING_ZERO_BUG (3) |
| F. Data / technical | 3 | 2 | 1 | CUSTOMS_BOOK_DATA_ERROR (2), LLM_OUTPUT_PARSE_FAILURE (1) |

**Only one primary cause is assigned per row.** Many rows also show a secondary issue, covered in the cross-cutting section below.

## What the groups mean

- **A. Label vs. line text (68).** The expected code does not follow from what the line says, and often the classifier's reading of the text is the literal tariff fit. Examples: sewing machine → 8412100000 *reaction engines*; bath bomb → 9615110000 *combs*; eyelash curler labelled three different ways (8214200000 / 9603291900 / 9603300000). Most of these come from **one code applied to a whole declaration**:
  - Alfa Kargo: men's suit, jacket, boxers, blouse, dress and skirt all → 6203490000 *men's trousers*.
  - Jwell: every spare part → 8424909000 *parts of spraying appliances*.
  - Yiwu Taoxuan: humidifier and roll paper → 3926909000 *plastic articles*.
  - Fifi Chen kit: hula hoop, traffic cones, sun hat and styrofoam balls → 9503000000 *toys*.

  The dataset is meant to be realistic, so these should be **verified, not dropped**. If a label is right, the signal that justifies it lives at declaration level (other lines, supplier, documents), not in the line.
- **B. Input missing the deciding fact (57).** The line lacks the attribute the tariff splits on: knitted vs woven, material, household vs commercial, composition behind a chemical trade name. Three rows had metadata invented at extraction that pushed the wrong way: 'glass box' → 'for packaging', 'column' → 'building material', a scanner cradle → 'barcode scanner'.
- **C. Evaluator reasoning (41).** The right candidate was in front of the evaluator and was wrongly rejected, or a wrong one was accepted.
- **D. Candidate generation (17).** The correct heading was never proposed, including 5 lines where the **invoice itself carries the HS code** in the description or model field and it was ignored (`HS Code: 8302300090`, `HS Code: 4016930090`, `7903 4000/9`, `9023-0000/3`, `HS Code:85241100`).
- **E. Milvus routing / bugs (14).** The single-leaf shortcut returned a wrong code with no LLM check, or leading-zero codes broke the lookup.
- **F. Data / technical (3).** Wrong generated requirements in the customs book, and an unparseable LLM response.

## Cross-cutting findings (secondary patterns, counted across all 200 rows)

1. **"No code at all" when the candidates span chapters: 77 of the 86 no-code rows.** When two or more candidates stay INSUFFICIENT_INFORMATION in different chapters, there is no common ancestor, so `predicted_hs_code` is empty. In many of these rows the correct heading *was* a candidate:
   - 24 apparel rows split only on knitted (Ch.61) vs woven (Ch.62).
   - About 56 rows where material was unknown (plastic / rubber / steel / paper / glass).
2. **The evaluator demands explicit evidence for defaults.** O-rings and quad rings "could be PTFE", a kitchen knife "may not be base metal", ISO 68 hydraulic oil "may be synthetic", contract chickpeas "not stated dried", "sexy underwear" "gender not specified", shower pouf "may be textile", "LABLE CARD" "may not be paper". The generic requirement *"must not be elsewhere specified"* alone kept the correct heading undecided in 8 rows (2008, 2106, 3824, 8471, 8477, ...).
3. **Correct candidate present but not chosen.**
   - In 95 of 200 rows a correct heading (or deeper code) was evaluated: it was **contradicted in 53** and left **insufficient in 40**.
   - Milvus returned the **exact expected leaf in 65 rows**, typically score 77 with the full 2/4/6/10-digit path (a history hit). In the hybrid path it is only a hint, and the evaluator often overrules it.
4. **Recurring evaluator misreadings:**
   - *"a sensor / accessory / part is not an instrument"*: force sensor → fell back to chapter 84 (8400000000); NO-therapy sensor; friction-test drum; screen changer. Headings 9024, 9031 and 8477 include their parts and accessories.
   - *"including X"* read as *"must be X"*: 8517.62 "including switching and routing apparatus".
   - Literal readings: "aerials of all kinds" read as telephone-only (GNSS antenna → ERROR); "remote pilot" not recognised as a pilot valve; "bouillon seasoning" rejected from "soups, broths and preparations therefor".
   - Section/chapter notes not applied (6 rows): Section XVII note 2 (intake air filters 8421 and base-metal fittings 8302 excluded from 8708), Section XVI note 1(g) (rubber belts 4010 excluded from machine parts), Ch.34 note (EBS is a chemically defined amide, not a prepared wax), GIR 5(b) (sand in PP sacks classified as the sacks).
   - Packaging judged instead of contents: Dolce Gusto Chococino "capsules, not powder" → ERROR; 25 kg sand bags → PP sacks.
5. **Dead ends (9 ERROR rows).** After a MATCHed heading, or a single candidate, every child was contradicted and the run stopped instead of backing off to the parent and trying siblings:
   - Face brushes: only 9603.21 toothbrushes tried.
   - Tea 1 kg: 0902.40 correctly rejected on pack size, 0902.30 never tried.
   - Bumper retaining strip: only 8708.99 tried.
   - Push-button cover plate: 8538 matched, both children contradicted.
6. **Milvus leading-zero bug (15 rows in the run; 5 among these failures).** Codes for chapters 01–09 come back with the leading zero stripped (`901210000` for 0901210000):
   - If the stripped code exists in another chapter it becomes a real, wrong leaf and the single-leaf shortcut accepts it: **Dolce Gusto coffee → 9012100000 *microscopes*; Colombian green coffee beans → 9011100000 *stereoscopic microscopes***, both SUCCESS with confidence 1.0.
   - Otherwise the hint is silently dropped (lamb racks, chickpeas, tea → treated as chapter 90).
7. **Single-leaf shortcut accuracy:** 98 rows in the run used `milvus_single_leaf`: 83 correct, **15 wrong (85%)**. Errors are mostly the wrong national line (fruit knife, coffee pot, USB lamp, printing ink named "BLACK" → "other") and material assumptions (piggy bank → metal savings box, slippers → non-leather uppers).
8. **Customs-book enrichment errors (wrong generated `requirements` / `simple_description`):**
   - 7113190000 says *"other than gold or silver"*; the official text only excludes silver. Result: an 18K gold bracelet got no code.
   - 3307909000 says *"must not be depilatories / bath preparations / deodorants"*; heading 3307 explicitly includes them. Result: depilatory wax went to 3304.

   Worth auditing the whole book for generation errors of this kind.
9. **LLM output parse failures (4 rows with warnings).** The aircraft water boiler lost both heading evaluations to *"No valid JSON array found in response"* and returned nothing, although 8516 was a candidate and Milvus had the exact code. Three other rows logged *"No CODE tags found, used digit-sequence fallback"*.
10. **Tax/requirements unaffected:** 28 of the 114 wrong-digit rows still have `any_leaf_full_match = True`.

## Suggested fixes, ordered by rows affected

| # | Fix | Rows it would address (approx.) |
|---|---|---|
| 1 | When candidates stay undecided across chapters, return the best-ranked candidate (for 61/62, the heading) instead of an empty code | up to 77 no-code rows |
| 2 | Let the evaluator accept typical defaults ("a knife is metal", "an O-ring is rubber", "a card is paper"), and stop treating the generic "not elsewhere specified" requirement as unresolved | ~20–30 |
| 3 | Treat a Milvus exact-leaf history hit (full path returned) as strong evidence instead of a plain hint | part of the 65 rows where Milvus had the exact leaf |
| 4 | Pass declaration context (other lines, supplier, invoice) to each line | Aljac valve parts, Jwell spares, AO Protey plastics, most of group A |
| 5 | Use an HS code printed on the invoice line (description/model) as a candidate | 5+ |
| 6 | Fix leading-zero normalisation for chapters 01–09 in the Milvus integration | 15 in the run (2 coffee → microscopes) |
| 7 | On a dead end, back off to the parent and evaluate the siblings | 9 ERROR rows |
| 8 | Add section/chapter-note checks (XVI 1(g), XVII 2, Ch.34/39 notes, GIR 5(b)) to the evaluator context | ~8 |
| 9 | Stricter single-leaf shortcut, e.g. no shortcut when the national lines split on an attribute not in the text | 11–15 |
| 10 | Audit generated customs-book requirements against the official text | 2 found, likely more |
| 11 | Retry on unparseable LLM JSON | 1–4 |


## Per-row index

| # | teid | Description | Expected | Predicted | Group | Category | Summary |
|---|---|---|---|---|---|---|---|
| 0 | 365821545 | MIND EMBEDDED MODULE FOR ALL-IN-ONE CARD READER | 8517790000 | — | C | EVAL_WRONG_CONTRADICTION | correct code offered by Milvus, rejected by evaluator |
| 1 | 365821546 | RFID KEY FOBS | 8523529000 | 8517699000 | C | EVAL_WRONG_MATCH | correct heading INSUFFICIENT, wrong heading MATCH |
| 2 | 361282012 | 1.8KW Generator | 8504409900 | 8502000000 | B | DESCRIPTION_INSUFFICIENT | label needs knowledge not in description |
| 3 | 368804166 | EC sensor | 9031809000 | 9027800000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | evaluator reasoning defensible; sibling never evaluated |
| 4 | 368694538 | ICO320-83C-N3350-4LAN-COM-CAN-WT-DC//(Type:SYS,Brand:Axiomte | 8471500000 | 8471400000 | C | EVAL_WRONG_CONTRADICTION | tariff misreading: box PC is a 'processing unit' (8471.50) |
| 5 | 368694542 | Rail Kit | 8473300000 | 9403900000 | C | EVAL_WRONG_CONTRADICTION | ignored brand context (computer maker) for parts/accessories |
| 6 | 372819374 | Your PO No.: CI 12429: 10 ESC NG S/N: 367, 368 Coating, Test | 8486900000 | 9031900000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf >=90 skipped the LLM |
| 7 | 386751181 | glass panel, Material: glass, use for repair, HS Code:852411 | 8524129000 | — | D | INVOICE_HS_HINT_IGNORED | + correct Milvus code contradicted; cross-chapter undecided -> no code |
| 8 | 388515659 | UC-BRKT-260-P-Z-ASSY UNI COMM, BRKT,UC-ENGINE-P-Z,HD-CONV-US | 8517629000 | 8471900000 | E | MILVUS_SHORTCUT_WRONG | CloseDistance leaf >=90 beat brand/model history |
| 9 | 395427164 | robot dog | 8479500000 | 9503000000 | A | DESCRIPTION_CONFLICTS_LABEL | input metadata says toy; label says industrial robot |
| 10 | 398889183 | SR1.2(BIDI) transceiver | 8517629000 | 8517621000 | C | EVAL_WRONG_CONTRADICTION | misread 'including switching and routing' as a requirement; wrong narrow sibling MATCH |
| 11 | 399434783 | ECCN 5A992.c RF Receivers | 8517629000 | 8517695900 | B | DESCRIPTION_INSUFFICIENT | vague line; subheading choice defensible |
| 12 | 410103672 | MEDICAL DEVICES | 9021109000 | 9018000000 | B | DESCRIPTION_INSUFFICIENT | generic line; correct chapter, stopped at heading |
| 13 | 411210341 | Control UM122 Lots:51699561 | 8537107900 | — | B | DESCRIPTION_INSUFFICIENT | + correct heading contradicted; cross-chapter undecided -> no code |
| 14 | 411213831 | replacement kit sensor NO for NO-A therapy unit | 9019200000 | 9018900000 | D | CANDIDATES_MISSED | correct heading never proposed |
| 15 | 414447521 | Novastar TB30 controller | 8537109000 | 8471000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | evaluator's literal reading of 8537 is correct |
| 16 | 455544355 | 62197-001-001 WATER BOILER Serial #: 09-02-2817 | 8516109000 | — | F | LLM_OUTPUT_PARSE_FAILURE | evaluation response unparseable -> both headings INSUFFICIENT -> no code |
| 17 | 433428807 | Saturn EN 2*22kW AC EVSE A12380001 DH-AC0220XG58-D | 8537107300 | 8504400000 | D | CANDIDATES_MISSED | Israeli national line (EV-charging control apparatus) never proposed |
| 18 | 434580133 | External push button panel for 2 stops type: RT42, connectin | 8536509900 | 8537107900 | D | CANDIDATES_MISSED | 8536 never proposed; ended on 8537 'others' leaf |
| 19 | 434580134 | Plate without print for push button panel type RT42 Imprint  | 7326901900 | — | C | EVAL_DEAD_END | heading MATCH but every child contradicted -> ERROR, no code |
| 20 | 434580135 | Control board PL640 | 8537109000 | 8431310000 | C | EVAL_WRONG_CONTRADICTION | assumed 'control board' = printed circuit to apply an exclusion |
| 21 | 437376505 | PVC 222nm UVC LED Light For disinfection | 9405420000 | 8539520000 | D | CANDIDATES_MISSED | luminaire heading 9405 never proposed (lamp vs luminaire) |
| 22 | 438845800 | High Precision GNSS L1/L2/L5 Vehicle Antenna | 8517710000 | — | C | EVAL_WRONG_CONTRADICTION | read 'aerials of all kinds' as telephone-only -> dead end, ERROR |
| 23 | 444783614 | Bumper | 8481909000 | 8708100000 | A | DESCRIPTION_CONFLICTS_LABEL | line only makes sense in document context (valve parts) |
| 24 | 444783846 | Handle Grip | 8481909000 | — | A | DESCRIPTION_CONFLICTS_LABEL | line only makes sense in document context; cross-chapter undecided -> no code |
| 25 | 444783849 | Back up | 8481909000 | — | A | DESCRIPTION_CONFLICTS_LABEL | line only makes sense in document context; cross-chapter undecided -> no code |
| 26 | 444783853 | QUAD Ring | 8481909000 | 4016000000 | A | DESCRIPTION_CONFLICTS_LABEL | valve-context label; even the text-correct 4016.93 was blocked by over-strict material check |
| 27 | 444783855 | Retainer | 8481909000 | 8708000000 | A | DESCRIPTION_CONFLICTS_LABEL | valve-context label; Milvus 8708 at 90 routed to motor-vehicle parts |
| 28 | 444783847 | Seal | 8484909000 | — | B | DESCRIPTION_INSUFFICIENT | material unknown; correct heading proposed but undecided across chapters -> no code |
| 29 | 444783848 | O-Ring | 4016939900 | — | C | EVAL_OVER_STRICT | refused the obvious default material; cross-chapter undecided -> no code |
| 30 | 444783852 | Remote Pilot for use with option Y on 60554 | 8481109000 | 9032000000 | C | EVAL_WRONG_CONTRADICTION | domain misunderstanding: a 'pilot' is a pilot valve |
| 31 | 447120847 | Wearable breast pump ABS, PP, silicone Sucking breast milk | 8501319100 | 8414100000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is DC motor (8501.31); product is a breast pump |
| 32 | 454537568 | biamba(logo) 1pcs soft host | 8501319100 | — | B | DESCRIPTION_INSUFFICIENT | uninterpretable line; extraction invented 'baby care product'; label copied from pump |
| 33 | 450773066 | Canyon FIX 6+1 Minitoolholder Workshop | 8204110000 | 8205599900 | D | CANDIDATES_MISSED | 8204 (spanners/hex keys) never proposed |
| 34 | 462813635 | Force Sensor | 9031802000 | 8400000000 | C | EVAL_WRONG_CONTRADICTION | 'a sensor is a component, not an instrument' -> fell back to chapter 84 (8400000000) |
| 35 | 457457034 | BRACKET FOR WHEEL HOUSING New / Genuine Bentley Part / Count | 8302301900 | 8708999000 | D | INVOICE_HS_HINT_IGNORED | invoice says 8302300090; also Section XVII note on parts of general use not applied |
| 36 | 457457036 | SENSOR PRIMED New / Genuine Bentley Part / Country of origin | 8512901000 | 8543700000 | C | EVAL_INCONSISTENT | accepted 'Bentley part = motor vehicle' at heading level, then denied automotive use at national-line level |
| 37 | 457457037 | SEAL RING SATIN BLACK New / Genuine Bentley Part / Country o | 4016939100 | — | D | INVOICE_HS_HINT_IGNORED | invoice says 4016930090; material 'not stated' -> cross-chapter undecided -> no code |
| 38 | 462050007 | 18K YELLOW GOLD BRACELET | 7113119000 | — | F | CUSTOMS_BOOK_DATA_ERROR | generated requirement for 7113.19 says 'other than gold or silver'; label itself says silver |
| 39 | 480110430 | Bearing sleeve for radiator rubber support / mounting | 8409999000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is engine parts (8409); item is a radiator mount bushing; no code |
| 40 | 480110431 | Water cooler / radiator fastening clamp | 3926908900 | 8708919000 | B | DESCRIPTION_INSUFFICIENT | material not stated; label is plastic article for vehicles (parts of general use) |
| 41 | 480110432 | A/C Evaporator / Condenser / radiator, Air condition / Refri | 8708919000 | 8415903100 | A | LABEL_NOT_SUPPORTED_BY_TEXT | prediction is a vehicle-specific A/C evaporator line; label is radiator parts |
| 42 | 480110434 | Air cleaner | 8421310000 | 8708999000 | C | EVAL_WRONG_CONTRADICTION | rejected chapter 84 for an automotive air filter (Section XVII note 2 not applied); Milvus leaf 87 not evaluated |
| 43 | 480110435 | Retaining strip, L/Listwa mocująca, L | 8708109000 | — | C | EVAL_DEAD_END | single LLM candidate contradicted -> ERROR; siblings (8708.10 / 8708.29) never tried |
| 44 | 480110437 | Air guide/Prowadnica powietrza | 8708919000 | 8708999000 | B | DESCRIPTION_INSUFFICIENT | line doesn't say the air guide belongs to the radiator; residual 8708.99 chosen |
| 45 | 482180549 | AFE156: AFE Momentum GT Cold Air Intakes | 8421310000 | 8708999000 | D | CANDIDATES_MISSED | 8421.31 never proposed; Section XVII note 2(e) not applied |
| 46 | 483449579 | DS3678-DP RUGG VIBR STD CRADLE USB KIT SHIELD CABLE NO A/C C | 8471900000 | 8471600000 | B | EXTRACTION_METADATA_WRONG | line is a scanner cradle kit; extraction said 'barcode scanner' |
| 47 | 483527824 | plastic Cutting plotter for Cutting label | 8441109000 | 8479000000 | B | DESCRIPTION_INSUFFICIENT | ambiguous 'plastic' read as the material being cut -> correct heading contradicted |
| 48 | 483527825 | plastic Cutting plotter parts for Cutting label | 8441909000 | 8441901000 | C | NATIONAL_LINE_ERROR | right 6 digits; picked a specific national line without evidence |
| 49 | 482876604 | PK2000IA0000E-2002-1BA-SBB Swissbit iShield Key Pro in Box w | 8471800000 | 8471900000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf >=90 (GeneralProductAndPurpose) skipped the LLM |
| 50 | 488066093 | HOUR METER | 9102990000 | 9029100000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is watches (9102.99); item is an equipment hour meter |
| 51 | 365008885 | Pistachio Filling (London Chocolate) | 2008191000 | — | C | EVAL_OVER_STRICT | generic 'not elsewhere specified' requirement blocks the correct heading; cross-chapter -> no code |
| 52 | 365008886 | White Hazelnut Filling (Mr.Cake Chef) 4 Pail | 1806200000 | — | B | DESCRIPTION_INSUFFICIENT | cocoa content not stated ('white' = white chocolate); cross-chapter undecided -> no code |
| 53 | 365015344 | FILMWAX 400g white chocolate - STALWAX Lotto: 260326 | 3307909000 | 3304999000 | F | CUSTOMS_BOOK_DATA_ERROR | generated requirements for 3307909000 say 'must not be depilatories' - the official text includes them |
| 54 | 365669587 | FROZEN BONE IN OVINE RACKS | 0204410000 | 0204420000 | E | MILVUS_LEADING_ZERO_BUG | Milvus returned '204410000' (0204410000 without leading zero) -> hint dropped; lamb vs sheep over-strict |
| 55 | 368806307 | NESCAFE DOLCE GUSTO ARDENZA 16CAP | 0901210000 | 9012100000 | E | MILVUS_LEADING_ZERO_BUG | 0901210000 became 9012100000 (microscopes) and was accepted by the single-leaf shortcut |
| 56 | 368806311 | NESCAFE DOLCE GUSTO CHOCOCINO 16 CAPS | 1806100000 | — | C | EVAL_WRONG_CONTRADICTION | judged the capsule packaging instead of the powder inside -> dead end, ERROR |
| 57 | 368446371 | 1X20FT(19.25MT) 550BAGS X 35KG COLOMBIAN ARABICA GREEN COFFE | 0901110000 | 9011100000 | E | MILVUS_LEADING_ZERO_BUG | 0901110000 became 9011100000 (stereoscopic microscopes) via single-leaf shortcut |
| 58 | 376858291 | Primer Universal (verpakt per 10kg) | 3906909000 | 3200000000 | B | DESCRIPTION_INSUFFICIENT | composition not given (acrylic dispersion vs paint); correct Milvus code contradicted |
| 59 | 376858296 | Coating CMT (verpakt per 10kg) | 3909500000 | — | B | DESCRIPTION_INSUFFICIENT | composition not given; cross-chapter undecided -> no code |
| 60 | 376858297 | Coating PU MG matt (set à 5kg) | 3909500000 | 3200000000 | B | DESCRIPTION_INSUFFICIENT | 'coating' read as paint; label is PU in primary form; correct Milvus code contradicted |
| 61 | 376858665 | Plex 1120, verpakt per 180kg | 3208909000 | — | B | DESCRIPTION_INSUFFICIENT | product name only; cross-chapter undecided -> no code |
| 62 | 376858668 | Mortel, MIX 0.4-0.8 (verpakt per 25kg) QMI22 / Mix 842 0, | 3824990000 | 3824500000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | GIR picked the specific 'non-refractory mortars' line over the label's 'other' |
| 63 | 369332380 | CHICKEN BULLUION SEASONING | 2104100000 | 2103909000 | C | EVAL_WRONG_CONTRADICTION | 'bouillon seasoning' is a broth preparation, rejected as 'a seasoning, not a soup' |
| 64 | 375324276 | שעווה מלאכותית EBS BEAD | 2924190000 | 3404900000 | C | EVAL_WRONG_CONTRADICTION | didn't recognise EBS as a chemically defined amide; trusted the 'artificial wax' label |
| 65 | 376065037 | FACE PADS | 3304999000 | 5600000000 | B | DESCRIPTION_INSUFFICIENT | not stated whether pads are impregnated with a preparation; correct Milvus code contradicted |
| 66 | 376065056 | EYE MASK | 3304200000 | 3304999000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | skin-care eye mask labelled as eye make-up |
| 67 | 382991570 | IL Rescue Remedy Dropper Kosher 10ml Batch 0000147986 Expiry | 2106909200 | 3004900000 | D | CANDIDATES_MISSED | Israeli national line for alcohol drops (2106909200) never proposed |
| 68 | 382991572 | GB Rescue Plus Lozenge O&E CDU Batch 290827 Expiry Date Aug  | 2106909990 | 3004000000 | D | CANDIDATES_MISSED | food-preparation heading 2106 never proposed for a flower-remedy lozenge |
| 69 | 393489923 | ROYAL SUPER HYDRAULIC ISO 68 20L | 2710197900 | — | C | EVAL_OVER_STRICT | refused to assume a hydraulic oil is petroleum-based; cross-chapter undecided -> no code |
| 70 | 396680929 | MEN TROUSERS TOTAL | 6203490000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 71 | 396680930 | MEN SUIT TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label: a men's suit labelled as trousers (6203.49); plus knit unknown -> no code |
| 72 | 396680932 | MEN SHORT TOTAL | 6203490000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 73 | 396680935 | MEN JACKET TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label (jacket labelled trousers); knit unknown -> no code |
| 74 | 396680936 | MEN BOXER TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label (boxers labelled trousers); knit unknown -> no code |
| 75 | 396680937 | MEN ATHELETE TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label; 'athlete' (singlet) with knit unknown -> no code |
| 76 | 396680939 | WOMEN BLOUSE TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label (women's blouse labelled men's trousers); knit unknown -> no code |
| 77 | 396680940 | WOMEN DRESS TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label (dress labelled men's trousers); knit unknown -> no code |
| 78 | 396680945 | WOMEN SKIRT TOTAL | 6203490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level label (skirt labelled men's trousers); knit unknown -> no code |
| 79 | 396680958 | BELT TOTAL | 6217102000 | — | B | DESCRIPTION_INSUFFICIENT | material unknown (leather vs textile); correct Milvus leaf INSUFFICIENT -> no code |
| 80 | 396680960 | CURTAINS BEADS ACCESSORIES TOTAL | 8302490000 | — | B | DESCRIPTION_INSUFFICIENT | material unknown; correct heading contradicted -> no code |
| 81 | 396680961 | DECORATIVE WALL PANEL TOTAL | 3921900000 | 3925909000 | E | MILVUS_SHORTCUT_WRONG | GeneralProductAndPurpose leaf >=90 beat the exact CloseDistance history hit |
| 82 | 396680963 | GLASS BOX TOTAL | 7013990000 | 7010000000 | B | EXTRACTION_METADATA_WRONG | extraction invented 'for packaging' -> 7010 containers; correct code contradicted on that purpose |
| 83 | 396680964 | LABLE CARD TOTAL | 4823909000 | — | C | EVAL_OVER_STRICT | 'card' not accepted as paper; cross-chapter undecided -> no code |
| 84 | 396680967 | NYLON BAGS TOTAL | 3923219000 | 3923290000 | B | DESCRIPTION_INSUFFICIENT | trade term 'nylon bags' (= polyethylene bags) read literally as polyamide |
| 85 | 396680969 | STICKER TOTAL | 4823906000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is 'gummed paper except self-adhesive' for stickers; material unknown -> no code |
| 86 | 396680970 | THREADS TOTAL | 5401209000 | — | B | DESCRIPTION_INSUFFICIENT | fibre unknown; three chapters -> no code |
| 87 | 396680972 | VISIT CARD TOTAL | 4909000000 | 4911999000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | business card labelled as greeting/announcement card (4909) |
| 88 | 396680973 | WALL MOUNTED DECORATION TOTAL | 3921900000 | — | B | DESCRIPTION_INSUFFICIENT | material/form unknown; five chapters -> no code |
| 89 | 397972904 | Chickpeas 6+ contract 18/03/26 | 0713200000 | — | C | EVAL_OVER_STRICT | bulk chickpeas not assumed dried; + Milvus leading-zero bug; cross-chapter -> no code |
| 90 | 419152533 | EYELASH CURLER STAINLESS STEEL | 8214200000 | 8205599900 | C | EVAL_WRONG_CONTRADICTION | literal reading of 'manicure/pedicure instruments' excluded an eyelash curler |
| 91 | 419152535 | EYELASH TWEEZER STAINLESS STEEL | 8214200000 | 8203200000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | tweezers are named in 8203.20; label uses 8214.20 |
| 92 | 419152536 | FACE BRUSH SET | 9603300000 | — | C | EVAL_DEAD_END | right heading (9603) but only the wrong subheading (toothbrushes) was tried -> ERROR |
| 93 | 421635890 | MAN BOXER | 6107990000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 94 | 421635892 | WOMAN VEST | 6109909000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 95 | 421635900 | SCARF CLIP | 9615110000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | scarf clip labelled as plastic hair slide; material unknown -> no code |
| 96 | 421635901 | COFFEE POT | 7323990000 | 7323930000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf >=90 assumed stainless steel |
| 97 | 421635904 | KITCHEN TUBE | 8210000000 | — | B | DESCRIPTION_INSUFFICIENT | 'kitchen tube' is uninterpretable; five chapters -> no code |
| 98 | 421635905 | FRUIT KNIFE | 8211911000 | 8211929000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf >=90 picked the wrong national knife line |
| 99 | 421635907 | HAND FAN | 3926909000 | 8414590000 | E | MILVUS_SHORTCUT_WRONG | Milvus non-leaf at 90 restricted evaluation to motorised fans |
| 100 | 421635908 | NUMDER ACCOUNT | 9029109900 | 9611000000 | B | DESCRIPTION_INSUFFICIENT | garbled line ('NUMDER ACCOUNT') |
| 101 | 421635909 | CRAFT BEAD | 3926909000 | — | B | DESCRIPTION_INSUFFICIENT | material unknown; four chapters -> no code |
| 102 | 421635912 | WOMAN DRESS | 6104490000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 103 | 436195931 | Shower pouf | 3924909000 | — | C | EVAL_OVER_STRICT | shower pouf not assumed plastic mesh; chapters 39/63 -> no code |
| 104 | 436195936 | Women's pants | 6204690000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 105 | 436195937 | Vest | 6211491000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | line/extraction says men's vest; label is women's other garments (shirts); knit unknown -> no code |
| 106 | 436195939 | Dress | 6204490000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 107 | 436195940 | Blouse | 6206900000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 108 | 436195946 | Lady clothes | 6211499000 | — | B | DESCRIPTION_INSUFFICIENT | generic 'Lady clothes'; knit unknown -> chapters 61/62 -> no code |
| 109 | 436195950 | Sexy underwear | 6108290000 | — | C | EVAL_OVER_STRICT | 'sexy underwear' not accepted as women's; knit unknown -> no code |
| 110 | 436195956 | Women's pajama set | 6208290000 | — | B | DESCRIPTION_INSUFFICIENT | knitted vs woven unknown -> chapters 61/62 -> no code |
| 111 | 436195957 | Men's slippers | 6403990000 | 6402990000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf >=90 assumed non-leather uppers |
| 112 | 436195961 | Storage glass set | 7013490000 | 7010900000 | C | EVAL_WRONG_CONTRADICTION | household storage jars sent to 7010 (packing containers) |
| 113 | 436195967 | Shorts suit | 6203490000 | — | B | DESCRIPTION_INSUFFICIENT | knit and gender unknown -> chapters 61/62 -> no code |
| 114 | 436195968 | Bib | 6211491000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | baby bib labelled as women's shirts (6211.49); knit/material unknown -> no code |
| 115 | 436195970 | Nappy | 6209909000 | 9619000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is textile babies' garments; 9619 covers napkins (diapers) of any material |
| 116 | 436195971 | Children's pants | 6211399000 | — | B | DESCRIPTION_INSUFFICIENT | knit and gender unknown -> chapters 61/62 -> no code |
| 117 | 459355611 | SHIFEI ACNE PATCH 24 PCS | 3304999000 | 3004900000 | C | EVAL_WRONG_MATCH | 'acne treatment' purpose pushed a cosmetic patch into medicaments |
| 118 | 459355630 | SHIFEI NATURAL EXFOLAITION FOOT MASK WITHIN 7 DAYS 1 pair/po | 3304999000 | 3304300000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | foot peel mask placed in 'pedicure preparations' (3304.30) vs label 'other' (3304.99) |
| 119 | 468392620 | DEEP FREEZE GEL 35G EXPORT 144 UNITS PER CASE BATCH NO.44302 | 3004900000 | 3304990000 | C | EVAL_WRONG_CONTRADICTION | didn't recognise Mentholatum Deep Freeze as a pain-relief gel; extraction purpose 'for deep freeze' |
| 120 | 468392630 | DEEP FREEZE PATCH 1 PK ME 480/CA ME0000022382SFDAA00001 BATC | 3005103000 | 3004000000 | D | CANDIDATES_MISSED | 3005 (adhesive plasters/medicated patches) never proposed |
| 121 | 466281721 | KAPPAFLEX BLACK 65-0003 | 3215110000 | 3215190000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf >=90 ignored 'BLACK' in the name |
| 122 | 470990944 | MFH-PE75 HIGH-SPEED ENERGY-SAVING TWO LAYER PIPE EXTRUSION L | 8477800000 | 8477200000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | complete extrusion line (functional unit) vs 'extruders' |
| 123 | 470990945 | TEST RUNNING MATERIAL | 3901100000 | — | B | DESCRIPTION_INSUFFICIENT | 'test running material' needs invoice context (PE raw material for the line) |
| 124 | 471001285 | Encoder + wheel | 8477900000 | 9031800000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | encoder assembly for the extrusion line labelled as machine parts (8477.90) |
| 125 | 471001286 | Belt on haul-off | 4010390000 | 8477900000 | C | EVAL_WRONG_MATCH | machine-parts residual matched for a conveyor belt (Section XVI note 1(g) not applied) |
| 126 | 471001289 | PTFE white conduit | 8477900000 | 3917000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | spare part for the extrusion line labelled as machine parts; classified by material instead |
| 127 | 471001290 | Mandrel connecting plate and screws | 8424909000 | 8487909000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | shipment-wide spare-parts label 8424909000 (parts of spraying appliances) |
| 128 | 471001291 | 3KW, Vacuum loader (PE granules) | 8424909000 | 8477000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | shipment-wide spare-parts label 8424909000; vacuum loader stopped at 8477 |
| 129 | 471001292 | Material conveying pipe | 8424909000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | shipment-wide spare-parts label 8424909000; material unknown -> no code |
| 130 | 471001293 | Silicone sheet | 8424909000 | 4008000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | shipment-wide spare-parts label 8424909000; silicone sheet stopped at 4008 |
| 131 | 471001294 | Nylon rollers on coiler | 8424909000 | 3926909000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | shipment-wide spare-parts label 8424909000; nylon rollers -> 3926.90 |
| 132 | 471001295 | Stainless steel pipe, inside vacuum tank | 8424909000 | 7300000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | shipment-wide spare-parts label 8424909000; seamless vs welded unknown -> chapter 73 |
| 133 | 471001296 | Screen changer for big extruder | 8424909000 | — | C | EVAL_WRONG_CONTRADICTION | misread 8477.90 'parts' as excluding extruder parts -> dead end, ERROR |
| 134 | 471001297 | Screen mesh | 8477900000 | 7419800000 | D | CANDIDATES_MISSED | neither machine parts (8477.90) nor woven wire cloth (7314.1x) proposed |
| 135 | 470991148 | 低温冷冻箱 Low temperature freezer XKW-25 | 8418300000 | 8418690000 | B | DESCRIPTION_INSUFFICIENT | freezer type (chest/upright) not stated |
| 136 | 470991150 | 动态摩擦系数测试用圆 Drum for dynamic friction coefficient testing | 9024909000 | — | C | EVAL_WRONG_CONTRADICTION | rejected heading 9024 for an accessory although 9024 includes parts and accessories -> ERROR |
| 137 | 471477890 | lamp with usb | 9405420000 | 9405490000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf at 90 picked non-LED 'other' lamps line |
| 138 | 471477921 | Door Bell | 8517699000 | — | B | DESCRIPTION_INSUFFICIENT | electric vs mechanical not stated; label is wireless (8517.69); chapters 83/85 -> no code |
| 139 | 471477922 | BATHBomb Gift | 9615110000 | 3307300000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is combs/hair-slides for a bath bomb - label looks wrong |
| 140 | 471477924 | Bluetooth remote control | 8517699000 | 8526920000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | Bluetooth remote as radio remote control (8526.92) vs label 8517.69 |
| 141 | 471477937 | Sewing machine with usb | 8412100000 | 8452000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is reaction engines (8412.10) for a sewing machine - label looks wrong |
| 142 | 471477938 | Nebulizer with usb | 8424201100 | 9019200000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label is spray guns (8424.20) for a nebulizer |
| 143 | 471477940 | Column | 9403990000 | — | B | EXTRACTION_METADATA_WRONG | extraction invented 'Building material / for construction' for a furniture column; material unknown -> no code |
| 144 | 471477944 | Scarves | 6106900000 | 6214900000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | scarves labelled as knitted women's blouses (6106.90) |
| 145 | 471477959 | Sweeper with gasoline | 8433190000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | gasoline sweeper labelled as lawn mower (8433.19); 8705/8479 undecided -> no code |
| 146 | 471477960 | 140*140 PVC tablecloth | 3926909000 | 3924909000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | PVC tablecloth: 3924.90 (household articles, which names tablecloths) vs label 3926.90 |
| 147 | 471477962 | clear table cover | 6302590000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | 'clear table cover' (plastic) labelled as textile table linen; chapters 39/63 -> no code |
| 148 | 471477964 | Luggage | 4202920000 | 4202100000 | B | DESCRIPTION_INSUFFICIENT | suitcase vs travel bag and outer material unknown |
| 149 | 471477970 | Knife | 8211929000 | — | C | EVAL_OVER_STRICT | knife not assumed base metal; chapters 39/44/82 -> no code |
| 150 | 471477973 | Watch display stand | 3926909000 | — | B | DESCRIPTION_INSUFFICIENT | material unknown; five chapters -> no code |
| 151 | 475830723 | ZINC GRANULAS,PK/500G 7903 4000/9 | 7903900000 | 7907000000 | D | INVOICE_HS_HINT_IGNORED | model field carries '7903 4000/9'; 'granules' read as not powder |
| 152 | 475830714 | BULB 3.8V | 8539520000 | 8539200000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | label says LED lamp; line says 'BULB 3.8V' for circuit experiments |
| 153 | 475830715 | CARDBOARD TELESCOPE 9023-0000/3 | 9023000000 | 9005801000 | D | INVOICE_HS_HINT_IGNORED | model field carries '9023-0000/3' (demonstration apparatus) |
| 154 | 475830720 | TEA 1KG 0902 4000/3 | 0902400000 | — | C | EVAL_DEAD_END | correct contradiction of 0902.40 (1kg pack -> 0902.30) but the sibling was never tried -> ERROR; + Milvus leading-zero bug |
| 155 | 479591742 | EYELASH CURLER | 9603291900 | 8205599900 | A | LABEL_NOT_SUPPORTED_BY_TEXT | eyelash curler labelled as toilet brushes (9603.29) |
| 156 | 479591713 | SPOONGE | 6307100000 | — | B | DESCRIPTION_INSUFFICIENT | sponge material unknown; label is textile cleaning cloths; no code |
| 157 | 479591720 | O'CLOCK | 9105999000 | — | C | EVAL_OVER_STRICT | exclusion for watch-movement clocks could not be ruled out; chapters 73/91 -> no code |
| 158 | 479591748 | PIGGY BANK | 3926909000 | 8303001000 | E | MILVUS_SHORTCUT_WRONG | single Milvus leaf at 100 assumed a base-metal savings box |
| 159 | 479591768 | HUMIDIFER | 3926909000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | humidifier labelled as plastic articles (3926.90) - shipment-wide code for Yiwu Taoxuan lines |
| 160 | 479591770 | GIFT BOX | 3926909000 | — | B | DESCRIPTION_INSUFFICIENT | gift box material unknown; chapters 39/44/48 -> no code |
| 161 | 479591771 | ROLL PAPER | 3926909000 | 4800000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | 'roll paper' labelled as plastic articles; chapter 48 fan-out ends at 4800000000 |
| 162 | 479591728 | STAND FOR CANDLE | 9405509000 | — | D | CANDIDATES_MISSED | 9405.50 (non-electrical luminaires / candle holders) never proposed; material unknown -> no code |
| 163 | 479591772 | RIBBON | 4016999000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | gift ribbon labelled as vulcanised-rubber articles; material unknown -> no code |
| 164 | 479591744 | GIFT BOX | 4819100000 | — | B | DESCRIPTION_INSUFFICIENT | gift box material unknown; chapters 39/44/48 -> no code |
| 165 | 479591718 | EYELASH CURLER | 9603300000 | 8205599900 | A | LABEL_NOT_SUPPORTED_BY_TEXT | eyelash curler labelled as cosmetic brushes (9603.30) - third different label for eyelash curlers |
| 166 | 475232363 | 1883 SAUCE CARAMEL 500ML | 2106909990 | 2103909000 | C | EVAL_WRONG_MATCH | sweet dessert syrup treated as a condiment sauce (2103) |
| 167 | 475232375 | DISPLAYS 1883 1L 6 BOTTLES | 7326909900 | — | B | DESCRIPTION_INSUFFICIENT | display material unknown; chapters 48/94 -> no code |
| 168 | 475232360 | 1883 CREATION FRUITS PINEAPPLE 1L (P) | 2008209000 | — | D | CANDIDATES_MISSED | 2008 (otherwise prepared pineapple) never proposed; 2007/2106 undecided -> no code |
| 169 | 482270175 | Non Stop Original | 2202100000 | 2202990000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | energy drink: 2202.10 (sweetened/flavoured waters) vs 2202.99 (other beverages) |
| 170 | 482883116 | DURUM SEMOLINA in 25kg bags | 1101002000 | 1103110000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | durum semolina: HS names semolina under 1103.11; label uses wheat flour (1101) |
| 171 | 486928939 | CHEM EMUL P | 3824990000 | — | C | EVAL_OVER_STRICT | generic 'not elsewhere specified' blocks 3824; chapters 34/38/39 -> no code |
| 172 | 486928944 | BENTONITE | 3802900000 | 2508100000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | bentonite labelled as activated natural mineral (3802.90) |
| 173 | 486928997 | CALCIUM CARBONATE - OMYADRILL 10 | 2517410000 | 2836500000 | C | EVAL_WRONG_MATCH | natural ground marble (Omyadrill) put in chemical calcium carbonate 2836.50 |
| 174 | 489499425 | REFRIGERATOR | 8418509000 | 8418200000 | B | DESCRIPTION_INSUFFICIENT | household vs commercial display fridge not stated |
| 175 | 489525999 | Drools Dog Salmon Oil Syrup 150ml | 2309102000 | 2309902000 | C | EVAL_WRONG_MATCH | retail dog supplement treated as 'other than dog food put up for retail sale' |
| 176 | 489959946 | ORGAL P 8820 | 3905219000 | — | B | DESCRIPTION_INSUFFICIENT | trade name only (ORGAL P 8820 = vinyl acetate copolymer dispersion); 3905 never proposed -> no code |
| 177 | 395581252 | 25kg sand bags in polypropylene sacks | 2505900000 | 6305330000 | C | EVAL_WRONG_MATCH | classified the packing sacks instead of the sand they contain |
| 178 | 394280258 | Lid K24.058.023, black, 1% | 3923509000 | — | B | DESCRIPTION_INSUFFICIENT | lid material unknown; chapters 39/83 -> no code |
| 179 | 394280259 | Separator, d 58, clear | 3923900000 | — | B | DESCRIPTION_INSUFFICIENT | separator material/function unknown; 3923 never proposed -> no code |
| 180 | 394280260 | Jar No. 450 M, 0.100 L, d58, P14.8, clear | 3923309000 | 7010900000 | B | DESCRIPTION_INSUFFICIENT | 'clear' jar - glass vs plastic unknown; glass assumed |
| 181 | 406335959 | Rhinestone stickers | 3919109000 | — | C | EVAL_OVER_STRICT | rhinestone stickers not assumed plastic; chapters 39/70 -> no code |
| 182 | 406335961 | Beeswax Sheets | 3404900000 | 1521900000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | beeswax sheets: 15.21 (beeswax, whether or not coloured) vs label 34.04 prepared waxes |
| 183 | 406335967 | Flying Plate | 9506990000 | 9503000000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | flying disc: toy (9503) vs outdoor-game equipment (9506.99) |
| 184 | 406335972 | Stickers | 4811490000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | label 4811.49 'gummed/adhesive paper, other than self-adhesive' for stickers; no code |
| 185 | 406335973 | cocoon of wool | 5511300000 | 5105000000 | A | DESCRIPTION_CONFLICTS_LABEL | 'cocoon of wool' is a yarn cake of artificial fibre; the name says wool |
| 186 | 406335975 | brushes | 9603300000 | 9603400000 | B | DESCRIPTION_INSUFFICIENT | generic 'brushes'; extraction invented 'for cleaning or painting' |
| 187 | 406335977 | Stickers | 4811900000 | 4911900000 | B | DESCRIPTION_INSUFFICIENT | generic 'Stickers'; paper vs plastic and printed vs plain unknown |
| 188 | 406335978 | Painting frames | 4419900000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | painting frames labelled as wooden tableware (4419.90); material unknown -> no code |
| 189 | 406335980 | Apron | 3926209000 | — | B | DESCRIPTION_INSUFFICIENT | apron material unknown; four chapters -> no code |
| 190 | 406335982 | Sand Art Painting Card | 4909000000 | 4823900000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | children's sand-art card labelled as printed greeting cards (4909) |
| 191 | 406335985 | Playdough Clay | 3407009000 | 3407002000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | playdough: 3407.00.20 'modelling pastes' vs label 3407.00.90 'others' (dental waxes) |
| 192 | 406335988 | Keychain | 3926909000 | — | B | DESCRIPTION_INSUFFICIENT | keychain material unknown; chapters 39/42/73/83 -> no code |
| 193 | 406335989 | Drawing Stencil | 3926100000 | — | B | DESCRIPTION_INSUFFICIENT | stencil material unknown; chapters 39/48 -> no code |
| 194 | 406335951 | DIY Craft Bottle | 9503000000 | — | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level toy label (9503) for a craft bottle; material unknown -> no code |
| 195 | 406335953 | Hula Hoop | 9503000000 | 9506919000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level toy label; hula hoop 'for exercise' -> 9506.91 |
| 196 | 406335956 | Plastic cone roadblocks | 9503000000 | 3926909000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level toy label; plastic cones -> 3926.90 |
| 197 | 406335957 | plastic ring | 9503000000 | 3926909000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level toy label; single Milvus leaf 3926.90 |
| 198 | 406335968 | Sun Hat | 9503000000 | 6505009000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level toy label; sun hat -> headgear 6505 |
| 199 | 406335984 | Styrofoam balls | 9503000000 | 3926909000 | A | LABEL_NOT_SUPPORTED_BY_TEXT | declaration-level toy label; styrofoam balls -> 3926.90 |
